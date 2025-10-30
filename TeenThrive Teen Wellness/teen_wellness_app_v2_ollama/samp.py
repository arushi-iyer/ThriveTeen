# ---- Mood-Enhancing Login Background (auto-fetch from web) ----
import base64, random, httpx, os

# Pick a theme (you can plug in user mood or time-of-day)
THEMES = {
    "happy":   ["sunrise", "wildflowers", "meadow", "sunny sky"],
    "calm":    ["forest mist", "lake reflections", "pastel ocean", "lavender field"],
    "focused": ["minimal gradient", "clean desk", "soft abstract", "geometric pastel"],
    "energized":["mountains", "ocean waves", "golden hour", "sun beams"],
    "tired":   ["soft sunset", "clouds pastel", "evening sky", "moonlight"]
}
theme = random.choice(list(THEMES.keys()))
query = random.choice(THEMES[theme]).replace(" ", ",")

def _fetch_random_image_bytes(q: str) -> bytes | None:
    # Unsplash “no-auth” random endpoint via query; follows redirect to a real JPG
    url = f"https://source.unsplash.com/1600x900/?{q}"
    try:
        r = httpx.get(url, follow_redirects=True, timeout=10.0)
        if r.status_code == 200 and r.headers.get("content-type","").startswith("image/"):
            return r.content
    except Exception:
        pass
    # Fallback: Picsum random
    try:
        r = httpx.get("https://picsum.photos/1600/900", follow_redirects=True, timeout=10.0)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None

img_bytes = _fetch_random_image_bytes(query)
if img_bytes:
    b64 = base64.b64encode(img_bytes).decode("ascii")
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background: linear-gradient(rgba(255,255,255,0.35), rgba(255,255,255,0.35)),
                    url("data:image/jpeg;base64,{b64}") no-repeat center center fixed !important;
        background-size: cover !important;
    }}
    [data-testid="stHeader"], [data-testid="stToolbar"] {{
        background: rgba(255,255,255,0.5) !important;
        backdrop-filter: blur(6px);
    }}
    .login-card {{
        background: rgba(255,255,255,0.85);
        padding: 1.6rem;
        border-radius: 1rem;
        box-shadow: 0 4px 10px rgba(0,0,0,0.12);
    }}
    </style>
    """, unsafe_allow_html=True)
    st.caption(f"✨ Scene: {theme.capitalize()} • Query: {query.replace(',',' ')}")

# ---- Your login UI wrapped in a soft card ----
st.markdown("<div class='login-card'>", unsafe_allow_html=True)
st.markdown("<h2 style='color:#3bb4c1;'>Welcome to Teen Wellness</h2>", unsafe_allow_html=True)
email = st.text_input("Email")
password = st.text_input("Password", type="password")
if st.button("Login"):
    r = request('POST', api + "/login", json={"email": email, "password": password})
    if r.status_code == 200:
        st.success("Login successful! 🌞")
        # ... handle token/session ...
    else:
        st.error("Invalid credentials.")
st.markdown("</div>", unsafe_allow_html=True)

