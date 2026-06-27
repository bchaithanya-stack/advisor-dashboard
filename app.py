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
Real Time Performance Analytics (Google Sheets)
</p>

</div>

""", unsafe_allow_html=True)

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
h1{ color:white; font-weight:700; }
h2,h3{ color:#cfd2ff; }

</style>
""", unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------
# Load Google Sheet with Cache
# ---------------------------------------------------

@st.cache_data(ttl=10)
def load_data_from_google_sheets():
    """Load data from Google Sheets with authentication"""
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scope,
        )

        client = gspread.authorize(creds)
        sheet = client.open_by_key("1CP0uVJXXiBxH4qXklkvh1q0xkocYg2mwMSf0VYXumYM")
        worksheet = sheet.sheet1
        df = pd.DataFrame(worksheet.get_all_records())

        if df.empty:
            st.error("❌ No data found in the Google Sheet.")
            st.stop()

        return df

    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.stop()

# ---------------------------------------------------
# Fetch Data
# ---------------------------------------------------

df = load_data_from_google_sheets()

# ---------------------------------------------------
# Helper Function for KPI Cards
# ---------------------------------------------------

def card(title, value):
    """Display a custom KPI card with fixed dimensions"""
    st.markdown(f"""
    <div style="
    background:#17194c;
    padding:20px;
    border-radius:18px;
    border:1px solid #545eff;
    text-align:center;
    box-shadow:0px 0px 15px rgba(120,120,255,.2);
    height:160px;
    width:100%;
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    box-sizing:border-box;
    ">
    <p style="font-size:14px;color:#9da2ff;margin:0;padding:0;">
    {title}
    </p>
    <h1 style="color:white;margin:8px 0 0 0;padding:0;font-size:48px;">
    {value}
    </h1>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------
# Top Bar with Refresh Button
# ---------------------------------------------------

col_space, col_refresh = st.columns([5, 1])
with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True, key="refresh_btn"):
        st.cache_data.clear()
        st.success("✅ Data refreshed!")
        st.rerun()

st.markdown("---")

# ---------------------------------------------------
# FILTER SECTION - MAIN CONTENT AREA
# ---------------------------------------------------

st.subheader("🔍 Filters & Selection")

filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

# View Type Selection
with filter_col1:
    view_type = st.radio(
        "View Type:",
        ["👤 Advisor View", "👥 Support Staff View"],
        horizontal=False
    )

# Initialize variables
process = "All"
advisor = None
staff_type = None
selected_staff = None
advisor_data = None
team_df = None

# ADVISOR VIEW FILTERS
if view_type == "👤 Advisor View":
    with filter_col2:
        process_list = ["All"] + sorted(df["Process"].dropna().unique().tolist())
        process = st.selectbox(
            "Process:",
            process_list,
            key="proc_select"
        )
    
    with filter_col3:
        if process != "All":
            filtered_df = df[df["Process"] == process]
        else:
            filtered_df = df.copy()
        
        advisor_list = sorted(filtered_df["Advisor Name"].dropna().unique().tolist())
        advisor = st.selectbox(
            "Advisor:",
            advisor_list,
            key="adv_select"
        )
        
        advisor_data = filtered_df[filtered_df["Advisor Name"] == advisor].iloc[0]

# SUPPORT STAFF VIEW FILTERS
else:
    with filter_col2:
        staff_type = st.selectbox(
            "Staff Category:",
            ["TL (Team Lead)", "AM (Area Manager)", "CM (Center Manager)", "POD_Leader"],
            key="staff_cat"
        )
    
    with filter_col3:
        staff_column_map = {
            "TL (Team Lead)": "TL",
            "AM (Area Manager)": "AM",
            "CM (Center Manager)": "CM",
            "POD_Leader": "POD_Leader"
        }
        staff_column = staff_column_map[staff_type]
        staff_list = sorted(df[staff_column].dropna().unique().tolist())
        selected_staff = st.selectbox(
            "Staff Member:",
            staff_list,
            key="staff_mem"
        )
        
        team_df = df[df[staff_column] == selected_staff].copy()

st.markdown("---")

# ===================================================
# ADVISOR VIEW CONTENT
# ===================================================

if view_type == "👤 Advisor View" and advisor_data is not None:
    
    st.success(f"✅ Selected Advisor: **{advisor}**")
    
    # ---------------------------------------------------
    # KPI Cards - Performance Summary
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
        if "POD_Leader" in advisor_data:
            st.write("**POD Leader:**", advisor_data["POD_Leader"])
    
    st.markdown("---")
    
    # ---------------------------------------------------
    # KPI Progress Scorecard
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
        "KPI": ["Attendance", "LOP", "Performance", "Productivity", "Compliance"],
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
    # Strengths & Improvements
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
        
        if len(strengths) == 0:
            st.warning("⚠️ No major strengths identified.")
        else:
            for strength in strengths:
                st.write(strength)
    
    with col2:
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
            st.success("✅ Excellent Performance!")
        else:
            for improvement in improvements:
                st.write("🔸", improvement)
    
    st.markdown("---")
    
    with st.expander("📄 View Complete Advisor Data"):
        st.dataframe(advisor_data.to_frame())

# ===================================================
# SUPPORT STAFF VIEW CONTENT
# ===================================================

elif view_type == "👥 Support Staff View" and team_df is not None and len(team_df) > 0:
    
    st.success(f"✅ Showing {len(team_df)} advisors under **{selected_staff}**")
    st.markdown("---")
    
    # ---------------------------------------------------
    # Team Summary Cards
    # ---------------------------------------------------
    
    st.subheader("📈 Team Summary")
    
    team_size = len(team_df)
    avg_star_rating = round(team_df["Star Rating (1-5)"].astype(float).mean(), 2)
    avg_productivity = round(team_df["Productivity (%)"].astype(float).mean(), 2)
    avg_compliance = round(team_df["Compliance (%) QA"].astype(float).mean(), 2)
    avg_attendance = round(team_df["Attendance (%)"].astype(float).mean(), 2)
    
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        card("👥 Team Size", team_size)
    
    with c2:
        card("⭐ Avg Rating", avg_star_rating)
    
    with c3:
        card("📈 Avg Productivity", f"{avg_productivity}%")
    
    with c4:
        card("✅ Avg Compliance", f"{avg_compliance}%")
    
    with c5:
        card("📅 Avg Attendance", f"{avg_attendance}%")
    
    st.markdown("---")
    
    # ---------------------------------------------------
    # Team Members Table
    # ---------------------------------------------------
    
    st.subheader("👥 Team Members Details")
    
    display_cols = [
        "Advisor Name", "EMP Id", "Email Id", "Status", "Productivity (%)",
        "Compliance (%) QA", "Attendance (%)", "Attendance Score (1-5)",
        "LOP Score (1-5)", "Productiviy Score (1-5)", "Compliance Score (1-5)",
        "Star Rating (1-5)", "Process"
    ]
    
    available_cols = [col for col in display_cols if col in team_df.columns]
    team_display = team_df[available_cols].copy()
    
    st.dataframe(team_display, use_container_width=True)
    
    st.markdown("---")
    
    # ---------------------------------------------------
    # Team Performance Chart
    # ---------------------------------------------------
    
    st.subheader("📊 Team Performance Analysis")
    
    score_cols = [
        "Attendance Score (1-5)",
        "LOP Score (1-5)",
        "Productiviy Score (1-5)",
        "Compliance Score (1-5)"
    ]
    
    team_scores = team_df[score_cols].astype(float).mean()
    
    team_chart_df = pd.DataFrame({
        "Metric": ["Attendance", "LOP", "Productivity", "Compliance"],
        "Avg Score": [
            team_scores["Attendance Score (1-5)"],
            team_scores["LOP Score (1-5)"],
            team_scores["Productiviy Score (1-5)"],
            team_scores["Compliance Score (1-5)"]
        ]
    })
    
    fig_team = px.bar(
        team_chart_df,
        x="Metric",
        y="Avg Score",
        text="Avg Score",
        color="Avg Score",
        color_continuous_scale="Blues"
    )
    
    fig_team.update_layout(
        template="plotly_dark",
        paper_bgcolor="#090a2f",
        plot_bgcolor="#090a2f",
        font=dict(color="white"),
        height=450,
        coloraxis_showscale=False
    )
    
    st.plotly_chart(fig_team, use_container_width=True)
    
    st.markdown("---")
    
    # ---------------------------------------------------
    # Top & Bottom Performers
    # ---------------------------------------------------
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏆 Top 3 Performers")
        top_performers = team_df.nlargest(3, "Star Rating (1-5)")[
            ["Advisor Name", "Star Rating (1-5)", "Productivity (%)", "Compliance (%) QA"]
        ]
        
        for idx, (_, row) in enumerate(top_performers.iterrows(), 1):
            st.write(f"{idx}. **{row['Advisor Name']}** - ⭐ {row['Star Rating (1-5)']} | Prod: {row['Productivity (%)']}% | Comp: {row['Compliance (%) QA']}%")
    
    with col2:
        st.subheader("⚠️ Needs Improvement")
        bottom_performers = team_df.nsmallest(3, "Star Rating (1-5)")[
            ["Advisor Name", "Star Rating (1-5)", "Productivity (%)", "Compliance (%) QA"]
        ]
        
        for idx, (_, row) in enumerate(bottom_performers.iterrows(), 1):
            st.write(f"{idx}. **{row['Advisor Name']}** - ⭐ {row['Star Rating (1-5)']} | Prod: {row['Productivity (%)']}% | Comp: {row['Compliance (%) QA']}%")
    
    st.markdown("---")
    
    with st.expander("📄 Export Team Data"):
        st.write(f"**Team Data for {selected_staff}**")
        csv = team_df.to_csv(index=False)
        st.download_button(
            label="⬇️ Download Team Data (CSV)",
            data=csv,
            file_name=f"{selected_staff}_team_data.csv",
            mime="text/csv"
        )
