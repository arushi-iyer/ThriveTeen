from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, Session, create_engine, select
from typing import Optional, List
from datetime import datetime, date, timedelta, timezone
from PIL import Image
import io, os, json, numpy as np, certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from .models import User, FoodItem, MoodLog, JournalEntry, TodoItem, BadgeEarned, ActivityLog
from .schemas import *
from .auth import *
from .matcher import compute_features, match_confidence

DB_URL = "sqlite:///./calorie_tracker.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
BASE_DIR = os.path.dirname(__file__)
STORAGE_DIR = os.path.join(BASE_DIR, "..", "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

def init_db():
    SQLModel.metadata.create_all(engine)
    try:
        conn = engine.raw_connection(); cur = conn.cursor()
        cur.execute("PRAGMA table_info(user)")
        cols = [r[1] for r in cur.fetchall()]
        for name, typ in [("name","TEXT"),("gender","TEXT"),("age_years","INTEGER"),
                          ("height_cm","REAL"),("weight_kg","REAL"),
                          ("activity_level","TEXT"),("kcal_goal","INTEGER")]:
            if name not in cols:
                cur.execute(f"ALTER TABLE user ADD COLUMN {name} {typ}")
        conn.commit(); cur.close(); conn.close()
    except Exception:
        pass

app = FastAPI(title="Teen Calorie Tracker — US11p (reco + badges + chat)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=os.path.abspath(STORAGE_DIR)), name="static")

@app.on_event("startup")
def startup(): init_db()

def get_session():
    with Session(engine) as s:
        yield s

def get_user(authorization: Optional[str] = Header(None), session: Session = Depends(get_session)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing token")
    parts = authorization.split()
    token = parts[1] if len(parts) > 1 else None
    payload = decode_token(token) if token else None
    if not payload: raise HTTPException(401, "Invalid token")
    u = session.exec(select(User).where(User.email == payload["sub"])).first()
    if not u: raise HTTPException(401, "User not found")
    return u

@app.get("/health")
def health():
    return {"status":"ok","message":"US11p build"}

# Auth
@app.post("/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.email == req.email)).first():
        raise HTTPException(400, "Email already registered")
    u = User(email=req.email, password_hash=hash_password(req.password))
    session.add(u); session.commit()
    return TokenResponse(access_token=create_token(u.email))

@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, session: Session = Depends(get_session)):
    u = session.exec(select(User).where(User.email == req.email)).first()
    if not u or not verify_password(req.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return TokenResponse(access_token=create_token(u.email))

# Profile
@app.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(get_user), session: Session = Depends(get_session)):
    u = session.get(User, user.id)
    return ProfileOut(
        email=u.email, name=u.name, gender=u.gender, age_years=u.age_years,
        height_cm=u.height_cm, weight_kg=u.weight_kg, activity_level=u.activity_level,
        kcal_goal=u.kcal_goal, created_at=u.created_at
    )

@app.put("/profile", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, user: User = Depends(get_user), session: Session = Depends(get_session)):
    u = session.get(User, user.id)
    for f in ("name","gender","age_years","height_cm","weight_kg","activity_level","kcal_goal"):
        v = getattr(payload, f)
        if v is not None:
            setattr(u, f, v)
    session.add(u); session.commit(); session.refresh(u)
    return ProfileOut(
        email=u.email, name=u.name, gender=u.gender, age_years=u.age_years,
        height_cm=u.height_cm, weight_kg=u.weight_kg, activity_level=u.activity_level,
        kcal_goal=u.kcal_goal, created_at=u.created_at
    )

# Helpers
def _day_bounds_local(d: date, tz_offset_minutes: int) -> tuple[datetime, datetime]:
    local_start = datetime(d.year, d.month, d.day, 0, 0, 0)
    start_utc = (local_start - timedelta(minutes=tz_offset_minutes)).replace(tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)
    return start_utc, end_utc

def _local_day(tz_offset_minutes:int)->str:
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    return (now_utc + timedelta(minutes=tz_offset_minutes)).date().isoformat()

# Items
@app.post("/items", response_model=PredictOut)
async def create_or_predict(file: UploadFile = File(...), calories: Optional[int] = Form(default=None),
                            user: User = Depends(get_user), session: Session = Depends(get_session)):
    content = await file.read()
    try:
        img = Image.open(io.BytesIO(content))
    except Exception:
        raise HTTPException(400, "Invalid image")
    q_hash, q_hist = compute_features(img)

    if calories is not None:
        filename = f"{int(datetime.utcnow().timestamp()*1000)}_upload.jpg"
        fpath = os.path.join(STORAGE_DIR, filename)
        with open(fpath, "wb") as out: out.write(content)
        rec = FoodItem(user_id=user.id, path=fpath, calories=int(calories),
                       phash=q_hash["phash"], ahash=q_hash["ahash"], dhash=q_hash["dhash"],
                       hist_json=json.dumps(q_hist.tolist()))
        session.add(rec); session.commit(); session.refresh(rec)
        return PredictOut(matched=False, saved_item_id=rec.id, hint="Saved with entered calories.")

    items = session.exec(select(FoodItem).where(FoodItem.user_id == user.id).order_by(FoodItem.id.desc()).limit(1000)).all()
    best, best_conf, best_hd = None, 0.0, 999
    for it in items:
        if it.calories is None: continue
        db_hash = {"phash": it.phash, "ahash": it.ahash, "dhash": it.dhash}
        db_hist = np.array(json.loads(it.hist_json), dtype=float)
        ok, conf, hd, cs = match_confidence(q_hash, q_hist, db_hash, db_hist)
        if ok and (conf > best_conf or (conf == best_conf and hd < best_hd)):
            best, best_conf, best_hd = it, conf, hd
    if best is not None:
        return PredictOut(matched=True, predicted_calories=best.calories, confidence=float(round(best_conf,3)), match_item_id=best.id, hint="Matched similar photo")
    return PredictOut(matched=False, hint="No close match yet. Enter calories once.")

@app.get("/items", response_model=List[ItemRow])
def list_items(user: User = Depends(get_user), session: Session = Depends(get_session)):
    rows = session.exec(select(FoodItem).where(FoodItem.user_id == user.id).order_by(FoodItem.created_at.desc())).all()
    return [ItemRow(id=r.id, calories=r.calories, created_at=r.created_at, image_url=f"/static/{os.path.basename(r.path)}") for r in rows]

@app.delete("/items/{item_id}")
def delete_item(item_id: int, user: User = Depends(get_user), session: Session = Depends(get_session)):
    it = session.get(FoodItem, item_id)
    if not it or it.user_id != user.id: raise HTTPException(404, "Not found")
    try:
        if it.path and os.path.exists(it.path): os.remove(it.path)
    except Exception: pass
    session.delete(it); session.commit()
    return {"ok": True}

# Summaries
@app.get("/summary/daily", response_model=DailySummary)
def daily_summary(date_str: Optional[str] = Query(default=None, alias="date"),
                  tz_offset_minutes: int = Query(default=0, ge=-24*60, le=24*60),
                  user: User = Depends(get_user), session: Session = Depends(get_session)):
    d = date.fromisoformat(date_str) if date_str else datetime.utcnow().date()
    s_utc, e_utc = _day_bounds_local(d, tz_offset_minutes)
    rows = session.exec(select(FoodItem).where(FoodItem.user_id==user.id, FoodItem.created_at>=s_utc, FoodItem.created_at<e_utc)).all()
    total = sum(int(r.calories or 0) for r in rows)
    return DailySummary(date=d, total_calories=total, items_count=len(rows))

@app.get("/summary/weekly", response_model=WeeklySummary)
def weekly_summary(end_str: Optional[str] = Query(default=None, alias="end"),
                   tz_offset_minutes: int = Query(default=0, ge=-24*60, le=24*60),
                   user: User = Depends(get_user), session: Session = Depends(get_session)):
    end_d = date.fromisoformat(end_str) if end_str else datetime.utcnow().date()
    start_d = end_d - timedelta(days=6)
    days_list, grand_total = [], 0
    for i in range(7):
        d = start_d + timedelta(days=i)
        s_utc, e_utc = _day_bounds_local(d, tz_offset_minutes)
        rows = session.exec(select(FoodItem).where(FoodItem.user_id==user.id, FoodItem.created_at>=s_utc, FoodItem.created_at<e_utc)).all()
        total = sum(int(r.calories or 0) for r in rows)
        grand_total += total
        days_list.append(DailySummary(date=d, total_calories=total, items_count=len(rows)))
    avg = grand_total / 7.0
    return WeeklySummary(start=start_d, end=end_d, total_calories=grand_total, avg_per_day=avg, days=days_list)

# Mood
MOODS = {"happy":"😄","sad":"😢","angry":"😠","frustrated":"😣","scared":"😱"}

def _local_day_and_slot(now_utc: datetime, tz_offset_minutes: int) -> tuple[str, str]:
    local_dt = now_utc + timedelta(minutes=tz_offset_minutes)
    minute = 0 if local_dt.minute < 30 else 30
    slot = f"{local_dt.hour:02d}:{minute:02d}"
    local_day = local_dt.date().isoformat()
    return local_day, slot

@app.post("/mood/set")
def mood_set(req: MoodSetRequest, user: User = Depends(get_user), session: Session = Depends(get_session)):
    m = req.mood.lower().strip()
    if m not in MOODS: raise HTTPException(400, "Invalid mood")
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    day, slot = _local_day_and_slot(now_utc, req.tz_offset_minutes)
    existing = session.exec(select(MoodLog).where(MoodLog.user_id==user.id, MoodLog.day==day, MoodLog.slot==slot)).first()
    if existing:
        existing.mood = m; existing.created_at = datetime.utcnow()
        session.add(existing); session.commit()
    else:
        session.add(MoodLog(user_id=user.id, day=day, slot=slot, mood=m)); session.commit()
    return {"ok": True, "day": day, "slot": slot, "mood": m, "icon": MOODS[m]}

@app.get("/mood/today", response_model=MoodSummaryOut)
def mood_today(tz_offset_minutes: int = Query(default=0), user: User = Depends(get_user), session: Session = Depends(get_session)):
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    local_day = (now_utc + timedelta(minutes=tz_offset_minutes)).date().isoformat()
    rows = session.exec(select(MoodLog).where(MoodLog.user_id==user.id, MoodLog.day==local_day)).all()
    counts = {k: 0 for k in MOODS.keys()}
    out_logs = []
    for r in rows:
        counts[r.mood] = counts.get(r.mood, 0) + 1
        out_logs.append(MoodLogOut(day=r.day, slot=r.slot, mood=r.mood, created_at=r.created_at))
    total = sum(counts.values())
    return MoodSummaryOut(day=date.fromisoformat(local_day), counts=counts, total=total, logs=out_logs)

# Journal
@app.post("/journal/add", response_model=JournalEntryOut)
def journal_add(req: JournalAddRequest, user: User = Depends(get_user), session: Session = Depends(get_session)):
    day = (datetime.utcnow() + timedelta(minutes=req.tz_offset_minutes)).date().isoformat()
    je = JournalEntry(user_id=user.id, day=day, note=req.note)
    session.add(je); session.commit(); session.refresh(je)
    return JournalEntryOut(id=je.id, day=je.day, note=je.note, created_at=je.created_at)

@app.get("/journal/today", response_model=List[JournalEntryOut])
def journal_today(tz_offset_minutes: int = Query(default=0), user: User = Depends(get_user), session: Session = Depends(get_session)):
    day = (datetime.utcnow() + timedelta(minutes=tz_offset_minutes)).date().isoformat()
    rows = session.exec(select(JournalEntry).where(JournalEntry.user_id==user.id, JournalEntry.day==day).order_by(JournalEntry.created_at.desc())).all()
    return [JournalEntryOut(id=r.id, day=r.day, note=r.note, created_at=r.created_at) for r in rows]

@app.delete("/journal/{entry_id}")
def journal_delete(entry_id: int, user: User = Depends(get_user), session: Session = Depends(get_session)):
    r = session.get(JournalEntry, entry_id)
    if not r or r.user_id != user.id: raise HTTPException(404, "Not found")
    session.delete(r); session.commit()
    return {"ok": True}

# To-Do + Badges
@app.post("/todo", response_model=TodoItemOut)
def todo_create(req: TodoCreateRequest, user: User = Depends(get_user), session: Session = Depends(get_session)):
    it = TodoItem(user_id=user.id, title=req.title, urgent=bool(req.urgent), important=bool(req.important))
    session.add(it); session.commit(); session.refresh(it)
    return TodoItemOut(**it.dict())

@app.get("/todo", response_model=List[TodoItemOut])
def todo_list(user: User = Depends(get_user), session: Session = Depends(get_session)):
    rows = session.exec(select(TodoItem).where(TodoItem.user_id==user.id).order_by(TodoItem.done.asc(), TodoItem.created_at.desc())).all()
    return [TodoItemOut(**r.dict()) for r in rows]

@app.put("/todo/{todo_id}", response_model=TodoItemOut)
def todo_update(todo_id: int, patch: TodoUpdateRequest, user: User = Depends(get_user), session: Session = Depends(get_session)):
    it = session.get(TodoItem, todo_id)
    if not it or it.user_id != user.id: raise HTTPException(404, "Not found")
    old_done = it.done
    if patch.title is not None: it.title = patch.title
    if patch.urgent is not None: it.urgent = bool(patch.urgent)
    if patch.important is not None: it.important = bool(patch.important)
    if patch.done is not None:
        new_done = bool(patch.done)
        if new_done and not old_done:
            it.done = True; it.completed_at = datetime.utcnow()
            session.add(BadgeEarned(user_id=user.id, title=it.title))
        elif not new_done and old_done:
            it.done = False; it.completed_at = None
    session.add(it); session.commit(); session.refresh(it)
    return TodoItemOut(**it.dict())

@app.delete("/todo/{todo_id}")
def todo_delete(todo_id: int, user: User = Depends(get_user), session: Session = Depends(get_session)):
    it = session.get(TodoItem, todo_id)
    if not it or it.user_id != user.id: raise HTTPException(404, "Not found")
    session.delete(it); session.commit()
    return {"ok": True}

@app.get("/badges/today", response_model=List[BadgeOut])
def badges_today(tz_offset_minutes: int = Query(default=0), user: User = Depends(get_user), session: Session = Depends(get_session)):
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    local_day = (now_utc + timedelta(minutes=tz_offset_minutes)).date()
    start_utc = datetime(local_day.year, local_day.month, local_day.day) - timedelta(minutes=tz_offset_minutes)
    start_utc = start_utc.replace(tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)
    rows = session.exec(select(BadgeEarned).where(BadgeEarned.user_id==user.id, BadgeEarned.created_at>=start_utc, BadgeEarned.created_at<end_utc).order_by(BadgeEarned.created_at.asc())).all()
    return [BadgeOut(id=r.id, title=r.title, created_at=r.created_at) for r in rows]

# -------- Activity Recommendations --------
def _compute_bmi(u: User) -> Optional[float]:
    if not u or not u.height_cm or not u.weight_kg or u.height_cm <= 0: return None
    m = float(u.height_cm) / 100.0
    return float(u.weight_kg) / (m*m)

def _bmi_band(bmi: Optional[float]) -> str:
    if bmi is None: return "unknown"
    if bmi < 18.5: return "under"
    if bmi < 25: return "healthy"
    if bmi < 30: return "over"
    return "obese"

BASE_RECO = {
    "under": [
        ("eat_breakfast", "Balanced breakfast (protein + whole grains + fruit)", 10),
        ("snack_combo", "Smart snack: yogurt + nuts/fruit", 10),
        ("walk_20", "Walk 20 minutes", 10),
        ("strength_10", "Bodyweight strength 10 minutes", 10),
        ("hydrate", "Hydrate: 6–8 cups across day", 10),
    ],
    "healthy": [
        ("fruit_veg_5", "5 servings fruits & veggies", 10),
        ("walk_30", "Walk 30 minutes", 10),
        ("strength_15", "Strength exercises 15 minutes", 10),
        ("screen_breaks", "Take screen breaks every hour", 10),
        ("hydrate", "Hydrate: 6–8 cups across day", 10),
    ],
    "over": [
        ("veg_half_plate", "Make half your plate veggies", 10),
        ("walk_30", "Walk 30 minutes (brisk)", 10),
        ("strength_15", "Strength exercises 15 minutes", 10),
        ("limit_sugary", "Swap sugary drinks for water", 10),
        ("screen_breaks", "Take screen breaks every hour", 10),
    ],
    "obese": [
        ("veg_half_plate", "Half plate non-starchy veggies", 10),
        ("walk_40", "Walk 40 minutes (comfortable pace)", 10),
        ("strength_20", "Strength exercises 20 minutes", 10),
        ("swap_snack", "Swap chips/candy for fruit/protein", 10),
        ("screen_breaks", "Take screen breaks every hour", 10),
    ],
    "unknown": [
        ("walk_20", "Walk 20 minutes", 10),
        ("fruit_veg_3", "3 servings fruits & veggies", 10),
        ("hydrate", "Hydrate: 6–8 cups across day", 10),
    ]
}

def _adjust_by_activity(level: str, items: list[tuple]) -> list[tuple]:
    # Simple heuristic: add duration or intensity variants
    if (level or "").lower() == "active":
        adj = []
        for k,t,p in items:
            if "Walk" in t: t = t.replace("Walk", "Walk/Jog")
            if "minutes" in t:
                t = t.replace("20 minutes","25 minutes").replace("30 minutes","35 minutes").replace("40 minutes","45 minutes")
            adj.append((k, t, p))
        return adj
    elif (level or "").lower() == "sedentary":
        adj = []
        for k,t,p in items:
            if "minutes" in t:
                t = t.replace("40 minutes","30 minutes").replace("35 minutes","30 minutes").replace("30 minutes","25 minutes").replace("20 minutes","15 minutes")
            adj.append((k, t, p))
        return adj
    return items

@app.get("/activities/recommend", response_model=List[ActivityReco])
def activities_recommend(tz_offset_minutes: int = Query(default=0), user: User = Depends(get_user), session: Session = Depends(get_session)):
    u = session.get(User, user.id)
    bmi = _compute_bmi(u)
    band = _bmi_band(bmi)
    base = BASE_RECO.get(band, BASE_RECO["unknown"])
    items = _adjust_by_activity(u.activity_level or "moderate", base)
    # Return consistent list
    recos = [ActivityReco(key=k, title=t, points=int(p)) for (k,t,p) in items]
    return recos

@app.get("/activities/status_today", response_model=List[ActivityStatus])
def activities_status_today(tz_offset_minutes: int = Query(default=0), user: User = Depends(get_user), session: Session = Depends(get_session)):
    day = _local_day(tz_offset_minutes)
    rows = session.exec(select(ActivityLog).where(ActivityLog.user_id==user.id, ActivityLog.day==day)).all()
    return [ActivityStatus(key=r.key, title=r.title, points=r.points, completed=bool(r.completed), completed_at=r.completed_at) for r in rows]

@app.post("/activities/complete", response_model=ActivityStatus)
def activities_complete(key: str = Form(...), title: str = Form(...), points: int = Form(10),
                        tz_offset_minutes: int = Form(0), user: User = Depends(get_user), session: Session = Depends(get_session)):
    day = _local_day(tz_offset_minutes)
    row = session.exec(select(ActivityLog).where(ActivityLog.user_id==user.id, ActivityLog.day==day, ActivityLog.key==key)).first()
    now = datetime.utcnow()
    if row:
        row.completed = True; row.completed_at = now
        session.add(row)
    else:
        row = ActivityLog(user_id=user.id, day=day, key=key, title=title, points=int(points), completed=True, completed_at=now)
        session.add(row)
    # Award a badge for each activity completion
    session.add(BadgeEarned(user_id=user.id, title=f"Activity: {title}"))
    session.commit(); session.refresh(row)
    return ActivityStatus(key=row.key, title=row.title, points=row.points, completed=row.completed, completed_at=row.completed_at)