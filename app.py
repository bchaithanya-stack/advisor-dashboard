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
.stApp{ background: linear-gradient(180deg,#090a2f,#070726); color:white; }
/* Hide default Streamlit menu */
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}
/* Sidebar */
section[data-testid="stSidebar"]{ background:#10133d; border-right:1px solid #34396b; }
/* Cards */
div[data-testid="metric-container"]{ background:#1a1d53; border:1px solid #4b52b6; padding:18px; border-radius:15px; box-shadow:0px 0px 15px rgba(97,91,255,.25); }
div[data-testid="metric-container"]:hover{ transform:translateY(-4px); transition:.3s; }
/* Buttons */
.stButton>button{ background:#5b5ef7; color:white; border:none; border-radius:10px; padding:10px; font-weight:600; }
.stButton>button:hover{ background:#7b7eff; }
/* Select Box */
.stSelectbox div[data-baseweb="select"]{ background:#17194c; color:white; }
/* Dataframe */
[data-testid="stDataFrame"]{ background:#151846; border-radius:15px; }
/* Expanders */
.streamlit-expanderHeader{ background:#1d2057; border-radius:10px; }
/* Progress bar */
.stProgress > div > div{ background:#7f63ff; }
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

        numeric_cols = [
            "Star Rating (1-5)", "Process Rank", "Productivity (%)", 
            "Compliance (%) QA", "Attendance (%)", "Total LOP's Days",
            "Attendance Score (1-5)", "LOP Score (1-5)", "Performance Score (1-5)", 
            "Productiviy Score (1-5)", "Compliance Score (1-5)"
        ]
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace('%', '', regex=False).str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce')

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
    st.markdown(f"""
    <div style="
    background:#17194c; padding:20px; border-radius:18px; border:1px solid #545eff; text-align:center; box-shadow:0px 0px 15px rgba(120,120,255,.2); height:160px; width:100%; display:flex; flex-direction:column; justify-content:center; align-items:center; box-sizing:border-box;
    ">
    <p style="font-size:14px;color:#9da2ff;margin:0;padding:0;">{title}</p>
    <h1 style="color:white;margin:8px 0 0 0;padding:0;font-size:48px;">{value}</h1>
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

view_col = st.columns(1)[0]
with view_col:
    # ADDED THE NEW MANAGEMENT VIEW HERE
    view_type = st.radio(
        "📊 Select View Type:",
        ["👤 Advisor View", "👥 Support Staff View", "📈 Overall View", "🏢 Management Summary"],
        horizontal=True
    )

st.markdown("---")

# Initialize variables to prevent errors later
advisor_data = None
team_df = None
overall_df = None
mgmt_df = None

# ===================================================
# ADVISOR VIEW FILTERS
# ===================================================
if view_type == "👤 Advisor View":
    
    st.markdown("**Advisor View - Select Filters Below:**")
    adv_col1, adv_col2, adv_col3, adv_col4 = st.columns(4)
    
    with adv_col1:
        process_list = ["All"] + sorted(df["Process"].dropna().unique().tolist())
        selected_process = st.selectbox("🔹 Process:", process_list, key="adv_process")
    
    with adv_col2:
        location_filtered = df[df["Process"] == selected_process] if selected_process != "All" else df.copy()
        location_list = ["All"] + sorted(location_filtered["Center / Location"].dropna().unique().tolist())
        selected_location = st.selectbox("🔹 Location:", location_list, key="adv_location")
    
    with adv_col3:
        emp_filtered = df[df["Process"] == selected_process] if selected_process != "All" else df.copy()
        if selected_location != "All": emp_filtered = emp_filtered[emp_filtered["Center / Location"] == selected_location]
        emp_list = ["All"] + sorted(emp_filtered["EMP Id"].dropna().unique().tolist())
        selected_emp_id = st.selectbox("🔹 Employee ID:", emp_list, key="adv_emp_id")
    
    with adv_col4:
        adv_filtered = df[df["Process"] == selected_process] if selected_process != "All" else df.copy()
        if selected_location != "All": adv_filtered = adv_filtered[adv_filtered["Center / Location"] == selected_location]
        if selected_emp_id != "All": adv_filtered = adv_filtered[adv_filtered["EMP Id"] == selected_emp_id]
        
        advisor_list = sorted(adv_filtered["Advisor Name"].dropna().unique().tolist())
        if advisor_list:
            selected_advisor = st.selectbox("🔹 Advisor Name:", advisor_list, key="adv_name")
            advisor_data = adv_filtered[adv_filtered["Advisor Name"] == selected_advisor].iloc[0]
        else:
            st.warning("⚠️ No advisors found with selected filters")

# ===================================================
# SUPPORT STAFF VIEW FILTERS
# ===================================================
elif view_type == "👥 Support Staff View":  
    
    st.markdown("**Support Staff View - Select Filters Below:**")
    staff_col1, staff_col2, staff_col3, staff_col4, staff_col5, staff_col6 = st.columns(6)
    
    with staff_col1:
        location_list = ["All"] + sorted(df["Center / Location"].dropna().unique().tolist())
        selected_location = st.selectbox("🔹 Location:", location_list, key="staff_location")
    
    with staff_col2:
        pod_filtered = df[df["Center / Location"] == selected_location] if selected_location != "All" else df.copy()
        pod_list = ["All"] + sorted(pod_filtered["POD_Leader"].dropna().unique().tolist())
        selected_pod = st.selectbox("🔹 POD Leader:", pod_list, key="staff_pod")
    
    with staff_col3:
        process_filtered = df[df["Center / Location"] == selected_location] if selected_location != "All" else df.copy()
        if selected_pod != "All": process_filtered = process_filtered[process_filtered["POD_Leader"] == selected_pod]
        process_list = ["All"] + sorted(process_filtered["Process"].dropna().unique().tolist())
        selected_process = st.selectbox("🔹 Process:", process_list, key="staff_process")
    
    with staff_col4:
        cm_filtered = df[df["Center / Location"] == selected_location] if selected_location != "All" else df.copy()
        if selected_pod != "All": cm_filtered = cm_filtered[cm_filtered["POD_Leader"] == selected_pod]
        if selected_process != "All": cm_filtered = cm_filtered[cm_filtered["Process"] == selected_process]
        cm_list = ["All"] + sorted(cm_filtered["CM"].dropna().unique().tolist())
        selected_cm = st.selectbox("🔹 CM (Collection Manager):", cm_list, key="staff_cm")
    
    with staff_col5:
        am_filtered = df[df["Center / Location"] == selected_location] if selected_location != "All" else df.copy()
        if selected_pod != "All": am_filtered = am_filtered[am_filtered["POD_Leader"] == selected_pod]
        if selected_process != "All": am_filtered = am_filtered[am_filtered["Process"] == selected_process]
        if selected_cm != "All": am_filtered = am_filtered[am_filtered["CM"] == selected_cm]
        am_list = ["All"] + sorted(am_filtered["AM"].dropna().unique().tolist())
        selected_am = st.selectbox("🔹 AM (Assistant Manager):", am_list, key="staff_am")
    
    with staff_col6:
        tl_filtered = df[df["Center / Location"] == selected_location] if selected_location != "All" else df.copy()
        if selected_pod != "All": tl_filtered = tl_filtered[tl_filtered["POD_Leader"] == selected_pod]
        if selected_process != "All": tl_filtered = tl_filtered[tl_filtered["Process"] == selected_process]
        if selected_cm != "All": tl_filtered = tl_filtered[tl_filtered["CM"] == selected_cm]
        if selected_am != "All": tl_filtered = tl_filtered[tl_filtered["AM"] == selected_am]
        tl_list = ["All"] + sorted(tl_filtered["TL"].dropna().unique().tolist())
        selected_tl = st.selectbox("🔹 Team Leader (TL):", tl_list, key="staff_tl")
    
    team_df = df.copy()
    if selected_location != "All": team_df = team_df[team_df["Center / Location"] == selected_location]
    if selected_pod != "All": team_df = team_df[team_df["POD_Leader"] == selected_pod]
    if selected_process != "All": team_df = team_df[team_df["Process"] == selected_process]
    if selected_cm != "All": team_df = team_df[team_df["CM"] == selected_cm]
    if selected_am != "All": team_df = team_df[team_df["AM"] == selected_am]
    if selected_tl != "All": team_df = team_df[team_df["TL"] == selected_tl]

# ===================================================
# OVERALL VIEW FILTERS
# ===================================================
elif view_type == "📈 Overall View":
    
    st.markdown("**Overall View - Top 10% Advisors by Star Rating**")
    overall_col1, overall_col2, overall_col3 = st.columns(3)
    
    with overall_col1:
        location_list = ["All"] + sorted(df["Center / Location"].dropna().unique().tolist())
        selected_overall_location = st.selectbox("🔹 Location:", location_list, key="overall_location")
    
    with overall_col2:
        overall_pod_filtered = df[df["Center / Location"] == selected_overall_location] if selected_overall_location != "All" else df.copy()
        overall_pod_list = ["All"] + sorted(overall_pod_filtered["POD_Leader"].dropna().unique().tolist())
        selected_overall_pod = st.selectbox("🔹 POD Leader:", overall_pod_list, key="overall_pod")
    
    with overall_col3:
        overall_cm_filtered = df[df["Center / Location"] == selected_overall_location] if selected_overall_location != "All" else df.copy()
        if selected_overall_pod != "All": overall_cm_filtered = overall_cm_filtered[overall_cm_filtered["POD_Leader"] == selected_overall_pod]
        overall_cm_list = ["All"] + sorted(overall_cm_filtered["CM"].dropna().unique().tolist())
        selected_overall_cm = st.selectbox("🔹 CM (Collection Manager):", overall_cm_list, key="overall_cm")
    
    overall_df = df.copy()
    if selected_overall_location != "All": overall_df = overall_df[overall_df["Center / Location"] == selected_overall_location]
    if selected_overall_pod != "All": overall_df = overall_df[overall_df["POD_Leader"] == selected_overall_pod]
    if selected_overall_cm != "All": overall_df = overall_df[overall_df["CM"] == selected_overall_cm]
    
    if len(overall_df) > 0:
        top_10_percent = []
        for process in overall_df["Process"].unique():
            process_data = overall_df[overall_df["Process"] == process].copy()
            count = len(process_data)
            top_count = max(1, int(count * 0.1))
            top_process = process_data.nlargest(top_count, "Star Rating (1-5)")
            top_10_percent.append(top_process)
        
        overall_df = pd.concat(top_10_percent, ignore_index=True)
        overall_df = overall_df.sort_values("Star Rating (1-5)", ascending=False)

# ===================================================
# MANAGEMENT SUMMARY VIEW FILTERS (NEW)
# ===================================================
elif view_type == "🏢 Management Summary":
    
    st.markdown("**Management Summary - Select Filters Below:**")
    mgmt_col1, mgmt_col2 = st.columns(2)
    
    with mgmt_col1:
        location_list = ["All"] + sorted(df["Center / Location"].dropna().unique().tolist())
        selected_mgmt_location = st.selectbox("🔹 Location:", location_list, key="mgmt_location")
        
    with mgmt_col2:
        mgmt_pod_filtered = df[df["Center / Location"] == selected_mgmt_location] if selected_mgmt_location != "All" else df.copy()
        pod_list = ["All"] + sorted(mgmt_pod_filtered["POD_Leader"].dropna().unique().tolist())
        selected_mgmt_pod = st.selectbox("🔹 POD Leader:", pod_list, key="mgmt_pod")
        
    mgmt_df = df.copy()
    if selected_mgmt_location != "All": mgmt_df = mgmt_df[mgmt_df["Center / Location"] == selected_mgmt_location]
    if selected_mgmt_pod != "All": mgmt_df = mgmt_df[mgmt_df["POD_Leader"] == selected_mgmt_pod]

st.markdown("---")

# ===================================================
# ADVISOR VIEW CONTENT
# ===================================================
if view_type == "👤 Advisor View" and advisor_data is not None:
    
    st.success(f"✅ Selected Advisor: **{selected_advisor}** (ID: {selected_emp_id}) | Location: **{selected_location}** | Process: **{selected_process}**")
    st.subheader("📈 Performance Summary")
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: card("⭐ Star Rating", advisor_data["Star Rating (1-5)"])
    with c2: card("🏆 Rank", advisor_data["Process Rank"])
    with c3: card("📈 Productivity", f"{advisor_data['Productivity (%)']}%")
    with c4: card("✅ Compliance", f"{advisor_data['Compliance (%) QA']}%")
    with c5: card("📅 Attendance", f"{advisor_data['Attendance (%)']}%")
    with c6: card("🚫 LOP", advisor_data["Total LOP's Days"])
    
    st.markdown("---")
    
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
        if "POD_Leader" in advisor_data: st.write("**POD Leader:**", advisor_data["POD_Leader"])
    
    st.markdown("---")
    
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
    
    st.subheader("📊 KPI Comparison")
    chart_df = pd.DataFrame({
        "KPI": ["Attendance", "LOP", "Performance", "Productivity", "Compliance"],
        "Score": [
            advisor_data["Attendance Score (1-5)"], advisor_data["LOP Score (1-5)"],
            advisor_data["Performance Score (1-5)"], advisor_data["Productiviy Score (1-5)"],
            advisor_data["Compliance Score (1-5)"]
        ]
    })
    
    fig = px.bar(chart_df, x="KPI", y="Score", text="Score", color="Score", color_continuous_scale="Blues")
    fig.update_layout(template="plotly_dark", paper_bgcolor="#090a2f", plot_bgcolor="#090a2f", font=dict(color="white"), height=450, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("💪 Strengths")
        strengths = []
        if advisor_data["Attendance Score (1-5)"] >= 4: strengths.append("✅ Excellent Attendance")
        if advisor_data["Productiviy Score (1-5)"] >= 4: strengths.append("✅ High Productivity")
        if advisor_data["Compliance Score (1-5)"] >= 4: strengths.append("✅ Good Compliance")
        if advisor_data["LOP Score (1-5)"] == 5: strengths.append("✅ Zero LOP")
        if not strengths: st.warning("⚠️ No major strengths identified.")
        else:
            for s in strengths: st.write(s)
            
    with col2:
        st.subheader("🎯 Improvement Areas")
        improvements = []
        if advisor_data["Attendance Score (1-5)"] < 4: improvements.append("Improve Attendance")
        if advisor_data["Productiviy Score (1-5)"] < 4: improvements.append("Increase Productivity")
        if advisor_data["Compliance Score (1-5)"] < 4: improvements.append("Improve Compliance")
        if advisor_data["Performance Score (1-5)"] < 4: improvements.append("Increase Performance")
        if not improvements: st.success("✅ Excellent Performance!")
        else:
            for imp in improvements: st.write("🔸", imp)
    
    st.markdown("---")
    with st.expander("📄 View Complete Advisor Data"):
        st.dataframe(advisor_data.to_frame())

# ===================================================
# SUPPORT STAFF VIEW CONTENT
# ===================================================
elif view_type == "👥 Support Staff View" and team_df is not None and len(team_df) > 0:
    
    filter_summary = []
    if selected_pod != "All": filter_summary.append(f"POD: {selected_pod}")
    if selected_process != "All": filter_summary.append(f"Process: {selected_process}")
    if selected_cm != "All": filter_summary.append(f"CM: {selected_cm}")
    if selected_am != "All": filter_summary.append(f"AM: {selected_am}")
    if selected_tl != "All": filter_summary.append(f"TL: {selected_tl}")
    
    summary_text = " | ".join(filter_summary) if filter_summary else "All Staff"
    st.success(f"✅ Showing {len(team_df)} advisors | {summary_text}")
    st.markdown("---")
    
    st.subheader("📈 Team Summary")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: card("👥 Team Size", len(team_df))
    with c2: card("⭐ Avg Rating", round(team_df["Star Rating (1-5)"].astype(float).mean(), 2))
    with c3: card("📈 Avg Productivity", f"{round(team_df['Productivity (%)'].astype(float).mean(), 2)}%")
    with c4: card("✅ Avg Compliance", f"{round(team_df['Compliance (%) QA'].astype(float).mean(), 2)}%")
    with c5: card("📅 Avg Attendance", f"{round(team_df['Attendance (%)'].astype(float).mean(), 2)}%")
    
    st.markdown("---")
    
    st.subheader("👥 Team Members Details")
    display_cols = ["Advisor Name", "EMP Id", "Email Id", "Status", "Productivity (%)", "Compliance (%) QA", "Attendance (%)", "Star Rating (1-5)", "Process"]
    st.dataframe(team_df[[c for c in display_cols if c in team_df.columns]].copy(), use_container_width=True)
    
    st.markdown("---")
    
    st.subheader("📊 Team Performance Analysis")
    score_cols = ["Attendance Score (1-5)", "LOP Score (1-5)", "Productiviy Score (1-5)", "Compliance Score (1-5)"]
    team_scores = team_df[score_cols].astype(float).mean()
    team_chart_df = pd.DataFrame({
        "Metric": ["Attendance", "LOP", "Productivity", "Compliance"],
        "Avg Score": [team_scores["Attendance Score (1-5)"], team_scores["LOP Score (1-5)"], team_scores["Productiviy Score (1-5)"], team_scores["Compliance Score (1-5)"]]
    })
    
    fig_team = px.bar(team_chart_df, x="Metric", y="Avg Score", text="Avg Score", color="Avg Score", color_continuous_scale="Blues")
    fig_team.update_layout(template="plotly_dark", paper_bgcolor="#090a2f", plot_bgcolor="#090a2f", font=dict(color="white"), height=450, coloraxis_showscale=False)
    st.plotly_chart(fig_team, use_container_width=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏆 Top 3 Performers")
        top_performers = team_df.nlargest(3, "Star Rating (1-5)")
        for idx, (_, row) in enumerate(top_performers.iterrows(), 1): st.write(f"{idx}. **{row['Advisor Name']}** - ⭐ {row['Star Rating (1-5)']} | Prod: {row['Productivity (%)']}% | Comp: {row['Compliance (%) QA']}%")
    with col2:
        st.subheader("⚠️ Needs Improvement")
        bottom_performers = team_df.nsmallest(3, "Star Rating (1-5)")
        for idx, (_, row) in enumerate(bottom_performers.iterrows(), 1): st.write(f"{idx}. **{row['Advisor Name']}** - ⭐ {row['Star Rating (1-5)']} | Prod: {row['Productivity (%)']}% | Comp: {row['Compliance (%) QA']}%")
    
    st.markdown("---")
    with st.expander("📄 Export Team Data"):
        st.download_button(label="⬇️ Download Team Data (CSV)", data=team_df.to_csv(index=False), file_name="team_data.csv", mime="text/csv")

# ===================================================
# OVERALL VIEW CONTENT
# ===================================================
elif view_type == "📈 Overall View" and overall_df is not None and len(overall_df) > 0:
    
    st.success(f"✅ Showing Top 10% Advisors per process based on Star Ratings (Total: {len(overall_df)} advisors)")
    
    st.subheader("🏆 Top Performers Details")
    
    overall_display_cols = [
        "Advisor Name", "Process", "Center / Location", "POD_Leader", "CM",
        "Star Rating (1-5)", "Productivity (%)", "Compliance (%) QA", "Attendance (%)"
    ]
    
    available_overall_cols = [c for c in overall_display_cols if c in overall_df.columns]
    
    st.dataframe(overall_df[available_overall_cols], use_container_width=True)
    
    st.markdown("---")
    
    with st.expander("📄 Export Top Performers Data"):
        st.write("**Top 10% Overall Data Export**")
        csv = overall_df.to_csv(index=False)
        st.download_button(
            label="⬇️ Download Top 10% Data (CSV)",
            data=csv,
            file_name="overall_top_10_percent_advisors.csv",
            mime="text/csv"
        )

# ===================================================
# MANAGEMENT SUMMARY VIEW CONTENT (NEW)
# ===================================================
elif view_type == "🏢 Management Summary" and mgmt_df is not None and len(mgmt_df) > 0:
    
    st.success(f"✅ Showing Management Summaries | Location: **{selected_mgmt_location}** | POD Leader: **{selected_mgmt_pod}**")
    st.markdown("---")
    
    # Helper function to generate aggregate tables
    def get_aggregated_summary(df, group_by_col):
        if group_by_col not in df.columns:
            return pd.DataFrame()
            
        summary = df.groupby(group_by_col).agg(
            Number_of_Advisors=('EMP Id', 'count'),
            Avg_Star_Rating=('Star Rating (1-5)', 'mean'),
            Avg_Productivity=('Productivity (%)', 'mean'),
            Avg_Compliance=('Compliance (%) QA', 'mean'),
            Avg_Attendance=('Attendance (%)', 'mean')
        ).reset_index()
        
        # Round the metrics for a cleaner look
        for col in summary.columns[1:]:
            summary[col] = summary[col].round(2)
            
        return summary
    
    # Create tabs for easy navigation
    tab_tl, tab_am, tab_cm, tab_pod, tab_loc = st.tabs([
        "👔 TL Wise", "👔 AM Wise", "👔 CM Wise", "🚀 POD Leader Wise", "📍 Location Wise"
    ])
    
    with tab_tl:
        st.subheader("Team Leader (TL) Aggregate Summary")
        st.dataframe(get_aggregated_summary(mgmt_df, "TL"), use_container_width=True)
        
    with tab_am:
        st.subheader("Assistant Manager (AM) Aggregate Summary")
        st.dataframe(get_aggregated_summary(mgmt_df, "AM"), use_container_width=True)
        
    with tab_cm:
        st.subheader("Collection Manager (CM) Aggregate Summary")
        st.dataframe(get_aggregated_summary(mgmt_df, "CM"), use_container_width=True)
        
    with tab_pod:
        st.subheader("POD Leader Aggregate Summary")
        if "POD_Leader" in mgmt_df.columns:
            st.dataframe(get_aggregated_summary(mgmt_df, "POD_Leader"), use_container_width=True)
        else:
            st.warning("POD_Leader column not found in data.")
            
    with tab_loc:
        st.subheader("Center / Location Aggregate Summary")
        st.dataframe(get_aggregated_summary(mgmt_df, "Center / Location"), use_container_width=True)
