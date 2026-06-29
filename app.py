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
<h1 style="color:white;margin-bottom:0;">📊 Advisor Performance Dashboard</h1>
<p style="color:#B8BCFF;">Real Time Performance Analytics (Google Sheets)</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.stApp{ background: linear-gradient(180deg,#090a2f,#070726); color:white; }
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}
section[data-testid="stSidebar"]{ background:#10133d; border-right:1px solid #34396b; }
.stButton>button{ background:#5b5ef7; color:white; border:none; border-radius:10px; padding:10px; font-weight:600; }
.stButton>button:hover{ background:#7b7eff; }
.stSelectbox div[data-baseweb="select"]{ background:#17194c; color:white; }
[data-testid="stDataFrame"]{ background:#151846; border-radius:15px; }
.streamlit-expanderHeader{ background:#1d2057; border-radius:10px; }
.stProgress > div > div{ background:#7f63ff; }
h1{ color:white; font-weight:700; }
h2,h3,h4{ color:#cfd2ff; }
</style>
""", unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------
# Load Google Sheet with Cache
# ---------------------------------------------------

@st.cache_data(ttl=10)
def load_data_from_google_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key("1CP0uVJXXiBxH4qXklkvh1q0xkocYg2mwMSf0VYXumYM")
        worksheet = sheet.sheet1
        df = pd.DataFrame(worksheet.get_all_records())

        if df.empty:
            st.error("❌ No data found in the Google Sheet.")
            st.stop()

        numeric_cols = [
            "Star Rating (1-5)", "Process Rank", "Productivity (%)", 
            "Compliance (%) QA", "Attendance (%)", "Performance (%)", "Total LOP's Days",
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
# Fetch Data & Helper Functions
# ---------------------------------------------------

df = load_data_from_google_sheets()

def card(title, value):
    st.markdown(f"""
    <div style="
    background:#17194c; padding:20px; border-radius:18px; border:1px solid #545eff; text-align:center; box-shadow:0px 0px 15px rgba(120,120,255,.2); height:140px; width:100%; display:flex; flex-direction:column; justify-content:center; align-items:center; box-sizing:border-box; margin-bottom:15px;
    ">
    <p style="font-size:14px;color:#9da2ff;margin:0;padding:0;">{title}</p>
    <h1 style="color:white;margin:8px 0 0 0;padding:0;font-size:32px;">{value}</h1>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------
# Top Bar
# ---------------------------------------------------

col_space, col_refresh = st.columns([5, 1])
with col_refresh:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

st.subheader("🔍 Filters & Selection")
view_type = st.radio(
    "Select View Type:",
    ["👤 Advisor View", "👥 Support Staff View", "📈 Overall View", "🏢 Management Summary"],
    horizontal=True,
    label_visibility="collapsed"
)
st.markdown("---")

# ===================================================
# 1. ADVISOR VIEW (Filters + Content)
# ===================================================
if view_type == "👤 Advisor View":
    st.markdown("#### Advisor Filters")
    adv_col1, adv_col2, adv_col3, adv_col4 = st.columns(4)
    
    with adv_col1:
        selected_process = st.selectbox("🔹 Process:", ["All"] + sorted(df["Process"].dropna().unique().tolist()))
    with adv_col2:
        loc_df = df[df["Process"] == selected_process] if selected_process != "All" else df
        selected_location = st.selectbox("🔹 Location:", ["All"] + sorted(loc_df["Center / Location"].dropna().unique().tolist()))
    with adv_col3:
        emp_df = loc_df[loc_df["Center / Location"] == selected_location] if selected_location != "All" else loc_df
        selected_emp_id = st.selectbox("🔹 Employee ID:", ["All"] + sorted(emp_df["EMP Id"].dropna().unique().tolist()))
    with adv_col4:
        adv_df = emp_df[emp_df["EMP Id"] == selected_emp_id] if selected_emp_id != "All" else emp_df
        advisor_list = sorted(adv_df["Advisor Name"].dropna().unique().tolist())
        selected_advisor = st.selectbox("🔹 Advisor Name:", advisor_list) if advisor_list else None

    if selected_advisor:
        advisor_data = adv_df[adv_df["Advisor Name"] == selected_advisor].iloc[0]
        st.markdown("---")
        st.subheader("📈 Performance Summary")
        
        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        with c1: card("⭐ Star Rating", advisor_data["Star Rating (1-5)"])
        with c2: card("🏆 Rank", advisor_data.get("Process Rank", "N/A"))
        with c3: card("📈 Productivity", f"{advisor_data['Productivity (%)']}%")
        with c4: card("✅ Compliance", f"{advisor_data['Compliance (%) QA']}%")
        with c5: card("📅 Attendance", f"{advisor_data['Attendance (%)']}%")
        with c6: card("🎯 Performance", f"{advisor_data.get('Performance (%)', 0)}%")
        with c7: card("🚫 LOP Days", advisor_data["Total LOP's Days"])
        
        # Advisor Details table format
        st.markdown("---")
        st.subheader("📄 Advisor Data")
        st.dataframe(advisor_data.to_frame().T, hide_index=True, use_container_width=True)

    else:
        st.warning("⚠️ No advisors found with the selected filters.")

# ===================================================
# 2. SUPPORT STAFF VIEW (Filters + Content)
# ===================================================
elif view_type == "👥 Support Staff View":
    st.markdown("#### Support Staff Filters")
    staff_col1, staff_col2, staff_col3, staff_col4, staff_col5, staff_col6 = st.columns(6)
    
    with staff_col1:
        selected_location = st.selectbox("🔹 Location:", ["All"] + sorted(df["Center / Location"].dropna().unique().tolist()))
    with staff_col2:
        pod_df = df[df["Center / Location"] == selected_location] if selected_location != "All" else df
        selected_pod = st.selectbox("🔹 POD Leader:", ["All"] + sorted(pod_df["POD_Leader"].dropna().unique().tolist()))
    with staff_col3:
        proc_df = pod_df[pod_df["POD_Leader"] == selected_pod] if selected_pod != "All" else pod_df
        selected_process = st.selectbox("🔹 Process:", ["All"] + sorted(proc_df["Process"].dropna().unique().tolist()))
    with staff_col4:
        cm_df = proc_df[proc_df["Process"] == selected_process] if selected_process != "All" else proc_df
        selected_cm = st.selectbox("🔹 CM:", ["All"] + sorted(cm_df["CM"].dropna().unique().tolist()))
    with staff_col5:
        am_df = cm_df[cm_df["CM"] == selected_cm] if selected_cm != "All" else cm_df
        selected_am = st.selectbox("🔹 AM:", ["All"] + sorted(am_df["AM"].dropna().unique().tolist()))
    with staff_col6:
        tl_df = am_df[am_df["AM"] == selected_am] if selected_am != "All" else am_df
        selected_tl = st.selectbox("🔹 TL:", ["All"] + sorted(tl_df["TL"].dropna().unique().tolist()))
    
    team_df = tl_df[tl_df["TL"] == selected_tl] if selected_tl != "All" else tl_df

    if not team_df.empty:
        st.markdown("---")
        st.subheader("📈 Team Summary")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1: card("👥 Team Size", len(team_df))
        with c2: card("⭐ Avg Rating", round(team_df["Star Rating (1-5)"].mean(), 2))
        with c3: card("📈 Avg Prod", f"{round(team_df['Productivity (%)'].mean(), 1)}%")
        with c4: card("✅ Avg Comp", f"{round(team_df['Compliance (%) QA'].mean(), 1)}%")
        with c5: card("📅 Avg Att", f"{round(team_df['Attendance (%)'].mean(), 1)}%")
        with c6: card("🎯 Avg Perf", f"{round(team_df.get('Performance (%)', pd.Series([0])).mean(), 1)}%")
        
        st.markdown("---")
        st.subheader("👥 Team Members Details")
        display_cols = ["Advisor Name", "EMP Id", "Status", "Productivity (%)", "Compliance (%) QA", "Attendance (%)", "Performance (%)", "Star Rating (1-5)"]
        st.dataframe(team_df[[c for c in display_cols if c in team_df.columns]], hide_index=True, use_container_width=True)

# ===================================================
# 3. OVERALL VIEW (Filters + Content)
# ===================================================
elif view_type == "📈 Overall View":
    st.markdown("#### Overall View Filters (Top 10% Advisors)")
    overall_col1, overall_col2, overall_col3 = st.columns(3)
    
    with overall_col1:
        selected_overall_location = st.selectbox("🔹 Location:", ["All"] + sorted(df["Center / Location"].dropna().unique().tolist()), key="ov_loc")
    with overall_col2:
        ov_pod_df = df[df["Center / Location"] == selected_overall_location] if selected_overall_location != "All" else df
        selected_overall_pod = st.selectbox("🔹 POD Leader:", ["All"] + sorted(ov_pod_df["POD_Leader"].dropna().unique().tolist()), key="ov_pod")
    with overall_col3:
        ov_cm_df = ov_pod_df[ov_pod_df["POD_Leader"] == selected_overall_pod] if selected_overall_pod != "All" else ov_pod_df
        selected_overall_cm = st.selectbox("🔹 CM:", ["All"] + sorted(ov_cm_df["CM"].dropna().unique().tolist()), key="ov_cm")
    
    overall_df = ov_cm_df[ov_cm_df["CM"] == selected_overall_cm] if selected_overall_cm != "All" else ov_cm_df
    
    if not overall_df.empty:
        top_10_percent = []
        for process in overall_df["Process"].unique():
            process_data = overall_df[overall_df["Process"] == process]
            top_count = max(1, int(len(process_data) * 0.1))
            top_10_percent.append(process_data.nlargest(top_count, "Star Rating (1-5)"))
        
        final_top_df = pd.concat(top_10_percent, ignore_index=True).sort_values("Star Rating (1-5)", ascending=False)
        
        st.markdown("---")
        st.subheader("🏆 Top Performers Details (Top 10%)")
        overall_cols = ["Advisor Name", "Process", "Center / Location", "POD_Leader", "Star Rating (1-5)", "Productivity (%)", "Compliance (%) QA", "Performance (%)"]
        st.dataframe(final_top_df[[c for c in overall_cols if c in final_top_df.columns]], hide_index=True, use_container_width=True)

# ===================================================
# 4. MANAGEMENT SUMMARY (Filters + Content)
# ===================================================
elif view_type == "🏢 Management Summary":
    st.markdown("#### Management Summary Filters")
    mgmt_col1, mgmt_col2 = st.columns(2)
    
    with mgmt_col1:
        selected_mgmt_location = st.selectbox("🔹 Location:", ["All"] + sorted(df["Center / Location"].dropna().unique().tolist()), key="mg_loc")
    with mgmt_col2:
        mg_pod_df = df[df["Center / Location"] == selected_mgmt_location] if selected_mgmt_location != "All" else df
        selected_mgmt_pod = st.selectbox("🔹 POD Leader:", ["All"] + sorted(mg_pod_df["POD_Leader"].dropna().unique().tolist()), key="mg_pod")
        
    mgmt_df = mg_pod_df[mg_pod_df["POD_Leader"] == selected_mgmt_pod] if selected_mgmt_pod != "All" else mg_pod_df

    if not mgmt_df.empty:
        st.markdown("---")
        def get_aggregated_summary(data, group_by_col):
            if group_by_col not in data.columns: return pd.DataFrame()
            summary = data.groupby(group_by_col).agg(
                Headcount=('EMP Id', 'count'),
                Avg_Rating=('Star Rating (1-5)', 'mean'),
                Avg_Prod=('Productivity (%)', 'mean'),
                Avg_Comp=('Compliance (%) QA', 'mean'),
                Avg_Att=('Attendance (%)', 'mean'),
                Avg_Perf=('Performance (%)', 'mean'),
                Avg_LOP=('Total LOP\'s Days', 'mean')
            ).reset_index()
            
            summary['🏆 Final Score (1-5)'] = (
                summary['Avg_Rating'] + (summary['Avg_Prod']/100*5) + (summary['Avg_Comp']/100*5) + 
                (summary['Avg_Att']/100*5) + (summary['Avg_Perf']/100*5) + (5 - summary['Avg_LOP'].clip(0,5))
            ) / 6
            
            return summary.round(2)
        
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["👔 TL Wise", "👔 AM Wise", "👔 CM Wise", "🚀 POD Leader Wise", "📍 Location Wise", "⚙️ Process Wise"])
        
        with tab1: st.dataframe(get_aggregated_summary(mgmt_df, "TL"), hide_index=True, use_container_width=True)
        with tab2: st.dataframe(get_aggregated_summary(mgmt_df, "AM"), hide_index=True, use_container_width=True)
        with tab3: st.dataframe(get_aggregated_summary(mgmt_df, "CM"), hide_index=True, use_container_width=True)
        with tab4: st.dataframe(get_aggregated_summary(mgmt_df, "POD_Leader"), hide_index=True, use_container_width=True)
        with tab5: st.dataframe(get_aggregated_summary(mgmt_df, "Center / Location"), hide_index=True, use_container_width=True)
        with tab6: st.dataframe(get_aggregated_summary(mgmt_df, "Process"), hide_index=True, use_container_width=True)
