# Dota 2 Draft Helper

Real-time hero suggestion tool for Dota 2's Captain's Mode draft. Scores every available hero against your current picks and the enemy lineup using win-rate, synergy, and counter data — updated live as picks and bans come in.

Uses only **official, public APIs** (Valve GSI, OpenDota, Stratz). No process injection, no memory reading, no TOS violations.

---

## Features

- **Live draft board** — mirrors the in-game pick/ban state via Valve's Game State Integration
- **Scored suggestions** — each hero ranked by a weighted composite of win rate, synergy with your allies, and counter advantage vs enemies
- **Stratz integration** — real synergy + counter data from Stratz GraphQL (free token, optional but recommended)
- **Rank bracket filter** — filter all data to your skill bracket (Herald → Immortal)
- **Position-aware baselines** — suggestions adjust when you filter by role (Carry, Support, etc.)
- **Personal hero stats** — loads your OpenDota match history automatically; shows your win rate per hero and comfort-pick badges
- **My Heroes panel** — most played, best and worst heroes by win rate
- **Patch tracking** — all cached data is tagged with the patch it was fetched for; refreshes automatically when a new patch drops
- **Draft Simulator** — test the tool without a live game
- **Fully offline after first run** — data is cached in SQLite, refreshed daily

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- Dota 2 installed via Steam

### 2. Install GSI config (one time)

```
python setup_gsi.py
```

This writes the Game State Integration config into your Dota 2 directory. Run once, then restart Dota 2.

### 3. Configure (optional but recommended)

```
cp config.example.json config.json
```

Edit `config.json`:

| Field | Description |
|---|---|
| `stratz_token` | Free token from [stratz.com/api](https://stratz.com/api). Enables real synergy + counter data. |
| `steam_account_id` | Your OpenDota account ID — loads your personal hero stats on startup (without needing a game). If you have a Stratz token, this is decoded automatically. |
| `rank_bracket` | Filter data to your rank: `all`, `herald`, `guardian`, `crusader`, `archon`, `legend`, `ancient`, `divine`, `immortal` |
| `scoring_weights` | Relative weight of win rate / synergy / counter in the score. Must sum to 1.0. |

### 4. Run

```
run.bat
```

Double-click `run.bat`. It installs dependencies (first run only), builds the frontend, starts the backend, and opens your browser. First run downloads ~5 MB of hero data — this takes a few minutes.

**Tip:** Start `run.bat` before you queue. The browser window can sit next to Dota 2 — it activates automatically when the draft begins.

---

## How It Works

```
Dota 2  ──GSI POST──►  Python backend (localhost:4000)
                              │
                    ┌─────────▼──────────┐
                    │  Suggestion engine  │
                    │  winrate × 0.25    │
                    │  synergy × 0.35    │
                    │  counter × 0.40    │
                    └─────────┬──────────┘
                              │ WebSocket
                    ┌─────────▼──────────┐
                    │   React frontend    │
                    │   Draft board       │
                    │   Suggestion list   │
                    └────────────────────┘
```

1. **GSI** — Dota 2 sends live draft state (picks, bans, active team) to the local HTTP server every 100 ms.
2. **Data** — Hero stats and matchup data come from OpenDota (free, no auth) and Stratz GraphQL (free token). Cached locally in SQLite and refreshed daily.
3. **Scoring** — Each hero is scored relative to its own baseline win rate. Synergy and counter deltas are computed from with-teammate and versus-enemy win rates from Stratz.
4. **Frontend** — React app renders the draft board and suggestion table, updating live over WebSocket as picks come in.

---

## Suggestion Columns

| Column | What it means |
|---|---|
| **Winrate** | Hero's baseline pub win rate in the selected rank bracket |
| **Synergy** | Win rate delta when paired with your current picks (positive = benefits from your lineup) |
| **Counter** | Win rate delta against the enemy picks (positive = counters their lineup) |
| **You** | Your personal win rate on this hero (shown when OpenDota profile is public) |
| **Score** | Weighted composite (0–100) |

🎮 badge = you've played this hero 30+ games (comfort pick).

---

## Supported Game Modes

| Mode | Supported |
|---|---|
| Captain's Mode | ✅ |
| Random Draft | ✅ |
| Single Draft | ✅ |
| All Pick (ranked/unranked) | ❌ Valve does not include draft data in GSI for All Pick |

---

## Project Structure

```
dota2-draft-helper/
├── backend/
│   ├── main.py          # FastAPI app — GSI receiver, WebSocket, API routes
│   ├── gsi_handler.py   # Parses raw GSI payloads → DraftState
│   ├── suggestion.py    # Scoring engine
│   ├── stratz.py        # Stratz GraphQL client (synergy + counter data)
│   ├── opendota.py      # OpenDota REST client (heroes, matchups, player stats)
│   ├── cache.py         # SQLite cache layer
│   ├── config.py        # Loads config.json + env vars
│   ├── models.py        # Pydantic models
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx               # Page routing, header nav
│       ├── useWebSocket.js       # WebSocket state hook
│       └── components/
│           ├── DraftBoard.jsx    # Pick/ban board
│           ├── SuggestionList.jsx# Ranked hero table
│           ├── MyHeroesPanel.jsx # Personal hero stats
│           └── StatusBar.jsx     # Data age + patch info
├── config.example.json  # Configuration template
├── setup_gsi.py         # One-time GSI installer
├── test_connection.py   # Verify backend + simulate a draft
├── simulator.html       # Draft simulator (test without a game)
└── run.bat              # One-click launcher (Windows)
```

---

## Personal Hero Stats

Personal stats load automatically if:
- You set `steam_account_id` in `config.json`, **or**
- You have a `stratz_token` (your Steam ID is decoded from it automatically), **or**
- You open Dota 2 (GSI sends your Steam ID when you enter a game)

Your OpenDota profile must be **public**. Enable it at [opendota.com](https://www.opendota.com) → Settings → *Expose Public Match Data*.

---

## Data Sources

| Data | Source | Refresh |
|---|---|---|
| Hero list + roles | OpenDota `/heroStats` | Weekly |
| Hero vs hero matchups | OpenDota `/heroes/{id}/matchups` | Daily |
| Synergy + counter (Stratz) | Stratz GraphQL `heroVsHeroMatchup` | Daily |
| Position win rates | Stratz GraphQL `heroStats.stats` | Daily |
| Current patch | OpenDota `/metadata` | On startup |
| Personal hero stats | OpenDota `/players/{id}/heroes` | Every 6 hours |

---

## TOS & Safety

This app uses only:
- **Valve GSI** — Valve's own broadcast system, used by hundreds of legitimate apps
- **Public read-only APIs** — OpenDota and Stratz are public community services
- **No process interaction** — the app never reads game memory, injects code, or touches the Dota 2 process

It does **not** read opponent Steam profiles or match history during the draft, which is the practice Valve restricted in their February 2024 update.

---

## License

[MIT](LICENSE)

