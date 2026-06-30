import re
import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------
st.set_page_config(
    page_title="Advisor Rostering Dashboard",
    page_icon="📊",
    layout="wide"
)

# -----------------------------
# Premium Dark Theme CSS
# -----------------------------
st.markdown("""
<style>

/* Main App */
.stApp {
    background: #0b0b2d;
    color: white;
}

/* Header Card */
.main-title {
    background: #1b1b52;
    padding: 30px;
    border-radius: 18px;
    border: 1px solid #4b4bb8;
    box-shadow: 0 0 20px rgba(70,70,255,.15);
    margin-bottom: 25px;
}

.main-title h1 {
    color: white;
    margin: 0;
    font-size: 42px;
    font-weight: 700;
}

.main-title p {
    color: #b8b8d4;
    margin: 5px 0 0 0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #10103a;
}

/* Metrics */
[data-testid="metric-container"] {
    background: #1b1b52;
    border: 1px solid #5050b5;
    border-radius: 15px;
    padding: 18px;
    box-shadow: 0 4px 20px rgba(0,0,0,.25);
}

[data-testid="metric-container"] label {
    color: #bfbfff;
}

[data-testid="metric-container"] div {
    color: white;
}

/* Buttons */
.stButton>button {
    background: #6366F1;
    color: white;
    border: none;
    border-radius: 10px;
    height: 45px;
    width: 100%;
    font-weight: bold;
}

.stButton>button:hover {
    background: #818CF8;
}

/* Select Boxes */
.stSelectbox div[data-baseweb="select"] {
    background: #1b1b52;
    border-radius: 10px;
}

/* Multiselect */
.stMultiSelect div[data-baseweb="select"] {
    background: #1b1b52;
    border-radius: 10px;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}

/* Expander */
.streamlit-expanderHeader {
    background: #1b1b52;
    border-radius: 10px;
}

/* Divider */
hr {
    border: 1px solid #333366;
}

/* Chart background */
.js-plotly-plot .plotly {
    border-radius: 15px;
}

/* Radio buttons */
.stRadio label {
    color: white;
}

/* Text */
h1, h2, h3, h4, h5, h6 {
    color: white;
}

label, p {
    color: #d8d8f5;
}

</style>
""", unsafe_allow_html=True)

# Styled Header Banner
st.markdown("""
<div class="main-title">
    <h1>📊 Advisor Rostering Dashboard</h1>
</div>
""", unsafe_allow_html=True)
st.markdown("---")


# ---------------------------------------------------
# Config
# ---------------------------------------------------
ROSTER_SHEET_ID = "1EHenAAvAY8r0foyzURuapQtOhBeAiWifpqYaXj_RYUo"
CREDENTIALS_FILE = "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

PRESENT_STATUS = "P"

ID_COLUMNS = [
    "Email ID", "Advisor Name", "Email Id", "New Product",
    "New Bucket", "Process Status", "Location", "DOJ",
    "Tenurity In DPD zero", "Status", "VP/Director", "CM",
    "AM", "TL", "Total Week offs", "Total PL's", "Process Name",
]

DATE_COL_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")


# ---------------------------------------------------
# Load Roster Data
# ---------------------------------------------------
@st.cache_data(ttl=10)
def load_roster_data() -> pd.DataFrame:
    creds = None

    if "gcp_service_account" in st.secrets:
        try:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=SCOPES,
            )
        except Exception as e:
            st.warning(f"⚠️ Found gcp_service_account in secrets, but failed to load it: {e}")

    if creds is None:
        import os
        if not os.path.exists(CREDENTIALS_FILE):
            st.error(
                "❌ No credentials found. Add `gcp_service_account` to st.secrets "
                f"or place a `{CREDENTIALS_FILE}` file next to this script."
            )
            st.stop()
        try:
            import json
            with open(CREDENTIALS_FILE) as f:
                creds_dict = json.load(f)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except Exception as e:
            st.error("❌ Error loading credentials.json")
            st.error(str(e))
            st.stop()

    try:
        client = gspread.authorize(creds)
    except Exception as e:
        st.error("❌ Error authorizing with Google Sheets")
        st.error(str(e))
        st.stop()

    try:
        worksheet = client.open_by_key(ROSTER_SHEET_ID).worksheet("Main Advisors")
    except Exception as e:
        st.error("❌ Error connecting to 'Main Advisors' worksheet in Google Sheet")
        st.error(str(e))
        st.stop()

    wide_df = pd.DataFrame(worksheet.get_all_records())

    if wide_df.empty:
        return wide_df

    date_cols = [c for c in wide_df.columns if DATE_COL_PATTERN.match(str(c).strip())]

    if not date_cols:
        st.error(
            "❌ No date columns found in the roster sheet (expected headers like '01/07/2026'). "
            f"Found columns: {', '.join(wide_df.columns)}"
        )
        st.stop()

    id_cols_present = [c for c in ID_COLUMNS if c in wide_df.columns]

    long_df = wide_df.melt(
        id_vars=id_cols_present,
        value_vars=date_cols,
        var_name="Date",
        value_name="DayStatus",
    )

    long_df["Date"] = pd.to_datetime(long_df["Date"], format="%d/%m/%Y", errors="coerce")
    long_df["DayStatus"] = long_df["DayStatus"].astype(str).str.strip()

    return long_df


# ---------------------------------------------------
# Manual Refresh Button
# ---------------------------------------------------
refresh_col, _ = st.columns([1, 5])
with refresh_col:
    if st.button("🔄 Refresh Roster Data"):
        st.cache_data.clear()
        st.success("Cache cleared successfully! Fetching new data...")
        st.rerun()


# ---------------------------------------------------
# Fetch Data & Clean Duplicates
# ---------------------------------------------------
df = load_roster_data()

if df.empty:
    st.error("No data found in the Roster Google Sheet.")
    st.stop()

# Standardize case formatting to eliminate dropdown duplicate options
if "Process Name" in df.columns:
    df["Process Name"] = df["Process Name"].astype(str).str.strip().str.upper()

required_cols = {"Process Name", "Location", "VP/Director"}
missing_cols = required_cols - set(df.columns)
if missing_cols:
    st.error(
        f"❌ The roster sheet is missing expected column(s): {', '.join(sorted(missing_cols))}. "
        f"Found columns: {', '.join(df.columns)}"
    )
    st.stop()


# =====================================================
# CASCADING FILTERS
# =====================================================

st.markdown("## 🔍 Filters")

filtered_df = df.copy()

c1, c2, c3, c4 = st.columns(4)

# ---------------- VP ----------------
with c1:
    vp_director = st.multiselect(
        "VP / Director",
        sorted(filtered_df["VP/Director"].dropna().unique())
    )

if vp_director:
    filtered_df = filtered_df[
        filtered_df["VP/Director"].isin(vp_director)
    ]

# ---------------- Location ----------------
with c2:
    location = st.multiselect(
        "Location",
        sorted(filtered_df["Location"].dropna().unique())
    )

if location:
    filtered_df = filtered_df[
        filtered_df["Location"].isin(location)
    ]

# ---------------- Process ----------------
with c3:
    process = st.multiselect(
        "Process",
        sorted(filtered_df["Process Name"].dropna().unique())
    )

if process:
    filtered_df = filtered_df[
        filtered_df["Process Name"].isin(process)
    ]

# ---------------- Advisor ----------------
with c4:
    advisor = st.multiselect(
        "Advisor Name",
        sorted(filtered_df["Advisor Name"].dropna().unique())
    )

if advisor:
    filtered_df = filtered_df[
        filtered_df["Advisor Name"].isin(advisor)
    ]

filtered = filtered_df.copy()

if filtered.empty:
    st.warning("No data found.")
    st.stop()
# ---------------------------------------------------
# Day-Level Aggregation (Occupancy and Shrinkage)
# ---------------------------------------------------
daily = (
    filtered.groupby(filtered["Date"].dt.date)
    .agg(
        Scheduled=("DayStatus", "size"),
        Present=("DayStatus", lambda s: (s == PRESENT_STATUS).sum()),
    )
    .reset_index()
)

# Calculations
daily["Shrinkage %"] = (
    (daily["Scheduled"] - daily["Present"]) / daily["Scheduled"] * 100
).round(2)

daily["Occupancy %"] = (
    (daily["Present"] / daily["Scheduled"]) * 100
).round(2)

daily = daily.sort_values("Date")


# ---------------------------------------------------
# KPI Summary Cards
# ---------------------------------------------------
st.subheader("📈 Summary Metrics")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Avg Daily Occupancy %", f"{daily['Occupancy %'].mean():.2f}%")
k2.metric("Avg Daily Shrinkage %", f"{daily['Shrinkage %'].mean():.2f}%")
k3.metric("Avg Daily Present Count", f"{daily['Present'].mean():.1f}")
k4.metric("Days in View", len(daily))

st.markdown("---")


# ---------------------------------------------------
# Chart 1 — Day-Level Occupancy %
# ---------------------------------------------------
st.subheader("🎯 Day-Level Occupancy % Trend")

fig_occupancy = px.line(
    daily,
    x="Date",
    y="Occupancy %",
    markers=True,
    text="Occupancy %"
)

fig_occupancy.update_traces(textposition="top center")
fig_occupancy.update_layout(
    height=420, 
    yaxis_title="Occupancy %",
    paper_bgcolor="#1b1b52",
    plot_bgcolor="#1b1b52",
    font_color="white",
    xaxis=dict(gridcolor="#444466"),
    yaxis=dict(gridcolor="#444466", range=[0, 105])
)
st.plotly_chart(fig_occupancy, use_container_width=True)

st.markdown("---")


# ---------------------------------------------------
# Chart 2 — Day-Level Shrinkage %
# ---------------------------------------------------
st.subheader("📉 Day-Level Shrinkage %")

fig_shrinkage = px.line(
    daily,
    x="Date",
    y="Shrinkage %",
    markers=True,
)

fig_shrinkage.update_layout(
    height=420, 
    yaxis_title="Shrinkage %",
    paper_bgcolor="#1b1b52",
    plot_bgcolor="#1b1b52",
    font_color="white",
    xaxis=dict(gridcolor="#444466"),
    yaxis=dict(gridcolor="#444466")
)
st.plotly_chart(fig_shrinkage, use_container_width=True)

st.markdown("---")


# ---------------------------------------------------
# Chart 3 — Day-Level Projected Present Count
# ---------------------------------------------------
st.subheader("👥 Day-Level Projected Present Count")

fig_present = px.bar(
    daily,
    x="Date",
    y="Present",
    text="Present",
)

fig_present.update_layout(
    height=420, 
    yaxis_title="Present Count",
    paper_bgcolor="#1b1b52",
    plot_bgcolor="#1b1b52",
    font_color="white",
    xaxis=dict(gridcolor="#444466"),
    yaxis=dict(gridcolor="#444466")
)
st.plotly_chart(fig_present, use_container_width=True)

st.markdown("---")

# =====================================================
# PROCESS-WISE LOGIN SUMMARY
# =====================================================

st.markdown("---")
st.subheader("📊 Process-wise Login Summary")

# Count only Present advisors
present_df = filtered[filtered["DayStatus"] == "P"].copy()

# Create date column for display
present_df["Roster Date"] = present_df["Date"].dt.strftime("%d-%b-%Y")

# -------------------------
# Stacked Bar Chart
# -------------------------
fig_process = px.bar(
    present_df.groupby(["Roster Date", "Process Name"])
              .size()
              .reset_index(name="Login Count"),
    x="Roster Date",
    y="Login Count",
    color="Process Name",
    text="Login Count",
    title="Day-wise Process Login Count"
)

fig_process.update_layout(
    height=500,
    paper_bgcolor="#1b1b52",
    plot_bgcolor="#1b1b52",
    font_color="white",
    xaxis_title="Date",
    yaxis_title="Present Count",
    legend_title="Process",
)

st.plotly_chart(fig_process, use_container_width=True)

# -------------------------
# Pivot Table
# -------------------------
st.subheader("📋 Day-wise Process Login Matrix")

login_matrix = (
    present_df.pivot_table(
        index="Roster Date",
        columns="Process Name",
        values="Advisor Name",
        aggfunc="count",
        fill_value=0,
        margins=True,
        margins_name="Total"
    )
)

st.dataframe(
    login_matrix,
    use_container_width=True
)

# ---------------------------------------------------
# Raw Daily Table
# ---------------------------------------------------
with st.expander("📄 View Day-Level Data Table"):
    st.dataframe(daily, use_container_width=True)
