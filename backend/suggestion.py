"""
Suggestion engine: scores every available hero given the current draft state.

Scoring formula per candidate hero H with baseline win rate B:
  counter_delta = avg(matchup_wr(H, enemy) for enemy in enemies) - B
  synergy_delta = avg(synergy_wr(H, ally)  for ally  in allies)  - B
  score = w_wr * B
        + w_ctr * (B + counter_delta)
        + w_syn * (B + synergy_delta)
        + w_me  * personal_score(H)   [when personal data loaded]

Using B as the reference for delta scores means:
  - counter/synergy deltas are relative to THIS hero's own baseline, not a universal 0.5
  - A hero with 48% baseline that wins 53% vs Storm Spirit shows +5% counter (correct)
  - A hero with 55% baseline that wins 56% vs Storm Spirit shows +1% counter (correct)
"""
import logging
from models import HeroSuggestion
import cache
import config

log = logging.getLogger(__name__)
W_PERSONAL = 0.15
# Amplifier for counter and synergy deltas in the score formula.
# With dense Stratz data (~3500 games per matchup pair), deltas are reliable and
# don't need heavy amplification. Value of 2 gives a +5% counter delta ~4% score impact.
DELTA_AMPLIFIER = 2.0

# Maps UI role filter strings to Stratz position IDs for position-specific baselines.
# "Carry" heroes are rated as pos-1 carry; "Support" blends pos-4 and pos-5.
# Other roles fall back to the global win rate.
_ROLE_TO_POSITIONS = {
    "Carry":   ["POSITION_1"],
    "Support": ["POSITION_4", "POSITION_5"],
}


def _counter_delta(hero_id, opponent_ids, baseline_wr):
    """
    How much better hero_id performs vs the enemy lineup relative to its own baseline.
    Prefers Stratz data (100% game coverage) over OpenDota sample data when available.
    Positive = genuine counter advantage. 0 = no enemies picked.
    """
    if not opponent_ids:
        return 0.0
    use_stratz = cache.has_stratz_matchup_data()
    if use_stratz:
        scores = [cache.get_stratz_matchup_winrate(hero_id, opp) for opp in opponent_ids]
    else:
        scores = [cache.get_matchup_winrate(hero_id, opp) for opp in opponent_ids]
    return sum(scores) / len(scores) - baseline_wr


def _synergy_delta(hero_id, ally_ids, baseline_wr):
    """
    How much better hero_id performs when paired with current allies, vs its own baseline.
    Uses Stratz with-teammate data when available, otherwise a neutrality heuristic.
    """
    if not ally_ids:
        return 0.0
    if cache.has_synergy_data():
        scores = [cache.get_synergy_winrate(hero_id, ally) for ally in ally_ids]
        return sum(scores) / len(scores) - baseline_wr
    # Fallback: reward pairs that don't strongly counter each other
    # (if ally wins X% when hero is the enemy, that's an anti-synergy signal)
    deltas = []
    for ally_id in ally_ids:
        ally_wr_vs_hero = cache.get_matchup_winrate(ally_id, hero_id)
        # Perfect neutral (0.5) = good synergy proxy; divergence = potential clash
        deltas.append(0.5 - abs(ally_wr_vs_hero - 0.5))
    return sum(deltas) / len(deltas) - 0.5  # Centre around 0


def _personal_score(hero_id, personal_stats):
    """Confidence-weighted personal win rate. Returns (0-1 score, display_wr, games)."""
    entry = personal_stats.get(hero_id)
    if not entry or entry["games"] == 0:
        return None, None, None
    games      = entry["games"]
    raw_wr     = entry["winrate"]
    confidence = min(1.0, games / cache.PERSONAL_FULL_CONFIDENCE_GAMES)
    blended    = raw_wr * confidence + 0.5 * (1 - confidence)
    return blended, round(raw_wr * 100, 1), games


def get_suggestions(draft, role_filter=None, weights=None, account_id=None, brackets=None):
    """
    brackets: list of int bracket numbers (1-8), or None for global pub stats.
    """
    w_wr, w_syn, w_ctr = weights or config.scoring_weights()
    all_heroes = cache.get_all_heroes()
    if not all_heroes:
        return []

    has_matchup = cache.has_matchup_data()

    if draft.my_team == "radiant":
        my_picks    = [h.id for h in draft.radiant.picks]
        enemy_picks = [h.id for h in draft.dire.picks]
    else:
        my_picks    = [h.id for h in draft.dire.picks]
        enemy_picks = [h.id for h in draft.radiant.picks]

    excluded_ids = set(
        h.id for h in (
            draft.radiant.picks + draft.radiant.bans +
            draft.dire.picks    + draft.dire.bans
        )
    )

    personal_stats = {}
    has_personal   = False
    if account_id and cache.has_personal_stats(account_id):
        personal_stats = cache.get_personal_stats(account_id)
        has_personal   = True

    suggestions = []
    position_keys = _ROLE_TO_POSITIONS.get(role_filter) if role_filter else None
    use_position_stats = position_keys and cache.has_position_stats()
    for hero in all_heroes:
        hero_id = hero["id"]
        if hero_id in excluded_ids:
            continue
        if role_filter and role_filter not in hero.get("roles", []):
            continue

        # Hero's baseline win rate: position-specific when available, else pub/bracket stats
        if use_position_stats:
            pos_wrs = [cache.get_position_winrate(hero_id, p) for p in position_keys]
            pos_wrs = [wr for wr in pos_wrs if wr is not None]
            baseline = sum(pos_wrs) / len(pos_wrs) if pos_wrs else cache.get_overall_winrate(hero_id, brackets=brackets)
        else:
            baseline = cache.get_overall_winrate(hero_id, brackets=brackets)

        # Deltas relative to hero's own baseline (0 = no picks yet)
        ctr_d = _counter_delta(hero_id, enemy_picks, baseline) if has_matchup else 0.0
        syn_d = _synergy_delta(hero_id, my_picks,    baseline) if has_matchup else 0.0

        # Reconstruct 0-1 scores for the weighted formula
        ctr_score = baseline + DELTA_AMPLIFIER * ctr_d
        syn_score = baseline + DELTA_AMPLIFIER * syn_d

        personal_blended, personal_wr, personal_games = _personal_score(hero_id, personal_stats)

        if has_personal and personal_blended is not None:
            scale = 1.0 - W_PERSONAL
            raw   = (w_wr * baseline + w_ctr * ctr_score + w_syn * syn_score) * scale \
                    + W_PERSONAL * personal_blended
        else:
            raw = w_wr * baseline + w_ctr * ctr_score + w_syn * syn_score

        suggestions.append(HeroSuggestion(
            hero_id=hero_id,
            hero_name=hero["name"],
            display_name=hero["display_name"],
            primary_attr=hero.get("primary_attr", ""),
            roles=hero.get("roles", []),
            winrate=round(baseline * 100, 1),
            synergy_score=round(syn_d * 100, 1),    # delta from own baseline
            counter_score=round(ctr_d * 100, 1),    # delta from own baseline
            personal_winrate=personal_wr,
            personal_games=personal_games,
            total_score=round(raw * 100, 1),
            image_url=hero.get("image_url", ""),
        ))

    suggestions.sort(key=lambda h: h.total_score, reverse=True)
    return suggestions
