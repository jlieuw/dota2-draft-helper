"""
Parses raw Dota 2 GSI payloads into DraftState and GameState objects.
Also extracts the local player's Steam account ID from the provider block.
"""
from __future__ import annotations

from models import DraftState, GameState, InventoryItem, TeamDraft, HeroSlot

HERO_SELECTION_STATES = {
    "DOTA_GAMERULES_STATE_HERO_SELECTION",
    "DOTA_GAMERULES_STATE_STRATEGY_TIME",
    "DOTA_GAMERULES_STATE_WAIT_FOR_PLAYERS_TO_LOAD",
}

GAME_ACTIVE_STATES = {
    "DOTA_GAMERULES_STATE_PRE_GAME",
    "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
}

STEAM64_OFFSET = 76561197960265728

# All item slots broadcast by GSI during a game.
_INVENTORY_SLOTS = (
    [f"slot{i}"  for i in range(6)] +
    [f"stash{i}" for i in range(6)] +
    ["neutral0"]
)


def extract_account_id(payload: dict) -> int | None:
    """
    Returns the OpenDota account ID (Steam3) from the GSI provider block, or None.
    GSI sends Steam64; OpenDota uses Steam64 - 76561197960265728.
    """
    steam64 = payload.get("provider", {}).get("steamid")
    if not steam64:
        return None
    try:
        return int(steam64) - STEAM64_OFFSET
    except (ValueError, TypeError):
        return None


def parse_draft_state(payload: dict) -> DraftState:
    """Returns the current draft state from a GSI payload, or an inactive DraftState."""
    map_data   = payload.get("map", {})
    game_state = map_data.get("game_state", "")

    if game_state not in HERO_SELECTION_STATES:
        return DraftState(active=False)

    draft_data = payload.get("draft", {})
    if not draft_data:
        return DraftState(active=False)

    team2_data = draft_data.get("team2", {})
    team3_data = draft_data.get("team3", {})
    radiant    = _parse_team(team2_data)
    dire       = _parse_team(team3_data)
    my_team    = "dire" if team3_data.get("home_team", False) else "radiant"

    active_team_num = draft_data.get("activeteam")
    active_team = {2: "radiant", 3: "dire"}.get(active_team_num)

    return DraftState(
        active=True,
        my_team=my_team,
        radiant=radiant,
        dire=dire,
        active_team=active_team,
        time_remaining=draft_data.get("activeteam_time_remaining"),
    )


def parse_game_state(payload: dict) -> GameState | None:
    """
    Returns GameState when a game is active, None otherwise.
    ally/enemy picks are NOT populated here — main.py injects them from the
    last known draft state via _enrich_game_state().
    """
    map_data = payload.get("map", {})
    if map_data.get("game_state") not in GAME_ACTIVE_STATES:
        return None

    hero_data = payload.get("hero", {})
    hero_name = hero_data.get("name", "").removeprefix("npc_dota_hero_")
    if not hero_name:
        return None

    player_data = payload.get("player", {})
    # GSI may give total gold directly, or only the reliable/unreliable split.
    gold = player_data.get("gold") or (
        player_data.get("gold_reliable", 0) + player_data.get("gold_unreliable", 0)
    )

    return GameState(
        active=True,
        hero_name=hero_name,
        hero_level=hero_data.get("level", 1),
        game_time=map_data.get("game_time", 0),
        gold=int(gold),
        net_worth=player_data.get("net_worth", 0),
        items=_parse_inventory(payload.get("items", {})),
    )


def _parse_team(team_data: dict) -> TeamDraft:
    picks, bans = [], []
    for i in range(5):
        hid   = team_data.get(f"pick{i}_id")
        hname = team_data.get(f"pick{i}_class", "")
        if hid and hid > 0:
            picks.append(HeroSlot(id=hid, name=hname))
    for i in range(7):
        hid   = team_data.get(f"ban{i}_id")
        hname = team_data.get(f"ban{i}_class", "")
        if hid and hid > 0:
            bans.append(HeroSlot(id=hid, name=hname))
    return TeamDraft(picks=picks, bans=bans)


def _parse_inventory(items_data: dict) -> list[InventoryItem]:
    result = []
    for slot in _INVENTORY_SLOTS:
        raw  = items_data.get(slot, {})
        name = raw.get("name", "")
        if name and name != "item_empty":
            result.append(InventoryItem(
                slot=slot,
                item_name=name.removeprefix("item_"),
            ))
    return result
