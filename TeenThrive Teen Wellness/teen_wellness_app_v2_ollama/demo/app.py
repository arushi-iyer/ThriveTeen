import os
import streamlit as st
import httpx
import datetime
import pandas as pd
import datetime as _dt
import ollama
import base64
import random

st.set_page_config(page_title="Teen Calorie Tracker — US11p", layout="wide")
st.markdown("<h1 style='color:#2eb5a3;'>ThriveTeen - Fitness. Focus. Flourish</h1>",
            unsafe_allow_html=True)
st.caption("Educational demo only. Avoid faces in photos. Not medical advice.")

api = st.text_input("API Base URL", "https://127.0.0.1:8030")

VERIFY_TLS = st.toggle("Verify HTTPS certificates (recommended)", value=True)
CERT_PATH = "cert.pem"
verify_param = CERT_PATH if VERIFY_TLS else False


def request(method: str, url: str, **kwargs):
    kwargs.setdefault("timeout", 60.0)
    kwargs.setdefault("verify", verify_param)
    return httpx.request(method, url, **kwargs)


def headers():
    tok = st.session_state.get("token")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _local_tz_offset_minutes() -> int:
    off = _dt.datetime.now().astimezone().utcoffset()
    return int(off.total_seconds() // 60) if off else 0


# ---- Auth ----
st.markdown("<h2 style='color:#fdd365;'>Register / Login</h2>",
            unsafe_allow_html=True)
email = st.text_input("Email", "teen@example.com")
password = st.text_input("Password", "demo123", type="password")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Register"):
        r = request('POST', api + "/auth/register",
                    json={"email": email, "password": password})
        if r.status_code == 200:
            st.session_state["token"] = r.json()["access_token"]
            st.success("Registered & logged in")
            st.rerun()
        else:
            st.error(r.text)
with c2:
    if st.button("Login"):
        r = request('POST', api + "/auth/login",
                    json={"email": email, "password": password})
        if r.status_code == 200:
            st.session_state["token"] = r.json()["access_token"]
            st.success("Logged in")
            st.rerun()
        else:
            st.error(r.text)
with c3:
    if st.button("Logout"):
        st.session_state.pop("token", None)
        st.success("Logged out")
        st.rerun()

if "token" not in st.session_state:
    st.stop()
st.markdown("</div>", unsafe_allow_html=True)


# ---- Profile & BMI ----
show_profile = st.toggle("Toggle to enter/change your profile", value=False)
if show_profile:
    st.divider()
    st.markdown("<h2 style='color:#9b8cff;'>Profile & BMI</h2>",
                unsafe_allow_html=True)

    rp = request('GET', api + "/profile", headers=headers())
    profile = rp.json() if rp.status_code == 200 else {}

    def to_us_from_metric(cm: float | None, kg: float | None):
        cm = cm or 0.0
        kg = kg or 0.0
        inches_total = cm / 2.54
        feet = int(inches_total // 12)
        inches = inches_total - feet*12
        pounds = kg / 0.45359237
        return feet, inches, pounds

    def to_metric_from_us(feet: int, inches: float, pounds: float):
        total_inches = feet*12.0 + inches
        return total_inches*2.54, pounds*0.45359237

    def compute_bmi(cm: float | None, kg: float | None):
        if not cm or not kg or cm <= 0:
            return None
        m = cm / 100.0
        return kg / (m*m)

    def bmi_bar_html(bmi: float | None):
        if bmi is None:
            return "<small>Enter height & weight to see BMI.</small>"
        segments = [
            ("#6EC3FF", 16.5, "Very Low"),
            ("#A6E3A1", 18.5, "Low"),
            ("#4CC38A", 25.0, "Healthy-ish"),
            ("#F8D172", 30.0, "High"),
            ("#F77B72", 40.0, "Very High"),
        ]
        max_bmi = 40.0
        pct = min(max(bmi / max_bmi, 0), 1) * 100
        parts = []
        prev = 0.0
        for color, cutoff, label in segments:
            width = (min(max_bmi, cutoff) - prev) / max_bmi * 100
            parts.append(
                f"<div style='background:{color}; width:{width:.1f}%; height:10px; display:inline-block'></div>")
            prev = cutoff
        if prev < max_bmi:
            parts.append(
                f"<div style='background:#F77B72; width:{(max_bmi-prev)/max_bmi*100:.1f}%; height:10px; display:inline-block'></div>")
        marker_left = pct
        return f"""
      <div style='position:relative; width:100%;'>
        <div style='width:100%;'>{''.join(parts)}</div>
        <div style='position:absolute; left:{marker_left:.1f}%; top:-2px; transform:translateX(-50%);'>
        <div style='width:0; height:0; border-left:6px solid transparent; border-right:6px solid transparent; border-top:10px solid #000;'></div>
        </div>
      </div>
      <small>BMI: <b>{bmi:.1f}</b> (illustrative bands — not medical advice)</small>
      """

    name = st.text_input("Name", value=profile.get("name") or "Me")
    gender = st.selectbox("Gender", ["female", "male"], index=(
        0 if (profile.get("gender") or "female") == "female" else 1))
    age = st.number_input("Age (years)", min_value=5, max_value=18, value=int(
        profile.get("age_years") or 13))

    ft, inch, lb = to_us_from_metric(
        profile.get("height_cm"), profile.get("weight_kg"))
    colh1, colh2, colw = st.columns([1, 1, 1])
    with colh1:
        feet = st.number_input("Height — feet", min_value=1,
                               max_value=7, value=int(ft or 5), step=1)
    with colh2:
        inches = st.number_input("Height — inches", min_value=0.0, max_value=11.99, value=float(
            inch or 3.0), step=0.5, format="%.1f")
    with colw:
        pounds = st.number_input("Weight — pounds", min_value=40.0,
                                 max_value=400.0, value=float(lb or 110.0), step=0.5)

    activity_level = st.selectbox("Activity level", ["sedentary", "moderate", "active"], index=[
                                  "sedentary", "moderate", "active"].index(profile.get("activity_level") or "moderate"))
    goal_default = int(profile.get("kcal_goal") or 2000)
    goal = st.number_input("Daily kcal goal", min_value=800,
                           max_value=4500, value=goal_default, step=50)

    if st.button("Save profile"):
        cm, kg = to_metric_from_us(int(feet), float(inches), float(pounds))
        r = request('PUT', api + "/profile", json={
            "name": name, "gender": gender, "age_years": int(age),
            "height_cm": float(cm), "weight_kg": float(kg),
            "activity_level": activity_level, "kcal_goal": int(goal),
        }, headers=headers())
        if r.status_code == 200:
            st.success("Profile saved")
            st.rerun()
        else:
            st.error(r.text)

# ---- Display BMI bar and daily and weekly calorie counts ----
    cm, kg = to_metric_from_us(int(feet), float(inches), float(pounds))
    bmi = compute_bmi(cm, kg)
    st.markdown(bmi_bar_html(bmi), unsafe_allow_html=True)


# ---- Mood (Counts) ----
# st.header("Mood (every 30 minutes)")
st.divider()
st.markdown("<h2 style='color:#3478e5;'>Your Mood </h2>",
            unsafe_allow_html=True)

# Gray #666

offset = _local_tz_offset_minutes()

ms = request('GET', api + "/mood/today",
             params={"tz_offset_minutes": offset}, headers=headers())
if ms.status_code == 200:
    data = ms.json()
    counts = data.get("counts", {}) or {}
    order = ["happy", "frustrated", "sad", "scared", "angry"]
    icons = {"happy": "😄", "frustrated": "😣",
             "sad": "😢", "scared": "😱", "angry": "😠"}

    st.caption("Today's mood taps (one every half hour):")
    cols = st.columns(len(order))
    for i, k in enumerate(order):
        with cols[i]:
            st.markdown(
                f"<div style='text-align:center; font-size:26px'>{icons[k]}</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div style='text-align:center; font-size:14px'>{k.capitalize()}</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div style='text-align:center; font-size:13px'>x {counts.get(k, 0)}</div>", unsafe_allow_html=True)
    if int(data.get("total", 0) or 0) == 0:
        st.caption("No mood taps yet today.")
else:
    st.warning("Mood summary unavailable.")

st.write("How are you feeling right now? Pick one:")
MOODS = {"happy": "😄", "frustrated": "😣",
         "sad": "😢", "scared": "😱", "angry": "😠"}
cols = st.columns(5)
for i, k in enumerate(MOODS.keys()):
    with cols[i]:
        if st.button(f"{MOODS[k]} {k.capitalize()}", key=f"mood_{k}"):
            r = request('POST', api + "/mood/set",
                        json={"mood": k, "tz_offset_minutes": offset}, headers=headers())
            if r.status_code == 200:
                st.success("Mood recorded for this 30-min slot.")
                st.rerun()
            else:
                st.error(r.text)


# ---- To-Do List Section ----
st.divider()
st.markdown("<h2 style='color:#5aa9e6;'>To-Do List</h2>",
            unsafe_allow_html=True)

# Define colors for task labels
LABEL_COLORS = {
    "Important": "#4CAF50",        # Green
    "Urgent": "#f44336",           # Red
    "Urgent AND Important": "#ff9800"  # Orange
}

# Gray #666

# Today's badges inline as well (already above, but okay to show again or skip)
# We'll skip duplicate row here.

todo_new = st.text_input("Add a task - mark it urgent/important?", "")
colU, colI, colBtn = st.columns([1, 1, 1])
with colU:
    set_u = st.checkbox("Urgent", value=False, key="todo_u")
with colI:
    set_i = st.checkbox("Important", value=False, key="todo_i")
with colBtn:
    if st.button("Add"):
        if todo_new.strip():
            r = request('POST', api + "/todo", json={"title": todo_new.strip(
            ), "urgent": set_u, "important": set_i}, headers=headers())
            if r.status_code == 200:
                st.success("Task added")
                st.rerun()
            else:
                st.error(r.text)
        else:
            st.info("Enter a task title.")

lr = request('GET', api + "/todo", headers=headers())
if lr.status_code == 200:
    tasks = lr.json()

    def group(tasks, urgent=None, important=None):
        out = []
        for t in tasks:
            if urgent is not None and bool(t["urgent"]) != urgent:
                continue
            if important is not None and bool(t["important"]) != important:
                continue
            out.append(t)
        return [t for t in out if not t["done"]] + [t for t in out if t["done"]]

    cats = [
        ("Urgent AND Important", group(tasks, urgent=True, important=True)),
        ("Urgent", group(tasks, urgent=True, important=False)),
        ("Important", group(tasks, urgent=False, important=True)),
        ("Others", group(tasks, urgent=False, important=False)),
    ]
    for title, items in cats:
        if not items:
            st.caption("_None_")
        for t in items:

            label = title
            color = LABEL_COLORS.get(title)

            box = st.container(border=True)
            c1, c2, c3 = box.columns([6, 2, 1])
            with c1:
                label_html = (
                    f"<span style='background:{color}; color:white; "
                    f"padding:3px 8px; border-radius:8px; font-size:0.85rem;'>{label}</span>"
                    if color else
                    f"<span style='background:#ddd; color:#333; "
                    f"padding:3px 8px; border-radius:8px; font-size:0.85rem;'>{label}</span>"
                )

                st.markdown(
                    f"<div style='margin-bottom:8px;'>"
                    f"<strong>{t['title']}</strong> — {label_html}"
                    f"</div>",
                    unsafe_allow_html=True
                )

                if t["done"]:
                    st.success("Completed")
            with c2:
                checked = st.checkbox(
                    "Done", value=t["done"], key=f"done_{t['id']}")
                if checked != t["done"]:
                    request(
                        'PUT', api + f"/todo/{t['id']}", json={"done": bool(checked)}, headers=headers())
                    st.rerun()
            with c3:
                if st.button("Delete", key=f"del_t_{t['id']}"):
                    dr = request('DELETE', api +
                                 f"/todo/{t['id']}", headers=headers())
                    if dr.status_code == 200:
                        st.success("Deleted")
                        st.rerun()
                    else:
                        st.error(dr.text)
else:
    st.error(lr.text)


# ---- Activity Recommendations (with badges on complete) ----
st.divider()
st.markdown("<h2 style='color:#e85b81;'>Recommended Activities (based on your BMI & activity level)</h2>",
            unsafe_allow_html=True)
# Pink #e85b81

rec = request('GET', api + "/activities/recommend",
              params={"tz_offset_minutes": offset}, headers=headers())
status = request('GET', api + "/activities/status_today",
                 params={"tz_offset_minutes": offset}, headers=headers())

done_keys = set()
if status.status_code == 200:
    for rstat in status.json():
        if rstat["completed"]:
            done_keys.add(rstat["key"])

if rec.status_code == 200:
    for a in rec.json():
        box = st.container(border=True)
        c1, c2 = box.columns([6, 2])
        with c1:
            st.write(f"**{a['title']}** — {a['points']} pts")
            if a["key"] in done_keys:
                st.success("Completed")
        with c2:
            if a["key"] not in done_keys:
                if st.button("Mark complete 🏅", key=f"comp_{a['key']}"):
                    r = request('POST', api + "/activities/complete", data={
                        "key": a["key"], "title": a["title"], "points": a["points"], "tz_offset_minutes": offset
                    }, headers=headers())
                    if r.status_code == 200:
                        st.success("Activity completed! Badge awarded.")
                        st.rerun()
                    else:
                        st.error(r.text)
else:
    st.warning("Recommendations unavailable.")

# ---- Badges row (today) ----
br = request('GET', api + "/badges/today",
             params={"tz_offset_minutes": offset}, headers=headers())
if br.status_code == 200:
    badges = br.json()
    if badges:
        st.caption("Today's badges:")
        cols = st.columns(min(len(badges), 8))
        icon = "🏅"
        for i, b in enumerate(badges):
            with cols[i % len(cols)]:
                st.markdown(
                    f"<div style='font-size:30px'>{icon}</div><div style='font-size:12px'>{b['title']}</div>", unsafe_allow_html=True)


# Totals
st.divider()
# Yellow #d4a017
st.markdown("<h2 style='color:#d4a017;'>Current Calorie Counts</h2>",
            unsafe_allow_html=True)
today = datetime.date.today().isoformat()
offset = _local_tz_offset_minutes()

dd = request('GET', api + "/summary/daily",
             params={"date": today, "tz_offset_minutes": offset}, headers=headers()).json()
ww = request('GET', api + "/summary/weekly",
             params={"end": today, "tz_offset_minutes": offset}, headers=headers()).json()
m1, m2 = st.columns(2)
m1.metric("Today", dd["total_calories"])
m2.metric("This week", ww["total_calories"])


# ---- Capture / Upload Food pictures ----
st.divider()
st.markdown("<h2 style='color:#ffa552;'>Capture Food & Calories</h2>",
            unsafe_allow_html=True)
# Apricot #ffa552

if "cam_open" not in st.session_state:
    st.session_state["cam_open"] = False
if "cam_bytes" not in st.session_state:
    st.session_state["cam_bytes"] = None
if "cam_pred" not in st.session_state:
    st.session_state["cam_pred"] = None

c1, c2 = st.columns(2)
with c1:
    if st.button("Open Camera", disabled=st.session_state["cam_open"]):
        st.session_state["cam_open"] = True
        st.session_state["cam_bytes"] = None
        st.session_state["cam_pred"] = None
        st.rerun()
with c2:
    if st.button("Close Camera", disabled=not st.session_state["cam_open"]):
        st.session_state["cam_open"] = False
        st.session_state["cam_bytes"] = None
        st.session_state["cam_pred"] = None
        st.rerun()


def predict_only(file_bytes: bytes):
    files = {"file": ("img.jpg", file_bytes, "image/jpeg")}
    data = {}
    return request('POST', api + "/items", files=files, data=data, headers=headers())


def save_with_calories(file_bytes: bytes, kcals: int):
    files = {"file": ("img.jpg", file_bytes, "image/jpeg")}
    data = {"calories": str(int(kcals))}
    return request('POST', api + "/items", files=files, data=data, headers=headers())


if st.session_state["cam_open"] and st.session_state["cam_bytes"] is None:
    photo = st.camera_input("Camera is open — take one photo")
    if photo is not None:
        st.session_state["cam_open"] = False
        st.session_state["cam_bytes"] = photo.getvalue()
        r = predict_only(st.session_state["cam_bytes"])
        if r.status_code == 200:
            st.session_state["cam_pred"] = r.json()
            st.rerun()
        else:
            st.error(r.text)

if st.session_state["cam_bytes"] is not None:
    st.image(st.session_state["cam_bytes"],
             caption="Captured photo", width=300)
    pred = st.session_state["cam_pred"]
    if pred and pred["matched"]:
        st.success(
            f"Prediction: {pred['predicted_calories']} kcal (conf {pred['confidence']:.2f})")
        s1, s2 = st.columns(2)
        with s1:
            if st.button("Save with predicted calories"):
                r2 = save_with_calories(
                    st.session_state["cam_bytes"], int(pred["predicted_calories"]))
                if r2.status_code == 200:
                    st.success("Saved")
                    st.session_state["cam_bytes"] = None
                    st.session_state["cam_pred"] = None
                    st.rerun()
                else:
                    st.error(r2.text)
        with s2:
            kcal = st.number_input("Or enter calories", min_value=0, step=10, value=int(
                pred["predicted_calories"] or 0), key="override_cam")
            if st.button("Save with entered calories"):
                r3 = save_with_calories(
                    st.session_state["cam_bytes"], int(kcal))
                if r3.status_code == 200:
                    st.success("Saved")
                    st.session_state["cam_bytes"] = None
                    st.session_state["cam_pred"] = None
                    st.rerun()
                else:
                    st.error(r3.text)
    else:
        st.info("No close match. Please enter calories to save.")
        kcal2 = st.number_input("Calories", min_value=0,
                                step=10, value=0, key="manual_cam")
        if st.button("Save new food with calories"):
            r4 = save_with_calories(st.session_state["cam_bytes"], int(kcal2))
            if r4.status_code == 200:
                st.success("Saved")
                st.session_state["cam_bytes"] = None
                st.session_state["cam_pred"] = None
                st.rerun()
            else:
                st.error(r4.text)


# ---- Food History ----
st.markdown("<h2 style='color:#ffa552;'>Food History</h2>",
            unsafe_allow_html=True)
r = request('GET', api + "/items", headers=headers())
if r.status_code == 200:
    rows = r.json()
    if not rows:
        st.info("No items yet.")
    else:
        for it in rows:
            cont = st.container(border=True)
            c1, c2, c3 = cont.columns([2, 4, 1])
            with c1:
                try:
                    img_resp = request('GET', api + it["image_url"])
                    if img_resp.status_code == 200:
                        st.image(img_resp.content, width=160,
                                 caption=f"ID {it['id']}")
                    else:
                        st.warning(
                            f"Image fetch failed ({img_resp.status_code})")
                        st.code(api + it["image_url"])
                except Exception as e:
                    st.warning(f"Image not available: {e}")
                    st.code(api + it["image_url"])
            with c2:
                st.markdown(
                    f"**Calories:** {it['calories'] if it['calories'] is not None else '—'}")
                st.caption(f"At: {it['created_at']}")
                st.code(it["image_url"])
            with c3:
                if st.button(f"Delete {it['id']}", key=f"del_{it['id']}"):
                    dr = request('DELETE', api +
                                 f"/items/{it['id']}", headers=headers())
                    if dr.status_code == 200:
                        st.success("Deleted")
                        st.rerun()
                    else:
                        st.error(dr.text)
else:
    st.error(r.text)

# ---- Hydration Tracker (session-based MVP) ----
st.divider()
st.markdown("<h2 style='color:#1aaf5d;'>Hydration Tracker</h2>",
            unsafe_allow_html=True)
# Green #1aaf5d

colh1, colh2, colh3 = st.columns([2, 1, 1])
with colh1:
    daily_goal = st.number_input(
        "Daily water goal (cups)", min_value=1, max_value=32, value=6, step=1)
with colh2:
    if "water_count" not in st.session_state:
        st.session_state.water_count = 0
    st.metric("Cups consumed", st.session_state.water_count)
with colh3:
    if st.button("+1 cup"):
        st.session_state.water_count += 1
    if st.button("-1 cup"):
        st.session_state.water_count = max(0, st.session_state.water_count - 1)

progress = min(1.0, st.session_state.water_count / max(1, daily_goal))
st.progress(
    progress, text=f"{st.session_state.water_count}/{int(daily_goal)} cups")

# Award a badge via Activities API when goal reached (one-time per day)
if progress >= 1.0 and st.session_state.get("hydration_badge_awarded") != True:
    try:
        tz_offset = int(
            round((_dt.datetime.now() - _dt.datetime.utcnow()).total_seconds() / 60.0))
    except Exception:
        tz_offset = 0
    resp = request('POST', api + "/activities/complete",
                   headers=headers(),
                   files={"key": (None, "hydration_goal"),
                          "title": (None, "Hydration Goal Met"),
                          "points": (None, "10"),
                          "tz_offset_minutes": (None, str(tz_offset))})
    if resp.status_code == 200:
        st.session_state["hydration_badge_awarded"] = True
        st.success("Hydration goal met! Badge awarded.")
    else:
        st.info("Hydration goal met! (Badge attempt failed)")

# ---- Gratitude Journal ----
st.divider()
st.markdown("<h2 style='color:#ff9aa2;'>Gratitude Journal</h2>",
            unsafe_allow_html=True)
# Coral


def _tz_off():
    off = _dt.datetime.now().astimezone().utcoffset()
    return int(off.total_seconds() // 60) if off else 0


tzm = _tz_off()
gj_col1, gj_col2 = st.columns([3, 2])
with gj_col1:
    note = st.text_area("Something you're grateful for today",
                        placeholder="A person, a moment, something you noticed…")
    if st.button("Add to journal", key="gj_add_bottom"):
        if note.strip():
            r = request('POST', api + "/journal/add",
                        json={"note": note.strip(), "tz_offset_minutes": tzm}, headers=headers())
            if r.status_code == 200:
                st.success("Added to today’s journal.")
                st.rerun()
            else:
                st.error(r.text)
        else:
            st.info("Write a short note first.")
with gj_col2:
    jr = request('GET', api + "/journal/today",
                 params={"tz_offset_minutes": tzm}, headers=headers())
    if jr.status_code == 200:
        entries = jr.json()
        if not entries:
            st.caption("_No entries yet today._")
        else:
            st.caption("Today’s entries:")
            for e in entries:
                c = st.container(border=True)
                c.write(e["note"])
                c.caption(f"At: {e['created_at']}")
                if c.button("Delete", key=f"del_j_bottom_{e['id']}"):
                    dr = request('DELETE', api +
                                 f"/journal/{e['id']}", headers=headers())
                    if dr.status_code == 200:
                        st.success("Deleted")
                        st.rerun()
                    else:
                        st.error(dr.text)
    else:
        st.error(jr.text)


# ---- Mini Chat bot (Ollama - local & free) ----
st.divider()
show_chat = st.toggle("Toggle for your personalized coach", value=False)
st.markdown("<h2 style='color:#d4a017;'>Ask your personalized health coach about diet, fitness, or motivation</h2>", unsafe_allow_html=True)
# Yellow #d4a017

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
if show_chat:
    if prompt := st.chat_input("Ask local LLM..."):
        # Add user message to history and display
        if 'bmi' in globals():
            final_prompt = "Given that my BMI is " + \
                str(round(bmi, 1)) + ", " + prompt
        else:
            final_prompt = prompt

        final_prompt = 'In short 3 point answers, ' + final_prompt

        st.session_state.messages.append(
            {"role": "user", "content": final_prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        prompt = final_prompt
        print(prompt)

        # Get response from Llama 3 using Ollama
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response_stream = ollama.chat(
                    model="mistral:latest",
                    messages=[
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages
                    ],
                    stream=True,
                )
                full_response = ""
                placeholder = st.empty()
                for chunk in response_stream:
                    full_response += chunk["message"]["content"]
                    # Add blinking cursor effect
                    placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)

            # Add assistant response to history
            st.session_state.messages.append(
                {"role": "assistant", "content": full_response})
