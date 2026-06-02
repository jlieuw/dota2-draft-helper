"""
Shared pytest fixtures.
Each test gets a fresh, isolated SQLite database in /tmp so tests are
independent and fast, and never touch the real user data directory.
"""
import sys
import uuid
import tempfile
import pytest
from pathlib import Path

# Make sure the backend package is importable from tests/
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def tmp_db(monkeypatch):
    """
    Patches cache.DB_PATH to a fresh temp file in /tmp and initialises the schema.
    Using /tmp explicitly to avoid SQLite locking issues on mounted NTFS paths.
    """
    import cache
    db_file = Path(tempfile.gettempdir()) / f"dota_test_{uuid.uuid4().hex}.db"
    monkeypatch.setattr(cache, "DB_PATH", db_file)
    cache.init_db()
    yield db_file
    if db_file.exists():
        db_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Shared sample data helpers
# ---------------------------------------------------------------------------

HERO_AM   = {"id": 1,  "name": "npc_dota_hero_antimage",  "localized_name": "Anti-Mage",
              "primary_attr": "agi", "attack_type": "Melee",  "roles": ["Carry", "Escape", "Nuker"]}
HERO_RUBICK = {"id": 86, "name": "npc_dota_hero_rubick",   "localized_name": "Rubick",
                "primary_attr": "int", "attack_type": "Ranged", "roles": ["Support", "Disabler", "Nuker"]}
HERO_INVOKER = {"id": 74, "name": "npc_dota_hero_invoker", "localized_name": "Invoker",
                 "primary_attr": "int", "attack_type": "Ranged", "roles": ["Carry", "Nuker", "Disabler", "Escape"]}
HERO_KOTL = {"id": 53, "name": "npc_dota_hero_keeper_of_the_light",
              "localized_name": "Keeper of the Light",
              "primary_attr": "int", "attack_type": "Ranged", "roles": ["Support", "Nuker"]}

ALL_HEROES = [HERO_AM, HERO_RUBICK, HERO_INVOKER, HERO_KOTL]

# Matchups: hero_id's win rate when facing enemy_hero_id
# AM counters Invoker strongly (55%), Rubick counters AM slightly (52%)
MATCHUPS = {
    1:  [{"hero_id": 74, "games_played": 10000, "wins": 5500},   # AM vs Invoker: 55%
         {"hero_id": 86, "games_played": 8000,  "wins": 3840},   # AM vs Rubick:  48%
         {"hero_id": 53, "games_played": 6000,  "wins": 3000}],  # AM vs KotL:    50%
    86: [{"hero_id": 1,  "games_played": 8000,  "wins": 4160},   # Rubick vs AM:  52%
         {"hero_id": 74, "games_played": 9000,  "wins": 4500},   # Rubick vs Inv: 50%
         {"hero_id": 53, "games_played": 7000,  "wins": 3500}],  # Rubick vs KotL:50%
    74: [{"hero_id": 1,  "games_played": 10000, "wins": 4500},   # Invoker vs AM: 45%
         {"hero_id": 86, "games_played": 9000,  "wins": 4500},   # Invoker vs Rub:50%
         {"hero_id": 53, "games_played": 8000,  "wins": 4000}],  # Invoker vs KotL:50%
    53: [{"hero_id": 1,  "games_played": 6000,  "wins": 3000},   # KotL vs AM:    50%
         {"hero_id": 86, "games_played": 7000,  "wins": 3500},   # KotL vs Rubick:50%
         {"hero_id": 74, "games_played": 8000,  "wins": 4000}],  # KotL vs Invoker:50%
}

# Synergy: Rubick has great synergy with AM (55%), KotL moderate (52%)
SYNERGIES = {
    1:  [{"hero_id2": 86, "wins": 5500, "games": 10000},   # AM + Rubick: 55%
         {"hero_id2": 53, "wins": 5200, "games": 10000},   # AM + KotL:   52%
         {"hero_id2": 74, "wins": 4800, "games": 10000}],  # AM + Invoker: 48%
    86: [{"hero_id2": 1,  "wins": 5500, "games": 10000},
         {"hero_id2": 53, "wins": 5000, "games": 10000},
         {"hero_id2": 74, "wins": 5000, "games": 10000}],
    74: [{"hero_id2": 1,  "wins": 4800, "games": 10000},
         {"hero_id2": 86, "wins": 5000, "games": 10000},
         {"hero_id2": 53, "wins": 5000, "games": 10000}],
    53: [{"hero_id2": 1,  "wins": 5200, "games": 10000},
         {"hero_id2": 86, "wins": 5000, "games": 10000},
         {"hero_id2": 74, "wins": 5000, "games": 10000}],
}


@pytest.fixture()
def populated_db(tmp_db):
    """tmp_db with heroes, matchups, and synergies already loaded."""
    import cache
    cache.upsert_heroes(ALL_HEROES)
    cache.upsert_matchups(MATCHUPS)
    cache.upsert_synergies(SYNERGIES)
    yield tmp_db


# ---------------------------------------------------------------------------
# Item test data
# ---------------------------------------------------------------------------

ITEM_BLINK = {
    "name": "blink",
    "display_name": "Blink Dagger",
    "cost": 2250,
    "components": [],
    "image_url": "https://example.com/blink.png",
}

ITEM_BKB = {
    "name": "black_king_bar",
    "display_name": "Black King Bar",
    "cost": 4050,
    "components": ["ogre_axe", "mithril_hammer"],
    "image_url": "https://example.com/bkb.png",
}

ITEM_TREADS = {
    "name": "power_treads",
    "display_name": "Power Treads",
    "cost": 1400,
    "components": ["boots", "gloves"],
    "image_url": "https://example.com/treads.png",
}

ALL_ITEMS = {i["name"]: i for i in [ITEM_BLINK, ITEM_BKB, ITEM_TREADS]}

# hero_id=1 (AM) item popularity data shaped like OpenDota's response
AM_ITEM_POPULARITY = {
    "start_game_items": {
        "item_tango":         {"games": 50000, "wins": 25000},
    },
    "early_game_items": {
        "item_power_treads":  {"games": 30000, "wins": 16500},
    },
    "mid_game_items": {
        "item_blink":         {"games": 25000, "wins": 14000},
        "item_black_king_bar": {"games": 20000, "wins": 11000},
    },
    "late_game_items": {
        "item_butterfly":     {"games": 15000, "wins": 8500},
    },
}


@pytest.fixture()
def item_db(tmp_db):
    """tmp_db with heroes and item constants loaded."""
    import cache
    cache.upsert_heroes(ALL_HEROES)
    cache.upsert_items(ALL_ITEMS)
    yield tmp_db


@pytest.fixture()
def full_db(tmp_db):
    """tmp_db with all data: heroes, matchups, synergies, items, and hero item popularity."""
    import cache
    cache.upsert_heroes(ALL_HEROES)
    cache.upsert_matchups(MATCHUPS)
    cache.upsert_synergies(SYNERGIES)
    cache.upsert_items(ALL_ITEMS)
    cache.upsert_hero_items(1, AM_ITEM_POPULARITY)
    yield tmp_db
