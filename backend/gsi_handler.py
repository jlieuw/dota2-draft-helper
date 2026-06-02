"""
Parses raw Dota 2 GSI payloads into DraftState objects.
Also extracts the local player's Steam account ID from the provider block.
"""
from models import DraftState, TeamDraft, HeroSlot

HERO_SELECTION_STATES = {
    "DOTA_GAMERULES_STATE_HERO_SELECTION",
    "DOTA_GAMERULES_STATE_STRATEGY_TIME",
    "DOTA_GAMERULES_STATE_WAIT_FOR_PLAYERS_TO_LOAD",
}

STEAM64_OFFSET = 76561197960265728


def extract_account_id(payload):
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


def _parse_team(team_data):
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


def parse_gsi_payload(payload):
    map_data   = payload.get("map", {})
    game_state = map_data.get("game_state", "")

    if game_state not in HERO_SELECTION_STATES:
        return DraftState(active=False)

    draft_data = payload.get("draft", {})
    if not draft_data:
        return DraftState(active=False)

    team2_data = draft_data.get("team2", {})
    team3_data = draft_data.get("team3", {})

    radiant = _parse_team(team2_data)
    dire    = _parse_team(team3_data)

    my_team = "dire" if team3_data.get("home_team", False) else "radiant"

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
