import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go

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
# Build parent -> child edges walking the hierarchy row by row.
# Node keys are "ColumnName::Value" so identical names at different
# levels never collide.
# ---------------------------------------------------
def build_hierarchy(df: pd.DataFrame):
    edges = set()
    node_counts = {}
    node_members = {}  # key -> set of downstream member names (for hover)

    for _, row in df.iterrows():
        chain = []
        for col in LEVEL_COLS:
            val = str(row.get(col, "")).strip()
            if val and val.lower() != "nan":
                chain.append(f"{col}::{val}")

        for i in range(len(chain) - 1):
            edges.add((chain[i], chain[i + 1]))

        team_size = int(row.get(COL_SIZE, 0) or 0)
        member_name = str(row.get("Name", "")).strip() if "Name" in df.columns else ""

        for key in chain:
            node_counts[key] = node_counts.get(key, 0) + team_size
            node_members.setdefault(key, set())
            if member_name and member_name.lower() != "nan":
                node_members[key].add(member_name)
            elif chain:
                node_members[key].add(chain[-1].split("::", 1)[1])

    return edges, node_counts, node_members


edges, node_counts, node_members = build_hierarchy(filtered_org)

parent_children = {}
for a, b in edges:
    parent_children.setdefault(a, set()).add(b)

all_nodes = set()
for a, b in edges:
    all_nodes.add(a)
    all_nodes.add(b)

all_children = {b for a, b in edges}
roots = sorted(all_nodes - all_children)

# ---------------------------------------------------
# Layout: x from column order. y is computed in two passes —
# an initial bottom-up average, then a per-column collision pass
# (deepest column first) so nodes that share a child (e.g. two
# Locations feeding the same CM) never land on the exact same y
# and overlap.
# ---------------------------------------------------
col_index = {col: i for i, col in enumerate(LEVEL_COLS)}

# Pass 1: rough leaf ordering (stable left-to-right order only)
y_raw = {}
leaf_counter = [0]


def compute_raw(node):
    if node in y_raw:
        return y_raw[node]
    children = sorted(parent_children.get(node, []))
    if not children:
        y = float(leaf_counter[0])
        leaf_counter[0] += 1
    else:
        ys = [compute_raw(c) for c in children]
        y = sum(ys) / len(ys)
    y_raw[node] = y
    return y


for r in roots:
    compute_raw(r)
for n in all_nodes:
    if n not in y_raw:
        compute_raw(n)

# Pass 2: column-by-column, deepest to shallowest, enforce a minimum
# gap between siblings in the same column so nothing overlaps.
from collections import defaultdict as _defaultdict

columns_by_index = _defaultdict(list)
for n in all_nodes:
    col_name = n.split("::", 1)[0]
    columns_by_index[col_index.get(col_name, 0)].append(n)

max_col_idx = max(columns_by_index.keys()) if columns_by_index else 0
y_final = {}
MIN_GAP = 1.0

for col in range(max_col_idx, -1, -1):
    nodes_in_col = columns_by_index.get(col, [])
    if not nodes_in_col:
        continue

    def _raw_for(n):
        children = parent_children.get(n, [])
        if children:
            return sum(y_final[c] for c in children) / len(children)
        return y_raw[n]

    nodes_sorted = sorted(nodes_in_col, key=lambda n: (_raw_for(n), n))
    prev_y = None
    for n in nodes_sorted:
        candidate = _raw_for(n)
        y_final[n] = candidate if prev_y is None else max(candidate, prev_y + MIN_GAP)
        prev_y = y_final[n]

X_SPACING = 300
Y_SPACING = 70
positions = {}
for node in all_nodes:
    col_name = node.split("::", 1)[0]
    x = col_index.get(col_name, 0) * X_SPACING
    y = y_final[node] * Y_SPACING
    positions[node] = (x, y)


def wrap_label(name, max_chars=20):
    """Wrap long names onto a second line at the nearest space instead of truncating."""
    if len(name) <= max_chars:
        return name, False
    mid = len(name) // 2
    left_space = name.rfind(" ", 0, mid)
    right_space = name.find(" ", mid)
    split_at = left_space if left_space != -1 else right_space
    if split_at is None or split_at == -1:
        return name, False
    return name[:split_at] + "<br>" + name[split_at + 1:], True



# ---------------------------------------------------
# Build the Plotly figure: rectangles for boxes, lines for connectors,
# invisible markers on top of each box for hover tooltips.
# ---------------------------------------------------
st.subheader("🗂️ Organization Hierarchy (Horizontal)")

BOX_W, BOX_H = 260, 46
BOX_H_WRAPPED = 64
level_colors = ["#e8a33d", "#3ac6a0", "#4b8bf5", "#7a5cf0", "#2a6f97", "#f06a6a"]

shapes = []
annotations = []
hover_x, hover_y, hover_text_list = [], [], []

for node in all_nodes:
    x, y = positions[node]
    col_name, name = node.split("::", 1)
    color = level_colors[col_index.get(col_name, 0) % len(level_colors)]

    label, wrapped = wrap_label(name)
    box_h = BOX_H_WRAPPED if wrapped else BOX_H

    shapes.append(dict(
        type="rect",
        x0=x - BOX_W / 2, x1=x + BOX_W / 2,
        y0=y - box_h / 2, y1=y + box_h / 2,
        line=dict(color="#1b4965", width=2),
        fillcolor=color,
        layer="above",
    ))

    count = node_counts.get(node, 0)
    sub = f"<br><span style='font-size:10px'>Team size: {count}</span>" if count else ""
    annotations.append(dict(
        x=x, y=y,
        text=f"<b>{label}</b>{sub}",
        showarrow=False,
        font=dict(color="white", size=12),
        align="center",
    ))

    members = sorted(node_members.get(node, []))
    hover_lines = members[:25]
    hover_str = "<br>".join(hover_lines) if hover_lines else "No members"
    if len(members) > 25:
        hover_str += f"<br>...and {len(members) - 25} more"

    hover_x.append(x)
    hover_y.append(y)
    hover_text_list.append(f"<b>{name}</b><br>Team size: {count}<br>{hover_str}")

edge_x, edge_y = [], []
for a, b in edges:
    xa, ya = positions[a]
    xb, yb = positions[b]
    edge_x += [xa + BOX_W / 2, xb - BOX_W / 2, None]
    edge_y += [ya, yb, None]

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=edge_x, y=edge_y,
    mode="lines",
    line=dict(color="#8fb8de", width=1.6),
    hoverinfo="skip",
    showlegend=False,
))

fig.add_trace(go.Scatter(
    x=hover_x, y=hover_y,
    mode="markers",
    marker=dict(size=1, color="rgba(0,0,0,0)"),
    hovertext=hover_text_list,
    hoverinfo="text",
    showlegend=False,
))

fig.update_layout(shapes=shapes, annotations=annotations)

max_x = max((p[0] for p in positions.values()), default=0)
max_y = max((p[1] for p in positions.values()), default=0)

fig.update_xaxes(visible=False, range=[-BOX_W, max_x + BOX_W])
fig.update_yaxes(visible=False, range=[-BOX_H, max_y + BOX_H], scaleanchor=None)
fig.update_layout(
    height=max(500, int(max_y) + 150),
    paper_bgcolor="#0b0b2d",
    plot_bgcolor="#0b0b2d",
    margin=dict(l=20, r=20, t=20, b=20),
)

st.plotly_chart(fig, use_container_width=True)
st.caption("Hover over any box to see downstream member names and team size.")

st.markdown("---")

# ---------------------------------------------------
# Underlying detail rows
# ---------------------------------------------------
st.subheader("📋 Underlying Roster")

detail_cols = [c for c in LEVEL_COLS + [COL_SIZE] if c in filtered_org.columns]
st.dataframe(filtered_org[detail_cols], use_container_width=True, hide_index=True)
