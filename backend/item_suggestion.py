"""
Scores items for the current in-game state using three factors:

  win_rate_score  – how often this item wins on this hero vs the hero's baseline
  phase_score     – how well the item timing matches the current game clock
  counter_score   – how much this item counters the enemy hero lineup

The final score is a weighted composite. Items the player already owns are
excluded. Items where a component is already owned receive a small bonus to
surface natural build progressions.
"""
from __future__ import annotations

import logging
from models import GameState, ItemSuggestion
import cache

log = logging.getLogger(__name__)

# ── Scoring weights (sum to 1.0) ──────────────────────────────────────────────

_W_WINRATE  = 0.50
_W_PHASE    = 0.30
_W_COUNTER  = 0.20

# Minimum games in phase data before a win rate is trusted.
_MIN_GAMES = 100

# Maximum items returned.
_MAX_SUGGESTIONS = 20

# Bonus score applied when the player already owns a component of the item.
_COMPONENT_BONUS = 0.05

# ── Game phase windows (seconds) ─────────────────────────────────────────────

_PHASE_WINDOWS: dict[str, tuple[int, int]] = {
    "start": (0,    300),    # 0–5 min
    "early": (300,  900),    # 5–15 min
    "mid":   (900,  2100),   # 15–35 min
    "late":  (2100, 99999),  # 35+ min
}

# ── Items excluded from suggestions ──────────────────────────────────────────
# Consumables and wards are purchased contextually, not strategic build choices.

_EXCLUDED_ITEMS = {
    "tpscroll", "tango", "clarity", "healing_salve", "enchanted_mango",
    "faerie_fire", "dust", "ward_observer", "ward_sentry", "smoke_of_deceit",
    "tome_of_knowledge", "sentry_ward", "observer_ward",
}

# ── Counter-item mappings ─────────────────────────────────────────────────────
# Maps item_name -> the set of threat tags the item counters.

_ITEM_COUNTERS: dict[str, set[str]] = {
    "black_king_bar":   {"magic_nuke", "disable", "silence", "hex"},
    "linkens_sphere":   {"targeted_spell"},
    "manta_style":      {"silence", "targeted_spell"},
    "lotus_orb":        {"targeted_spell", "debuff"},
    "pipe_of_insight":  {"magic_nuke"},
    "eternal_shroud":   {"magic_nuke"},
    "heaven_halberd":   {"high_dps"},
    "ghost_scepter":    {"high_dps"},
    "ethereal_blade":   {"high_dps"},
    "blade_mail":       {"high_dps"},
    "silver_edge":      {"strong_passive"},
    "diffusal_blade":   {"illusion", "summon_heavy"},
    "monkey_king_bar":  {"evasion"},
    "nullifier":        {"item_dependent"},
    "bloodthorn":       {"evasion"},
    "radiance":         {"illusion", "summon_heavy"},
    "blink":            {"disable"},
    "force_staff":      {"disable"},
}

# ── Hero threat tag mappings ──────────────────────────────────────────────────
# Maps hero internal name (npc_dota_hero_ stripped) -> threat tags.
# Used to compute which items counter the current enemy lineup.

_HERO_THREAT_TAGS: dict[str, set[str]] = {
    # Magic nukers / burst damage
    "zuus":               {"magic_nuke"},
    "lina":               {"magic_nuke", "disable"},
    "lion":               {"magic_nuke", "disable", "targeted_spell", "hex"},
    "storm_spirit":       {"magic_nuke", "disable"},
    "skywrath_mage":      {"magic_nuke", "silence"},
    "invoker":            {"magic_nuke"},
    "razor":              {"magic_nuke"},
    "ancient_apparition": {"magic_nuke"},
    "jakiro":             {"magic_nuke", "disable"},
    "crystal_maiden":     {"magic_nuke", "disable"},
    "viper":              {"magic_nuke", "debuff"},
    "queen_of_pain":      {"magic_nuke"},
    "lich":               {"magic_nuke", "disable"},
    "necrolyte":          {"magic_nuke", "debuff"},
    "ogre_magi":          {"magic_nuke", "disable"},
    # Targeted / single-target disablers
    "shadow_shaman":      {"targeted_spell", "disable", "hex"},
    "bane":               {"targeted_spell", "disable"},
    "doom_bringer":       {"targeted_spell", "silence", "disable"},
    "disruptor":          {"targeted_spell", "disable", "silence"},
    "rubick":             {"targeted_spell", "disable"},
    "witch_doctor":       {"targeted_spell", "disable"},
    "obsidian_destroyer": {"targeted_spell", "silence"},
    # Silencers
    "silencer":           {"silence", "magic_nuke"},
    "drow_ranger":        {"silence"},
    "puck":               {"silence", "magic_nuke"},
    "troll_warlord":      {"silence", "high_dps"},
    # Illusion / summon-heavy
    "phantom_lancer":     {"illusion"},
    "chaos_knight":       {"illusion", "disable"},
    "terrorblade":        {"illusion"},
    "naga_siren":         {"illusion", "disable", "silence"},
    "furion":             {"summon_heavy"},   # Nature's Prophet
    "broodmother":        {"summon_heavy"},
    "warlock":            {"summon_heavy"},
    "lycan":              {"summon_heavy"},
    # Evasion
    "phantom_assassin":   {"evasion"},
    "windranger":         {"evasion"},
    # High physical DPS
    "ursa":               {"high_dps"},
    "juggernaut":         {"high_dps"},
    "clinkz":             {"high_dps"},
    "antimage":           {"high_dps"},
    "luna":               {"high_dps"},
    "faceless_void":      {"high_dps", "disable"},
    # Strong passives (Silver Edge counters)
    "bristleback":        {"strong_passive"},
    "axe":                {"strong_passive"},
    "centaur_warrunner":  {"strong_passive"},
    "huskar":             {"strong_passive"},
    # Item-dependent carries (Nullifier counters)
    "medusa":             {"item_dependent"},
    "spectre":            {"item_dependent"},
    "wraith_king":        {"item_dependent"},
}


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _phase_score(item_phase: str, game_time: int) -> float:
    """
    Returns 0.0–1.0 relevance of an item's purchase phase at the current game time.
    Items in the current phase score 1.0. Adjacent phases score proportionally less,
    decaying over one phase window in either direction.
    """
    start, end = _PHASE_WINDOWS[item_phase]
    if start <= game_time < end:
        return 1.0
    window = end - start
    distance = min(abs(game_time - start), abs(game_time - end))
    return max(0.0, 1.0 - distance / window)


def _counter_score(item_name: str, enemy_names: list[str]) -> tuple[float, str | None]:
    """
    Returns (score 0.0–1.0, human-readable reason | None).
    Score grows with the number of enemies the item counters, capped at three.
    """
    item_tags = _ITEM_COUNTERS.get(item_name)
    if not item_tags or not enemy_names:
        return 0.0, None

    countered = [
        hero for hero in enemy_names
        if _HERO_THREAT_TAGS.get(hero, set()) & item_tags
    ]
    if not countered:
        return 0.0, None

    score = min(1.0, len(countered) / 3.0)
    names = ", ".join(h.replace("_", " ").title() for h in countered[:3])
    return score, f"Counters {names}"


# ── Public API ────────────────────────────────────────────────────────────────

def get_item_suggestions(game_state: GameState) -> list[ItemSuggestion]:
    """
    Returns a ranked list of item suggestions for the current in-game state.
    Returns an empty list if game state is inactive or hero data is unavailable.
    """
    if not game_state.active or not game_state.hero_name:
        return []

    hero_id = cache.get_hero_id_by_name(game_state.hero_name)
    if not hero_id:
        log.debug("No hero_id found for '%s' — skipping item suggestions", game_state.hero_name)
        return []

    hero_items = cache.get_hero_items(hero_id)
    all_items  = cache.get_items_dict()
    if not hero_items or not all_items:
        return []

    hero_baseline = cache.get_overall_winrate(hero_id)
    owned_names   = {item.item_name for item in game_state.items}

    candidates: list[ItemSuggestion] = []

    for entry in hero_items:
        item_name = entry["item_name"]
        phase     = entry["phase"]
        games     = entry["games"]
        wins      = entry["wins"]

        if item_name in _EXCLUDED_ITEMS:
            continue
        if item_name in owned_names:
            continue
        if "recipe" in item_name:
            continue
        if games < _MIN_GAMES:
            continue

        meta = all_items.get(item_name)
        if not meta:
            continue

        phase_sc = _phase_score(phase, game_state.game_time)
        if phase_sc < 0.05:
            continue

        # Win rate score: normalised to hero baseline so items are judged relative
        # to how well this hero performs in general, not absolute win rate.
        raw_wr   = wins / games
        wr_delta = raw_wr - hero_baseline
        wr_score = min(1.0, max(0.0, 0.5 + wr_delta * 5.0))

        ctr_sc, reason = _counter_score(item_name, game_state.enemy_hero_names)

        total = _W_WINRATE * wr_score + _W_PHASE * phase_sc + _W_COUNTER * ctr_sc

        components    = meta.get("components", [])
        has_component = bool(components and owned_names & set(components))
        if has_component:
            total = min(1.0, total + _COMPONENT_BONUS)

        candidates.append(ItemSuggestion(
            item_name=item_name,
            display_name=meta["display_name"],
            cost=meta["cost"],
            image_url=meta["image_url"],
            win_rate=round(raw_wr * 100, 1),
            games=games,
            phase=phase,
            counter_bonus=round(ctr_sc * 100, 1),
            total_score=round(total * 100, 1),
            can_afford=meta["cost"] <= game_state.gold,
            has_component=has_component,
            reason=reason,
        ))

    # Multiple phases can exist for the same item; keep only the highest-scoring entry.
    best: dict[str, ItemSuggestion] = {}
    for s in candidates:
        if s.item_name not in best or s.total_score > best[s.item_name].total_score:
            best[s.item_name] = s

    return sorted(best.values(), key=lambda s: s.total_score, reverse=True)[:_MAX_SUGGESTIONS]
