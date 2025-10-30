from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, date

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    age_years: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    activity_level: Optional[str] = None
    kcal_goal: Optional[int] = None

class ProfileOut(BaseModel):
    email: str
    name: Optional[str]
    gender: Optional[str]
    age_years: Optional[int]
    height_cm: Optional[float]
    weight_kg: Optional[float]
    activity_level: Optional[str]
    kcal_goal: Optional[int]
    created_at: datetime

class PredictOut(BaseModel):
    matched: bool
    predicted_calories: Optional[int] = None
    confidence: float = 0.0
    match_item_id: Optional[int] = None
    saved_item_id: Optional[int] = None
    hint: str = ""

class ItemRow(BaseModel):
    id: int
    calories: Optional[int]
    created_at: datetime
    image_url: str

class DailySummary(BaseModel):
    date: date
    total_calories: int
    items_count: int

class WeeklySummary(BaseModel):
    start: date
    end: date
    total_calories: int
    avg_per_day: float
    days: List[DailySummary]

class MoodSetRequest(BaseModel):
    mood: str
    tz_offset_minutes: int = 0

class MoodLogOut(BaseModel):
    day: str
    slot: str
    mood: str
    created_at: datetime

class MoodSummaryOut(BaseModel):
    day: date
    counts: dict
    total: int
    logs: List[MoodLogOut]

class JournalAddRequest(BaseModel):
    note: str
    tz_offset_minutes: int = 0

class JournalEntryOut(BaseModel):
    id: int
    day: str
    note: str
    created_at: datetime

class TodoCreateRequest(BaseModel):
    title: str
    urgent: bool = False
    important: bool = False

class TodoUpdateRequest(BaseModel):
    title: Optional[str] = None
    urgent: Optional[bool] = None
    important: Optional[bool] = None
    done: Optional[bool] = None

class TodoItemOut(BaseModel):
    id: int
    title: str
    urgent: bool
    important: bool
    done: bool
    created_at: datetime
    completed_at: Optional[datetime]

class BadgeOut(BaseModel):
    id: int
    title: str
    created_at: datetime

class ActivityReco(BaseModel):
    key: str
    title: str
    points: int

class ActivityStatus(BaseModel):
    key: str
    title: str
    points: int
    completed: bool
    completed_at: Optional[datetime]