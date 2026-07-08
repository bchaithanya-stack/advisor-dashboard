import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import graphviz

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------
st.set_page_config(
    page_title="Horizontal Tree Hierarchy",
    page_icon="🌳",
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
.stMultiSelect div[data-baseweb="select"] { background: #1b1b52; border-radius: 10px; }
h1, h2, h3, h4 { color: white; }
label, p { color: #d8d8f5; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-title">
    <h1>🌳 Horizontal Tree Hierarchy</h1>
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
# Order here = order of the tree, left to right (matches the reference photo:
# POD_Leader -> Location -> CM -> AM -> TL)
# ---------------------------------------------------
COL_POD = "POD_Leader"
COL_LOCATION = "Location"
COL_CM = "Collection_Manager"
COL_AM = "Assistant_Manager"
COL_TL = "Team_Lead"
COL_SIZE = "Team_Size"

LEVEL_COLS = [c for c in [COL_POD, COL_LOCATION, COL_CM, COL_AM, COL_TL] if c in df_org.columns]

if not LEVEL_COLS:
    st.error("❌ None of the expected hierarchy columns were found. "
             "Update COL_POD / COL_LOCATION / COL_CM / COL_AM / COL_TL at the top of the script.")
    st.stop()

# ---------------------------------------------------
# Sidebar Filtering Setup
# ---------------------------------------------------
st.sidebar.header("🔍 Structure Scope")

pod_filter = []
if COL_POD in df_org.columns:
    pod_filter = st.sidebar.multiselect("Filter POD Leader", sorted(df_org[COL_POD].dropna().unique()))

location_filter = []
if COL_LOCATION in df_org.columns:
    location_filter = st.sidebar.multiselect("Filter Location", sorted(df_org[COL_LOCATION].dropna().unique()))

filtered_org = df_org.copy()
if pod_filter:
    filtered_org = filtered_org[filtered_org[COL_POD].isin(pod_filter)]
if location_filter:
    filtered_org = filtered_org[filtered_org[COL_LOCATION].isin(location_filter)]

if filtered_org.empty:
    st.warning("No structure paths match your selected filters.")
    st.stop()

# ---------------------------------------------------
# Build parent -> child edges walking the hierarchy row by row
# ---------------------------------------------------
def build_hierarchy_edges(df: pd.DataFrame):
    edges = set()
    node_counts = {}  # rollup of Team_Size at the deepest node reached per row

    for _, row in df.iterrows():
        chain = []
        for col in LEVEL_COLS:
            val = str(row.get(col, "")).strip()
            if val and val.lower() != "nan":
                # Prefix with column name to avoid collisions between identical
                # names appearing at different levels (e.g. a location and a person sharing a name)
                chain.append((col, val))

        for i in range(len(chain) - 1):
            parent_key = f"{chain[i][0]}::{chain[i][1]}"
            child_key = f"{chain[i + 1][0]}::{chain[i + 1][1]}"
            edges.add((parent_key, child_key))

        if chain:
            last_key = f"{chain[-1][0]}::{chain[-1][1]}"
            node_counts[last_key] = node_counts.get(last_key, 0) + int(row.get(COL_SIZE, 1) or 1)

    return edges, node_counts


edges, node_counts = build_hierarchy_edges(filtered_org)

# ---------------------------------------------------
# Render horizontal (left-to-right) tree
# ---------------------------------------------------
st.subheader("🗂️ Organization Hierarchy (Horizontal)")

dot = graphviz.Digraph()
dot.attr(
    rankdir="LR",
    bgcolor="#0b0b2d",
    splines="line",
    nodesep="0.35",
    ranksep="1.0",
)
dot.attr(
    "node",
    shape="box",
    style="rounded,filled",
    fillcolor="#2a6f97",
    fontcolor="white",
    color="#1b4965",
    penwidth="2",
    fontname="Helvetica",
    fontsize="13",
    margin="0.3,0.2",
)
dot.attr("edge", color="#8fb8de", penwidth="1.6", arrowhead="none")

all_node_keys = set()
for a, b in edges:
    all_node_keys.add(a)
    all_node_keys.add(b)

for key in all_node_keys:
    col, name = key.split("::", 1)
    count = node_counts.get(key)
    label_lines = [f"<B>{name}</B>"]
    if count:
        label_lines.append(f'<FONT POINT-SIZE="10" COLOR="#dff0ff">Team size: {count}</FONT>')
    label = "<" + "<BR/>".join(label_lines) + ">"
    dot.node(key, label=label)

for a, b in edges:
    dot.edge(a, b)

st.graphviz_chart(dot, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Underlying detail rows
# ---------------------------------------------------
st.subheader("📋 Underlying Roster")

detail_cols = [c for c in LEVEL_COLS + [COL_SIZE] if c in filtered_org.columns]
st.dataframe(filtered_org[detail_cols], use_container_width=True, hide_index=True)
