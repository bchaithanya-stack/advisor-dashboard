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

# Styled Header Banner matching the screenshot layout
st.markdown("""
<div class="main-title">
    <h1>📊 Advisor Rostering Dashboard</h1>
</div>
""", unsafe_allow_html=True)
st.markdown("---")


# ---------------------------------------------------
# Config — edit these for your setup
# ---------------------------------------------------
ROSTER_SHEET_ID = "1EHenAAvAY8r0foyzURuapQtOhBeAiWifpqYaXj_RYUo"   # ID from the sheet's URL
CREDENTIALS_FILE = "credentials.json"                                # fallback for local dev

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

PRESENT_STATUS = "P"  # exact value in a date cell that counts as "present"

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

    # --- 1. Try Streamlit secrets first ---
    if "gcp_service_account" in st.secrets:
        try:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=SCOPES,
            )
        except Exception as e:
            st.warning(f"⚠️ Found gcp_service_account in secrets, but failed to load it: {e}")

    # --- 2. Fall back to local credentials.json ---
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

    # --- Connect to Google Sheets ---
    try:
        client = gspread.authorize(creds)
    except Exception as e:
        st.error("❌ Error authorizing with Google Sheets")
        st.error(str(e))
        st.stop()

    # --- Open the roster sheet by key and target the "Main Advisors" tab ---
    try:
        worksheet = client.open_by_key(ROSTER_SHEET_ID).worksheet("Main Advisors")
    except Exception as e:
        st.error("❌ Error connecting to 'Main Advisors' worksheet in Google Sheet")
        st.error(str(e))
        st.stop()

    wide_df = pd.DataFrame(worksheet.get_all_records())

    if wide_df.empty:
        return wide_df

    # --- Identify date columns dynamically ---
    date_cols = [c for c in wide_df.columns if DATE_COL_PATTERN.match(str(c).strip())]

    if not date_cols:
        st.error(
            "❌ No date columns found in the roster sheet (expected headers like '01/07/2026'). "
            f"Found columns: {', '.join(wide_df.columns)}"
        )
        st.stop()

    # --- Reshape wide -> long ---
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
# Fetch Data
# ---------------------------------------------------
df = load_roster_data()

if df.empty:
    st.error("No data found in the Roster Google Sheet.")
    st.stop()

# 👇 ADD THIS LINE HERE to force all process names to uppercase and remove extra spaces
if "Process Name" in df.columns:
    df["Process Name"] = df["Process Name"].astype(str).str.strip().str.upper()

required_cols = {"Process Name", "Location", "VP/Director"}


# ---------------------------------------------------
# Sidebar Filters
# ---------------------------------------------------
st.sidebar.header("🔍 Filters")

vp_director = st.sidebar.multiselect(
    "VP / Director",
    sorted(df["VP/Director"].dropna().unique()),
    default=None,
)

location = st.sidebar.multiselect(
    "Location",
    sorted(df["Location"].dropna().unique()),
    default=None,
)

process = st.sidebar.multiselect(
    "Process",
    sorted(df["Process Name"].dropna().unique()),
    default=None,
)

# 👇 FIX: Changed "Advisor Name" to "advisor_name" (no spaces)
advisor_name = st.sidebar.multiselect(
    "Advisor Name",
    sorted(df["Advisor Name"].dropna().unique()),
    default=None,
)

filtered = df.copy()

if vp_director:
    filtered = filtered[filtered["VP/Director"].isin(vp_director)]

if location:
    filtered = filtered[filtered["Location"].isin(location)]

if process:
    filtered = filtered[filtered["Process Name"].isin(process)]

# 👇 REMEMBER TO APPLY THE FILTER TO YOUR DATAFRAME AS WELL:
if advisor_name:
    filtered = filtered[filtered["Advisor Name"].isin(advisor_name)]


# ---------------------------------------------------
# Day-Level Aggregation
# ---------------------------------------------------
daily = (
    filtered.groupby(filtered["Date"].dt.date)
    .agg(
        Scheduled=("DayStatus", "size"),
        Present=("DayStatus", lambda s: (s == PRESENT_STATUS).sum()),
    )
    .reset_index()
)

daily["Shrinkage %"] = (
    (daily["Scheduled"] - daily["Present"]) / daily["Scheduled"] * 100
).round(2)

daily = daily.sort_values("Date")


# ---------------------------------------------------
# KPI Summary
# ---------------------------------------------------
st.subheader("📈 Summary")

k1, k2, k3 = st.columns(3)
k1.metric("Avg Daily Shrinkage %", f"{daily['Shrinkage %'].mean():.2f}%")
k2.metric("Avg Daily Present Count", f"{daily['Present'].mean():.1f}")
k3.metric("Days in View", len(daily))

st.markdown("---")


# ---------------------------------------------------
# Chart 1 — Day-Level Shrinkage %
# ---------------------------------------------------
st.subheader("📉 Day-Level Shrinkage %")

fig_shrinkage = px.line(
    daily,
    x="Date",
    y="Shrinkage %",
    markers=True,
)

# Apply premium dark backgrounds and styling directly to the generated figure
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
# Chart 2 — Day-Level Projected Present Count
# ---------------------------------------------------
st.subheader("👥 Day-Level Projected Present Count")

fig_present = px.bar(
    daily,
    x="Date",
    y="Present",
    text="Present",
)

# Apply premium dark backgrounds and styling directly to the generated figure
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


# ---------------------------------------------------
# Raw Daily Table
# ---------------------------------------------------
with st.expander("📄 View Day-Level Data Table"):
    st.dataframe(daily, use_container_width=True)
