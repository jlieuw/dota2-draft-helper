"""Tests for the cache layer (heroes, matchups, synergies, meta, items)."""
import pytest
from datetime import datetime, timedelta
from tests.conftest import (
    ALL_HEROES, MATCHUPS, SYNERGIES, HERO_AM, HERO_RUBICK,
    ALL_ITEMS, AM_ITEM_POPULARITY,
)


class TestHeroes:
    def test_upsert_and_retrieve(self, tmp_db):
        import cache
        cache.upsert_heroes(ALL_HEROES)
        heroes = cache.get_all_heroes()
        assert len(heroes) == len(ALL_HEROES)
        names = {h["display_name"] for h in heroes}
        assert "Anti-Mage" in names
        assert "Rubick" in names

    def test_heroes_sorted_alphabetically(self, tmp_db):
        import cache
        cache.upsert_heroes(ALL_HEROES)
        heroes = cache.get_all_heroes()
        display_names = [h["display_name"] for h in heroes]
        assert display_names == sorted(display_names)

    def test_roles_deserialized_as_list(self, tmp_db):
        import cache
        cache.upsert_heroes([HERO_AM])
        hero = cache.get_all_heroes()[0]
        assert isinstance(hero["roles"], list)
        assert "Carry" in hero["roles"]

    def test_get_hero_ids(self, tmp_db):
        import cache
        cache.upsert_heroes(ALL_HEROES)
        ids = cache.get_hero_ids()
        assert set(ids) == {1, 86, 74, 53}

    def test_heroes_need_refresh_when_empty(self, tmp_db):
        import cache
        assert cache.heroes_need_refresh() is True

    def test_heroes_not_stale_after_upsert(self, tmp_db):
        import cache
        cache.upsert_heroes(ALL_HEROES)
        assert cache.heroes_need_refresh() is False

    def test_heroes_stale_after_threshold(self, tmp_db, monkeypatch):
        import cache
        cache.upsert_heroes(ALL_HEROES)
        # Simulate timestamp 8 days ago
        old_ts = (datetime.utcnow() - timedelta(days=8)).isoformat()
        cache.set_meta("heroes_updated", old_ts)
        assert cache.heroes_need_refresh() is True

    def test_upsert_is_idempotent(self, tmp_db):
        import cache
        cache.upsert_heroes(ALL_HEROES)
        cache.upsert_heroes(ALL_HEROES)   # second upsert should not duplicate
        assert len(cache.get_all_heroes()) == len(ALL_HEROES)


class TestMatchups:
    def test_matchup_winrate_correct(self, populated_db):
        import cache
        # AM vs Invoker: 5500/10000 = 55%
        wr = cache.get_matchup_winrate(1, 74)
        assert wr == pytest.approx(0.55)

    def test_matchup_winrate_neutral_when_missing(self, tmp_db):
        import cache
        assert cache.get_matchup_winrate(999, 888) == pytest.approx(0.5)

    def test_overall_winrate(self, populated_db):
        import cache
        # AM: 5500 + 3840 + 3000 = 12340 wins / (10000 + 8000 + 6000) = 24000 games = 51.4%
        wr = cache.get_overall_winrate(1)
        assert wr == pytest.approx(12340 / 24000, rel=1e-3)

    def test_overall_winrate_neutral_when_missing(self, tmp_db):
        import cache
        assert cache.get_overall_winrate(999) == pytest.approx(0.5)

    def test_matchups_need_refresh_when_empty(self, tmp_db):
        import cache
        assert cache.matchups_need_refresh() is True

    def test_matchups_not_stale_after_upsert(self, populated_db):
        import cache
        assert cache.matchups_need_refresh() is False


class TestSynergies:
    def test_synergy_winrate_correct(self, populated_db):
        import cache
        # AM + Rubick: 5500/10000 = 55%
        wr = cache.get_synergy_winrate(1, 86)
        assert wr == pytest.approx(0.55)

    def test_synergy_winrate_reverse_direction(self, populated_db):
        import cache
        # Stored both directions; Rubick + AM should also return 55%
        wr = cache.get_synergy_winrate(86, 1)
        assert wr == pytest.approx(0.55)

    def test_synergy_neutral_when_no_data(self, tmp_db):
        import cache
        assert cache.get_synergy_winrate(1, 86) == pytest.approx(0.5)

    def test_has_synergy_data_false_when_empty(self, tmp_db):
        import cache
        assert cache.has_synergy_data() is False

    def test_has_synergy_data_true_after_upsert(self, populated_db):
        import cache
        assert cache.has_synergy_data() is True

    def test_synergies_need_refresh_when_empty(self, tmp_db):
        import cache
        assert cache.synergies_need_refresh() is True


class TestMeta:
    def test_set_and_get_meta(self, tmp_db):
        import cache
        cache.set_meta("current_patch", "7.37e")
        assert cache.get_meta("current_patch") == "7.37e"

    def test_get_meta_none_when_missing(self, tmp_db):
        import cache
        assert cache.get_meta("nonexistent") is None

    def test_data_ages_returns_patch(self, populated_db):
        import cache
        cache.set_meta("current_patch", "7.37e")
        ages = cache.get_data_ages()
        assert ages["current_patch"] == "7.37e"

    def test_data_ages_has_synergy_flag(self, populated_db):
        import cache
        ages = cache.get_data_ages()
        assert ages["has_synergy_data"] is True


class TestItemConstants:
    def test_upsert_and_retrieve(self, tmp_db):
        import cache
        cache.upsert_items(ALL_ITEMS)
        items = cache.get_items_dict()
        assert "blink" in items
        assert items["blink"]["display_name"] == "Blink Dagger"
        assert items["blink"]["cost"] == 2250

    def test_components_deserialized_as_list(self, tmp_db):
        import cache
        cache.upsert_items(ALL_ITEMS)
        items = cache.get_items_dict()
        assert isinstance(items["black_king_bar"]["components"], list)
        assert "ogre_axe" in items["black_king_bar"]["components"]

    def test_item_with_no_components_returns_empty_list(self, tmp_db):
        import cache
        cache.upsert_items(ALL_ITEMS)
        items = cache.get_items_dict()
        assert items["blink"]["components"] == []

    def test_upsert_is_idempotent(self, tmp_db):
        import cache
        cache.upsert_items(ALL_ITEMS)
        cache.upsert_items(ALL_ITEMS)
        assert len(cache.get_items_dict()) == len(ALL_ITEMS)

    def test_items_need_refresh_when_empty(self, tmp_db):
        import cache
        assert cache.items_need_refresh() is True

    def test_items_not_stale_after_upsert(self, tmp_db):
        import cache
        cache.upsert_items(ALL_ITEMS)
        assert cache.items_need_refresh() is False

    def test_items_stale_after_threshold(self, tmp_db):
        import cache
        cache.upsert_items(ALL_ITEMS)
        old_ts = (datetime.utcnow() - timedelta(days=8)).isoformat()
        cache.set_meta("items_updated", old_ts)
        assert cache.items_need_refresh() is True


class TestHeroItems:
    def test_upsert_and_retrieve(self, item_db):
        import cache
        cache.upsert_hero_items(1, AM_ITEM_POPULARITY)
        rows = cache.get_hero_items(1)
        assert len(rows) > 0

    def test_phase_keys_normalised(self, item_db):
        import cache
        cache.upsert_hero_items(1, AM_ITEM_POPULARITY)
        rows = cache.get_hero_items(1)
        phases = {r["phase"] for r in rows}
        assert phases <= {"start", "early", "mid", "late"}

    def test_item_name_prefix_stripped(self, item_db):
        import cache
        cache.upsert_hero_items(1, AM_ITEM_POPULARITY)
        rows = cache.get_hero_items(1)
        names = {r["item_name"] for r in rows}
        # Stored without "item_" prefix
        assert "power_treads" in names
        assert "blink" in names
        assert not any(n.startswith("item_") for n in names)

    def test_games_and_wins_stored_correctly(self, item_db):
        import cache
        cache.upsert_hero_items(1, AM_ITEM_POPULARITY)
        rows = cache.get_hero_items(1)
        blink = next(r for r in rows if r["item_name"] == "blink")
        assert blink["games"] == 25000
        assert blink["wins"] == 14000
        assert blink["phase"] == "mid"

    def test_zero_games_rows_excluded(self, item_db):
        import cache
        popularity = {"mid_game_items": {"item_blink": {"games": 0, "wins": 0}}}
        cache.upsert_hero_items(1, popularity)
        rows = cache.get_hero_items(1)
        assert all(r["games"] > 0 for r in rows)

    def test_unknown_phase_key_silently_ignored(self, item_db):
        import cache
        popularity = {"ultra_late_game_items": {"item_blink": {"games": 1000, "wins": 600}}}
        cache.upsert_hero_items(1, popularity)
        rows = cache.get_hero_items(1)
        # Unknown phase key produces no rows
        assert rows == []

    def test_hero_items_need_refresh_when_empty(self, item_db):
        import cache
        assert cache.hero_items_need_refresh(1) is True

    def test_hero_items_not_stale_after_upsert(self, item_db):
        import cache
        cache.upsert_hero_items(1, AM_ITEM_POPULARITY)
        assert cache.hero_items_need_refresh(1) is False

    def test_hero_items_stale_after_threshold(self, item_db):
        import cache
        cache.upsert_hero_items(1, AM_ITEM_POPULARITY)
        old_ts = (datetime.utcnow() - timedelta(days=2)).isoformat()
        cache.set_meta("hero_items_updated_1", old_ts)
        assert cache.hero_items_need_refresh(1) is True

    def test_has_hero_item_data_false_when_empty(self, item_db):
        import cache
        assert cache.has_hero_item_data(1) is False

    def test_has_hero_item_data_true_after_upsert(self, item_db):
        import cache
        cache.upsert_hero_items(1, AM_ITEM_POPULARITY)
        assert cache.has_hero_item_data(1) is True


class TestGetHeroIdByName:
    def test_known_hero_returns_id(self, populated_db):
        import cache
        assert cache.get_hero_id_by_name("antimage") == 1

    def test_known_hero_rubick(self, populated_db):
        import cache
        assert cache.get_hero_id_by_name("rubick") == 86

    def test_unknown_hero_returns_none(self, populated_db):
        import cache
        assert cache.get_hero_id_by_name("nonexistent_hero") is None

    def test_empty_db_returns_none(self, tmp_db):
        import cache
        assert cache.get_hero_id_by_name("antimage") is None

    def test_full_prefixed_name_not_found(self, populated_db):
        """Callers must pass the bare name, not the npc_dota_hero_ prefixed version."""
        import cache
        assert cache.get_hero_id_by_name("npc_dota_hero_antimage") is None
