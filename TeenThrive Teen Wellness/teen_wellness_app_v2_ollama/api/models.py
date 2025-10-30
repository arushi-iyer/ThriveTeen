from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    name: Optional[str] = None
    gender: Optional[str] = Field(default=None)  # 'female' or 'male'
    age_years: Optional[int] = Field(default=None)
    height_cm: Optional[float] = Field(default=None)
    weight_kg: Optional[float] = Field(default=None)
    activity_level: Optional[str] = Field(default="moderate")
    kcal_goal: Optional[int] = Field(default=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class FoodItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    path: str
    calories: Optional[int] = None
    phash: str
    ahash: str
    dhash: str
    hist_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MoodLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    day: str = Field(index=True)  # YYYY-MM-DD
    slot: str = Field(index=True) # HH:MM rounded to 30-min
    mood: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class JournalEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    day: str = Field(index=True)
    note: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TodoItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str
    urgent: bool = False
    important: bool = False
    done: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

class BadgeEarned(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ActivityLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    day: str = Field(index=True)  # YYYY-MM-DD local day
    key: str  # activity key
    title: str
    points: int = 10
    completed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None