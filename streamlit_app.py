# streamlit_app.py
# ---------------------------------------------------------
# Interview-grade Streamlit UI for the assignment:
# - Uses your precomputed CSV: match_recommendations_top10_per_user.csv
# - Lets you select a User ID
# - Shows Top-K recommendations
# - Adds filters + sorting
# - Shows explainability (component contributions)
# - Generates "Why this matched" 1-line explanation per property
# - Allows CSV download per user
#
# Run:
#   pip install streamlit pandas numpy
#   streamlit run streamlit_app.py
# ---------------------------------------------------------

import os
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Property Match Recommender (Assignment Demo)",
    page_icon="🏠",
    layout="wide",
)

# -----------------------------
# Config
# -----------------------------
DEFAULT_CSV = "match_recommendations_top10_per_user.csv"

# Weights used in scoring (must match your notebook)
W = {"price": 0.30, "bed": 0.18, "bath": 0.10, "type": 0.12, "cond": 0.08, "year": 0.07, "size": 0.07, "loc": 0.08}

COMP_COLS = ["s_price", "s_bed", "s_bath", "s_type", "s_cond", "s_year", "s_size", "s_loc"]
META_COLS = ["User ID", "Property ID", "Location", "Type", "Condition", "Bedrooms", "Bathrooms", "Size", "Year Built", "Price", "MatchScore", "g_budget"]

# -----------------------------
# Helpers
# -----------------------------
def safe_float(x, default=np.nan):
    try:
        return float(x)
    except Exception:
        return default

def format_money(x):
    x = safe_float(x, np.nan)
    if np.isnan(x):
        return "—"
    return f"{int(round(x)):,}"

def clamp01(x):
    x = safe_float(x, 0.0)
    return float(np.clip(x, 0.0, 1.0))

def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Make sure required columns exist; if missing, create safe defaults."""
    df = df.copy()

    # Required numeric cols
    for c in ["MatchScore", "Price", "Size", "Bedrooms", "Bathrooms", "Year Built", "g_budget"]:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Component scores (0-1), create neutral defaults if missing
    for c in COMP_COLS:
        if c not in df.columns:
            df[c] = 0.5
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.5).clip(0, 1)

    # Required categoricals
    for c in ["User ID", "Property ID", "Location", "Type", "Condition"]:
        if c not in df.columns:
            df[c] = "Unknown"
        df[c] = df[c].astype(str)

    # Coerce ids to int-like strings where possible
    def to_intish(s):
        try:
            return str(int(float(s)))
        except Exception:
            return str(s)

    df["User ID"] = df["User ID"].apply(to_intish)
    df["Property ID"] = df["Property ID"].apply(to_intish)

    return df

@st.cache_data(show_spinner=False)
def load_csv_from_path(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return ensure_columns(df)

@st.cache_data(show_spinner=False)
def load_csv_from_upload(uploaded_file) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    return ensure_columns(df)

def compute_weighted_contributions(row: pd.Series) -> pd.DataFrame:
    parts = {
        "price": W["price"] * clamp01(row.get("s_price", 0.5)),
        "bed":   W["bed"]   * clamp01(row.get("s_bed", 0.5)),
        "bath":  W["bath"]  * clamp01(row.get("s_bath", 0.5)),
        "type":  W["type"]  * clamp01(row.get("s_type", 0.5)),
        "cond":  W["cond"]  * clamp01(row.get("s_cond", 0.5)),
        "year":  W["year"]  * clamp01(row.get("s_year", 0.5)),
        "size":  W["size"]  * clamp01(row.get("s_size", 0.5)),
        "loc":   W["loc"]   * clamp01(row.get("s_loc", 0.5)),
    }
    out = pd.DataFrame({"component": list(parts.keys()), "weighted_contribution": list(parts.values())})
    out = out.sort_values("weighted_contribution", ascending=False).reset_index(drop=True)
    return out

def generate_reason(row: pd.Series) -> str:
    """
    Creates a concise, interview-friendly explanation using sub-scores.
    """
    bullets = []

    # Budget gate
    g = safe_float(row.get("g_budget", np.nan), np.nan)
    if not np.isnan(g):
        if g >= 0.98:
            bullets.append("within budget")
        elif g >= 0.85:
            bullets.append("slightly above budget (small penalty)")
        else:
            bullets.append("over budget (strong penalty)")

    # Strong components (>=0.80)
    strong = []
    mapping = {
        "s_price": "price fit",
        "s_bed": "bedroom match",
        "s_bath": "bathroom match",
        "s_type": "property type match",
        "s_cond": "condition match",
        "s_year": "modernity/year match",
        "s_size": "size/spaciousness match",
        "s_loc": "location intent match",
    }
    for k, label in mapping.items():
        v = clamp01(row.get(k, 0.5))
        if v >= 0.80:
            strong.append(label)

    if strong:
        bullets.append("strong on: " + ", ".join(strong[:3]))

    # Weak components (<=0.35) – add only if needed
    weak = []
    for k, label in mapping.items():
        v = clamp01(row.get(k, 0.5))
        if v <= 0.35:
            weak.append(label)
    if weak and len(bullets) < 2:
        bullets.append("trade-offs: " + ", ".join(weak[:2]))

    if not bullets:
        return "Balanced match across constraints and preferences."
    return " • ".join(bullets).capitalize() + "."

def apply_filters(df: pd.DataFrame,
                  loc_filter, type_filter, cond_filter,
                  price_range, size_range,
                  min_score, min_budget_gate) -> pd.DataFrame:

    out = df.copy()

    if loc_filter:
        out = out[out["Location"].isin(loc_filter)]
    if type_filter:
        out = out[out["Type"].isin(type_filter)]
    if cond_filter:
        out = out[out["Condition"].isin(cond_filter)]

    if price_range is not None:
        out = out[(out["Price"] >= price_range[0]) & (out["Price"] <= price_range[1])]
    if size_range is not None:
        out = out[(out["Size"] >= size_range[0]) & (out["Size"] <= size_range[1])]

    out = out[out["MatchScore"] >= min_score]
    out = out[out["g_budget"] >= min_budget_gate]

    return out

def style_recs(df: pd.DataFrame):
    return (
        df.style.format(
            {
                "MatchScore": "{:.2f}",
                "Price": "{:,.0f}",
                "Size": "{:,.0f}",
                "Bedrooms": "{:.0f}",
                "Bathrooms": "{:.0f}",
                "Year Built": "{:.0f}",
                "g_budget": "{:.2f}",
            }
        )
    )
# -----------------------------
# UI
# -----------------------------
st.title("🏠 Property Match Recommender")
st.caption("Assignment demo: reads precomputed recommendations CSV and provides a clean interface with explainability.")

with st.sidebar:
    st.header("1) Load your CSV")

    uploaded = st.file_uploader("Upload CSV (recommended)", type=["csv"])
    st.caption("If you upload, the app ignores the path below.")

    csv_path = st.text_input("Or CSV path (if already on disk)", DEFAULT_CSV)
    st.caption("Example: match_recommendations_top10_per_user.csv")

    st.divider()
    st.header("2) Display settings")
    top_k = st.slider("Top-K to show", 5, 50, 10, 1)

    st.divider()
    st.header("3) Filters (optional)")
    min_score = st.slider("Min MatchScore", 0.0, 100.0, 0.0, 1.0)
    min_budget_gate = st.slider("Min budget gate (g_budget)", 0.0, 1.0, 0.0, 0.05)

# Load CSV
if uploaded is not None:
    recs_all = load_csv_from_upload(uploaded)
    source_label = "uploaded file"
else:
    if not os.path.exists(csv_path):
        st.error(
            f"CSV not found at: {csv_path}\n\n"
            f"Fix: put `{DEFAULT_CSV}` in the same folder as this app OR upload the file from the sidebar."
        )
        st.stop()
    recs_all = load_csv_from_path(csv_path)
    source_label = csv_path

# Build user list
user_ids = sorted(recs_all["User ID"].unique().tolist())
if not user_ids:
    st.error("No User IDs found in the CSV. Check your file content.")
    st.stop()

# Choose user
cA, cB = st.columns([2, 1], gap="large")
with cA:
    selected_user_id = st.selectbox("Select User ID", user_ids, index=0)
with cB:
    st.metric("Data source", source_label)

# Filter to user
user_df = recs_all[recs_all["User ID"] == selected_user_id].copy()
user_df = user_df.sort_values("MatchScore", ascending=False).reset_index(drop=True)

# Filters depend on user's subset
loc_options = sorted(user_df["Location"].unique().tolist())
type_options = sorted(user_df["Type"].unique().tolist())
cond_options = sorted(user_df["Condition"].unique().tolist())

price_min, price_max = float(user_df["Price"].min()), float(user_df["Price"].max())
size_min, size_max = float(user_df["Size"].min()), float(user_df["Size"].max())

with st.sidebar:
    # Multi-select filters
    loc_filter = st.multiselect("Location", loc_options, default=[])
    type_filter = st.multiselect("Type", type_options, default=[])
    cond_filter = st.multiselect("Condition", cond_options, default=[])

    price_range = st.slider("Price range", min_value=int(price_min), max_value=int(price_max),
                            value=(int(price_min), int(price_max)), step=max(1, int((price_max - price_min) / 100) or 1))
    size_range = st.slider("Size range (sqft)", min_value=int(size_min), max_value=int(size_max),
                           value=(int(size_min), int(size_max)), step=max(1, int((size_max - size_min) / 100) or 1))

# Apply filters
filtered = apply_filters(
    user_df,
    loc_filter=loc_filter,
    type_filter=type_filter,
    cond_filter=cond_filter,
    price_range=price_range,
    size_range=size_range,
    min_score=min_score,
    min_budget_gate=min_budget_gate
)

# Sorting
sort_col_map = {
    "MatchScore (desc)": ("MatchScore", False),
    "Price (asc)": ("Price", True),
    "Price (desc)": ("Price", False),
    "Size (desc)": ("Size", False),
    "Year Built (desc)": ("Year Built", False),
    "Budget gate (desc)": ("g_budget", False),
}
c1, c2, c3 = st.columns([2, 2, 1], gap="large")
with c1:
    sort_choice = st.selectbox("Sort by", list(sort_col_map.keys()), index=0)
with c2:
    search_pid = st.text_input("Search Property ID (optional)", "")
with c3:
    show_components = st.toggle("Show component columns", value=False)

sort_col, ascending = sort_col_map[sort_choice]
filtered = filtered.sort_values(sort_col, ascending=ascending).reset_index(drop=True)

# Search by Property ID
if search_pid.strip():
    filtered = filtered[filtered["Property ID"].astype(str).str.contains(search_pid.strip())].reset_index(drop=True)

# Take top-k
display_df = filtered.head(top_k).copy()

# Add "Why this matched"
display_df["Why this matched"] = display_df.apply(generate_reason, axis=1)

# Show summary metrics
m1, m2, m3, m4 = st.columns(4, gap="large")
m1.metric("Total rows (this user)", f"{len(user_df):,}")
m2.metric("After filters", f"{len(filtered):,}")
m3.metric("Top score", f"{user_df['MatchScore'].max():.2f}")
m4.metric("Avg score (filtered)", f"{filtered['MatchScore'].mean():.2f}" if len(filtered) else "—")

st.divider()
st.subheader(f"🏆 Recommendations for User {selected_user_id}")

base_cols = ["MatchScore", "Property ID", "Location", "Type", "Condition", "Bedrooms", "Bathrooms", "Size", "Year Built", "Price", "g_budget", "Why this matched"]
cols_to_show = base_cols + (COMP_COLS if show_components else [])

st.dataframe(
    style_recs(display_df[cols_to_show]),
    use_container_width=True,
    hide_index=True
)

# Download per user
st.download_button(
    "Download shown table (CSV)",
    data=display_df[cols_to_show].to_csv(index=False).encode("utf-8"),
    file_name=f"user_{selected_user_id}_top_{top_k}.csv",
    mime="text/csv"
)

st.divider()
st.subheader("🔎 Explainability (pick one property)")

if len(display_df) == 0:
    st.info("No rows to explain after filters. Relax filters from the sidebar.")
    st.stop()

chosen_pid = st.selectbox("Choose Property ID", display_df["Property ID"].tolist(), index=0)
row = user_df[user_df["Property ID"] == str(chosen_pid)].iloc[0]

left, right = st.columns([2, 3], gap="large")
with left:
    st.metric("Final MatchScore", f"{safe_float(row['MatchScore']):.2f}")
    st.metric("Budget gate (g_budget)", f"{safe_float(row['g_budget']):.2f}")
    st.write("**Property details**")
    st.write({
        "Property ID": row["Property ID"],
        "Location": row["Location"],
        "Type": row["Type"],
        "Condition": row["Condition"],
        "Bedrooms": int(round(safe_float(row["Bedrooms"]))),
        "Bathrooms": int(round(safe_float(row["Bathrooms"]))),
        "Size (sqft)": int(round(safe_float(row["Size"]))),
        "Year Built": int(round(safe_float(row["Year Built"]))),
        "Price": format_money(row["Price"]),
    })
    st.write("**Why this matched**")
    st.success(generate_reason(row))

with right:
    contrib_df = compute_weighted_contributions(row)
    st.write("**Weighted contribution by component** (sᵢ × wᵢ)")
    st.bar_chart(contrib_df.set_index("component"))

    # Show raw component scores
    st.write("**Raw component scores** (0–1)")
    raw = pd.DataFrame({
        "component": ["price", "bed", "bath", "type", "cond", "year", "size", "loc"],
        "s_i": [
            clamp01(row.get("s_price", 0.5)),
            clamp01(row.get("s_bed", 0.5)),
            clamp01(row.get("s_bath", 0.5)),
            clamp01(row.get("s_type", 0.5)),
            clamp01(row.get("s_cond", 0.5)),
            clamp01(row.get("s_year", 0.5)),
            clamp01(row.get("s_size", 0.5)),
            clamp01(row.get("s_loc", 0.5)),
        ]
    }).sort_values("s_i", ascending=False)
    st.dataframe(raw, use_container_width=True, hide_index=True)

st.caption(
    "Tip: For interviews, demo the filters + explainability: "
    "select a user → show top results → click one property → explain the component contributions."
)
