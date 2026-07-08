import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------
st.set_page_config(
    page_title="Hierarchy Rollup Summary",
    page_icon="🧮",
    layout="wide"
)

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
.stSelectbox div[data-baseweb="select"] { background: #1b1b52; border-radius: 10px; }
h1, h2, h3, h4 { color: white; }
label, p { color: #d8d8f5; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-title">
    <h1>🧮 POD / CM / AM / TL Rollup Summary</h1>
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
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
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


df_org = load_org_data()

if "Team_Size" in df_org.columns:
    df_org["Team_Size"] = pd.to_numeric(df_org["Team_Size"], errors="coerce").fillna(0).astype(int)

# ---------------------------------------------------
# Column mapping — edit these to match your "Mapping" tab headers exactly
# ---------------------------------------------------
COL_POD = "POD_Leader"
COL_CM = "Collection_Manager"
COL_AM = "Assistant_Manager"
COL_TL = "Team_Lead"
COL_SIZE = "Team_Size"

required_cols = [COL_POD, COL_CM, COL_AM, COL_TL, COL_SIZE]
missing = [c for c in required_cols if c not in df_org.columns]
if missing:
    st.error(f"❌ Missing expected column(s) in the sheet: {missing}. "
             f"Update COL_POD / COL_CM / COL_AM / COL_TL / COL_SIZE at the top of the script to match your headers.")
    st.stop()

# ---------------------------------------------------
# Sidebar: choose scope level and specific entity
# ---------------------------------------------------
st.sidebar.header("🔍 Rollup Scope")

view_level = st.sidebar.radio(
    "View by",
    ["POD Leader wise", "Collection Manager wise", "Assistant Manager wise", "Team Lead wise"]
)

level_col_map = {
    "POD Leader wise": COL_POD,
    "Collection Manager wise": COL_CM,
    "Assistant Manager wise": COL_AM,
    "Team Lead wise": COL_TL,
}
scope_col = level_col_map[view_level]

entity_options = sorted(df_org[scope_col].dropna().unique())
entity_options = [e for e in entity_options if str(e).strip() and str(e).lower() != "nan"]

selected_entity = st.sidebar.selectbox(f"Select {scope_col.replace('_', ' ')}", entity_options)

scoped_df = df_org[df_org[scope_col] == selected_entity]

if scoped_df.empty:
    st.warning("No data found for this selection.")
    st.stop()

# ---------------------------------------------------
# Build funnel steps depending on the chosen level
# (mirrors the whiteboard: POD_leader -> No.of CM's -> No.of AM's -> No.of TL's -> Total Size)
# ---------------------------------------------------
funnel_labels = []
funnel_values = []

def nunique_clean(series):
    return series.dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique()

if scope_col == COL_POD:
    funnel_labels = [
        f"POD Leader: {selected_entity}",
        "No. of CM's",
        "No. of AM's",
        "No. of TL's",
        "Total Size",
    ]
    funnel_values = [
        1,
        nunique_clean(scoped_df[COL_CM]),
        nunique_clean(scoped_df[COL_AM]),
        nunique_clean(scoped_df[COL_TL]),
        int(scoped_df[COL_SIZE].sum()),
    ]

elif scope_col == COL_CM:
    funnel_labels = [
        f"CM: {selected_entity}",
        "No. of AM's",
        "No. of TL's",
        "Total Size",
    ]
    funnel_values = [
        1,
        nunique_clean(scoped_df[COL_AM]),
        nunique_clean(scoped_df[COL_TL]),
        int(scoped_df[COL_SIZE].sum()),
    ]

elif scope_col == COL_AM:
    funnel_labels = [
        f"AM: {selected_entity}",
        "No. of TL's",
        "Total Size",
    ]
    funnel_values = [
        1,
        nunique_clean(scoped_df[COL_TL]),
        int(scoped_df[COL_SIZE].sum()),
    ]

else:  # Team Lead wise — bottom of the hierarchy, just the headcount under this TL
    funnel_labels = [
        f"TL: {selected_entity}",
        "Total Size",
    ]
    funnel_values = [
        1,
        int(scoped_df[COL_SIZE].sum()),
    ]

# ---------------------------------------------------
# Funnel chart
# ---------------------------------------------------
st.subheader(f"📉 Rollup Funnel — {view_level}: {selected_entity}")

fig = go.Figure(go.Funnel(
    y=funnel_labels,
    x=funnel_values,
    textinfo="value+text",
    marker=dict(color=["#e8a33d", "#4b8bf5", "#7a5cf0", "#3ac6a0", "#f06a6a"][:len(funnel_labels)]),
    connector=dict(line=dict(color="#8888c0", width=2)),
))

fig.update_layout(
    height=500,
    paper_bgcolor="#0b0b2d",
    plot_bgcolor="#0b0b2d",
    font_color="white",
    margin=dict(l=20, r=20, t=20, b=20),
)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------
# Metrics row (quick glance numbers)
# ---------------------------------------------------
cols = st.columns(len(funnel_labels))
for c, label, value in zip(cols, funnel_labels, funnel_values):
    c.metric(label, value)

st.markdown("---")

# ---------------------------------------------------
# Underlying detail rows for this scope
# ---------------------------------------------------
st.subheader("📋 Underlying Roster for this Scope")

detail_cols = [c for c in [COL_POD, COL_CM, COL_AM, COL_TL, COL_SIZE] if c in scoped_df.columns]
st.dataframe(scoped_df[detail_cols], use_container_width=True, hide_index=True)
