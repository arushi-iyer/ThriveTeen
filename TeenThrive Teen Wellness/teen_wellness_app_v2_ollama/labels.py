# ---- To-Do List Section ----
st.markdown(
    "<div class='section-box' style='border:2px solid #5aa9e6; background:#eaf5ff;'>",
    unsafe_allow_html=True
)
st.markdown("<h2 style='color:#5aa9e6;'>To-Do List</h2>", unsafe_allow_html=True)

# Define colors for task labels
LABEL_COLORS = {
    "Important": "#4CAF50",        # Green
    "Urgent": "#f44336",           # Red
    "Important & Urgent": "#ff9800" # Orange
}

# Example list of tasks (you can replace with your own dynamic list)
tasks = [
    {"title": "Finish biology notes", "label": "Important"},
    {"title": "Submit project report", "label": "Urgent"},
    {"title": "Prepare for tomorrow’s test", "label": "Important & Urgent"},
    {"title": "Read 10 pages", "label": "Optional"}
]

st.markdown("<hr>", unsafe_allow_html=True)

# Render each task with color-coded priority
for t in tasks:
    label = t.get("label", "")
    color = LABEL_COLORS.get(label)  # Check if the label has a color
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

st.markdown("</div>", unsafe_allow_html=True)

