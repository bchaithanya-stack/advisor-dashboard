import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------
st.set_page_config(
    page_title="DPDzero Shrinkage Dashboard",
    page_icon="📉",
    layout="wide"
)

st.markdown("""
<div style="
background:#17194c;
padding:25px;
border-radius:18px;
border:1px solid #5058d4;
">
<h1 style="color:white;margin-bottom:0;">
📉 DPDzero Shrinkage Dashboard
</h1>
<p style="color:#B8BCFF;">
Roster vs Attendance &amp; Shrinkage Analytics
</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.stApp { background: linear-gradient(180deg,#090a2f,#070726); color:white; }
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}

/* Hide sidebar and the multipage nav (Manpower / Rostering etc.) */
section[data-testid="stSidebar"] {display:none;}
[data-testid="stSidebarNav"] {display:none;}
[data-testid="collapsedControl"] {display:none;}

.stButton>button{ background:#5b5ef7; color:white; border:none; border-radius:10px; padding:10px; font-weight:600; }
.stButton>button:hover{ background:#7b7eff; }
.stSelectbox div[data-baseweb="select"]{ background:#17194c; color:white; }
[data-testid="stDataFrame"]{ background:#151846; border-radius:15px; }
.streamlit-expanderHeader{ background:#1d2057; border-radius:10px; }
h1{ color:white; font-weight:700; }
h2,h3{ color:#cfd2ff; }
</style>
""", unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------
# Config
# ---------------------------------------------------
SHEET_ID = "1zBPCx0rP7yVjXl5MVn5ZlQHZa81SeT5P7PTZ3Z2SqBc"   # ID from the sheet URL (between /d/ and /edit)
SHEET_TAB = "Main"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

EXPECTED_COLS = [
    "EMP ID", "Name", "Email ID", "Date", "DOJ", "TL", "AM", "CM", "Final",
    "POD Leader", "Location", "Active Status", "Roster Status",
    "Attendance Status", "Roster Count", "Attendance Count", "Shrinkage %",
]

PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#090a2f",
    plot_bgcolor="#090a2f",
    font=dict(color="white"),
)


# ---------------------------------------------------
# Helper — KPI Card
# ---------------------------------------------------
def card(title, value):
    st.markdown(f"""
<div style="
background:#17194c; padding:20px; border-radius:18px; border:1px solid #545eff;
text-align:center; box-shadow:0px 0px 15px rgba(120,120,255,.2); height:150px;
width:100%; display:flex; flex-direction:column; justify-content:center;
align-items:center; box-sizing:border-box;
">
<p style="font-size:13px;color:#9da2ff;margin:0;padding:0;">{title}</p>
<h1 style="color:white;margin:8px 0 0 0;padding:0;font-size:30px;">{value}</h1>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------
# Load Data
# ---------------------------------------------------
@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES,
        )
        client = gspread.authorize(creds)
        ws = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)

        # get_all_values avoids header-duplicate errors from blank/helper columns
        values = ws.get_all_values()
        if len(values) < 2:
            st.error("❌ No data found in the sheet.")
            st.stop()

        headers = [str(h).strip().replace("\n", " ") for h in values[0]]
        df = pd.DataFrame(values[1:], columns=headers)

        # Keep only the real data columns (drops blank / helper columns like TEXTJOIN in Z1)
        keep = [c for c in EXPECTED_COLS if c in df.columns]
        df = df[keep].copy()

        missing = [c for c in ["Date", "Roster Count", "Attendance Count"] if c not in df.columns]
        if missing:
            st.error(f"❌ Missing required column(s): {', '.join(missing)}. "
                     f"Found: {', '.join(df.columns)}")
            st.stop()

        # Clean types
        df["Date"] = pd.to_datetime(df["Date"], format="%d %b %Y", errors="coerce")
        if df["Date"].isna().all():
            df["Date"] = pd.to_datetime(values_to_series(values, headers, "Date"),
                                        dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Date"])

        for col in ["Roster Count", "Attendance Count"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        for col in ["TL", "AM", "CM", "Final", "POD Leader", "Location", "Active Status", "Name"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        return df

    except Exception as e:
        st.error(f"❌ Error loading data: {e}")
        st.stop()


def values_to_series(values, headers, col):
    idx = headers.index(col)
    return pd.Series([row[idx] if idx < len(row) else "" for row in values[1:]])


def shrinkage(roster, attendance):
    return ((roster - attendance) / roster * 100).where(roster > 0, 0).round(2)


# ---------------------------------------------------
# Refresh
# ---------------------------------------------------
_, col_refresh = st.columns([5, 1])
with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

df = load_data()

# ---------------------------------------------------
# Filters (cascading)
# ---------------------------------------------------
st.subheader("🔍 Filters")

filtered = df.copy()


def cascade_select(label, column, container, key):
    """Selectbox whose options depend on filters applied so far."""
    global filtered
    if column not in filtered.columns:
        return "All"
    options = ["All"] + sorted([x for x in filtered[column].dropna().unique() if x != ""])
    with container:
        choice = st.selectbox(label, options, key=key)
    if choice != "All":
        filtered = filtered[filtered[column] == choice]
    return choice


r1 = st.columns(4)
cascade_select("🔹 Location:", "Location", r1[0], "f_loc")
cascade_select("🔹 Process (Final):", "Final", r1[1], "f_final")
cascade_select("🔹 POD Leader:", "POD Leader", r1[2], "f_pod")
cascade_select("🔹 CM:", "CM", r1[3], "f_cm")

r2 = st.columns(4)
cascade_select("🔹 AM:", "AM", r2[0], "f_am")
cascade_select("🔹 TL:", "TL", r2[1], "f_tl")
cascade_select("🔹 Active Status:", "Active Status", r2[2], "f_active")

min_d, max_d = df["Date"].min().date(), df["Date"].max().date()
with r2[3]:
    date_range = st.date_input("🔹 Date Range:", value=(min_d, max_d),
                               min_value=min_d, max_value=max_d, key="f_date")

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[(filtered["Date"].dt.date >= start) & (filtered["Date"].dt.date <= end)]

st.markdown("---")

if filtered.empty:
    st.warning("⚠️ No data matches the selected filters.")
    st.stop()

# ---------------------------------------------------
# Day-level aggregation
# ---------------------------------------------------
daily = (
    filtered.groupby("Date")
    .agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
    .reset_index()
    .sort_values("Date")
)
daily["Shrinkage %"] = shrinkage(daily["Roster"], daily["Attendance"])

total_roster = daily["Roster"].sum()
total_att = daily["Attendance"].sum()
overall_shrink = ((total_roster - total_att) / total_roster * 100) if total_roster > 0 else 0

# ---------------------------------------------------
# KPI Cards
# ---------------------------------------------------
st.subheader("📈 Summary")

c1, c2, c3, c4, c5 = st.columns(5)
with c1: card("📉 Overall Shrinkage %", f"{overall_shrink:.2f}%")
with c2: card("📅 Avg Daily Shrinkage %", f"{daily['Shrinkage %'].mean():.2f}%")
with c3: card("👥 Avg Daily Roster", f"{daily['Roster'].mean():.1f}")
with c4: card("✅ Avg Daily Attendance", f"{daily['Attendance'].mean():.1f}")
with c5: card("🧑‍💼 Advisors in View", filtered["EMP ID"].nunique() if "EMP ID" in filtered.columns else "-")

st.markdown("---")

# ---------------------------------------------------
# Chart 1 — Day-level Shrinkage %
# ---------------------------------------------------
st.subheader("📉 Day-Level Shrinkage %")

fig1 = px.line(daily, x="Date", y="Shrinkage %", markers=True)
fig1.update_traces(line_color="#7f63ff", marker=dict(size=8))
fig1.update_layout(**PLOT_LAYOUT, height=420, yaxis_title="Shrinkage %")
st.plotly_chart(fig1, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Chart 2 — Day-level Roster vs Attendance
# ---------------------------------------------------
st.subheader("👥 Day-Level Projected Present (Roster) vs Actual Present (Attendance)")

fig2 = go.Figure()
fig2.add_bar(x=daily["Date"], y=daily["Roster"], name="Projected Present (Roster)",
             marker_color="#5b5ef7")
fig2.add_bar(x=daily["Date"], y=daily["Attendance"], name="Actual Present (Attendance)",
             marker_color="#38d9a9")
fig2.update_layout(**PLOT_LAYOUT, height=420, barmode="group", yaxis_title="Headcount",
                   legend=dict(orientation="h", y=1.1))
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Chart 3 — Shrinkage by chosen dimension
# ---------------------------------------------------
st.subheader("📊 Shrinkage % Breakdown")

dim_options = [c for c in ["TL", "AM", "CM", "POD Leader", "Location", "Final"] if c in filtered.columns]
dim = st.selectbox("Break down by:", dim_options, key="breakdown_dim")

by_dim = (
    filtered.groupby(dim)
    .agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
    .reset_index()
)
by_dim["Shrinkage %"] = shrinkage(by_dim["Roster"], by_dim["Attendance"])
by_dim = by_dim[by_dim["Roster"] > 0].sort_values("Shrinkage %", ascending=False)

fig3 = px.bar(by_dim, x=dim, y="Shrinkage %", text="Shrinkage %",
              color="Shrinkage %", color_continuous_scale="Purples")
fig3.update_traces(texttemplate="%{text:.1f}%")
fig3.update_layout(**PLOT_LAYOUT, height=420, coloraxis_showscale=False)
st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Tables
# ---------------------------------------------------
with st.expander("📄 Day-Level Data Table"):
    st.dataframe(daily.assign(Date=daily["Date"].dt.strftime("%d %b %Y")),
                 use_container_width=True)
    st.download_button("⬇️ Download Day-Level CSV", daily.to_csv(index=False),
                       "shrinkage_daily.csv", "text/csv")

with st.expander(f"📄 {dim}-wise Summary Table"):
    st.dataframe(by_dim, use_container_width=True)
