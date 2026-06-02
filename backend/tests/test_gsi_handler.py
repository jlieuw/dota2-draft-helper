"""Tests for gsi_handler.parse_gsi_payload."""
import pytest
from gsi_handler import parse_gsi_payload


def _make_payload(game_state="DOTA_GAMERULES_STATE_HERO_SELECTION",
                  draft=None, include_map=True):
    payload = {}
    if include_map:
        payload["map"] = {"game_state": game_state}
    if draft is not None:
        payload["draft"] = draft
    return payload


def _basic_draft(**kwargs):
    base = {
        "activeteam": 2,
        "activeteam_time_remaining": 30.0,
        "radiant_bonus_time": 130.0,
        "dire_bonus_time": 130.0,
        "team2": {"home_team": True},
        "team3": {"home_team": False},
    }
    base.update(kwargs)
    return base


# ── Not in draft ──────────────────────────────────────────────────────────────

class TestNotInDraft:
    def test_pre_game_state_returns_inactive(self):
        state = parse_gsi_payload(_make_payload("DOTA_GAMERULES_STATE_WAIT_FOR_MAP_TO_LOAD"))
        assert state.active is False

    def test_in_game_state_returns_inactive(self):
        state = parse_gsi_payload(_make_payload("DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"))
        assert state.active is False

    def test_post_game_returns_inactive(self):
        state = parse_gsi_payload(_make_payload("DOTA_GAMERULES_STATE_POST_GAME"))
        assert state.active is False

    def test_missing_map_key_returns_inactive(self):
        state = parse_gsi_payload({})
        assert state.active is False

    def test_missing_draft_key_returns_inactive(self):
        # map says hero selection but no draft block
        state = parse_gsi_payload({"map": {"game_state": "DOTA_GAMERULES_STATE_HERO_SELECTION"}})
        assert state.active is False


# ── In draft ──────────────────────────────────────────────────────────────────

class TestInDraft:
    def test_hero_selection_returns_active(self):
        payload = _make_payload(draft=_basic_draft())
        state = parse_gsi_payload(payload)
        assert state.active is True

    def test_strategy_time_returns_active(self):
        payload = _make_payload(
            game_state="DOTA_GAMERULES_STATE_STRATEGY_TIME",
            draft=_basic_draft(),
        )
        assert parse_gsi_payload(payload).active is True

    def test_radiant_picks_parsed(self):
        draft = _basic_draft()
        draft["team2"]["pick0_id"] = 1
        draft["team2"]["pick0_class"] = "antimage"
        draft["team2"]["pick1_id"] = 86
        draft["team2"]["pick1_class"] = "rubick"

        state = parse_gsi_payload(_make_payload(draft=draft))
        assert len(state.radiant.picks) == 2
        assert state.radiant.picks[0].id == 1
        assert state.radiant.picks[0].name == "antimage"
        assert state.radiant.picks[1].id == 86

    def test_dire_picks_parsed(self):
        draft = _basic_draft()
        draft["team3"]["pick0_id"] = 74
        draft["team3"]["pick0_class"] = "invoker"

        state = parse_gsi_payload(_make_payload(draft=draft))
        assert len(state.dire.picks) == 1
        assert state.dire.picks[0].id == 74

    def test_radiant_bans_parsed(self):
        draft = _basic_draft()
        draft["team2"]["ban0_id"] = 8
        draft["team2"]["ban0_class"] = "juggernaut"
        draft["team2"]["ban1_id"] = 11
        draft["team2"]["ban1_class"] = "nevermore"

        state = parse_gsi_payload(_make_payload(draft=draft))
        assert len(state.radiant.bans) == 2
        assert state.radiant.bans[0].id == 8

    def test_zero_hero_id_ignored(self):
        """hero_id=0 means empty slot, should not be included."""
        draft = _basic_draft()
        draft["team2"]["pick0_id"] = 0
        draft["team2"]["pick0_class"] = ""

        state = parse_gsi_payload(_make_payload(draft=draft))
        assert len(state.radiant.picks) == 0

    def test_empty_draft_has_no_picks(self):
        state = parse_gsi_payload(_make_payload(draft=_basic_draft()))
        assert state.radiant.picks == []
        assert state.dire.picks == []
        assert state.radiant.bans == []

    def test_my_team_is_radiant_when_team2_is_home(self):
        draft = _basic_draft()
        draft["team2"]["home_team"] = True
        draft["team3"]["home_team"] = False

        state = parse_gsi_payload(_make_payload(draft=draft))
        assert state.my_team == "radiant"

    def test_my_team_is_dire_when_team3_is_home(self):
        draft = _basic_draft()
        draft["team2"]["home_team"] = False
        draft["team3"]["home_team"] = True

        state = parse_gsi_payload(_make_payload(draft=draft))
        assert state.my_team == "dire"

    def test_active_team_radiant(self):
        state = parse_gsi_payload(_make_payload(draft=_basic_draft(activeteam=2)))
        assert state.active_team == "radiant"

    def test_active_team_dire(self):
        state = parse_gsi_payload(_make_payload(draft=_basic_draft(activeteam=3)))
        assert state.active_team == "dire"

    def test_time_remaining_parsed(self):
        state = parse_gsi_payload(_make_payload(draft=_basic_draft(activeteam_time_remaining=27.5)))
        assert state.time_remaining == pytest.approx(27.5)
