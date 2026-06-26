import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------
st.set_page_config(
    page_title="Advisor Performance Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Advisor Performance Dashboard")
st.markdown("---")

# ---------------------------------------------------
# Load Google Sheet
# ---------------------------------------------------
# Reduced ttl to 10 seconds so the application is much more responsive to live sheet edits
@st.cache_data(ttl=10)
def load_data():

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope,
    )

    client = gspread.authorize(creds)

    sheet = client.open_by_key(
        "1CP0uVJXXiBxH4qXklkvh1q0xkocYg2mwMSf0VYXumYM"
    )

    worksheet = sheet.sheet1

    return pd.DataFrame(worksheet.get_all_records())


# ---------------------------------------------------
# Manual Refresh Button
# ---------------------------------------------------
refresh_col, _ = st.columns([1, 5])
with refresh_col:
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()  # Crucial Fix: Clears ALL cached data globally across the app
        st.success("Cache cleared successfully! Fetching new data...")
        st.rerun()

# ---------------------------------------------------
# Fetch Data Frame
# ---------------------------------------------------
df = load_data()

st.subheader("🔍 Debug Data")

st.write("Total Rows:", len(df))

st.dataframe(df)

if df.empty:
    st.error("No data found in the Google Sheet. Check the sheet ID, sharing permissions, "
              "and that the service account has access.")
    st.stop()

# ---------------------------------------------------
# Sidebar Filters
# ---------------------------------------------------
st.sidebar.header("🔍 Filters")

process = st.sidebar.selectbox(
    "Select Process",
    ["All"] + sorted(df["Process"].dropna().unique())
)

if process != "All":
    df = df[df["Process"] == process]

advisor = st.sidebar.selectbox(
    "Select Advisor",
    sorted(df["Advisor Name"].dropna().unique())
)

advisor_data = df[df["Advisor Name"] == advisor].iloc[0]

# ---------------------------------------------------
# Header
# ---------------------------------------------------
st.success(f"Selected Advisor : {advisor}")

# ---------------------------------------------------
# KPI Cards
# ---------------------------------------------------
st.subheader("📈 Performance Summary")

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("⭐ Star Rating", advisor_data["Star Rating (1-5)"])
c2.metric("🏆 Process Rank", advisor_data["Process Rank"])
c3.metric("📈 Productivity", f"{advisor_data['Productivity (%)']}%")
c4.metric("✅ Compliance", f"{advisor_data['Compliance (%) QA']}%")
c5.metric("📅 Attendance", f"{advisor_data['Attendance (%)']}%")
c6.metric("🚫 LOP", advisor_data["Total LOP's Days"])

st.markdown("---")

# ---------------------------------------------------
# Advisor Details
# ---------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("👤 Advisor Details")

    st.write("**EMP ID:**", advisor_data["EMP Id"])
    st.write("**Advisor:**", advisor_data["Advisor Name"])
    st.write("**Email:**", advisor_data["Email Id"])
    st.write("**Location:**", advisor_data["Center / Location"])
    st.write("**Status:**", advisor_data["Status"])

with right:
    st.subheader("🏢 Reporting Hierarchy")

    st.write("**Process:**", advisor_data["Process"])
    st.write("**TL:**", advisor_data["TL"])
    st.write("**AM:**", advisor_data["AM"])
    st.write("**CM:**", advisor_data["CM"])

st.markdown("---")

# ---------------------------------------------------
# KPI Scorecard
# ---------------------------------------------------
st.subheader("⭐ KPI Scorecard")

col1, col2 = st.columns(2)

with col1:
    st.write("Attendance Score")
    st.progress(float(advisor_data["Attendance Score (1-5)"]) / 5)

    st.write("LOP Score")
    st.progress(float(advisor_data["LOP Score (1-5)"]) / 5)

    st.write("Performance Score")
    st.progress(float(advisor_data["Performance Score (1-5)"]) / 5)

with col2:
    st.write("Productivity Score")
    st.progress(float(advisor_data["Productiviy Score (1-5)"]) / 5)

    st.write("Compliance Score")
    st.progress(float(advisor_data["Compliance Score (1-5)"]) / 5)

st.markdown("---")

# ---------------------------------------------------
# KPI Comparison Chart
# ---------------------------------------------------
st.subheader("📊 KPI Comparison")

chart_df = pd.DataFrame({
    "KPI": [
        "Attendance",
        "LOP",
        "Performance",
        "Productivity",
        "Compliance"
    ],
    "Score": [
        advisor_data["Attendance Score (1-5)"],
        advisor_data["LOP Score (1-5)"],
        advisor_data["Performance Score (1-5)"],
        advisor_data["Productiviy Score (1-5)"],
        advisor_data["Compliance Score (1-5)"]
    ]
})

fig = px.bar(
    chart_df,
    x="KPI",
    y="Score",
    text="Score",
    color="Score",
    color_continuous_scale="Blues"
)

fig.update_layout(height=450)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Strengths & Improvement
# ---------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("💪 Strengths")

    strengths = []

    if advisor_data["Attendance Score (1-5)"] >= 4:
        strengths.append("✅ Excellent Attendance")

    if advisor_data["Productiviy Score (1-5)"] >= 4:
        strengths.append("✅ High Productivity")

    if advisor_data["Compliance Score (1-5)"] >= 4:
        strengths.append("✅ Good Compliance")

    if advisor_data["LOP Score (1-5)"] == 5:
        strengths.append("✅ Zero LOP")

    if strengths:
        for item in strengths:
            st.success(item)
    else:
        st.warning("No major strengths identified.")

with col2:
    st.subheader("🎯 Improvement Areas")

    improvements = []

    if advisor_data["Attendance Score (1-5)"] < 4:
        improvements.append("Improve Attendance")

    if advisor_data["Performance Score (1-5)"] < 4:
        improvements.append("Increase Performance")

    if advisor_data["Productiviy Score (1-5)"] < 4:
        improvements.append("Increase Productivity")

    if advisor_data["Compliance Score (1-5)"] < 4:
        improvements.append("Improve Compliance")

    if improvements:
        for item in improvements:
            st.warning(item)
    else:
        st.success("Excellent Performance!")

st.markdown("---")

# ---------------------------------------------------
# Complete Advisor Record
# ---------------------------------------------------
with st.expander("📄 View Complete Advisor Record"):
    st.dataframe(advisor_data.to_frame())
