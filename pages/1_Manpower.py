import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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

# Premium Dark Theme CSS
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
        worksheet = client.open_by_key(ORG_SHEET_ID).worksheet("Mapping")
        raw_data = worksheet.get_all_values()
        
        if not raw_data:
            return pd.DataFrame()
            
        headers = raw_data[0]
        data_rows = raw_data[1:]
        
        df = pd.DataFrame(data_rows, columns=headers)
        return df
    except Exception as e:
        st.error(f"❌ Connection Error: {str(e)}")
        st.stop()

# Load Data
df_org = load_org_data()

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
# Building Node Relationships dynamically
# ---------------------------------------------------
st.subheader("🌲 Reporting Hierarchy Tree View")

ids = []
labels = []
parents = []

# Root Anchor
ids.append("Org Root")
labels.append("🏢 Company Scope")
parents.append("")

# Helper dictionary to prevent duplicate relationship registrations
seen_nodes = set()

for _, row in filtered_org.iterrows():
    pod = str(row["POD_Leader"]).strip()
    cm = str(row["Collection_Manager"]).strip()
    am = str(row["Assistant_Manager"]).strip()
    tl = str(row["Team_Lead"]).strip()
    proc = str(row["Process"]).strip()
    
    # Layer 1: Root to POD Leader
    if pod and pod not in seen_nodes:
        ids.append(pod)
        labels.append(f"👑 {pod}<br><span style='font-size:10px;color:#a0a0ff;'>POD Leader</span>")
        parents.append("Org Root")
        seen_nodes.add(pod)
        
    # Layer 2: POD Leader to Collection Manager
    cm_id = f"{pod}->{cm}"
    if cm and cm_id not in seen_nodes:
        ids.append(cm_id)
        labels.append(f"👔 {cm}<br><span style='font-size:10px;color:#bfbfff;'>Collection Mgr</span>")
        parents.append(pod)
        seen_nodes.add(cm_id)
        
    # Layer 3: Collection Manager to Assistant Manager
    am_id = f"{cm_id}->{am}"
    if am and am_id not in seen_nodes:
        ids.append(am_id)
        labels.append(f"💼 {am}<br><span style='font-size:10px;color:#dfdfff;'>Asst. Manager</span>")
        parents.append(cm_id)
        seen_nodes.add(am_id)
        
    # Layer 4: Assistant Manager to Team Lead
    tl_id = f"{am_id}->{tl}"
    if tl and tl_id not in seen_nodes:
        ids.append(tl_id)
        labels.append(f"👥 {tl}<br><span style='font-size:10px;color:#ffffff;'>Team Lead</span>")
        parents.append(am_id)
        seen_nodes.add(tl_id)

    # Layer 5: Team Lead to Operational Process Node
    proc_id = f"{tl_id}->{proc}"
    if proc and proc_id not in seen_nodes:
        ids.append(proc_id)
        labels.append(f"⚙️ {proc}<br><span style='font-size:10px;color:#ffd700;'>Size: {row['Team_Size']}</span>")
        parents.append(tl_id)
        seen_nodes.add(proc_id)

# Render Node Tree Layout Map via Plotly Graph Objects Icicle Tiling Engine
fig_tree = go.Figure(go.Icicle(
    ids=ids,
    labels=labels,
    parents=parents,
    root_color="#10103a",
    tiling=dict(orientation="v")
))

fig_tree.update_layout(
    height=650,
    margin=dict(t=10, b=10, r=10, l=10),
    paper_bgcolor="#1b1b52",
    font_color="white"
)

fig_tree.update_traces(
    marker=dict(line=dict(width=2, color='#4b4bb8')),
    pathbar=dict(visible=False)
)

st.plotly_chart(fig_tree, use_container_width=True)

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

```
