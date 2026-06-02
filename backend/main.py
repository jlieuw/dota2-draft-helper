"""
Dota 2 Draft Helper - FastAPI backend
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path

import cache
import opendota
import stratz
import gsi_handler
import suggestion
import item_suggestion
import config
from models import DraftState, GameState, SuggestionResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

# -- Shared state -------------------------------------------------------------

current_draft      = DraftState()
current_game_state = GameState()
connected_clients  = set()
last_gsi_contact   = None
last_gsi_payload   = None
current_account_id = None

# Tracks which heroes are currently being fetched to avoid duplicate requests.
# These are module-level (process-local) — the app must run with a single worker.
# Multi-worker deployments would lose cross-request deduplication; use a single
# uvicorn worker (the default when launched via run.bat).
_fetching_hero_items: set[str] = set()

# Per-hero cooldown after a failed fetch (hero_name -> datetime of last failure).
# Prevents a 10 Hz retry storm when OpenDota returns an error.
_FETCH_FAILURE_COOLDOWN_SECONDS = 60
_hero_item_fetch_failures: dict[str, datetime] = {}


# -- Startup ------------------------------------------------------------------

async def refresh_data():
    log.info("Checking data cache...")

    try:
        patch = await opendota.fetch_current_patch()
        if patch:
            cache.set_meta("current_patch", patch)
            log.info("Current patch: %s", patch)
    except Exception as e:
        log.warning("Could not fetch patch info: %s", e)

    if cache.heroes_need_refresh():
        log.info("Fetching hero list from OpenDota...")
        heroes = await opendota.fetch_all_heroes()
        cache.upsert_heroes(heroes)
        log.info("Hero data cached (%d heroes)", len(heroes))
    else:
        log.info("Hero data is fresh.")

    if cache.matchups_need_refresh():
        hero_ids = cache.get_hero_ids()
        log.info("Fetching matchup data for %d heroes (~3 min on first run)...", len(hero_ids))
        all_matchups = await opendota.fetch_all_matchups(hero_ids)
        cache.upsert_matchups(all_matchups)
        log.info("Matchup data cached.")
    else:
        log.info("Matchup data is fresh.")

    if stratz.has_token():
        if cache.synergies_need_refresh():
            hero_ids = cache.get_hero_ids()
            log.info("Fetching synergy+counter data from Stratz for %d heroes...", len(hero_ids))
            all_data   = await stratz.fetch_all_matchup_data(hero_ids)
            synergies  = {hid: d["with"] for hid, d in all_data.items()}
            cache.upsert_synergies(synergies)
            cache.upsert_stratz_matchups(all_data)
            log.info("Stratz synergy and counter data cached.")
        else:
            log.info("Stratz data is fresh.")

        if cache.position_stats_need_refresh():
            log.info("Fetching position win rates from Stratz...")
            try:
                pos_rows = await stratz.fetch_all_position_stats()
                cache.upsert_position_stats(pos_rows)
                log.info("Position stats cached (%d rows).", len(pos_rows))
            except Exception as e:
                log.warning("Could not fetch position stats from Stratz: %s", e)
        else:
            log.info("Position stats are fresh.")
    else:
        log.info("No Stratz token — using OpenDota matchup data for counters, heuristic for synergy.")

    if cache.items_need_refresh():
        log.info("Fetching item constants from OpenDota...")
        try:
            items = await opendota.fetch_item_constants()
            cache.upsert_items(items)
            log.info("Item constants cached (%d items).", len(items))
        except Exception as e:
            log.warning("Could not fetch item constants: %s", e)
    else:
        log.info("Item constants are fresh.")


async def fetch_personal_stats(account_id: int):
    if not account_id:
        return
    if not cache.personal_stats_need_refresh(account_id):
        log.info("Personal stats for account %d are fresh.", account_id)
        return
    try:
        log.info("Fetching personal hero stats for account %d...", account_id)
        hero_stats = await opendota.fetch_player_heroes(account_id)
        cache.upsert_personal_stats(account_id, hero_stats)
        log.info("Personal stats cached (%d heroes played).", len(hero_stats))
        if connected_clients:
            asyncio.create_task(broadcast(build_payload()))
    except Exception as e:
        log.warning("Could not fetch personal stats for account %d: %s", account_id, e)


async def ensure_hero_item_data(hero_name: str):
    """Lazily fetches and caches item popularity for the hero being played."""
    if hero_name in _fetching_hero_items:
        return

    last_failure = _hero_item_fetch_failures.get(hero_name)
    if last_failure and (datetime.utcnow() - last_failure).total_seconds() < _FETCH_FAILURE_COOLDOWN_SECONDS:
        return

    hero_id = cache.get_hero_id_by_name(hero_name)
    if not hero_id or not cache.hero_items_need_refresh(hero_id):
        return

    _fetching_hero_items.add(hero_name)
    try:
        log.info("Fetching item popularity for %s (hero_id=%d)...", hero_name, hero_id)
        data = await opendota.fetch_hero_item_popularity(hero_id)
        cache.upsert_hero_items(hero_id, data)
        _hero_item_fetch_failures.pop(hero_name, None)
        log.info("Item data cached for %s.", hero_name)
        if connected_clients:
            asyncio.create_task(broadcast(build_payload()))
    except Exception as e:
        _hero_item_fetch_failures[hero_name] = datetime.utcnow()
        log.warning("Could not fetch item popularity for %s: %s — retrying after %ds.",
                    hero_name, e, _FETCH_FAILURE_COOLDOWN_SECONDS)
    finally:
        _fetching_hero_items.discard(hero_name)


@asynccontextmanager
async def lifespan(app):
    cache.init_db()
    if not cache.get_meta("migrated_to_herostats"):
        cache.invalidate_hero_cache()
        cache.set_meta("migrated_to_herostats", "1")
    asyncio.create_task(refresh_data())
    startup_account_id = config.steam_account_id()
    if startup_account_id:
        global current_account_id
        current_account_id = startup_account_id
        log.info("Account ID from config/token: %d — fetching personal stats on startup", startup_account_id)
        asyncio.create_task(fetch_personal_stats(startup_account_id))
    yield


# -- App ----------------------------------------------------------------------

app = FastAPI(title="Dota Draft Helper", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# -- Helpers ------------------------------------------------------------------

async def broadcast(payload: dict):
    dead = set()
    for ws in connected_clients:
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


def _determine_mode(draft: DraftState, game: GameState) -> str:
    if game.active:
        return "game"
    if draft.active:
        return "draft"
    return "idle"


def _enrich_game_state(game: GameState, draft: DraftState) -> GameState:
    """Populate ally/enemy hero names from the last known draft state."""
    if not draft.radiant.picks and not draft.dire.picks:
        return game

    if draft.my_team == "radiant":
        all_my_picks = [h.name for h in draft.radiant.picks]
        enemy_picks  = [h.name for h in draft.dire.picks]
    else:
        all_my_picks = [h.name for h in draft.dire.picks]
        enemy_picks  = [h.name for h in draft.radiant.picks]

    allies = [h for h in all_my_picks if h != game.hero_name]
    return game.model_copy(update={
        "ally_hero_names":  allies,
        "enemy_hero_names": enemy_picks,
    })


def build_payload(role_filter=None, brackets=None) -> dict:
    draft = current_draft
    game  = current_game_state
    mode  = _determine_mode(draft, game)

    account_id   = current_account_id
    has_personal = bool(account_id and cache.has_personal_stats(account_id))

    hero_suggestions = (
        suggestion.get_suggestions(draft, role_filter=role_filter, account_id=account_id, brackets=brackets)
        if mode == "draft" else []
    )
    item_suggestions = (
        item_suggestion.get_item_suggestions(game)
        if mode == "game" else []
    )

    excluded = list({
        h.id for h in (
            draft.radiant.picks + draft.radiant.bans +
            draft.dire.picks    + draft.dire.bans
        )
    })

    gsi_connected = (
        last_gsi_contact is not None and
        (datetime.utcnow() - last_gsi_contact).total_seconds() < 60
    )
    personal_summary = cache.get_personal_hero_summary(account_id) if has_personal else None

    return {
        **SuggestionResponse(
            draft=draft,
            suggestions=hero_suggestions,
            excluded_ids=excluded,
            has_personal_data=has_personal,
        ).model_dump(),
        "mode":             mode,
        "game_state":       game.model_dump() if game.active else None,
        "item_suggestions": [s.model_dump() for s in item_suggestions],
        "gsi_connected":    gsi_connected,
        "last_gsi_contact": last_gsi_contact.isoformat() if last_gsi_contact else None,
        "personal_summary": personal_summary,
        "comfort_games":    cache.PERSONAL_COMFORT_GAMES,
    }


# -- Routes -------------------------------------------------------------------

@app.post("/gsi")
async def receive_gsi(request: Request):
    global current_draft, current_game_state, last_gsi_contact, last_gsi_payload, current_account_id
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid JSON"}, status_code=400)

    last_gsi_contact = datetime.utcnow()
    last_gsi_payload = payload

    game_state_str = payload.get("map", {}).get("game_state", "")
    log.info("GSI: game_state=%s", game_state_str)

    account_id = gsi_handler.extract_account_id(payload)
    if account_id and account_id != current_account_id:
        current_account_id = account_id
        log.info("Player identified: account_id=%d", account_id)
        asyncio.create_task(fetch_personal_stats(account_id))

    changed = False

    if game_state_str in gsi_handler.HERO_SELECTION_STATES:
        new_draft = gsi_handler.parse_draft_state(payload)
        if new_draft.active:
            if new_draft != current_draft:
                current_draft      = new_draft
                current_game_state = GameState()   # reset stale game state when a new draft begins
                changed = True
        elif current_draft.active:
            # Hero selection state reached but draft block not yet populated (e.g. lobby
            # just loaded). Clear any stale draft from a previous game so the frontend
            # doesn't show ghost picks while waiting for the ban phase to start.
            current_draft      = DraftState()
            current_game_state = GameState()
            changed = True

    elif game_state_str in gsi_handler.GAME_ACTIVE_STATES:
        new_game = gsi_handler.parse_game_state(payload)
        if new_game:
            new_game = _enrich_game_state(new_game, current_draft)
            if new_game != current_game_state:
                current_game_state = new_game
                changed = True
                # Lazily ensure item data is available for this hero.
                asyncio.create_task(ensure_hero_item_data(new_game.hero_name))

    else:
        # Post-game or idle: clear game state, keep draft for reference.
        if current_game_state.active:
            current_game_state = GameState()
            changed = True

    if changed and connected_clients:
        asyncio.create_task(broadcast(build_payload()))
    elif connected_clients and not current_draft.active and not current_game_state.active:
        asyncio.create_task(broadcast(build_payload()))

    return JSONResponse({"ok": True})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    log.info("Frontend connected (%d clients)", len(connected_clients))
    try:
        await websocket.send_text(json.dumps(build_payload()))
        while True:
            data = await websocket.receive_text()
            try:
                msg      = json.loads(data)
                role     = msg.get("role_filter")
                brackets = msg.get("brackets") or None
                await websocket.send_text(json.dumps(build_payload(role_filter=role, brackets=brackets)))
            except Exception:
                pass
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        log.info("Frontend disconnected (%d clients)", len(connected_clients))


@app.get("/api/heroes")
async def get_heroes():
    return cache.get_all_heroes()


@app.get("/api/items")
async def get_items():
    return cache.get_items_dict()


@app.get("/api/status")
async def get_status():
    gsi_connected = (
        last_gsi_contact is not None and
        (datetime.utcnow() - last_gsi_contact).total_seconds() < 60
    )
    ages = cache.get_data_ages()
    current_patch = ages.get("current_patch")
    patch_warnings = {
        key: ages.get(f"{key}_patch") != current_patch
        for key in ("heroes", "matchups", "synergies", "position_stats")
        if ages.get(f"{key}_patch") and current_patch
    }
    return {
        **ages,
        "patch_warnings":        patch_warnings,
        "has_stratz_token":      stratz.has_token(),
        "draft_active":          current_draft.active,
        "game_active":           current_game_state.active,
        "heroes_need_refresh":   cache.heroes_need_refresh(),
        "matchups_need_refresh": cache.matchups_need_refresh(),
        "items_need_refresh":    cache.items_need_refresh(),
        "synergies_need_refresh": cache.synergies_need_refresh() if stratz.has_token() else None,
        "gsi_connected":         gsi_connected,
        "last_gsi_contact":      last_gsi_contact.isoformat() if last_gsi_contact else None,
        "account_id":            current_account_id,
        "has_personal_data":     bool(current_account_id and cache.has_personal_stats(current_account_id)),
    }


@app.get("/api/debug/last-gsi")
async def debug_last_gsi():
    return {
        "last_contact": last_gsi_contact.isoformat() if last_gsi_contact else None,
        "payload":      last_gsi_payload,
    }


@app.post("/api/refresh")
async def trigger_refresh():
    asyncio.create_task(refresh_data())
    if current_account_id:
        asyncio.create_task(fetch_personal_stats(current_account_id))
    return {"ok": True, "message": "Refresh started in background"}


@app.get("/simulator", include_in_schema=False)
async def simulator_page():
    sim = Path(__file__).parent.parent / "simulator.html"
    return FileResponse(str(sim))


# -- Serve React frontend (must be last) --------------------------------------

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=4000, reload=False)
