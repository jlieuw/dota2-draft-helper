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
import config
from models import DraftState, SuggestionResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

# -- Shared state -------------------------------------------------------------

current_draft     = DraftState()
connected_clients = set()
last_gsi_contact  = None
last_gsi_payload  = None
current_account_id = None   # Steam account ID of the local player (from GSI provider)


# -- Startup ------------------------------------------------------------------

async def refresh_data():
    log.info("Checking data cache...")

    # Fetch current patch FIRST so all need_refresh() checks can detect a patch change.
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
            # Fetch both synergy (with) and counter (vs) data in one pass
            all_data = await stratz.fetch_all_matchup_data(hero_ids)
            # Split and store separately
            synergies = {hid: d["with"] for hid, d in all_data.items()}
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
        log.info("No Stratz token - using OpenDota matchup data for counters, heuristic for synergy.")


async def fetch_personal_stats(account_id):
    """Fetch and cache the player's personal hero stats from OpenDota."""
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
        # Push updated suggestions to all connected clients
        if connected_clients:
            asyncio.create_task(broadcast(build_payload(current_draft)))
    except Exception as e:
        log.warning("Could not fetch personal stats for account %d: %s", account_id, e)


@asynccontextmanager
async def lifespan(app):
    cache.init_db()
    # One-time migration: clear hero cache if it was populated using the old /heroes endpoint
    if not cache.get_meta('migrated_to_herostats'):
        cache.invalidate_hero_cache()
        cache.set_meta('migrated_to_herostats', '1')
    asyncio.create_task(refresh_data())
    # Load personal stats at startup if account ID is available from config/token
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

async def broadcast(payload):
    dead = set()
    for ws in connected_clients:
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


def build_payload(draft, role_filter=None, brackets=None):
    account_id   = current_account_id
    has_personal = bool(account_id and cache.has_personal_stats(account_id))
    suggestions  = suggestion.get_suggestions(draft, role_filter=role_filter, account_id=account_id, brackets=brackets)
    excluded     = list({
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
            suggestions=suggestions,
            excluded_ids=excluded,
            has_personal_data=has_personal,
        ).model_dump(),
        "gsi_connected":     gsi_connected,
        "last_gsi_contact":  last_gsi_contact.isoformat() if last_gsi_contact else None,
        "personal_summary":  personal_summary,
        "comfort_games":     cache.PERSONAL_COMFORT_GAMES,
    }


# -- Routes -------------------------------------------------------------------

@app.post("/gsi")
async def receive_gsi(request: Request):
    global current_draft, last_gsi_contact, last_gsi_payload, current_account_id
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid JSON"}, status_code=400)

    last_gsi_contact = datetime.utcnow()
    last_gsi_payload = payload

    game_state = payload.get("map", {}).get("game_state", "unknown")
    has_draft  = bool(payload.get("draft"))
    log.info("GSI: game_state=%s  has_draft=%s", game_state, has_draft)

    # Extract and store player's Steam account ID
    account_id = gsi_handler.extract_account_id(payload)
    if account_id and account_id != current_account_id:
        current_account_id = account_id
        log.info("Player identified: account_id=%d", account_id)
        asyncio.create_task(fetch_personal_stats(account_id))

    new_draft = gsi_handler.parse_gsi_payload(payload)

    if new_draft != current_draft:
        current_draft = new_draft
        if connected_clients:
            asyncio.create_task(broadcast(build_payload(current_draft)))
    elif connected_clients and not current_draft.active:
        asyncio.create_task(broadcast(build_payload(current_draft)))

    return JSONResponse({"ok": True})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    log.info("Frontend connected (%d clients)", len(connected_clients))
    try:
        await websocket.send_text(json.dumps(build_payload(current_draft)))
        while True:
            data = await websocket.receive_text()
            try:
                msg  = json.loads(data)
                role = msg.get("role_filter")
                brackets = msg.get("brackets") or None
                await websocket.send_text(json.dumps(build_payload(current_draft, role_filter=role, brackets=brackets)))
            except Exception:
                pass
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        log.info("Frontend disconnected (%d clients)", len(connected_clients))


@app.get("/api/heroes")
async def get_heroes():
    return cache.get_all_heroes()


@app.get("/api/status")
async def get_status():
    gsi_connected = (
        last_gsi_contact is not None and
        (datetime.utcnow() - last_gsi_contact).total_seconds() < 60
    )
    ages = cache.get_data_ages()
    current_patch = ages.get("current_patch")
    # Flag each data source whose patch doesn't match the current game patch
    patch_warnings = {
        key: ages.get(f"{key}_patch") != current_patch
        for key in ("heroes", "matchups", "synergies", "position_stats")
        if ages.get(f"{key}_patch") and current_patch
    }
    return {
        **ages,
        "patch_warnings":      patch_warnings,
        "has_stratz_token":    stratz.has_token(),
        "draft_active":        current_draft.active,
        "heroes_need_refresh": cache.heroes_need_refresh(),
        "matchups_need_refresh": cache.matchups_need_refresh(),
        "synergies_need_refresh": cache.synergies_need_refresh() if stratz.has_token() else None,
        "gsi_connected":       gsi_connected,
        "last_gsi_contact":    last_gsi_contact.isoformat() if last_gsi_contact else None,
        "account_id":          current_account_id,
        "has_personal_data":   bool(current_account_id and cache.has_personal_stats(current_account_id)),
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
