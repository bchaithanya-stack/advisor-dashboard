import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import graphviz

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
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
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

# Ensure numeric parsing works correctly for downstream math
if "Team_Size" in df_org.columns:
    df_org["Team_Size"] = pd.to_numeric(df_org["Team_Size"], errors="coerce").fillna(0).astype(int)

# Expecting columns like:
# POD_Leader, POD_Leader_Title, Collection_Manager, Collection_Manager_Title,
# Assistant_Manager, Assistant_Manager_Title, Team_Lead, Team_Lead_Title,
# Name, Title/Process, Location, Team_Size
# Adjust the LEVEL_COLS list below to match your actual sheet headers.

# ---------------------------------------------------
# Sidebar Filtering Setup
# ---------------------------------------------------
st.sidebar.header("🔍 Structure Scope")

if "Location" in df_org.columns:
    locations = st.sidebar.multiselect("Filter Location", sorted(df_org["Location"].dropna().unique()))
else:
    locations = []

if "Process" in df_org.columns:
    processes = st.sidebar.multiselect("Filter Process", sorted(df_org["Process"].dropna().unique()))
else:
    processes = []

if "POD_Leader" in df_org.columns:
    processes = st.sidebar.multiselect("Filter POD_Leader", sorted(df_org["POD_Leader"].dropna().unique()))
else:
    processes = []

filtered_org = df_org.copy()
if locations:
    filtered_org = filtered_org[filtered_org["Location"].isin(locations)]
if processes:
    filtered_org = filtered_org[filtered_org["Process"].isin(processes)]
 if processes:
    filtered_org = filtered_org[filtered_org["POD_Leader"].isin(processes)]

if filtered_org.empty:
    st.warning("No structure paths match your selected filters.")
    st.stop()

# ---------------------------------------------------
# Card-Based Org Chart (Graphviz)
# ---------------------------------------------------
st.subheader("🗂️ Organization Hierarchy")

# Columns that define the reporting chain, from top to bottom.
# Each tuple is (name_column, title_column). Edit these to match your sheet.
LEVEL_COLS = [
    ("POD_Leader", "POD_Leader_Title"),
    ("Collection_Manager", "Collection_Manager_Title"),
    ("Assistant_Manager", "Assistant_Manager_Title"),
    ("Team_Lead", "Team_Lead_Title"),
]
# Final leaf level: the individual contributor / process row itself
LEAF_COL = ("Team_Lead", "Process")  # fallback if no separate "Name" column exists
if "Name" in filtered_org.columns:
    LEAF_COL = ("Name", "Process")


def build_hierarchy_edges(df: pd.DataFrame):
    """Walk each row and collect parent->child links plus node titles/counts."""
    edges = set()
    node_titles = {}
    node_counts = {}

    for _, row in df.iterrows():
        chain = []
        for name_col, title_col in LEVEL_COLS:
            if name_col in df.columns:
                name_val = str(row.get(name_col, "")).strip()
                title_val = str(row.get(title_col, "")).strip() if title_col in df.columns else ""
                if name_val and name_val.lower() != "nan":
                    chain.append((name_val, title_val))

        # Leaf node (the actual person / process on this row)
        leaf_name_col, leaf_title_col = LEAF_COL
        leaf_name = str(row.get(leaf_name_col, "")).strip()
        leaf_title = str(row.get(leaf_title_col, "")).strip() if leaf_title_col in df.columns else ""
        if leaf_name and leaf_name.lower() != "nan" and (not chain or leaf_name != chain[-1][0]):
            chain.append((leaf_name, leaf_title))

        # Register titles
        for name_val, title_val in chain:
            if name_val not in node_titles or not node_titles[name_val]:
                node_titles[name_val] = title_val

        # Register edges + headcount rollup at the last node
        for i in range(len(chain) - 1):
            edges.add((chain[i][0], chain[i + 1][0]))

        if chain:
            last_name = chain[-1][0]
            node_counts[last_name] = node_counts.get(last_name, 0) + int(row.get("Team_Size", 1) or 1)

    return edges, node_titles, node_counts


edges, node_titles, node_counts = build_hierarchy_edges(filtered_org)

if not edges and not node_titles:
    st.info("No hierarchy columns found matching LEVEL_COLS — update the column names in the script to match your sheet headers.")
else:
    dot = graphviz.Digraph()
    dot.attr(
        rankdir="TB",
        bgcolor="#0b0b2d",
        splines="ortho",
        nodesep="0.4",
        ranksep="0.9",
    )
    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fillcolor="#1b1b52",
        fontcolor="white",
        color="#e8a33d",
        penwidth="2",
        fontname="Helvetica",
        fontsize="12",
        margin="0.25,0.18",
    )
    dot.attr("edge", color="#8888c0", penwidth="1.4", arrowhead="none")

    all_nodes = set(node_titles.keys())
    for a, b in edges:
        all_nodes.add(a)
        all_nodes.add(b)

    for node in all_nodes:
        title = node_titles.get(node, "")
        count = node_counts.get(node)
        label_lines = [f"<B>{node}</B>"]
        if title:
            label_lines.append(f'<FONT POINT-SIZE="10" COLOR="#c9c9ee">{title}</FONT>')
        if count:
            label_lines.append(f'<FONT POINT-SIZE="10" COLOR="#e8a33d">Team size: {count}</FONT>')
        label = "<" + "<BR/>".join(label_lines) + ">"
        dot.node(node, label=label)

    for a, b in edges:
        dot.edge(a, b)

    st.graphviz_chart(dot, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Nested Team Breakdown Matrix Data View
# ---------------------------------------------------
st.subheader("📋 Drill-Down Matrix Details")

display_cols = [c for c in
                 ["Location", "POD_Leader", "Collection_Manager", "Assistant_Manager",
                  "Team_Lead", "Name", "Process", "Team_Size"]
                 if c in filtered_org.columns]

with st.expander("📄 View Operational Matrix Roster", expanded=True):
    sort_cols = [c for c in ["POD_Leader", "Collection_Manager"] if c in filtered_org.columns]
    display_df = filtered_org[display_cols]
    if sort_cols:
        display_df = display_df.sort_values(by=sort_cols)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
