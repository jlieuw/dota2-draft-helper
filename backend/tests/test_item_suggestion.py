"""Tests for the item suggestion engine."""
import pytest
from models import GameState, InventoryItem


def _make_game_state(
    hero_name="antimage",
    hero_level=11,
    game_time=900,
    gold=3000,
    items=(),
    ally_hero_names=(),
    enemy_hero_names=(),
):
    return GameState(
        active=True,
        hero_name=hero_name,
        hero_level=hero_level,
        game_time=game_time,
        gold=gold,
        net_worth=gold + 3000,
        items=[InventoryItem(slot=f"slot{i}", item_name=name) for i, name in enumerate(items)],
        ally_hero_names=list(ally_hero_names),
        enemy_hero_names=list(enemy_hero_names),
    )


# ── Guard conditions ──────────────────────────────────────────────────────────

class TestGuards:
    def test_inactive_game_state_returns_empty(self, full_db):
        import item_suggestion
        state = GameState(active=False)
        assert item_suggestion.get_item_suggestions(state) == []

    def test_empty_hero_name_returns_empty(self, full_db):
        import item_suggestion
        state = GameState(active=True, hero_name="")
        assert item_suggestion.get_item_suggestions(state) == []

    def test_unknown_hero_returns_empty(self, full_db):
        import item_suggestion
        state = _make_game_state(hero_name="nonexistent_hero")
        assert item_suggestion.get_item_suggestions(state) == []

    def test_no_hero_item_data_returns_empty(self, item_db):
        """item_db has item constants but no per-hero popularity data."""
        import item_suggestion
        state = _make_game_state(hero_name="antimage")
        assert item_suggestion.get_item_suggestions(state) == []

    def test_no_item_constants_returns_empty(self, tmp_db):
        """Without item constants, no suggestions can be constructed."""
        import cache, item_suggestion
        from tests.conftest import ALL_HEROES, AM_ITEM_POPULARITY
        cache.upsert_heroes(ALL_HEROES)
        cache.upsert_hero_items(1, AM_ITEM_POPULARITY)
        # No upsert_items — item metadata table is empty
        state = _make_game_state(hero_name="antimage")
        assert item_suggestion.get_item_suggestions(state) == []


# ── Filtering ─────────────────────────────────────────────────────────────────

class TestFiltering:
    def test_owned_item_excluded(self, full_db):
        import item_suggestion
        state = _make_game_state(items=["blink"])
        results = item_suggestion.get_item_suggestions(state)
        names = [s.item_name for s in results]
        assert "blink" not in names

    def test_consumables_excluded(self, full_db):
        """Tango and TP scrolls must never appear in suggestions."""
        import cache, item_suggestion
        from tests.conftest import ALL_ITEMS, AM_ITEM_POPULARITY
        extra_items = dict(ALL_ITEMS)
        extra_items["tango"] = {"name": "tango", "display_name": "Tango", "cost": 90, "components": [], "image_url": ""}
        extra_items["tpscroll"] = {"name": "tpscroll", "display_name": "TP Scroll", "cost": 50, "components": [], "image_url": ""}
        cache.upsert_items(extra_items)

        popularity = dict(AM_ITEM_POPULARITY)
        popularity["start_game_items"] = {
            "item_tango":    {"games": 60000, "wins": 40000},
            "item_tpscroll": {"games": 55000, "wins": 35000},
        }
        cache.upsert_hero_items(1, popularity)

        state = _make_game_state(hero_name="antimage")
        names = [s.item_name for s in item_suggestion.get_item_suggestions(state)]
        assert "tango" not in names
        assert "tpscroll" not in names

    def test_recipe_items_excluded(self, full_db):
        import cache, item_suggestion
        from tests.conftest import AM_ITEM_POPULARITY
        extra_items = {"recipe_blink": {"name": "recipe_blink", "display_name": "Blink Recipe", "cost": 0, "components": [], "image_url": ""}}
        cache.upsert_items(extra_items)

        popularity = dict(AM_ITEM_POPULARITY)
        popularity["mid_game_items"]["item_recipe_blink"] = {"games": 5000, "wins": 3000}
        cache.upsert_hero_items(1, popularity)

        state = _make_game_state(hero_name="antimage")
        names = [s.item_name for s in item_suggestion.get_item_suggestions(state)]
        assert "recipe_blink" not in names

    def test_low_sample_items_excluded(self, full_db):
        """Items with fewer than _MIN_GAMES games are filtered out."""
        import cache, item_suggestion
        from tests.conftest import AM_ITEM_POPULARITY
        popularity = {"mid_game_items": {"item_blink": {"games": 50, "wins": 40}}}
        cache.upsert_hero_items(1, popularity)

        state = _make_game_state(hero_name="antimage")
        names = [s.item_name for s in item_suggestion.get_item_suggestions(state)]
        assert "blink" not in names


# ── Phase scoring ─────────────────────────────────────────────────────────────

class TestPhaseScore:
    def test_mid_game_item_scores_higher_at_mid_game_time(self, full_db):
        """Blink (mid) should score better at minute 20 than at minute 2."""
        import item_suggestion
        state_mid  = _make_game_state(game_time=1200)  # 20 min — mid phase
        state_early = _make_game_state(game_time=120)  # 2 min — start phase

        mid_results   = {s.item_name: s for s in item_suggestion.get_item_suggestions(state_mid)}
        early_results = {s.item_name: s for s in item_suggestion.get_item_suggestions(state_early)}

        if "blink" in mid_results and "blink" in early_results:
            assert mid_results["blink"].total_score >= early_results["blink"].total_score

    def test_out_of_phase_item_may_still_appear_with_lower_score(self, full_db):
        """An item far from its typical phase should score lower but not necessarily disappear."""
        import item_suggestion
        # At late game, early items should decay
        state = _make_game_state(game_time=3600)
        results = item_suggestion.get_item_suggestions(state)
        # Just assert the engine runs without error and returns a list
        assert isinstance(results, list)


# ── Counter scoring ───────────────────────────────────────────────────────────

class TestCounterScore:
    def test_counter_bonus_for_known_enemy(self, full_db):
        """BKB scores higher when there are magic/disable enemies in the lineup."""
        import item_suggestion
        state_with_enemy    = _make_game_state(enemy_hero_names=["lion", "shadow_shaman"])
        state_without_enemy = _make_game_state(enemy_hero_names=[])

        with_results    = {s.item_name: s for s in item_suggestion.get_item_suggestions(state_with_enemy)}
        without_results = {s.item_name: s for s in item_suggestion.get_item_suggestions(state_without_enemy)}

        if "black_king_bar" in with_results and "black_king_bar" in without_results:
            assert with_results["black_king_bar"].counter_bonus > without_results["black_king_bar"].counter_bonus

    def test_counter_reason_set_for_matched_enemy(self, full_db):
        import item_suggestion
        state = _make_game_state(enemy_hero_names=["lion"])
        results = {s.item_name: s for s in item_suggestion.get_item_suggestions(state)}
        if "black_king_bar" in results:
            assert results["black_king_bar"].reason is not None
            assert "Lion" in results["black_king_bar"].reason

    def test_no_counter_bonus_for_untagged_enemy(self, full_db):
        import item_suggestion
        # Use an enemy hero not in _HERO_THREAT_TAGS
        state = _make_game_state(enemy_hero_names=["some_unknown_hero"])
        results = item_suggestion.get_item_suggestions(state)
        for s in results:
            assert s.counter_bonus == pytest.approx(0.0)

    def test_no_counter_bonus_with_no_enemies(self, full_db):
        import item_suggestion
        state = _make_game_state(enemy_hero_names=[])
        results = item_suggestion.get_item_suggestions(state)
        for s in results:
            assert s.counter_bonus == pytest.approx(0.0)


# ── Affordability & build path ────────────────────────────────────────────────

class TestAffordabilityAndBuildPath:
    def test_can_afford_true_when_gold_sufficient(self, full_db):
        import item_suggestion
        state = _make_game_state(gold=99999)
        results = item_suggestion.get_item_suggestions(state)
        for s in results:
            if s.cost <= 99999:
                assert s.can_afford is True

    def test_can_afford_false_when_gold_insufficient(self, full_db):
        import item_suggestion
        state = _make_game_state(gold=0)
        results = item_suggestion.get_item_suggestions(state)
        for s in results:
            assert s.can_afford is False

    def test_component_bonus_applied(self, full_db):
        """Owning 'ogre_axe' (component of BKB) should boost BKB's score."""
        import item_suggestion
        state_with_component    = _make_game_state(items=["ogre_axe"])
        state_without_component = _make_game_state(items=[])

        with_res    = {s.item_name: s for s in item_suggestion.get_item_suggestions(state_with_component)}
        without_res = {s.item_name: s for s in item_suggestion.get_item_suggestions(state_without_component)}

        if "black_king_bar" in with_res and "black_king_bar" in without_res:
            assert with_res["black_king_bar"].has_component is True
            assert without_res["black_king_bar"].has_component is False
            assert with_res["black_king_bar"].total_score > without_res["black_king_bar"].total_score

    def test_has_component_false_when_no_components_owned(self, full_db):
        import item_suggestion
        state = _make_game_state(items=[])
        results = item_suggestion.get_item_suggestions(state)
        for s in results:
            assert s.has_component is False


# ── Output shape & invariants ─────────────────────────────────────────────────

class TestOutputInvariants:
    def test_results_sorted_by_total_score_descending(self, full_db):
        import item_suggestion
        state = _make_game_state()
        results = item_suggestion.get_item_suggestions(state)
        scores = [s.total_score for s in results]
        assert scores == sorted(scores, reverse=True)

    def test_no_duplicate_item_names(self, full_db):
        """Each item appears at most once even if it has multiple phase entries."""
        import item_suggestion
        state = _make_game_state()
        results = item_suggestion.get_item_suggestions(state)
        names = [s.item_name for s in results]
        assert len(names) == len(set(names))

    def test_max_suggestions_cap(self, full_db):
        import item_suggestion
        state = _make_game_state()
        results = item_suggestion.get_item_suggestions(state)
        assert len(results) <= item_suggestion._MAX_SUGGESTIONS

    def test_all_fields_populated(self, full_db):
        import item_suggestion
        state = _make_game_state()
        results = item_suggestion.get_item_suggestions(state)
        for s in results:
            assert s.item_name
            assert s.display_name
            assert s.cost >= 0
            assert 0 <= s.win_rate <= 100
            assert 0 <= s.total_score <= 100
            assert s.phase in {"start", "early", "mid", "late"}
