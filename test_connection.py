"""
Connection test for Dota Draft Helper.
Run this to verify the backend is working without needing a real Dota 2 game.

Usage:
  python test_connection.py          # full test (heartbeat + fake draft)
  python test_connection.py --quick  # heartbeat only
"""
import sys
import json
import urllib.request
import urllib.error

BACKEND = "http://localhost:4000"


def ok(msg):  print(f"  \033[32m[OK]\033[0m  {msg}")
def fail(msg): print(f"  \033[31m[FAIL]\033[0m {msg}")
def info(msg): print(f"  \033[90m[..]\033[0m  {msg}")
def header(msg): print(f"\n{msg}\n{'─' * len(msg)}")


def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BACKEND + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def get(path):
    with urllib.request.urlopen(BACKEND + path, timeout=5) as resp:
        return json.loads(resp.read())


# ── 1. Backend reachability ───────────────────────────────────────────────────

header("1. Backend")
try:
    status = get("/api/status")
    ok("Backend is running")
except urllib.error.URLError:
    fail("Cannot reach backend at " + BACKEND)
    print("\n  Make sure run.bat is running first, then try again.")
    sys.exit(1)


# ── 2. Data cache status ──────────────────────────────────────────────────────

header("2. Data cache")
heroes_age  = status.get("heroes")
matchup_age = status.get("matchups")
patch       = status.get("current_patch")

if heroes_age:
    ok(f"Heroes loaded  ({heroes_age['hours_ago']}h ago)")
else:
    info("Heroes not yet downloaded (still loading in background)")

if matchup_age:
    ok(f"Matchup data   ({matchup_age['hours_ago']}h ago)")
else:
    info("Matchup data not yet downloaded (will take ~3 min on first run)")

if patch:
    ok(f"Current patch: {patch}")
else:
    info("Patch info not yet fetched")

if status.get("has_synergy_data"):
    ok("Synergy data loaded (Stratz)")
elif status.get("has_stratz_token"):
    info("Stratz token present but synergy data not downloaded yet")
else:
    info("No Stratz token — synergy will use heuristic fallback")


# ── 3. Simulate a Dota 2 heartbeat ───────────────────────────────────────────

header("3. GSI heartbeat simulation")
heartbeat = {
    "provider": {"name": "Dota 2", "appid": 570, "version": 47},
    "map": {"game_state": "DOTA_GAMERULES_STATE_WAIT_FOR_PLAYERS_TO_LOAD"}
}
try:
    result = post("/gsi", heartbeat)
    if result.get("ok"):
        ok("Backend accepted heartbeat payload")
    else:
        fail(f"Backend rejected heartbeat: {result}")
except Exception as e:
    fail(f"Heartbeat failed: {e}")

# Verify it registered
status2 = get("/api/status")
if status2.get("gsi_connected"):
    ok("Dota 2 connection status now shows CONNECTED in the UI")
else:
    fail("GSI contact not registered (unexpected)")


if "--quick" in sys.argv:
    print("\nQuick check done. Run without --quick to also test the full draft pipeline.\n")
    sys.exit(0)


# ── 4. Simulate a full draft ──────────────────────────────────────────────────

header("4. Full draft simulation")

heroes = get("/api/heroes")
if not heroes:
    info("Hero data not loaded yet — skipping draft simulation")
    info("Wait for the background download to finish, then re-run this script")
    print()
    sys.exit(0)

# Pick 4 real heroes from the cache for a realistic test
sample = heroes[:8]
radiant = sample[:2]
dire    = sample[4:6]
r_ban   = sample[6]
d_ban   = sample[7]

def hero_slot(hero, i, prefix):
    return {
        f"{prefix}{i}_id":    hero["id"],
        f"{prefix}{i}_class": hero["name"].replace("npc_dota_hero_", ""),
    }

team2 = {"home_team": True}
team3 = {"home_team": False}

for i, h in enumerate(radiant):
    team2.update(hero_slot(h, i, "pick"))
team2.update(hero_slot(r_ban, 0, "ban"))

for i, h in enumerate(dire):
    team3.update(hero_slot(h, i, "pick"))
team3.update(hero_slot(d_ban, 0, "ban"))

draft_payload = {
    "map":   {"game_state": "DOTA_GAMERULES_STATE_HERO_SELECTION"},
    "draft": {
        "activeteam":                2,
        "activeteam_time_remaining": 30.0,
        "radiant_bonus_time":        130.0,
        "dire_bonus_time":           130.0,
        "team2":                     team2,
        "team3":                     team3,
    }
}

try:
    result = post("/gsi", draft_payload)
    if result.get("ok"):
        ok("Draft payload accepted")
    else:
        fail(f"Draft payload rejected: {result}")
except Exception as e:
    fail(f"Draft simulation failed: {e}")
    sys.exit(1)

r_names = [h["display_name"] for h in radiant]
d_names = [h["display_name"] for h in dire]
print(f"\n  Simulated draft:")
print(f"    Radiant picks : {', '.join(r_names)}")
print(f"    Dire picks    : {', '.join(d_names)}")
print(f"\n  The browser should now show hero suggestions.")
print(f"  Check http://localhost:4000 — the draft board should be visible.\n")
print(f"  (Sending a heartbeat to clear the simulated draft...)")

# Clean up — send a non-draft payload so the UI resets
post("/gsi", {"map": {"game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"}})


# ── Summary ───────────────────────────────────────────────────────────────────

header("Summary")
print("  Everything looks good! When you're ready to play:")
print("  1. The backend is already running (run.bat)")
print("  2. Open Dota 2 — it will connect within ~30 seconds")
print("  3. The browser header will show  Dota 2: connected")
print("  4. Queue up and enter hero selection\n")
