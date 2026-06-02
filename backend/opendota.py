"""
OpenDota API client. All requests are cached locally in SQLite.
"""
import httpx
import asyncio
import logging

log = logging.getLogger(__name__)

BASE_URL = "https://api.opendota.com/api"
RATE_LIMIT_DELAY = 1.0


async def fetch_current_patch():
    """Returns current patch string e.g. '7.37e', or None on failure."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{BASE_URL}/metadata")
            resp.raise_for_status()
            data = resp.json()
            # Try several locations where OpenDota stores the patch
            patches = data.get("patches", [])
            if patches:
                name = patches[-1].get("name") or patches[-1].get("patch")
                if name:
                    return str(name)
            # Fallback: check top-level
            for key in ("patch", "current_patch", "game_version"):
                if data.get(key):
                    return str(data[key])
        except Exception as e:
            log.warning("fetch_current_patch failed: %s", e)
    return None


async def fetch_all_heroes():
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/heroStats")
        resp.raise_for_status()
        return resp.json()


async def fetch_hero_matchups(hero_id):
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/heroes/{hero_id}/matchups")
        resp.raise_for_status()
        return resp.json()


async def fetch_all_matchups(hero_ids):
    results = {}
    for i, hero_id in enumerate(hero_ids):
        try:
            matchups = await fetch_hero_matchups(hero_id)
            results[hero_id] = matchups
            log.info("Fetched matchups for hero %d (%d/%d)", hero_id, i + 1, len(hero_ids))
        except Exception as e:
            log.warning("Failed to fetch matchups for hero %d: %s", hero_id, e)
            results[hero_id] = []
        await asyncio.sleep(RATE_LIMIT_DELAY)
    return results


async def fetch_player_heroes(account_id):
    """
    Fetches hero stats for a player from OpenDota.
    Returns list of { hero_id, games, win, last_played }.
    account_id is Steam3 ID (Steam64 - 76561197960265728).
    """
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{BASE_URL}/players/{account_id}/heroes")
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            if attempt < 2:
                log.warning("fetch_player_heroes timeout (attempt %d/3), retrying...", attempt + 1)
                await asyncio.sleep(5)
            else:
                raise
    return []
