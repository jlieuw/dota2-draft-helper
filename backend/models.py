from pydantic import BaseModel
from typing import Optional


class HeroSlot(BaseModel):
    id: int
    name: str  # internal class name e.g. "antimage"


class TeamDraft(BaseModel):
    picks: list[HeroSlot]  # up to 5
    bans: list[HeroSlot]   # up to 7


class DraftState(BaseModel):
    active: bool = False
    my_team: str = "radiant"
    radiant: TeamDraft = TeamDraft(picks=[], bans=[])
    dire: TeamDraft = TeamDraft(picks=[], bans=[])
    active_team: Optional[str] = None
    time_remaining: Optional[float] = None


class HeroSuggestion(BaseModel):
    hero_id: int
    hero_name: str
    display_name: str
    primary_attr: str
    roles: list[str]
    winrate: float           # 0-100, global win rate
    synergy_score: float     # delta from 50%, paired with my picks
    counter_score: float     # delta from 50%, against enemy picks
    personal_winrate: Optional[float] = None   # your win rate on this hero (0-100), None if no data
    personal_games: Optional[int] = None       # how many games you've played this hero
    total_score: float       # weighted composite 0-100
    image_url: str


class SuggestionResponse(BaseModel):
    draft: DraftState
    suggestions: list[HeroSuggestion]
    excluded_ids: list[int]
    has_personal_data: bool = False   # whether personal stats are loaded


# ── In-game models ────────────────────────────────────────────────────────────

class InventoryItem(BaseModel):
    slot: str       # e.g. "slot0", "stash2", "neutral0"
    item_name: str  # e.g. "power_treads" (no "item_" prefix)


class GameState(BaseModel):
    active: bool = False
    hero_name: str = ""         # e.g. "antimage" (no npc_dota_hero_ prefix)
    hero_level: int = 1
    game_time: int = 0          # seconds since game start
    gold: int = 0
    net_worth: int = 0
    items: list[InventoryItem] = []
    ally_hero_names: list[str] = []    # teammates, excluding self
    enemy_hero_names: list[str] = []


class ItemSuggestion(BaseModel):
    item_name: str
    display_name: str
    cost: int
    image_url: str
    win_rate: float         # 0-100, hero's win rate when buying this item
    games: int              # sample size
    phase: str              # "start" | "early" | "mid" | "late"
    counter_bonus: float    # extra score from countering enemy heroes, 0-100
    total_score: float      # 0-100 composite
    can_afford: bool
    has_component: bool     # player already owns a component of this item
    reason: Optional[str] = None  # e.g. "Counters Lion, Bane"
