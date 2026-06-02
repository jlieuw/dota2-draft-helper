"""
Loads configuration from config.json (project root) with env var overrides.
All values have safe defaults so the app runs without any configuration.
"""
import json
import os
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

_RANK_BRACKET_IDS = {
    "all": 0, "herald": 1, "guardian": 2, "crusader": 3,
    "archon": 4, "legend": 5, "ancient": 6, "divine": 7, "immortal": 8,
}


def _load():
    if not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH) as f:
            raw = json.load(f)
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    except Exception as e:
        log.warning("Could not load config.json: %s", e)
        return {}


_cfg = _load()


def stratz_token():
    return os.environ.get("STRATZ_TOKEN", _cfg.get("stratz_token", "")).strip()


def rank_bracket():
    return _cfg.get("rank_bracket", "all").lower()


def rank_bracket_id():
    return _RANK_BRACKET_IDS.get(rank_bracket(), 0)


def steam_account_id():
    """
    Returns the player's OpenDota account ID (Steam64 - offset) if configured.
    First checks config.json `steam_account_id`, then tries to decode it from the
    Stratz JWT token (which embeds SteamId in the payload).
    Returns int or None.
    """
    # Explicit config takes priority
    explicit = _cfg.get("steam_account_id")
    if explicit:
        try:
            return int(explicit)
        except (ValueError, TypeError):
            pass

    # Try to decode from Stratz JWT (no signature verification needed — we just read claims)
    token = stratz_token()
    if token:
        try:
            import base64, json as _json
            parts = token.split(".")
            if len(parts) == 3:
                # Add padding if needed
                payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
                claims = _json.loads(base64.urlsafe_b64decode(payload_b64))
                steam_id = claims.get("SteamId")
                if steam_id:
                    STEAM64_OFFSET = 76561197960265728
                    steam64 = int(steam_id)
                    # SteamId in Stratz JWT is Steam32 (account ID directly), not Steam64
                    # Values < offset are already account IDs; values >= offset need conversion
                    if steam64 >= STEAM64_OFFSET:
                        return steam64 - STEAM64_OFFSET
                    return steam64
        except Exception as e:
            log.debug("Could not decode Steam ID from Stratz token: %s", e)
def scoring_weights():
    w = _cfg.get("scoring_weights", {})
    return (
        float(w.get("winrate", 0.25)),
        float(w.get("synergy", 0.35)),
        float(w.get("counter", 0.40)),
    )
