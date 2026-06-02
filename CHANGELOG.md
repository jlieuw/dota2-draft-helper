# Changelog

## [Unreleased]

### Added

#### In-Game Item Suggestions
- New **In-Game tab** in the frontend that activates automatically when a Dota 2 match starts.
- Live item suggestions based on the hero you are playing, your current gold, game time, and the enemy lineup.
- Suggestions are scored on three factors: historical win rate for this hero, game-phase relevance (early/mid/late timing), and counter value against the enemy heroes picked.
- Items you already own are excluded from suggestions. If you own a component of an item it receives a build-path bonus.
- **Inventory bar** shows your current items (main slots, stash, neutral) pulled live from GSI.
- Item data is fetched lazily from OpenDota `/heroes/{id}/itemPopularity` on first game entry and cached locally for 24 hours.
- Item constants (costs, components, display names) fetched from OpenDota `/constants/items` and cached for 7 days.
- Counter-item mappings: 20+ item types mapped to enemy ability tags (magic nuke, disable, silence, illusion, evasion, etc.) covering 40+ heroes.
- New `/api/items` endpoint exposes item constants to the frontend and simulator.

#### GSI Expansion
- GSI config now requests `items`, `player`, and `abilities` keys in addition to the existing `draft`, `map`, and `hero` keys — required for in-game inventory and gold data.
- `setup_gsi.py` auto-detects stale configs and upgrades them in-place without requiring manual re-installation. Config detection now parses actual key-value pairs instead of doing a substring search (respects `//` comments).

#### Simulator improvements
- **All Pick mode** toggle: hides ban slots so the simulator can be used to model ranked/unranked All Pick games.
- **In-Game Preview tab**: select your hero, set game time (slider), gold, hero level, and manually add items to your inventory — the backend immediately computes and broadcasts item suggestions based on this simulated state, making it usable for testing item builds without a live game.

#### Testing
- 96 new automated tests (120 total, up from 24).
- New `test_item_suggestion.py`: guards, filtering, phase scoring, counter scoring, affordability, build-path bonus, output invariants.
- Extended `test_gsi_handler.py`: `parse_game_state` (all state transitions, field parsing, gold fallback), `_parse_inventory` (slot types, prefix stripping, empty filtering).
- Extended `test_cache.py`: item constants, hero item popularity, `get_hero_id_by_name`, refresh TTL.
- Extended `conftest.py`: item fixtures (`item_db`, `full_db`), shared item and popularity test data.

### Changed
- App auto-switches to the **In-Game** tab when a match starts and back to **Draft** when the draft phase begins.
- `gsi_handler.parse_gsi_payload` renamed to `parse_draft_state` for clarity; existing tests updated via import alias.
- Backend `build_payload()` now includes `mode` (`"draft"` | `"game"` | `"idle"`), `game_state`, and `item_suggestions` in every WebSocket broadcast.
- `backend/models.py` extended with `InventoryItem`, `GameState`, and `ItemSuggestion` Pydantic models.

### Fixed
- **Retry storm on failed item fetch**: `ensure_hero_item_data` previously cleared its in-flight guard in the `finally` block regardless of outcome, causing the backend to retry a failed OpenDota request at up to 10 Hz for the rest of the game. A 60-second failure cooldown is now applied per hero.
- **React DOM mutation**: `ItemSuggestionList` image `onError` handler used `replaceWith()` to swap a React-managed `<img>` with a raw DOM node, which caused `removeChild` reconciliation errors on the next render. Replaced with `style.display = 'none'`.
- **Stale draft on new lobby entry**: `current_draft` was never cleared when entering hero selection before the draft block was populated by Valve's GSI, so picks from the previous game appeared as the current draft state. Draft is now reset as soon as the hero-selection game state is detected.
- **GSI config key detection**: `_config_needs_update` in `setup_gsi.py` used a plain substring search which could be fooled by commented-out keys. Now parses active key-value pairs and skips `//`-prefixed comment lines.
- **Python 3.9 compatibility**: `X | None` union type syntax requires Python 3.10+. Added `from __future__ import annotations` to `gsi_handler.py`, `cache.py`, and `item_suggestion.py`.
- **`conftest.py` temp path**: hardcoded `/tmp` (Linux only) replaced with `tempfile.gettempdir()` so tests run on Windows.
