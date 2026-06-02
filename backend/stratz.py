"""
Stratz API client for hero synergy AND counter matchup data.
Stratz processes 100% of Dota 2 pub games — far denser than OpenDota's parsed sample.

Free token: https://stratz.com/api
Set in config.json as "stratz_token" or the STRATZ_TOKEN env var.

Uses the GraphQL API (api.stratz.com/graphql) via curl_cffi with Chrome impersonation
to bypass Cloudflare bot protection that blocks the REST API.

heroVsHeroMatchup returns:
  with: win rates when this hero and ally_hero are on the SAME team (synergy)
  vs:   win rates when this hero faces enemy_hero on the OPPOSING team (counter)
"""
import asyncio
import json
import logging
from curl_cffi.requests import AsyncSession
from config import stratz_token, rank_bracket_id

log = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.stratz.com/graphql"
RATE_LIMIT_DELAY = 1.2   # Stratz free tier: ~50 req/min

# Maps internal rank_bracket_id to Stratz RankBracketBasicEnum values.
# Stratz groups two adjacent ranks into one bracket.
_BRACKET_MAP = {
    0: None,               # all — omit bracketBasicIds param
    1: "HERALD_GUARDIAN",
    2: "HERALD_GUARDIAN",
    3: "CRUSADER_ARCHON",
    4: "CRUSADER_ARCHON",
    5: "LEGEND_ANCIENT",
    6: "LEGEND_ANCIENT",
    7: "DIVINE_IMMORTAL",
    8: "DIVINE_IMMORTAL",
}

_MATCHUP_QUERY = """
query HeroMatchup($heroId: Short!, $bracketIds: [RankBracketBasicEnum]) {
  heroStats {
    heroVsHeroMatchup(heroId: $heroId, bracketBasicIds: $bracketIds) {
      advantage {
        heroId
        with { heroId2 matchCount winCount winsAverage synergy }
        vs   { heroId2 matchCount winCount winsAverage }
      }
    }
  }
}
"""

_POSITION_STATS_QUERY = """
query PositionStats($bracketIds: [RankBracketBasicEnum]) {
  heroStats {
    stats(groupByPosition: true, bracketBasicIds: $bracketIds) {
      heroId
      position
      matchCount
      winCount
    }
  }
}
"""


def _headers():
    token = stratz_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _bracket_enum():
    """Returns the Stratz bracket enum string for the configured rank bracket, or None for 'all'."""
    return _BRACKET_MAP.get(rank_bracket_id())


def has_token():
    return bool(stratz_token())


def _parse_dryad_list(entries):
    result = []
    for entry in (entries or []):
        hero_id2    = entry.get("heroId2")
        match_count = entry.get("matchCount", 0)
        win_count   = entry.get("winCount", 0)
        wins_avg    = entry.get("winsAverage", 0.5)
        synergy     = entry.get("synergy")  # pre-computed advantage in %-points, may be None
        if hero_id2 and match_count > 0:
            result.append({
                "hero_id2": hero_id2,
                "wins":     win_count,
                "games":    match_count,
                "winrate":  wins_avg,
                "synergy":  synergy,
            })
    return result


async def fetch_hero_matchup_data(hero_id):
    """
    Fetches both synergy (with) and counter (vs) data for hero_id from Stratz.

    Returns:
      {
        "with": [ { hero_id2, wins, games, winrate, synergy }, ... ],
        "vs":   [ { hero_id2, wins, games, winrate }, ... ],
      }

    The "vs" entries are from hero_id's perspective:
      winrate > 0.5 means hero_id wins more often when enemy has hero_id2.
    """
    bracket = _bracket_enum()
    variables = {"heroId": hero_id, "bracketIds": [bracket] if bracket else None}
    payload = json.dumps({"query": _MATCHUP_QUERY, "variables": variables})
    async with AsyncSession(impersonate="chrome") as client:
        resp = await client.post(GRAPHQL_URL, headers=_headers(), data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    if "errors" in data:
        raise ValueError(f"GraphQL errors for hero {hero_id}: {data['errors']}")

    matchup = data.get("data", {}).get("heroStats", {}).get("heroVsHeroMatchup", {})
    advantage_list = matchup.get("advantage", [])
    # advantage is a list with one entry for the queried hero
    hero_data = advantage_list[0] if advantage_list else {}

    return {
        "with": _parse_dryad_list(hero_data.get("with", [])),
        "vs":   _parse_dryad_list(hero_data.get("vs", [])),
    }


async def fetch_all_position_stats():
    """
    Fetches win rate per hero per position in a single bulk GraphQL request.
    Returns: [ { heroId, position, matchCount, winCount }, ... ]
    Positions: POSITION_1 (carry) … POSITION_5 (hard support)
    """
    bracket = _bracket_enum()
    variables = {"bracketIds": [bracket] if bracket else None}
    payload = json.dumps({"query": _POSITION_STATS_QUERY, "variables": variables})
    async with AsyncSession(impersonate="chrome") as client:
        resp = await client.post(GRAPHQL_URL, headers=_headers(), data=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()

    if "errors" in data:
        raise ValueError(f"GraphQL errors fetching position stats: {data['errors']}")

    rows = data.get("data", {}).get("heroStats", {}).get("stats", []) or []
    log.info("Fetched Stratz position stats: %d rows", len(rows))
    return rows


async def fetch_all_matchup_data(hero_ids):
    """
    Fetches both synergy and counter data for all heroes.
    Returns:
      {
        hero_id: {
          "with": [ { hero_id2, wins, games, winrate, synergy } ],
          "vs":   [ { hero_id2, wins, games, winrate } ],
        }
      }
    """
    results = {}
    for i, hero_id in enumerate(hero_ids):
        try:
            data = await fetch_hero_matchup_data(hero_id)
            results[hero_id] = data
            log.info(
                "Fetched Stratz matchup data for hero %d (%d/%d) — "
                "%d synergy, %d counter entries",
                hero_id, i + 1, len(hero_ids),
                len(data["with"]), len(data["vs"])
            )
        except Exception as e:
            log.warning("Failed to fetch Stratz data for hero %d: %s", hero_id, e)
            results[hero_id] = {"with": [], "vs": []}
        await asyncio.sleep(RATE_LIMIT_DELAY)
    return results
