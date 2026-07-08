import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------
st.set_page_config(
    page_title="Organization Structure",
    page_icon="🕸️",
    layout="wide"
)

# Premium Dark Theme CSS Matching your Roster Dashboard
st.markdown("""
<style>
.stApp { background: #0b0b2d; color: white; }
.main-title {
    background: #1b1b52; padding: 30px; border-radius: 18px;
    border: 1px solid #4b4bb8; box-shadow: 0 0 20px rgba(70,70,255,.15);
    margin-bottom: 25px;
}
.main-title h1 { color: white; margin: 0; font-size: 42px; font-weight: 700; }
section[data-testid="stSidebar"] { background: #10103a; }
.stMultiSelect div[data-baseweb="select"] { background: #1b1b52; border-radius: 10px; }
div[data-testid="stExpander"] { background: #1b1b52; border-radius: 10px; }
h1, h2, h3, h4 { color: white; }
label, p { color: #d8d8f5; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-title">
    <h1>🕸️ Operational Org Structure Chart</h1>
</div>
""", unsafe_allow_html=True)
st.markdown("---")

# ---------------------------------------------------
# Configurations & Connections
# ---------------------------------------------------
ORG_SHEET_ID = "1EBpgLKAdKmxe_oqkFL0iN4Jw9YHDqyEXRxB4zobVUeo"
CREDENTIALS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_data(ttl=15)
def load_org_data():
    creds = None
    if "gcp_service_account" in st.secrets:
        try:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
        except Exception:
            pass
            
    if creds is None:
        import os
        if os.path.exists(CREDENTIALS_FILE):
            creds = Credentials.from_service_account_info(CREDENTIALS_FILE, scopes=SCOPES)
        else:
            st.error("❌ Google Service Account Credentials not configured.")
            st.stop()

    try:
        client = gspread.authorize(creds)
        
        # Target the specific "Mapping" worksheet tab
        worksheet = client.open_by_key(ORG_SHEET_ID).worksheet("Mapping")
        
        # Fetch raw values as a list of lists to bypass strict duplicate header dictionary limitations
        raw_data = worksheet.get_all_values()
        
        if not raw_data:
            return pd.DataFrame()
            
        # Extract headers and data split rows
        headers = raw_data[0]
        data_rows = raw_data[1:]
        
        df = pd.DataFrame(data_rows, columns=headers)
        return df
        
    except Exception as e:
        st.error(f"❌ Connection Error: {str(e)}")
        st.stop()

# Load Data
df_org = load_org_data()

# Ensure numeric parsing works correctly for downstream visualization math
if "Team_Size" in df_org.columns:
    df_org["Team_Size"] = pd.to_numeric(df_org["Team_Size"], errors='coerce').fillna(0).astype(int)

# ---------------------------------------------------
# Sidebar Filtering Setup
# ---------------------------------------------------
st.sidebar.header("🔍 Structure Scope")

locations = st.sidebar.multiselect("Filter Location", sorted(df_org["Location"].dropna().unique()))
processes = st.sidebar.multiselect("Filter Process", sorted(df_org["Process"].dropna().unique()))

filtered_org = df_org.copy()
if locations:
    filtered_org = filtered_org[filtered_org["Location"].isin(locations)]
if processes:
    filtered_org = filtered_org[filtered_org["Process"].isin(processes)]

if filtered_org.empty:
    st.warning("No structure paths match your selected filters.")
    st.stop()

# ---------------------------------------------------
# Visual Hierarchy Tree View (Sunburst)
# ---------------------------------------------------
st.subheader("📊 Hierarchical Roll-Up (Headcount Weighting)")

# Build deep nesting pathway layout matching headers
fig_sunburst = px.sunburst(
    filtered_org,
    path=["POD_Leader", "Collection_Manager", "Assistant_Manager", "Team_Lead", "Process"],
    values="Team_Size",
    color="Location",
    color_discrete_sequence=px.colors.qualitative.Pastel
)

fig_sunburst.update_layout(
    height=600,
    paper_bgcolor="#1b1b52",
    plot_bgcolor="#1b1b52",
    font_color="white"
)
st.plotly_chart(fig_sunburst, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Nested Team Breakdown Matrix Data View
# ---------------------------------------------------
st.subheader("📋 Drill-Down Matrix Details")

with st.expander("📄 View Operational Matrix Roster", expanded=True):
    display_df = filtered_org[[
        "Location", "POD_Leader", "Collection_Manager", 
        "Assistant_Manager", "Process", "Team_Lead", "Team_Size"
    ]].sort_values(by=["POD_Leader", "Collection_Manager"])
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
