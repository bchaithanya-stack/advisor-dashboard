import streamlit as st
import pandas as pd
import plotly.express as px

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
# Load Data
# ---------------------------------------------------

df = pd.read_excel("Advisor_Data.xlsx")   # Replace with your file name

# ---------------------------------------------------
# Sidebar Filters
# ---------------------------------------------------

st.sidebar.header("Filters")

process = st.sidebar.selectbox(
    "Select Process",
    ["All"] + sorted(df["Process"].dropna().unique().tolist())
)

if process != "All":
    df = df[df["Process"] == process]

advisor = st.sidebar.selectbox(
    "Select Advisor",
    sorted(df["Advisor Name"].unique())
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

c1.metric(
    "⭐ Star Rating",
    advisor_data["Star Rating (1-5)"]
)

c2.metric(
    "🏆 Process Rank",
    advisor_data["Process Rank"]
)

c3.metric(
    "📈 Productivity",
    f"{advisor_data['Productivity (%)']}%"
)

c4.metric(
    "✅ Compliance",
    f"{advisor_data['Compliance (%) QA']}%"
)

c5.metric(
    "📅 Attendance",
    f"{advisor_data['Attendance (%)']}%"
)

c6.metric(
    "🚫 LOP",
    advisor_data["Total LOP's Days"]
)

st.markdown("---")

# ---------------------------------------------------
# Advisor Details
# ---------------------------------------------------

left, right = st.columns(2)

with left:

    st.subheader("👤 Advisor Details")

    st.write("**EMP ID:**", advisor_data["EMP Id"])
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
# KPI Progress
# ---------------------------------------------------

st.subheader("⭐ KPI Scorecard")

col1, col2 = st.columns(2)

with col1:

    st.write("Attendance Score")

    st.progress(float(advisor_data["Attendance Score (1-5)"])/5)

    st.write(advisor_data["Attendance Score (1-5)"])

    st.write("LOP Score")

    st.progress(float(advisor_data["LOP Score (1-5)"])/5)

    st.write(advisor_data["LOP Score (1-5)"])

    st.write("Performance Score")

    st.progress(float(advisor_data["Performance Score (1-5)"])/5)

    st.write(advisor_data["Performance Score (1-5)"])

with col2:

    st.write("Productivity Score")

    st.progress(float(advisor_data["Productiviy Score (1-5)"])/5)

    st.write(advisor_data["Productiviy Score (1-5)"])

    st.write("Compliance Score")

    st.progress(float(advisor_data["Compliance Score (1-5)"])/5)

    st.write(advisor_data["Compliance Score (1-5)"])

st.markdown("---")

# ---------------------------------------------------
# Performance Chart
# ---------------------------------------------------

st.subheader("📊 KPI Comparison")

chart_df = pd.DataFrame({

    "KPI":[

        "Attendance",

        "LOP",

        "Performance",

        "Productivity",

        "Compliance"

    ],

    "Score":[

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

# ---------------------------------------------------
# Strengths
# ---------------------------------------------------

st.subheader("💪 Strengths")

strength = []

if advisor_data["Attendance Score (1-5)"] >= 4:
    strength.append("✅ Excellent Attendance")

if advisor_data["Productiviy Score (1-5)"] >= 4:
    strength.append("✅ High Productivity")

if advisor_data["Compliance Score (1-5)"] >= 4:
    strength.append("✅ Good Compliance")

if advisor_data["LOP Score (1-5)"] == 5:
    strength.append("✅ Zero LOP")

if len(strength)==0:
    st.warning("No major strengths identified.")

else:
    for i in strength:
        st.write(i)

# ---------------------------------------------------
# Improvement Areas
# ---------------------------------------------------

st.subheader("🎯 Improvement Areas")

improve=[]

if advisor_data["Attendance Score (1-5)"]<4:
    improve.append("Improve Attendance")

if advisor_data["Productiviy Score (1-5)"]<4:
    improve.append("Increase Productivity")

if advisor_data["Compliance Score (1-5)"]<4:
    improve.append("Improve Compliance")

if advisor_data["Performance Score (1-5)"]<4:
    improve.append("Increase Performance")

if len(improve)==0:
    st.success("Excellent Performance!")

else:
    for i in improve:
        st.write("🔸",i)

st.markdown("---")

# ---------------------------------------------------
# Raw Data
# ---------------------------------------------------

with st.expander("📄 View Complete Advisor Data"):

    st.dataframe(advisor_data.to_frame())