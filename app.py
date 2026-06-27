import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------

st.set_page_config(
    page_title="Advisor Performance Dashboard",
    page_icon="📊",
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
📊 Advisor Performance Dashboard
</h1>

<p style="color:#B8BCFF;">
Real Time Performance Analytics
</p>

</div>

""", unsafe_allow_html=True)
st.markdown("---")

st.markdown("""
<style>

/* Main App */
.stApp{
    background: linear-gradient(180deg,#090a2f,#070726);
    color:white;
}

/* Hide default Streamlit menu */
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}

/* Sidebar */
section[data-testid="stSidebar"]{
    background:#10133d;
    border-right:1px solid #34396b;
}

/* Cards */
div[data-testid="metric-container"]{
    background:#1a1d53;
    border:1px solid #4b52b6;
    padding:18px;
    border-radius:15px;
    box-shadow:0px 0px 15px rgba(97,91,255,.25);
}

div[data-testid="metric-container"]:hover{
    transform:translateY(-4px);
    transition:.3s;
}

/* Buttons */
.stButton>button{
    background:#5b5ef7;
    color:white;
    border:none;
    border-radius:10px;
    padding:10px;
    font-weight:600;
}

.stButton>button:hover{
    background:#7b7eff;
}

/* Select Box */
.stSelectbox div[data-baseweb="select"]{
    background:#17194c;
    color:white;
}

/* Text input */
.stTextInput input{
    background:#17194c;
    color:white;
}

/* Dataframe */
[data-testid="stDataFrame"]{
    background:#151846;
    border-radius:15px;
}

/* Expanders */
.streamlit-expanderHeader{
    background:#1d2057;
    border-radius:10px;
}

/* Progress bar */
.stProgress > div > div{
    background:#7f63ff;
}

/* Headers */
h1{
    color:white;
    font-weight:700;
}

h2,h3{
    color:#cfd2ff;
}

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# Load Data with Error Handling
# ---------------------------------------------------

@st.cache_data
def load_data():
    """Load and validate data from Excel file"""
    try:
        if not os.path.exists("Advisor_Data.xlsx"):
            st.error("❌ Error: 'Advisor_Data.xlsx' file not found. Please ensure the file is in the working directory.")
            st.stop()
        
        df = pd.read_excel("Advisor_Data.xlsx")
        
        # Validate required columns
        required_columns = [
            "Advisor Name", "Process", "EMP Id", "Email Id", "Center / Location",
            "Status", "TL", "AM", "CM", "Star Rating (1-5)", "Process Rank",
            "Productivity (%)", "Compliance (%) QA", "Attendance (%)", "Total LOP's Days",
            "Attendance Score (1-5)", "LOP Score (1-5)", "Performance Score (1-5)",
            "Productiviy Score (1-5)", "Compliance Score (1-5)"
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"❌ Missing columns in data: {', '.join(missing_columns)}")
            st.stop()
        
        return df
    
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.stop()

df = load_data()

# ---------------------------------------------------
# Sidebar Filters
# ---------------------------------------------------

st.sidebar.header("Filters")

# Process Filter
process_list = ["All"] + sorted(df["Process"].dropna().unique().tolist())
process = st.sidebar.selectbox(
    "Select Process",
    process_list
)

# Filter data by process
if process != "All":
    filtered_df = df[df["Process"] == process]
else:
    filtered_df = df.copy()

# Advisor Filter (filtered by selected process)
if len(filtered_df) == 0:
    st.warning("⚠️ No advisors found for the selected process.")
    st.stop()

advisor_list = sorted(filtered_df["Advisor Name"].unique().tolist())
advisor = st.sidebar.selectbox(
    "Select Advisor",
    advisor_list
)

# Get selected advisor data
advisor_data = filtered_df[filtered_df["Advisor Name"] == advisor].iloc[0]

# ---------------------------------------------------
# Helper Function for KPI Cards
# ---------------------------------------------------

def card(title, value):
    """Display a KPI card"""
    st.markdown(f"""
    <div style="
    background:#17194c;
    padding:20px;
    border-radius:18px;
    border:1px solid #545eff;
    text-align:center;
    box-shadow:0px 0px 15px rgba(120,120,255,.2);
    min-height:180px;
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    ">
    <p style="font-size:14px;color:#9da2ff;margin:0;">
    {title}
    </p>
    <h1 style="color:white;margin:10px 0 0 0;">
    {value}
    </h1>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------
# Header
# ---------------------------------------------------

st.success(f"Selected Advisor: {advisor}")

# ---------------------------------------------------
# KPI Cards
# ---------------------------------------------------

st.subheader("📈 Performance Summary")

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    card("⭐ Star Rating", advisor_data["Star Rating (1-5)"])

with c2:
    card("🏆 Rank", advisor_data["Process Rank"])

with c3:
    card("📈 Productivity", f"{advisor_data['Productivity (%)']}%")

with c4:
    card("✅ Compliance", f"{advisor_data['Compliance (%) QA']}%")

with c5:
    card("📅 Attendance", f"{advisor_data['Attendance (%)']}%")

with c6:
    card("🚫 LOP", advisor_data["Total LOP's Days"])

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
    st.write("**Attendance Score**")
    st.progress(float(advisor_data["Attendance Score (1-5)"]) / 5)
    st.write(f"Score: {advisor_data['Attendance Score (1-5)']}/5")

    st.write("**LOP Score**")
    st.progress(float(advisor_data["LOP Score (1-5)"]) / 5)
    st.write(f"Score: {advisor_data['LOP Score (1-5)']}/5")

    st.write("**Performance Score**")
    st.progress(float(advisor_data["Performance Score (1-5)"]) / 5)
    st.write(f"Score: {advisor_data['Performance Score (1-5)']}/5")

with col2:
    st.write("**Productivity Score**")
    st.progress(float(advisor_data["Productiviy Score (1-5)"]) / 5)
    st.write(f"Score: {advisor_data['Productiviy Score (1-5)']}/5")

    st.write("**Compliance Score**")
    st.progress(float(advisor_data["Compliance Score (1-5)"]) / 5)
    st.write(f"Score: {advisor_data['Compliance Score (1-5)']}/5")

st.markdown("---")

# ---------------------------------------------------
# Performance Chart
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

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="#090a2f",
    plot_bgcolor="#090a2f",
    font=dict(color="white"),
    height=450,
    coloraxis_showscale=False
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Strengths
# ---------------------------------------------------

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

if len(strengths) == 0:
    st.warning("No major strengths identified.")
else:
    for strength in strengths:
        st.write(strength)

# ---------------------------------------------------
# Improvement Areas
# ---------------------------------------------------

st.subheader("🎯 Improvement Areas")

improvements = []

if advisor_data["Attendance Score (1-5)"] < 4:
    improvements.append("Improve Attendance")

if advisor_data["Productiviy Score (1-5)"] < 4:
    improvements.append("Increase Productivity")

if advisor_data["Compliance Score (1-5)"] < 4:
    improvements.append("Improve Compliance")

if advisor_data["Performance Score (1-5)"] < 4:
    improvements.append("Increase Performance")

if len(improvements) == 0:
    st.success("✅ Excellent Performance! No improvement areas identified.")
else:
    for improvement in improvements:
        st.write("🔸", improvement)

st.markdown("---")

# ---------------------------------------------------
# Raw Data
# ---------------------------------------------------

with st.expander("📄 View Complete Advisor Data"):
    st.dataframe(advisor_data.to_frame())
