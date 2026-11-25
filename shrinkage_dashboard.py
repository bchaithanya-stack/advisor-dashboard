import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------
st.set_page_config(
    page_title="DPDzero Shrinkage Dashboard",
    page_icon="📉",
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
📉 DPDzero Shrinkage Dashboard
</h1>
<p style="color:#B8BCFF;">
Roster vs Attendance &amp; Shrinkage Analytics
</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.stApp { background: linear-gradient(180deg,#090a2f,#070726); color:white; }
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}

/* Hide sidebar and the multipage nav (Manpower / Rostering etc.) */
section[data-testid="stSidebar"] {display:none;}
[data-testid="stSidebarNav"] {display:none;}
[data-testid="collapsedControl"] {display:none;}

.stButton>button{ background:#5b5ef7; color:white; border:none; border-radius:10px; padding:10px; font-weight:600; }
.stButton>button:hover{ background:#7b7eff; }
.stSelectbox div[data-baseweb="select"]{ background:#17194c; color:white; }
.stMultiSelect div[data-baseweb="select"]{ background:#17194c; color:white; }
.stMultiSelect span[data-baseweb="tag"]{ background:#5b5ef7; color:white; }
[data-testid="stDataFrame"]{ background:#151846; border-radius:15px; }
.streamlit-expanderHeader{ background:#1d2057; border-radius:10px; }
h1{ color:white; font-weight:700; }
h2,h3{ color:#cfd2ff; }
</style>
""", unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------
# Config
# ---------------------------------------------------
SHEET_ID = "1zBPCx0rP7yVjXl5MVn5ZlQHZa81SeT5P7PTZ3Z2SqBc"   # ID from the sheet URL (between /d/ and /edit)
SHEET_TAB = "Main"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

EXPECTED_COLS = [
    "EMP ID", "Name", "Email ID", "Date", "DOJ", "TL", "AM", "CM", "Final",
    "POD Leader", "Location", "Lender", "Active Status", "Roster Status",
    "Attendance Status", "Roster Count", "Attendance Count", "Shrinkage %",
]

PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#090a2f",
    plot_bgcolor="#090a2f",
    font=dict(color="white"),
)


# ---------------------------------------------------
# Helper — KPI Card
# ---------------------------------------------------
def card(title, value):
    st.markdown(f"""
<div style="
background:#17194c; padding:20px; border-radius:18px; border:1px solid #545eff;
text-align:center; box-shadow:0px 0px 15px rgba(120,120,255,.2); height:150px;
width:100%; display:flex; flex-direction:column; justify-content:center;
align-items:center; box-sizing:border-box;
">
<p style="font-size:13px;color:#9da2ff;margin:0;padding:0;">{title}</p>
<h1 style="color:white;margin:8px 0 0 0;padding:0;font-size:30px;">{value}</h1>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------
# Load Data
# ---------------------------------------------------
@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES,
        )
        client = gspread.authorize(creds)
        ws = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)

        # get_all_values avoids header-duplicate errors from blank/helper columns
        values = ws.get_all_values()
        if len(values) < 2:
            st.error("❌ No data found in the sheet.")
            st.stop()

        headers = [str(h).strip().replace("\n", " ") for h in values[0]]
        df = pd.DataFrame(values[1:], columns=headers)

        # Keep only the real data columns (drops blank / helper columns like TEXTJOIN in Z1)
        keep = [c for c in EXPECTED_COLS if c in df.columns]
        df = df[keep].copy()

        missing = [c for c in ["Date", "Roster Count", "Attendance Count"] if c not in df.columns]
        if missing:
            st.error(f"❌ Missing required column(s): {', '.join(missing)}. "
                     f"Found: {', '.join(df.columns)}")
            st.stop()

        # Clean types
        df["Date"] = pd.to_datetime(df["Date"], format="%d %b %Y", errors="coerce")
        if df["Date"].isna().all():
            df["Date"] = pd.to_datetime(values_to_series(values, headers, "Date"),
                                        dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Date"])

        for col in ["Roster Count", "Attendance Count"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        for col in ["TL", "AM", "CM", "Final", "POD Leader", "Location", "Lender",
                    "Active Status", "Name"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        return df

    except Exception as e:
        st.error(f"❌ Error loading data: {type(e).__name__}: {e!r}")
        if type(e).__name__ == "SpreadsheetNotFound":
            st.info("The sheet isn't shared with the service account (or the sheet ID is wrong). "
                    "Share it with advisor-dashboard@advisor-dashboard-500613.iam.gserviceaccount.com as Viewer.")
        elif type(e).__name__ == "WorksheetNotFound":
            st.info(f"No tab named '{SHEET_TAB}' was found in the sheet. Check the tab name.")
        elif type(e).__name__ == "KeyError":
            st.info("Secrets look missing: add [gcp_service_account] in the app's Settings → Secrets.")
        st.stop()


def values_to_series(values, headers, col):
    idx = headers.index(col)
    return pd.Series([row[idx] if idx < len(row) else "" for row in values[1:]])


def shrinkage(roster, attendance):
    return ((roster - attendance) / roster * 100).where(roster > 0, 0).round(2)


# ---------------------------------------------------
# Refresh
# ---------------------------------------------------
_, col_refresh = st.columns([5, 1])
with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

df = load_data()

# ---------------------------------------------------
# Filters (cascading)
# ---------------------------------------------------
st.subheader("🔍 Filters")

filtered = df.copy()


active_filters = {}   # column -> list of chosen values (used for the PowerPoint footer)


def cascade_select(label, column, container, key):
    """Multiselect whose options depend on filters applied so far. Nothing selected = All."""
    global filtered
    if column not in filtered.columns:
        return []
    options = sorted([x for x in filtered[column].dropna().unique() if x != ""])

    # Drop previously selected values that are no longer valid after upstream filters change
    if key in st.session_state:
        st.session_state[key] = [v for v in st.session_state[key] if v in options]

    with container:
        choice = st.multiselect(label, options, key=key, placeholder="All")
    if choice:
        filtered = filtered[filtered[column].isin(choice)]
        active_filters[column] = choice
    return choice


r1 = st.columns(4)
cascade_select("🔹 Location:", "Location", r1[0], "f_loc")
cascade_select("🔹 Process (Final):", "Final", r1[1], "f_final")
cascade_select("🔹 POD Leader:", "POD Leader", r1[2], "f_pod")
cascade_select("🔹 CM:", "CM", r1[3], "f_cm")

r2 = st.columns(4)
cascade_select("🔹 AM:", "AM", r2[0], "f_am")
cascade_select("🔹 TL:", "TL", r2[1], "f_tl")
cascade_select("🔹 Active Status:", "Active Status", r2[2], "f_active")
cascade_select("🔹 Lender:", "Lender", r2[3], "f_lender")

r3 = st.columns(4)
min_d, max_d = df["Date"].min().date(), df["Date"].max().date()
with r3[0]:
    date_range = st.date_input("🔹 Date Range:", value=(min_d, max_d),
                               min_value=min_d, max_value=max_d, key="f_date")

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[(filtered["Date"].dt.date >= start) & (filtered["Date"].dt.date <= end)]

st.markdown("---")

if filtered.empty:
    st.warning("⚠️ No data matches the selected filters.")
    st.stop()

# ---------------------------------------------------
# Day-level aggregation
# ---------------------------------------------------
daily = (
    filtered.groupby("Date")
    .agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
    .reset_index()
    .sort_values("Date")
)
daily["Shrinkage %"] = shrinkage(daily["Roster"], daily["Attendance"])

total_roster = daily["Roster"].sum()
total_att = daily["Attendance"].sum()
overall_shrink = ((total_roster - total_att) / total_roster * 100) if total_roster > 0 else 0

# ---------------------------------------------------
# KPI Cards
# ---------------------------------------------------
st.subheader("📈 Summary")

c1, c2, c3, c4, c5 = st.columns(5)
with c1: card("📉 Overall Shrinkage %", f"{overall_shrink:.2f}%")
with c2: card("📅 Avg Daily Shrinkage %", f"{daily['Shrinkage %'].mean():.2f}%")
with c3: card("👥 Avg Daily Roster", f"{daily['Roster'].mean():.1f}")
with c4: card("✅ Avg Daily Attendance", f"{daily['Attendance'].mean():.1f}")
with c5: card("🧑‍💼 Advisors in View", filtered["EMP ID"].nunique() if "EMP ID" in filtered.columns else "-")

st.markdown("---")

# ---------------------------------------------------
# Chart 1 — Day-level Shrinkage %
# ---------------------------------------------------
st.subheader("📉 Day-Level Shrinkage %")

fig1 = px.line(daily, x="Date", y="Shrinkage %", markers=True)
fig1.update_traces(line_color="#7f63ff", marker=dict(size=8))
fig1.update_layout(**PLOT_LAYOUT, height=420, yaxis_title="Shrinkage %")
st.plotly_chart(fig1, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Chart 2 — Day-level Roster vs Attendance
# ---------------------------------------------------
st.subheader("👥 Day-Level Projected Present (Roster) vs Actual Present (Attendance)")

fig2 = go.Figure()
fig2.add_bar(x=daily["Date"], y=daily["Roster"], name="Projected Present (Roster)",
             marker_color="#5b5ef7")
fig2.add_bar(x=daily["Date"], y=daily["Attendance"], name="Actual Present (Attendance)",
             marker_color="#38d9a9")
fig2.update_layout(**PLOT_LAYOUT, height=420, barmode="group", yaxis_title="Headcount",
                   legend=dict(orientation="h", y=1.1))
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Chart 3 — Day-level Shrinkage % by Process / TL / CM / Lender
# ---------------------------------------------------
st.subheader("📉 Day-Level Shrinkage % — Process / TL / CM / Lender")


def day_level_by(dim, label, key):
    """One line per `dim` value, x = Date, y = Shrinkage %."""
    if dim not in filtered.columns:
        st.info(f"Column '{dim}' was not found in the sheet.")
        return

    g = (
        filtered.groupby(["Date", dim])
        .agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
        .reset_index()
    )
    g = g[(g["Roster"] > 0) & (g[dim] != "")]      # skip days with nobody rostered
    g["Shrinkage %"] = shrinkage(g["Roster"], g["Attendance"])

    if g.empty:
        st.warning(f"No rostered data available for {label}.")
        return

    options = g.groupby(dim)["Roster"].sum().sort_values(ascending=False).index.tolist()
    selected = st.multiselect(
        f"Select {label} to plot (top 8 by roster size shown by default):",
        options, default=options[:8], key=key,
    )
    if not selected:
        st.warning(f"Select at least one {label}.")
        return

    plot_df = g[g[dim].isin(selected)].sort_values("Date")

    fig = px.line(plot_df, x="Date", y="Shrinkage %", color=dim, markers=True)
    fig.update_layout(**PLOT_LAYOUT, height=460, yaxis_title="Shrinkage %",
                      legend_title_text=label)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander(f"📄 {label} × Date table (Shrinkage %)"):
        pivot = plot_df.pivot_table(index=dim, columns="Date", values="Shrinkage %")
        pivot.columns = [d.strftime("%d %b") for d in pivot.columns]
        st.dataframe(pivot, use_container_width=True)


tab_proc, tab_tl, tab_cm, tab_lender = st.tabs(["🏭 Process", "👔 TL", "🧑‍💼 CM", "🏦 Lender"])

with tab_proc:
    day_level_by("Final", "Process", "dl_proc")
with tab_tl:
    day_level_by("TL", "TL", "dl_tl")
with tab_cm:
    day_level_by("CM", "CM", "dl_cm")
with tab_lender:
    day_level_by("Lender", "Lender", "dl_lender")

st.markdown("---")

# ---------------------------------------------------
# Chart 4 — Shrinkage by chosen dimension
# ---------------------------------------------------
st.subheader("📊 Shrinkage % Breakdown")

dim_options = [c for c in ["TL", "AM", "CM", "POD Leader", "Location", "Lender", "Final"]
               if c in filtered.columns]
dim = st.selectbox("Break down by:", dim_options, key="breakdown_dim")

by_dim = (
    filtered.groupby(dim)
    .agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
    .reset_index()
)
by_dim["Shrinkage %"] = shrinkage(by_dim["Roster"], by_dim["Attendance"])
by_dim = by_dim[by_dim["Roster"] > 0].sort_values("Shrinkage %", ascending=False)

fig3 = px.bar(by_dim, x=dim, y="Shrinkage %", text="Shrinkage %",
              color="Shrinkage %", color_continuous_scale="Purples")
fig3.update_traces(texttemplate="%{text:.1f}%")
fig3.update_layout(**PLOT_LAYOUT, height=420, coloraxis_showscale=False)
st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Chart 5 — Attendance Count by chosen dimension
# ---------------------------------------------------
st.subheader("✅ Attendance Count Breakdown")

att_dim = st.selectbox("Break down by:", dim_options, key="att_breakdown_dim")

by_att = (
    filtered.groupby(att_dim)
    .agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
    .reset_index()
)
by_att = by_att[(by_att[att_dim] != "") & (by_att["Attendance"] >= 0)]
by_att = by_att.sort_values("Attendance", ascending=False)

fig_att = px.bar(by_att, x=att_dim, y="Attendance", text="Attendance",
                 color="Attendance", color_continuous_scale="Teal")
fig_att.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
fig_att.update_layout(**PLOT_LAYOUT, height=420, yaxis_title="Attendance Count",
                      coloraxis_showscale=False)
st.plotly_chart(fig_att, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Chart 6 — Overall Count Breakdown (starts from Active Headcount)
# ---------------------------------------------------
st.subheader("🧮 Overall Count Breakdown")
st.caption("Starts from Active Headcount (advisor-days where Active Status = Active), then splits it into "
           "Rostered / Week Off and Present / Absent. Absent = active and Attendance Count = 0, irrespective of roster.")

ACTIVE_VALUE = "active"     # matches Active Status == "Active" (case-insensitive; "Inactive" is excluded)

COUNT_COLS = ["Rostered", "Week Off", "Present", "Absent (Attendance = 0)",
              "Present (Not Rostered)"]

cnt_df = filtered.copy()
if "Active Status" in cnt_df.columns:
    _act = cnt_df["Active Status"].astype(str).str.strip().str.lower().eq(ACTIVE_VALUE)
else:
    _act = pd.Series(True, index=cnt_df.index)     # no Active Status column -> treat everyone as active
_r = cnt_df["Roster Count"] > 0
_a = cnt_df["Attendance Count"] > 0
_zero = cnt_df["Attendance Count"] == 0

cnt_df["Active Headcount"] = _act.astype(int)
cnt_df["Rostered"] = (_act & _r).astype(int)
cnt_df["Week Off"] = (_act & ~_r).astype(int)
cnt_df["Present"] = (_act & _a).astype(int)
cnt_df["Absent (Attendance = 0)"] = (_act & _zero).astype(int)
cnt_df["Present (Not Rostered)"] = (_act & ~_r & _a).astype(int)

k1, k2, k3, k4, k5 = st.columns(5)
with k1: card("👥 Active Headcount", f"{int(cnt_df['Active Headcount'].sum()):,}")
with k2: card("🗓️ Rostered", f"{int(cnt_df['Rostered'].sum()):,}")
with k3: card("🛌 Week Off", f"{int(cnt_df['Week Off'].sum()):,}")
with k4: card("✅ Present", f"{int(cnt_df['Present'].sum()):,}")
with k5: card("❌ Absent (Attendance = 0)", f"{int(cnt_df['Absent (Attendance = 0)'].sum()):,}")

cnt_dim = st.selectbox("Break down by:", dim_options, key="count_breakdown_dim")

by_cnt = (
    cnt_df[cnt_df[cnt_dim] != ""]
    .groupby(cnt_dim)[["Active Headcount"] + COUNT_COLS]
    .sum()
    .reset_index()
    .sort_values("Active Headcount", ascending=False)
)

plot_cols = ["Active Headcount", "Rostered", "Week Off", "Present", "Absent (Attendance = 0)"]
cnt_long = by_cnt.melt(id_vars=cnt_dim, value_vars=plot_cols, var_name="Category", value_name="Count")

fig_cnt = px.bar(
    cnt_long, x=cnt_dim, y="Count", color="Category", barmode="group", text="Count",
    category_orders={"Category": plot_cols},
    color_discrete_map={
        "Active Headcount": "#b8bcff",
        "Rostered": "#5b5ef7",
        "Week Off": "#8d92b8",
        "Present": "#38d9a9",
        "Absent (Attendance = 0)": "#ff6b6b",
    },
)
fig_cnt.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
fig_cnt.update_layout(**PLOT_LAYOUT, height=460, yaxis_title="Count",
                      legend=dict(orientation="h", y=1.12, title_text=""))
st.plotly_chart(fig_cnt, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Chart 7 — Advisor-wise Attendance Summary (every advisor in view)
# ---------------------------------------------------
st.subheader("👤 Advisor-wise Attendance Summary")
st.caption("One row per advisor. Attendance Status codes are grouped as: Present = Present / NA / New · "
           "Leave = ML / CO / PL / SL / EL · Absent = LOP · plus HalfDay, WO (Week Off) and Holiday as they are. "
           "Working Days = Present + 0.5 × HalfDay. Roster Days = days with Roster Count > 0.")

# Attendance Status (upper-case) -> group used in this table
STATUS_MAP = {
    "HOLIDAY": "Holiday", "PRESENT": "Present", "WO": "Week Off",
    "HALFDAY": "HalfDay", "HALF DAY": "HalfDay",
    "ML": "Leave", "CO": "Leave", "PL": "Leave", "SL": "Leave", "EL": "Leave",
    "LOP": "Absent", "NA": "Present", "NEW": "Present",
}
STATUS_COLS = ["Present", "HalfDay", "Leave", "Absent", "Week Off", "Holiday", "Other", "Not Marked"]

if "Attendance Status" not in filtered.columns or "EMP ID" not in filtered.columns:
    st.info("This table needs the 'EMP ID' and 'Attendance Status' columns in the sheet.")
else:
    adv_period = st.radio(
        "Period:",
        ["📅 Selected date range (filters above)", "🗓️ MTD (month of the latest date in view)"],
        horizontal=True, key="adv_period",
    )
    adv_src = filtered.copy()
    if adv_period.startswith("🗓️"):
        _last = adv_src["Date"].max()
        adv_src = adv_src[(adv_src["Date"].dt.year == _last.year) & (adv_src["Date"].dt.month == _last.month)]

    _raw = adv_src["Attendance Status"].astype(str).str.strip()
    adv_src["Status Group"] = (
        _raw.str.upper().map(STATUS_MAP).mask(_raw == "", "Not Marked").fillna("Other")
    )
    adv_src["_roster_day"] = (adv_src["Roster Count"] > 0).astype(int)

    counts = (
        adv_src.pivot_table(index="EMP ID", columns="Status Group", values="Date",
                            aggfunc="count", fill_value=0)
        .reindex(columns=STATUS_COLS, fill_value=0)
    )
    attr_cols = [c for c in ["Name", "TL", "AM", "CM", "POD Leader", "Location", "Lender", "Final",
                             "Active Status"] if c in adv_src.columns]
    attrs = adv_src.sort_values("Date").groupby("EMP ID")[attr_cols].last()
    days = adv_src.groupby("EMP ID").agg(**{"Total Days": ("Date", "nunique"),
                                            "Roster Days": ("_roster_day", "sum")})

    adv_tbl = attrs.join(days).join(counts).reset_index()
    adv_tbl["Working Days"] = adv_tbl["Present"] + 0.5 * adv_tbl["HalfDay"]
    adv_tbl["Attendance % (vs Roster)"] = (
        (adv_tbl["Working Days"] / adv_tbl["Roster Days"] * 100)
        .where(adv_tbl["Roster Days"] > 0, 0).round(1)
    )

    # Hide the catch-all columns when there is nothing in them
    for _c in ["Other", "Not Marked"]:
        if adv_tbl[_c].sum() == 0:
            adv_tbl = adv_tbl.drop(columns=_c)

    lead = ["EMP ID"] + attr_cols
    metrics = ["Total Days", "Roster Days", "Working Days"] + \
              [c for c in STATUS_COLS if c in adv_tbl.columns] + ["Attendance % (vs Roster)"]
    adv_tbl = adv_tbl[lead + metrics].sort_values("Name" if "Name" in lead else "EMP ID")

    st.caption(f"{len(adv_tbl):,} advisors · {adv_src['Date'].min():%d %b %Y} – {adv_src['Date'].max():%d %b %Y}")
    st.dataframe(adv_tbl, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download Advisor Attendance CSV", adv_tbl.to_csv(index=False),
                       "advisor_attendance_summary.csv", "text/csv", key="dl_adv_csv")

    if "Other" in adv_tbl.columns:
        _unk = sorted(_raw[adv_src["Status Group"] == "Other"].unique())
        st.warning("Some Attendance Status values are not in the mapping and are counted under 'Other': "
                   + ", ".join(_unk))

st.markdown("---")

# ---------------------------------------------------
# PowerPoint Snapshots — export-ready visuals
# ---------------------------------------------------
st.subheader("📸 PowerPoint Snapshots")
st.caption("Hover over a visual and click the 📷 camera icon (top-right of the visual) to download it "
           "as a high-resolution PNG, then paste it into your slide. "
           "All snapshots follow the filters selected above.")

SNAP_THEMES = {
    "dark": dict(bg="#090a2f", card="#17194c", border="#545eff", muted="#9da2ff",
                 text="#ffffff", bar="#7f63ff", grid="#2a2d63"),
    "light": dict(bg="#ffffff", card="#eef0ff", border="#5058d4", muted="#4b52b6",
                  text="#1a1d53", bar="#5058d4", grid="#e3e5f5"),
}

snap_choice = st.radio("Image style:", ["🌙 Dark (matches dashboard)", "☀️ Light (white background)"],
                       horizontal=True, key="snap_style")
theme = SNAP_THEMES["dark"] if snap_choice.startswith("🌙") else SNAP_THEMES["light"]


def export_config(name, width, height):
    """Plotly modebar config -> the camera icon downloads a crisp PNG of this size."""
    return {
        "displaylogo": False,
        "toImageButtonOptions": {"format": "png", "filename": name,
                                 "width": width, "height": height, "scale": 2},
    }


def summary_figure(items, th):
    """Row of KPI cards drawn as a Plotly figure so it can be exported as an image."""
    n = len(items)
    gap = 0.02
    w = (1 - gap * (n - 1)) / n
    fig = go.Figure()
    for i, (title, value) in enumerate(items):
        x0 = i * (w + gap)
        x1 = x0 + w
        xm = (x0 + x1) / 2
        fig.add_shape(type="rect", xref="paper", yref="paper", x0=x0, x1=x1, y0=0.04, y1=0.96,
                      fillcolor=th["card"], line=dict(color=th["border"], width=2), layer="below")
        fig.add_annotation(xref="paper", yref="paper", x=xm, y=0.70, text=title, showarrow=False,
                           xanchor="center", yanchor="middle", font=dict(size=16, color=th["muted"]))
        fig.add_annotation(xref="paper", yref="paper", x=xm, y=0.36, text=f"<b>{value}</b>",
                           showarrow=False, xanchor="center", yanchor="middle",
                           font=dict(size=36, color=th["text"]))
    fig.update_layout(height=190, margin=dict(l=8, r=8, t=8, b=8),
                      paper_bgcolor=th["bg"], plot_bgcolor=th["bg"],
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def breakdown_df(dim_col):
    """Shrinkage % per value of one dimension (highest first)."""
    d = (filtered.groupby(dim_col)
         .agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
         .reset_index())
    d = d[(d[dim_col] != "") & (d["Roster"] > 0)]
    d["Shrinkage %"] = shrinkage(d["Roster"], d["Attendance"])
    return d.sort_values("Shrinkage %", ascending=False)


def breakdown_snapshot(dim_col, label, th):
    """Shrinkage % bar chart for one dimension, styled for slides."""
    d = breakdown_df(dim_col)

    fig = px.bar(d, x=dim_col, y="Shrinkage %", text="Shrinkage %")
    fig.update_traces(marker_color=th["bar"], texttemplate="%{text:.1f}%", textposition="outside",
                      cliponaxis=False, textfont=dict(color=th["text"], size=14))
    fig.update_layout(
        title=dict(text=f"<b>Shrinkage % — {label} wise</b>", font=dict(size=22, color=th["text"]), x=0.01),
        paper_bgcolor=th["bg"], plot_bgcolor=th["bg"], font=dict(color=th["text"]),
        height=470, margin=dict(l=40, r=20, t=70, b=60),
        xaxis=dict(title="", tickfont=dict(size=13), showgrid=False),
        yaxis=dict(title="Shrinkage %", gridcolor=th["grid"], zeroline=False),
        bargap=0.35,
    )
    return fig


def attendance_df(dim_col):
    """Attendance Count per value of one dimension (highest first)."""
    d = (filtered.groupby(dim_col)
         .agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
         .reset_index())
    d = d[d[dim_col] != ""]
    return d.sort_values("Attendance", ascending=False)


def attendance_snapshot(dim_col, label, th):
    """Attendance Count bar chart for one dimension, styled for slides."""
    d = attendance_df(dim_col)

    fig = px.bar(d, x=dim_col, y="Attendance", text="Attendance")
    fig.update_traces(marker_color=th["bar"], texttemplate="%{text:,.0f}", textposition="outside",
                      cliponaxis=False, textfont=dict(color=th["text"], size=14))
    fig.update_layout(
        title=dict(text=f"<b>Attendance Count — {label} wise</b>", font=dict(size=22, color=th["text"]), x=0.01),
        paper_bgcolor=th["bg"], plot_bgcolor=th["bg"], font=dict(color=th["text"]),
        height=470, margin=dict(l=40, r=20, t=70, b=60),
        xaxis=dict(title="", tickfont=dict(size=13), showgrid=False),
        yaxis=dict(title="Attendance Count", gridcolor=th["grid"], zeroline=False),
        bargap=0.35,
    )
    return fig


# 1) Summary strip
adv_in_view = filtered["EMP ID"].nunique() if "EMP ID" in filtered.columns else "-"
summary_items = [
    ("Overall Shrinkage %", f"{overall_shrink:.2f}%"),
    ("Avg Daily Shrinkage %", f"{daily['Shrinkage %'].mean():.2f}%"),
    ("Avg Daily Roster", f"{daily['Roster'].mean():,.1f}"),
    ("Avg Daily Attendance", f"{daily['Attendance'].mean():,.1f}"),
    ("Advisors in View", f"{adv_in_view}"),
]
st.markdown("**1️⃣ Summary**")
st.plotly_chart(summary_figure(summary_items, theme), use_container_width=True,
                config=export_config("shrinkage_summary", 1600, 220))

# 2) POD Leader wise
if "POD Leader" in filtered.columns:
    st.markdown("**2️⃣ Shrinkage % — POD Leader wise**")
    st.plotly_chart(breakdown_snapshot("POD Leader", "POD Leader", theme), use_container_width=True,
                    config=export_config("shrinkage_pod_leader_wise", 1600, 700))

# 3) Location wise
if "Location" in filtered.columns:
    st.markdown("**3️⃣ Shrinkage % — Location wise**")
    st.plotly_chart(breakdown_snapshot("Location", "Location", theme), use_container_width=True,
                    config=export_config("shrinkage_location_wise", 1600, 700))

# 4) Attendance Count — POD Leader wise
if "POD Leader" in filtered.columns:
    st.markdown("**4️⃣ Attendance Count — POD Leader wise**")
    st.plotly_chart(attendance_snapshot("POD Leader", "POD Leader", theme), use_container_width=True,
                    config=export_config("attendance_pod_leader_wise", 1600, 700))

# 5) Attendance Count — Location wise
if "Location" in filtered.columns:
    st.markdown("**5️⃣ Attendance Count — Location wise**")
    st.plotly_chart(attendance_snapshot("Location", "Location", theme), use_container_width=True,
                    config=export_config("attendance_location_wise", 1600, 700))

# 6) Shrinkage % — Lender wise
if "Lender" in filtered.columns:
    st.markdown("**6️⃣ Shrinkage % — Lender wise**")
    st.plotly_chart(breakdown_snapshot("Lender", "Lender", theme), use_container_width=True,
                    config=export_config("shrinkage_lender_wise", 1600, 700))

# 7) Attendance Count — Lender wise
if "Lender" in filtered.columns:
    st.markdown("**7️⃣ Attendance Count — Lender wise**")
    st.plotly_chart(attendance_snapshot("Lender", "Lender", theme), use_container_width=True,
                    config=export_config("attendance_lender_wise", 1600, 700))

# ---------------------------------------------------
# One-click PowerPoint (native, editable charts)
# ---------------------------------------------------
try:
    from io import BytesIO
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE
    PPTX_OK = True
except ImportError:
    PPTX_OK = False


def _rgb(hex_color):
    return RGBColor.from_string(hex_color.lstrip("#").upper())


def _add_text(slide, text, left, top, width, height, size, color, bold=False, align=None):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    if align is not None:
        p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size, r.font.bold, r.font.name = Pt(size), bold, "Calibri"
    r.font.color.rgb = _rgb(color)


def _new_slide(prs, th, title, subtitle, footer):
    slide = prs.slides.add_slide(prs.slide_layouts[6])          # blank layout
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _rgb(th["bg"])
    _add_text(slide, title, 0.5, 0.35, 12.3, 0.7, 30, th["text"], bold=True)
    _add_text(slide, subtitle, 0.5, 1.0, 12.3, 0.4, 14, th["muted"])
    _add_text(slide, footer, 0.5, 6.95, 12.3, 0.35, 11, th["muted"])
    return slide


def _summary_slide(prs, th, items, subtitle, footer):
    slide = _new_slide(prs, th, "Shrinkage Summary", subtitle, footer)
    n, gap, margin = len(items), 0.2, 0.5
    w = (13.333 - 2 * margin - gap * (n - 1)) / n
    for i, (title, value) in enumerate(items):
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(margin + i * (w + gap)),
                                     Inches(2.4), Inches(w), Inches(2.3))
        shp.adjustments[0] = 0.12
        shp.fill.solid()
        shp.fill.fore_color.rgb = _rgb(th["card"])
        shp.line.color.rgb = _rgb(th["border"])
        shp.line.width = Pt(1.75)
        shp.shadow.inherit = False
        tf = shp.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p1 = tf.paragraphs[0]
        p1.alignment = PP_ALIGN.CENTER
        r1 = p1.add_run()
        r1.text = title
        r1.font.size, r1.font.name = Pt(14), "Calibri"
        r1.font.color.rgb = _rgb(th["muted"])
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        r2.text = str(value)
        r2.font.size, r2.font.bold, r2.font.name = Pt(34), True, "Calibri"
        r2.font.color.rgb = _rgb(th["text"])


def _bar_slide(prs, th, title, subtitle, footer, labels, values,
               series_name="Shrinkage %", label_fmt='0.0"%"', axis_fmt='0"%"'):
    slide = _new_slide(prs, th, title, subtitle, footer)
    cd = CategoryChartData()
    cd.categories = labels
    cd.add_series(series_name, [float(v) for v in values])
    chart = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.6),
                                   Inches(12.33), Inches(5.25), cd).chart
    chart.has_legend = False
    chart.has_title = False
    chart.font.size, chart.font.name = Pt(12), "Calibri"
    chart.font.color.rgb = _rgb(th["text"])

    plot = chart.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = label_fmt, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(12)
    dl.font.color.rgb = _rgb(th["text"])
    plot.series[0].format.fill.solid()
    plot.series[0].format.fill.fore_color.rgb = _rgb(th["bar"])

    va = chart.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = _rgb(th["grid"])
    va.format.line.fill.background()
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = axis_fmt, False
    va.tick_labels.font.color.rgb = _rgb(th["text"])
    ca = chart.category_axis
    ca.has_major_gridlines = False
    ca.format.line.color.rgb = _rgb(th["grid"])
    ca.tick_labels.font.color.rgb = _rgb(th["text"])


def build_pptx(th, items, pod_df, loc_df, att_pod_df, att_loc_df, lender_df, att_lender_df,
               subtitle, footer):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)     # 16:9
    _summary_slide(prs, th, items, subtitle, footer)
    if pod_df is not None and not pod_df.empty:
        _bar_slide(prs, th, "Shrinkage % — POD Leader wise", subtitle, footer,
                   pod_df["POD Leader"].tolist(), pod_df["Shrinkage %"].tolist())
    if loc_df is not None and not loc_df.empty:
        _bar_slide(prs, th, "Shrinkage % — Location wise", subtitle, footer,
                   loc_df["Location"].tolist(), loc_df["Shrinkage %"].tolist())
    if lender_df is not None and not lender_df.empty:
        _bar_slide(prs, th, "Shrinkage % — Lender wise", subtitle, footer,
                   lender_df["Lender"].tolist(), lender_df["Shrinkage %"].tolist())
    if att_pod_df is not None and not att_pod_df.empty:
        _bar_slide(prs, th, "Attendance Count — POD Leader wise", subtitle, footer,
                   att_pod_df["POD Leader"].tolist(), att_pod_df["Attendance"].tolist(),
                   series_name="Attendance Count", label_fmt='#,##0', axis_fmt='#,##0')
    if att_loc_df is not None and not att_loc_df.empty:
        _bar_slide(prs, th, "Attendance Count — Location wise", subtitle, footer,
                   att_loc_df["Location"].tolist(), att_loc_df["Attendance"].tolist(),
                   series_name="Attendance Count", label_fmt='#,##0', axis_fmt='#,##0')
    if att_lender_df is not None and not att_lender_df.empty:
        _bar_slide(prs, th, "Attendance Count — Lender wise", subtitle, footer,
                   att_lender_df["Lender"].tolist(), att_lender_df["Attendance"].tolist(),
                   series_name="Attendance Count", label_fmt='#,##0', axis_fmt='#,##0')
    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()


st.markdown("**📥 Get all as an editable PowerPoint**")

if PPTX_OK:
    try:
        label_map = {"Final": "Process"}
        d_min, d_max = filtered["Date"].min(), filtered["Date"].max()
        ppt_subtitle = f"Period: {d_min:%d %b %Y} – {d_max:%d %b %Y}"
        ppt_footer = "Filters: " + (", ".join(f"{label_map.get(k, k)}: {', '.join(v)}" for k, v in active_filters.items())
                                    or "None (all data)")
        pptx_bytes = build_pptx(
            theme, summary_items,
            breakdown_df("POD Leader") if "POD Leader" in filtered.columns else None,
            breakdown_df("Location") if "Location" in filtered.columns else None,
            attendance_df("POD Leader") if "POD Leader" in filtered.columns else None,
            attendance_df("Location") if "Location" in filtered.columns else None,
            breakdown_df("Lender") if "Lender" in filtered.columns else None,
            attendance_df("Lender") if "Lender" in filtered.columns else None,
            ppt_subtitle, ppt_footer,
        )
        st.download_button(
            "⬇️ Download PowerPoint (.pptx)", pptx_bytes, "Shrinkage_Snapshots.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            key="dl_pptx",
        )
        st.caption("7 slides (Summary, then Shrinkage % and Attendance Count by POD Leader, Location & Lender) "
                   "using the selected image style and filters. "
                   "The charts are native PowerPoint charts: right-click → Edit Data, or copy them into your own deck.")
    except Exception as e:
        st.error(f"Could not build the PowerPoint: {type(e).__name__}: {e}")
else:
    st.info("To enable the PowerPoint download, add a line `python-pptx` to requirements.txt in GitHub and redeploy.")

st.markdown("---")

# ---------------------------------------------------
# Tables
# ---------------------------------------------------
with st.expander("📄 Day-Level Data Table"):
    st.dataframe(daily.assign(Date=daily["Date"].dt.strftime("%d %b %Y")),
                 use_container_width=True)
    st.download_button("⬇️ Download Day-Level CSV", daily.to_csv(index=False),
                       "shrinkage_daily.csv", "text/csv")

with st.expander(f"📄 {dim}-wise Summary Table"):
    st.dataframe(by_dim, use_container_width=True)

with st.expander(f"📄 {att_dim}-wise Attendance Count Table"):
    st.dataframe(by_att, use_container_width=True)
    st.download_button("⬇️ Download Attendance Breakdown CSV", by_att.to_csv(index=False),
                       "attendance_breakdown.csv", "text/csv", key="dl_att_csv")

with st.expander(f"📄 {cnt_dim}-wise Overall Count Table"):
    st.dataframe(by_cnt, use_container_width=True)
    st.download_button("⬇️ Download Overall Count CSV", by_cnt.to_csv(index=False),
                       "overall_count_breakdown.csv", "text/csv", key="dl_cnt_csv")
