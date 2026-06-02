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
