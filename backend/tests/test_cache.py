"""Tests for the cache layer (heroes, matchups, synergies, meta)."""
import pytest
from datetime import datetime, timedelta
from tests.conftest import ALL_HEROES, MATCHUPS, SYNERGIES, HERO_AM, HERO_RUBICK


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
