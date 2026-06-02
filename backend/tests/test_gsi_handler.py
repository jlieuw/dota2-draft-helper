"""Tests for gsi_handler — both parse_draft_state and parse_game_state."""
import pytest
from gsi_handler import parse_draft_state as parse_gsi_payload, parse_game_state, _parse_inventory
from models import InventoryItem


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


# ── parse_game_state ──────────────────────────────────────────────────────────

def _make_game_payload(
    game_state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
    hero_name="npc_dota_hero_antimage",
    hero_level=11,
    gold=2500,
    game_time=900,
    items=None,
):
    return {
        "map":    {"game_state": game_state, "game_time": game_time},
        "hero":   {"name": hero_name, "level": hero_level},
        "player": {"gold": gold, "net_worth": gold + 3000},
        "items":  items or {},
    }


class TestParseGameStateInactive:
    def test_hero_selection_returns_none(self):
        assert parse_game_state(_make_game_payload("DOTA_GAMERULES_STATE_HERO_SELECTION")) is None

    def test_post_game_returns_none(self):
        assert parse_game_state(_make_game_payload("DOTA_GAMERULES_STATE_POST_GAME")) is None

    def test_empty_payload_returns_none(self):
        assert parse_game_state({}) is None

    def test_missing_hero_name_returns_none(self):
        payload = _make_game_payload()
        payload["hero"] = {}
        assert parse_game_state(payload) is None


class TestParseGameStateActive:
    def test_game_in_progress_returns_active(self):
        state = parse_game_state(_make_game_payload())
        assert state is not None
        assert state.active is True

    def test_pre_game_returns_active(self):
        state = parse_game_state(_make_game_payload("DOTA_GAMERULES_STATE_PRE_GAME"))
        assert state is not None
        assert state.active is True

    def test_hero_name_prefix_stripped(self):
        state = parse_game_state(_make_game_payload(hero_name="npc_dota_hero_antimage"))
        assert state.hero_name == "antimage"

    def test_hero_level_parsed(self):
        state = parse_game_state(_make_game_payload(hero_level=18))
        assert state.hero_level == 18

    def test_game_time_parsed(self):
        state = parse_game_state(_make_game_payload(game_time=1800))
        assert state.game_time == 1800

    def test_gold_from_direct_key(self):
        state = parse_game_state(_make_game_payload(gold=3000))
        assert state.gold == 3000

    def test_gold_from_split_keys_when_direct_missing(self):
        payload = _make_game_payload()
        del payload["player"]["gold"]
        payload["player"]["gold_reliable"]   = 800
        payload["player"]["gold_unreliable"] = 400
        state = parse_game_state(payload)
        assert state.gold == 1200

    def test_ally_and_enemy_names_empty_by_default(self):
        """main.py injects these after parsing; parser leaves them empty."""
        state = parse_game_state(_make_game_payload())
        assert state.ally_hero_names == []
        assert state.enemy_hero_names == []


# ── _parse_inventory ──────────────────────────────────────────────────────────

class TestParseInventory:
    def test_empty_slots_excluded(self):
        items = {"slot0": {"name": "item_empty"}, "slot1": {"name": "item_empty"}}
        assert _parse_inventory(items) == []

    def test_missing_slots_excluded(self):
        assert _parse_inventory({}) == []

    def test_prefix_stripped(self):
        items = {"slot0": {"name": "item_power_treads"}}
        result = _parse_inventory(items)
        assert len(result) == 1
        assert result[0].item_name == "power_treads"
        assert result[0].slot == "slot0"

    def test_multiple_slots_all_parsed(self):
        items = {
            "slot0": {"name": "item_blink"},
            "slot1": {"name": "item_black_king_bar"},
            "slot2": {"name": "item_empty"},
        }
        result = _parse_inventory(items)
        names = {i.item_name for i in result}
        assert names == {"blink", "black_king_bar"}

    def test_stash_slot_included(self):
        items = {"stash0": {"name": "item_manta_style"}}
        result = _parse_inventory(items)
        assert len(result) == 1
        assert result[0].slot == "stash0"
        assert result[0].item_name == "manta_style"

    def test_neutral_slot_included(self):
        items = {"neutral0": {"name": "item_possessed_mask"}}
        result = _parse_inventory(items)
        assert len(result) == 1
        assert result[0].slot == "neutral0"

    def test_returns_inventory_item_instances(self):
        items = {"slot0": {"name": "item_blink"}}
        result = _parse_inventory(items)
        assert all(isinstance(i, InventoryItem) for i in result)
