"""
SQLite cache for hero data, matchup statistics, synergy data, and personal stats.
"""
import os
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from config import rank_bracket_id

log = logging.getLogger(__name__)

# Bracket number → name mapping (matches OpenDota field prefix e.g. "1_win", "2_pick")
BRACKETS = {
    1: "Herald",
    2: "Guardian",
    3: "Crusader",
    4: "Archon",
    5: "Legend",
    6: "Ancient",
    7: "Divine",
    8: "Immortal",
}

# Min games for a matchup to get full confidence weight
MIN_MATCHUP_GAMES = 30


def _get_db_path():
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home())) / "DotaDraftHelper"
    else:
        base = Path.home() / ".local" / "share" / "DotaDraftHelper"
    base.mkdir(parents=True, exist_ok=True)
    return base / "cache.db"


DB_PATH = _get_db_path()
HERO_REFRESH_DAYS     = 7
MATCHUP_REFRESH_DAYS  = 1
SYNERGY_REFRESH_DAYS  = 1
POSITION_REFRESH_DAYS = 1


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS heroes (
                id            INTEGER PRIMARY KEY,
                name          TEXT NOT NULL,
                display_name  TEXT NOT NULL,
                primary_attr  TEXT,
                attack_type   TEXT,
                roles         TEXT,
                image_url     TEXT,
                pub_win       INTEGER DEFAULT 0,
                pub_pick      INTEGER DEFAULT 0,
                bracket_stats TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS matchups (
                hero_id         INTEGER NOT NULL,
                enemy_hero_id   INTEGER NOT NULL,
                games_played    INTEGER NOT NULL,
                wins            INTEGER NOT NULL,
                PRIMARY KEY (hero_id, enemy_hero_id)
            );
            CREATE TABLE IF NOT EXISTS synergies (
                hero_id         INTEGER NOT NULL,
                ally_hero_id    INTEGER NOT NULL,
                games_played    INTEGER NOT NULL,
                wins            INTEGER NOT NULL,
                synergy_score   REAL DEFAULT NULL,
                PRIMARY KEY (hero_id, ally_hero_id)
            );
            CREATE TABLE IF NOT EXISTS personal_stats (
                account_id  INTEGER NOT NULL,
                hero_id     INTEGER NOT NULL,
                games       INTEGER NOT NULL,
                wins        INTEGER NOT NULL,
                PRIMARY KEY (account_id, hero_id)
            );
            CREATE TABLE IF NOT EXISTS stratz_matchups (
                hero_id         INTEGER NOT NULL,
                enemy_hero_id   INTEGER NOT NULL,
                games_played    INTEGER NOT NULL,
                wins            INTEGER NOT NULL,
                PRIMARY KEY (hero_id, enemy_hero_id)
            );
            CREATE TABLE IF NOT EXISTS hero_position_stats (
                hero_id     INTEGER NOT NULL,
                position    TEXT NOT NULL,
                match_count INTEGER NOT NULL,
                win_count   INTEGER NOT NULL,
                PRIMARY KEY (hero_id, position)
            );
            CREATE TABLE IF NOT EXISTS meta (
                key     TEXT PRIMARY KEY,
                value   TEXT NOT NULL
            );
        """)
        # Migrate older schemas
        for col, default in (("pub_win","0"),("pub_pick","0"),("bracket_stats","'{}'")):
            try:
                conn.execute(f"ALTER TABLE heroes ADD COLUMN {col} TEXT DEFAULT {default}")
            except Exception:
                pass
        # Migrate synergies table: add synergy_score if missing
        try:
            conn.execute("ALTER TABLE synergies ADD COLUMN synergy_score REAL DEFAULT NULL")
        except Exception:
            pass
    log.info("Database initialised at %s", DB_PATH)


# -- Patch helpers ------------------------------------------------------------

def get_current_patch():
    """Returns the current game patch stored in meta, or None."""
    return get_meta("current_patch")


def _data_matches_current_patch(data_patch_key):
    """
    Returns True if the data was fetched for the current patch.
    Returns True (don't force refresh) when either value is unknown.
    """
    stored = get_meta(data_patch_key)
    current = get_meta("current_patch")
    if not stored or not current:
        return True  # can't compare — don't force a refresh
    return stored == current


def _store_data_patch(conn, data_patch_key):
    """Writes the current patch alongside a data timestamp."""
    current = get_meta("current_patch")
    if current:
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (data_patch_key, current))


# -- Heroes -------------------------------------------------------------------

def heroes_need_refresh():
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key='heroes_updated'").fetchone()
        if not row:
            return True
        if datetime.utcnow() - datetime.fromisoformat(row["value"]) > timedelta(days=HERO_REFRESH_DAYS):
            return True
        return not _data_matches_current_patch("heroes_patch")


def upsert_heroes(heroes):
    """Store heroes with global pub stats and all 8 bracket stats."""
    with get_conn() as conn:
        for h in heroes:
            pub_win  = h.get("pub_win",  0) or 0
            pub_pick = h.get("pub_pick", 0) or 0

            # Collect all bracket stats
            bracket_stats = {}
            for num in range(1, 9):
                w = h.get(f"{num}_win",  0) or 0
                p = h.get(f"{num}_pick", 0) or 0
                if p > 0:
                    bracket_stats[num] = {"win": w, "pick": p}

            conn.execute("""
                INSERT OR REPLACE INTO heroes
                    (id, name, display_name, primary_attr, attack_type, roles, image_url,
                     pub_win, pub_pick, bracket_stats)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                h["id"],
                h.get("name", ""),
                h.get("localized_name", h.get("name", "")),
                h.get("primary_attr", ""),
                h.get("attack_type", ""),
                json.dumps(h.get("roles", [])),
                "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/"
                + h.get("name", "").replace("npc_dota_hero_", "") + ".png",
                pub_win, pub_pick,
                json.dumps(bracket_stats),
            ))
        conn.execute(
            "INSERT OR REPLACE INTO meta VALUES ('heroes_updated', ?)",
            (datetime.utcnow().isoformat(),)
        )
        _store_data_patch(conn, "heroes_patch")
    log.info("Cached %d heroes", len(heroes))


def get_all_heroes():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM heroes ORDER BY display_name").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["roles"] = json.loads(d["roles"] or "[]")
            # Include bracket_stats for frontend info
            try:
                d["bracket_stats"] = json.loads(d.get("bracket_stats") or "{}")
            except Exception:
                d["bracket_stats"] = {}
            result.append(d)
        return result


def get_hero_ids():
    with get_conn() as conn:
        return [r["id"] for r in conn.execute("SELECT id FROM heroes").fetchall()]


def get_overall_winrate(hero_id, brackets=None):
    """
    Returns the hero's win rate.
    brackets: list of bracket numbers (1-8) to blend. None = use global pub stats.
    Priority: selected brackets > global pub stats > matchup average.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT pub_win, pub_pick, bracket_stats FROM heroes WHERE id=?",
            (hero_id,)
        ).fetchone()

        if row:
            if brackets:
                try:
                    bs = json.loads(row["bracket_stats"] or "{}")
                    total_win  = sum(bs.get(str(b), {}).get("win",  0) for b in brackets)
                    total_pick = sum(bs.get(str(b), {}).get("pick", 0) for b in brackets)
                    if total_pick > 100:
                        return total_win / total_pick
                except Exception:
                    pass

            # Global pub stats
            if row["pub_pick"] and int(row["pub_pick"] or 0) > 100:
                return int(row["pub_win"] or 0) / int(row["pub_pick"])

        # Fallback: matchup average
        row2 = conn.execute(
            "SELECT SUM(wins) as w, SUM(games_played) as g FROM matchups WHERE hero_id=?",
            (hero_id,)
        ).fetchone()
        if row2 and row2["g"] and row2["g"] > 0:
            return row2["w"] / row2["g"]
        return 0.5


# -- Matchups -----------------------------------------------------------------

def matchups_need_refresh():
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key='matchups_updated'").fetchone()
        if not row:
            return True
        if datetime.utcnow() - datetime.fromisoformat(row["value"]) > timedelta(days=MATCHUP_REFRESH_DAYS):
            return True
        return not _data_matches_current_patch("matchups_patch")


def upsert_matchups(all_matchups):
    with get_conn() as conn:
        for hero_id, matchup_list in all_matchups.items():
            for m in matchup_list:
                conn.execute(
                    "INSERT OR REPLACE INTO matchups (hero_id, enemy_hero_id, games_played, wins) VALUES (?,?,?,?)",
                    (hero_id, m["hero_id"], m["games_played"], m["wins"])
                )
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('matchups_updated', ?)", (datetime.utcnow().isoformat(),))
        _store_data_patch(conn, "matchups_patch")
    log.info("Cached matchup data for %d heroes", len(all_matchups))


def get_matchup_winrate(hero_id, enemy_id):
    """Win rate of hero_id vs enemy_id, confidence-weighted by sample size."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT games_played, wins FROM matchups WHERE hero_id=? AND enemy_hero_id=?",
            (hero_id, enemy_id)
        ).fetchone()
        if row and row["games_played"] > 0:
            raw        = row["wins"] / row["games_played"]
            confidence = min(1.0, row["games_played"] / MIN_MATCHUP_GAMES)
            return raw * confidence + 0.5 * (1.0 - confidence)
        return 0.5


def has_matchup_data():
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM matchups").fetchone()
        return row["c"] > 0


# -- Synergies ----------------------------------------------------------------

def synergies_need_refresh():
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key='synergies_updated'").fetchone()
        if not row:
            return True
        if datetime.utcnow() - datetime.fromisoformat(row["value"]) > timedelta(days=SYNERGY_REFRESH_DAYS):
            return True
        # Re-fetch if the rank bracket setting has changed
        bracket_row = conn.execute("SELECT value FROM meta WHERE key='synergies_bracket'").fetchone()
        stored = bracket_row["value"] if bracket_row else None
        if stored != str(rank_bracket_id()):
            return True
        return not _data_matches_current_patch("synergies_patch")


def has_synergy_data():
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM synergies").fetchone()
        return row["c"] > 0


def upsert_synergies(all_synergies):
    with get_conn() as conn:
        for hero_id, synergy_list in all_synergies.items():
            for s in synergy_list:
                ally_id  = s["hero_id2"]
                games    = s["games"]
                wins     = s["wins"]
                syn_val  = s.get("synergy")  # may be None
                if games <= 0:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO synergies (hero_id, ally_hero_id, games_played, wins, synergy_score) VALUES (?,?,?,?,?)",
                    (hero_id, ally_id, games, wins, syn_val)
                )
                # Mirror row: same data, reversed perspective.
                # synergy is directional (from hero_id's baseline), so set NULL for mirror.
                conn.execute(
                    "INSERT OR REPLACE INTO synergies (hero_id, ally_hero_id, games_played, wins, synergy_score) VALUES (?,?,?,?,?)",
                    (ally_id, hero_id, games, wins, None)
                )
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('synergies_updated', ?)", (datetime.utcnow().isoformat(),))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('synergies_bracket', ?)", (str(rank_bracket_id()),))
        _store_data_patch(conn, "synergies_patch")
    log.info("Cached synergy data for %d heroes", len(all_synergies))


def get_synergy_winrate(hero_id, ally_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT games_played, wins FROM synergies WHERE hero_id=? AND ally_hero_id=?",
            (hero_id, ally_id)
        ).fetchone()
        if row and row["games_played"] > 0:
            raw        = row["wins"] / row["games_played"]
            confidence = min(1.0, row["games_played"] / MIN_MATCHUP_GAMES)
            return raw * confidence + 0.5 * (1.0 - confidence)
        return 0.5


# -- Personal stats -----------------------------------------------------------

PERSONAL_REFRESH_HOURS        = 6
PERSONAL_MIN_GAMES_FOR_WINRATE = 20   # min games to appear in best/worst lists
PERSONAL_COMFORT_GAMES         = 30   # min games to show comfort-pick badge in UI
PERSONAL_FULL_CONFIDENCE_GAMES = 50   # games at which personal score reaches full weight


def personal_stats_need_refresh(account_id):
    val = get_meta(f"personal_updated_{account_id}")
    if not val:
        return True
    return datetime.utcnow() - datetime.fromisoformat(val) > timedelta(hours=PERSONAL_REFRESH_HOURS)


def upsert_personal_stats(account_id, hero_stats):
    with get_conn() as conn:
        for h in hero_stats:
            hero_id = h.get("hero_id")
            games   = h.get("games", 0)
            wins    = h.get("win", 0)
            if not hero_id or games == 0:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO personal_stats (account_id, hero_id, games, wins) VALUES (?,?,?,?)",
                (account_id, hero_id, games, wins)
            )
        conn.execute(
            "INSERT OR REPLACE INTO meta VALUES (?,?)",
            (f"personal_updated_{account_id}", datetime.utcnow().isoformat())
        )
    log.info("Cached personal stats for account %d (%d heroes)", account_id, len(hero_stats))


def get_personal_stats(account_id):
    with get_conn() as conn:
        try:
            rows = conn.execute(
                "SELECT hero_id, games, wins FROM personal_stats WHERE account_id=?",
                (account_id,)
            ).fetchall()
        except Exception:
            return {}
        return {
            r["hero_id"]: {"games": r["games"], "winrate": r["wins"] / r["games"]}
            for r in rows if r["games"] > 0
        }


def has_personal_stats(account_id):
    with get_conn() as conn:
        try:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM personal_stats WHERE account_id=?", (account_id,)
            ).fetchone()
            return row["c"] > 0
        except Exception:
            return False


def get_personal_hero_summary(account_id, top_n=10):
    """
    Returns best/worst/most-played heroes for a player.
    Joins with heroes table for display names.
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.hero_id, h.display_name, h.name, h.image_url, p.games, p.wins
            FROM personal_stats p
            LEFT JOIN heroes h ON h.id = p.hero_id
            WHERE p.account_id = ?
            ORDER BY p.games DESC
        """, (account_id,)).fetchall()

    heroes = [
        {
            "hero_id":      r["hero_id"],
            "display_name": r["display_name"] or f"Hero {r['hero_id']}",
            "hero_name":    r["name"] or "",
            "image_url":    r["image_url"] or "",
            "games":        r["games"],
            "win_rate":     round(r["wins"] / r["games"] * 100, 1) if r["games"] > 0 else 0.0,
        }
        for r in rows if r["games"] > 0
    ]

    most_played  = heroes[:top_n]
    qualified    = [h for h in heroes if h["games"] >= PERSONAL_MIN_GAMES_FOR_WINRATE]
    best_winrate  = sorted(qualified, key=lambda h: h["win_rate"], reverse=True)[:top_n]
    worst_winrate = sorted(qualified, key=lambda h: h["win_rate"])[:top_n]

    return {
        "most_played":   most_played,
        "best_winrate":  best_winrate,
        "worst_winrate": worst_winrate,
        "total_heroes_played": len(heroes),
    }


# -- Meta ---------------------------------------------------------------------

def set_meta(key, value):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))


def get_meta(key):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def get_data_ages():
    now = datetime.utcnow()
    def age(key):
        val = get_meta(key)
        if not val:
            return None
        delta = now - datetime.fromisoformat(val)
        return {"timestamp": val, "hours_ago": int(delta.total_seconds() / 3600)}
    current_patch = get_meta("current_patch")
    return {
        "current_patch":       current_patch,
        "heroes":              age("heroes_updated"),
        "heroes_patch":        get_meta("heroes_patch"),
        "matchups":            age("matchups_updated"),
        "matchups_patch":      get_meta("matchups_patch"),
        "synergies":           age("synergies_updated"),
        "synergies_patch":     get_meta("synergies_patch"),
        "position_stats":      age("position_stats_updated"),
        "position_stats_patch": get_meta("position_stats_patch"),
        "has_synergy_data":    has_synergy_data(),
        "has_matchup_data":    has_matchup_data(),
        "has_position_stats":  has_position_stats(),
        "brackets":            BRACKETS,
    }


# -- Stratz matchups (counter data from full pub game dataset) ----------------

def has_stratz_matchup_data():
    with get_conn() as conn:
        try:
            row = conn.execute("SELECT COUNT(*) as c FROM stratz_matchups").fetchone()
            return row["c"] > 0
        except Exception:
            return False


def upsert_stratz_matchups(all_data):
    """
    all_data: { hero_id: { "vs": [ { hero_id2, wins, games } ] } }
    Stores bidirectionally so lookups work from either hero's perspective.
    """
    with get_conn() as conn:
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS stratz_matchups (
                hero_id INTEGER NOT NULL, enemy_hero_id INTEGER NOT NULL,
                games_played INTEGER NOT NULL, wins INTEGER NOT NULL,
                PRIMARY KEY (hero_id, enemy_hero_id))""")
        except Exception:
            pass
        for hero_id, data in all_data.items():
            for entry in data.get("vs", []):
                enemy_id = entry["hero_id2"]
                games    = entry["games"]
                wins     = entry["wins"]
                if games <= 0:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO stratz_matchups (hero_id, enemy_hero_id, games_played, wins) VALUES (?,?,?,?)",
                    (hero_id, enemy_id, games, wins)
                )
                # Mirror: from enemy's perspective, wins = games - wins (enemy loses those games)
                conn.execute(
                    "INSERT OR REPLACE INTO stratz_matchups (hero_id, enemy_hero_id, games_played, wins) VALUES (?,?,?,?)",
                    (enemy_id, hero_id, games, games - wins)
                )
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('stratz_matchups_updated', ?)", (datetime.utcnow().isoformat(),))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('stratz_matchups_bracket', ?)", (str(rank_bracket_id()),))
        _store_data_patch(conn, "stratz_matchups_patch")
    log.info("Cached Stratz counter data for %d heroes", len(all_data))


def get_stratz_matchup_winrate(hero_id, enemy_id):
    """
    Win rate of hero_id when enemy_id is on the opposing team (Stratz data).
    Much larger sample than OpenDota matchup data.
    Returns 0.5 if no data.
    """
    with get_conn() as conn:
        try:
            row = conn.execute(
                "SELECT games_played, wins FROM stratz_matchups WHERE hero_id=? AND enemy_hero_id=?",
                (hero_id, enemy_id)
            ).fetchone()
            if row and row["games_played"] > 0:
                raw        = row["wins"] / row["games_played"]
                confidence = min(1.0, row["games_played"] / MIN_MATCHUP_GAMES)
                return raw * confidence + 0.5 * (1.0 - confidence)
        except Exception:
            pass
        return 0.5


def invalidate_hero_cache():
    """
    Force hero data to re-download on next startup.
    Call this after switching to a new API endpoint so stale cached data is replaced.
    """
    with get_conn() as conn:
        conn.execute("DELETE FROM meta WHERE key='heroes_updated'")
    log.info("Hero cache invalidated — will re-download on next startup.")


# -- Position stats (Stratz hero win rates per lane position) -----------------

def position_stats_need_refresh():
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key='position_stats_updated'").fetchone()
        if not row:
            return True
        if datetime.utcnow() - datetime.fromisoformat(row["value"]) > timedelta(days=POSITION_REFRESH_DAYS):
            return True
        bracket_row = conn.execute("SELECT value FROM meta WHERE key='position_stats_bracket'").fetchone()
        stored = bracket_row["value"] if bracket_row else None
        if stored != str(rank_bracket_id()):
            return True
        return not _data_matches_current_patch("position_stats_patch")


def has_position_stats():
    with get_conn() as conn:
        try:
            row = conn.execute("SELECT COUNT(*) as c FROM hero_position_stats").fetchone()
            return row["c"] > 0
        except Exception:
            return False


def upsert_position_stats(rows):
    """
    rows: [ { heroId, position, matchCount, winCount }, ... ]
    Replaces all position stats for heroes present in the new data.
    """
    with get_conn() as conn:
        for row in rows:
            hero_id     = row.get("heroId")
            position    = row.get("position")
            match_count = row.get("matchCount", 0)
            win_count   = row.get("winCount", 0)
            if not hero_id or not position or match_count <= 0:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO hero_position_stats (hero_id, position, match_count, win_count) VALUES (?,?,?,?)",
                (hero_id, position, match_count, win_count)
            )
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('position_stats_updated', ?)", (datetime.utcnow().isoformat(),))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('position_stats_bracket', ?)", (str(rank_bracket_id()),))
        _store_data_patch(conn, "position_stats_patch")
    log.info("Cached position stats: %d rows", len(rows))


def get_position_winrate(hero_id, position):
    """
    Returns the win rate for hero_id at the given position, or None if insufficient data.
    Requires at least 100 games to be usable (avoids noisy results for off-meta picks).
    """
    with get_conn() as conn:
        try:
            row = conn.execute(
                "SELECT match_count, win_count FROM hero_position_stats WHERE hero_id=? AND position=?",
                (hero_id, position)
            ).fetchone()
            if row and row["match_count"] >= 100:
                return row["win_count"] / row["match_count"]
        except Exception:
            pass
        return None
