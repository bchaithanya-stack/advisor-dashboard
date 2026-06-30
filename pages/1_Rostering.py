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

    page_icon="🗓️",

    layout="wide"

)



st.title("🗓️ Advisor Rostering Dashboard")

st.markdown("---")



# ---------------------------------------------------

# Config — edit these for your setup

# ---------------------------------------------------

ROSTER_SHEET_ID = "1EHenAAvAY8r0foyzURuapQtOhBeAiWifpqYaXj_RYUo"   # ID from the sheet's URL (between /d/ and /edit)

CREDENTIALS_FILE = "credentials.json"                                # fallback for local dev



SCOPES = [

    "https://www.googleapis.com/auth/spreadsheets",

    "https://www.googleapis.com/auth/drive",

]



PRESENT_STATUS = "P"  # exact value in a date cell that counts as "present"



# Columns in the sheet that are NOT dates (everything else is treated as a date column)

ID_COLUMNS = [

    "Email ID",

    "Advisor Name",

    "Email Id",

    "New Product",

    "New Bucket",

    "Process Status",

    "Location",

    "DOJ",

    "Tenurity In DPD zero",

    "Status",

    "VP/Director",

    "CM",

    "AM",

    "TL",

    "Total Week offs",

    "Total PL's",

    "Process Name",

]



# Pattern that matches the date column headers, e.g. "01/07/2026"

DATE_COL_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")





# ---------------------------------------------------

# Load Roster Data

# ---------------------------------------------------

@st.cache_data(ttl=10)

def load_roster_data() -> pd.DataFrame:

    """

    Loads roster/shift data from Google Sheets and reshapes it from wide format

    (one row per advisor, one column per date) into long format

    (one row per advisor per date) for filtering and aggregation.

    """



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



    # --- Open the roster sheet by key ---

    try:

        worksheet = client.open_by_key(ROSTER_SHEET_ID).sheet1

    except Exception as e:

        st.error("❌ Error connecting to Roster Google Sheet")

        st.error(str(e))

        st.stop()



    wide_df = pd.DataFrame(worksheet.get_all_records())



    if wide_df.empty:

        return wide_df



    # --- Identify date columns dynamically (anything matching DD/MM/YYYY) ---

    date_cols = [c for c in wide_df.columns if DATE_COL_PATTERN.match(str(c).strip())]



    if not date_cols:

        st.error(

            "❌ No date columns found in the roster sheet (expected headers like '01/07/2026'). "

            f"Found columns: {', '.join(wide_df.columns)}"

        )

        st.stop()



    # --- Reshape wide -> long: one row per advisor per date ---

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

    st.error(

        "No data found in the Roster Google Sheet. Check the sheet ID, sharing permissions, "

        "and that the service account has access."

    )

    st.stop()



required_cols = {"Process Name", "Location", "VP/Director"}

missing_cols = required_cols - set(df.columns)

if missing_cols:

    st.error(

        f"❌ The roster sheet is missing expected column(s): {', '.join(sorted(missing_cols))}. "

        f"Found columns: {', '.join(df.columns)}"

    )

    st.stop()



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



filtered = df.copy()



if vp_director:

    filtered = filtered[filtered["VP/Director"].isin(vp_director)]



if location:

    filtered = filtered[filtered["Location"].isin(location)]



if process:

    filtered = filtered[filtered["Process Name"].isin(process)]



if filtered.empty:

    st.warning("No data matches the selected filters.")

    st.stop()



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

fig_shrinkage.update_layout(height=420, yaxis_title="Shrinkage %")

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

fig_present.update_layout(height=420, yaxis_title="Present Count")

st.plotly_chart(fig_present, use_container_width=True)



st.markdown("---")



# ---------------------------------------------------

# Raw Daily Table

# ---------------------------------------------------

with st.expander("📄 View Day-Level Data Table"):

    st.dataframe(daily, use_container_width=True)
