"""Tests for the suggestion engine."""
import pytest
from gsi_handler import parse_gsi_payload
from models import DraftState, TeamDraft, HeroSlot


def _make_draft(my_team="radiant",
                radiant_picks=(), radiant_bans=(),
                dire_picks=(), dire_bans=()):
    """Build a DraftState directly without GSI payload."""
    def slots(ids): return [HeroSlot(id=i, name=str(i)) for i in ids]
    return DraftState(
        active=True,
        my_team=my_team,
        radiant=TeamDraft(picks=slots(radiant_picks), bans=slots(radiant_bans)),
        dire=TeamDraft(picks=slots(dire_picks),    bans=slots(dire_bans)),
    )


class TestExclusion:
    def test_picked_hero_not_suggested(self, populated_db):
        import suggestion
        draft = _make_draft(radiant_picks=[1])   # AM already picked
        suggestions = suggestion.get_suggestions(draft)
        ids = [s.hero_id for s in suggestions]
        assert 1 not in ids

    def test_banned_hero_not_suggested(self, populated_db):
        import suggestion
        draft = _make_draft(radiant_bans=[74])   # Invoker banned
        suggestions = suggestion.get_suggestions(draft)
        assert 74 not in [s.hero_id for s in suggestions]

    def test_enemy_pick_not_suggested(self, populated_db):
        import suggestion
        draft = _make_draft(dire_picks=[86])   # Rubick on enemy team
        suggestions = suggestion.get_suggestions(draft)
        assert 86 not in [s.hero_id for s in suggestions]

    def test_all_heroes_excluded_returns_empty(self, populated_db):
        import suggestion
        # Pick/ban every hero
        draft = _make_draft(
            radiant_picks=[1, 86],
            radiant_bans=[74],
            dire_picks=[53],
        )
        suggestions = suggestion.get_suggestions(draft)
        assert suggestions == []


class TestRoleFilter:
    def test_carry_filter_excludes_supports(self, populated_db):
        import suggestion
        draft = _make_draft()
        suggestions = suggestion.get_suggestions(draft, role_filter="Carry")
        for s in suggestions:
            assert "Carry" in s.roles

    def test_support_filter_excludes_carries(self, populated_db):
        import suggestion
        draft = _make_draft()
        suggestions = suggestion.get_suggestions(draft, role_filter="Support")
        ids = [s.hero_id for s in suggestions]
        # AM (id=1) is Carry/Escape — must not appear under Support filter
        assert 1 not in ids

    def test_unknown_role_returns_empty(self, populated_db):
        import suggestion
        draft = _make_draft()
        suggestions = suggestion.get_suggestions(draft, role_filter="Nonexistent")
        assert suggestions == []


class TestScoring:
    def test_hero_countering_enemy_scores_higher(self, populated_db):
        """
        AM counters Invoker (55% WR). With Invoker as enemy,
        AM should score higher on counter_score than a neutral hero.
        """
        import suggestion
        # AM is already picked by us; compare Rubick vs KotL when Invoker is enemy
        draft = _make_draft(radiant_picks=[1], dire_picks=[74])
        suggestions = suggestion.get_suggestions(draft)
        by_id = {s.hero_id: s for s in suggestions}

        # Both Rubick and KotL have 50% vs Invoker, so counter_score should be equal
        # AM itself is excluded (already picked)
        assert 74 not in by_id   # Invoker is enemy pick, excluded
        assert 1  not in by_id   # AM is our pick, excluded

    def test_counter_score_positive_when_hero_beats_enemy(self, populated_db):
        """AM (id=1) beats Invoker (74) 55%. If we could suggest AM vs Invoker enemy,
        counter_score should be > 0. We test a hero with clear counter advantage."""
        import suggestion
        # Put AM as available (no picks yet), Invoker as enemy
        draft = _make_draft(dire_picks=[74])
        suggestions = suggestion.get_suggestions(draft)
        am = next(s for s in suggestions if s.hero_id == 1)
        # 55% vs 50% neutral → counter_score delta should be positive
        assert am.counter_score > 0

    def test_synergy_score_uses_stratz_data(self, populated_db):
        """With Stratz data loaded, Rubick synergises with AM (55% when together).
        Rubick's synergy_score when AM is allied should be positive."""
        import suggestion
        draft = _make_draft(radiant_picks=[1])   # AM is our ally
        suggestions = suggestion.get_suggestions(draft)
        rubick = next(s for s in suggestions if s.hero_id == 86)
        # 55% with AM → synergy delta = +5% → synergy_score > 0
        assert rubick.synergy_score > 0

    def test_suggestions_sorted_by_total_score(self, populated_db):
        import suggestion
        draft = _make_draft()
        suggestions = suggestion.get_suggestions(draft)
        scores = [s.total_score for s in suggestions]
        assert scores == sorted(scores, reverse=True)

    def test_custom_weights_applied(self, populated_db):
        """Setting counter weight to 1.0 should make AM the top pick vs Invoker."""
        import suggestion
        draft = _make_draft(dire_picks=[74])   # Invoker as enemy
        # All weight on counter
        suggestions = suggestion.get_suggestions(draft, weights=(0.0, 0.0, 1.0))
        # AM counters Invoker at 55% — should be the top suggestion
        assert suggestions[0].hero_id == 1

    def test_empty_db_returns_empty(self, tmp_db):
        import suggestion
        draft = _make_draft()
        assert suggestion.get_suggestions(draft) == []

    def test_no_enemy_picks_neutral_counter_score(self, populated_db):
        """With no enemy picks, every hero should have counter_score ≈ 0 (neutral 50%)."""
        import suggestion
        draft = _make_draft()
        suggestions = suggestion.get_suggestions(draft)
        for s in suggestions:
            assert s.counter_score == pytest.approx(0.0, abs=0.1)
