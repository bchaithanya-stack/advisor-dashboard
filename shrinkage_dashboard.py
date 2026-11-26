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

# Values to leave out of the dashboard completely (matched case-insensitively)
EXCLUDE_FINAL = ["Excess", "Maternity"]
EXCLUDE_LENDER = ["Excess", "Maternity"]

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

        # City derived from Location (Bangalore / Mumbai / Kolkata; otherwise the Location itself)
        if "Location" in df.columns:
            _loc = df["Location"].str.lower()
            df["City"] = df["Location"]
            df.loc[_loc.str.contains("bangalore|bengaluru", na=False), "City"] = "Bangalore"
            df.loc[_loc.str.contains("mumbai", na=False), "City"] = "Mumbai"
            df.loc[_loc.str.contains("kolkata", na=False), "City"] = "Kolkata"

        # Remove excluded Final / Lender values everywhere in the dashboard
        for col, bad in (("Final", EXCLUDE_FINAL), ("Lender", EXCLUDE_LENDER)):
            if col in df.columns:
                df = df[~df[col].str.lower().isin([b.lower() for b in bad])]

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

dim_options = [c for c in ["TL", "AM", "CM", "POD Leader", "Location", "City", "Lender", "Final"]
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
           "Rostered / Week Off and Present / Absent. Absent = active and Attendance Count = 0, irrespective of roster. "
           "Shrinkage % = (Rostered − Present) ÷ Rostered.")

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

_rostered_tot = int(cnt_df["Rostered"].sum())
_present_tot = int(cnt_df["Present"].sum())
cnt_shrink = ((_rostered_tot - _present_tot) / _rostered_tot * 100) if _rostered_tot > 0 else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1: card("👥 Active Headcount", f"{int(cnt_df['Active Headcount'].sum()):,}")
with k2: card("🗓️ Rostered", f"{_rostered_tot:,}")
with k3: card("🛌 Week Off", f"{int(cnt_df['Week Off'].sum()):,}")
with k4: card("✅ Present", f"{_present_tot:,}")
with k5: card("❌ Absent (Attendance = 0)", f"{int(cnt_df['Absent (Attendance = 0)'].sum()):,}")
with k6: card("📉 Shrinkage %", f"{cnt_shrink:.2f}%")

cnt_dim = st.selectbox("Break down by:", dim_options, key="count_breakdown_dim")

by_cnt = (
    cnt_df[cnt_df[cnt_dim] != ""]
    .groupby(cnt_dim)[["Active Headcount"] + COUNT_COLS]
    .sum()
    .reset_index()
    .sort_values("Active Headcount", ascending=False)
)
by_cnt["Shrinkage %"] = shrinkage(by_cnt["Rostered"], by_cnt["Present"])

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
# Chart 7 — Attendance Summary (Advisor / Lender / TL / CM / POD Leader wise)
# ---------------------------------------------------
st.subheader("📋 Attendance Summary")
st.caption("Attendance Status is grouped as: Present = Present / NA / New · Leave = ML / CO / PL / SL / EL · "
           "Absent = LOP · plus HalfDay, WO (Week Off) and Holiday as they are. "
           "Working Days = Present + 0.5 × HalfDay. Roster Days = days with Roster Count > 0.")

# Attendance Status (upper-case) -> group used in these tables
STATUS_MAP = {
    "HOLIDAY": "Holiday", "PRESENT": "Present", "WO": "Week Off",
    "HALFDAY": "HalfDay", "HALF DAY": "HalfDay",
    "ML": "Leave", "CO": "Leave", "PL": "Leave", "SL": "Leave", "EL": "Leave",
    "LOP": "Absent", "NA": "Present", "NEW": "Present",
}
STATUS_COLS = ["Present", "HalfDay", "Leave", "Absent", "Week Off", "Holiday", "Other", "Not Marked"]

# Column colours used to shade the tables
COL_COLORS = {
    "Advisors": "#5b5ef7", "Total Days": "#5b5ef7", "Advisor-Days": "#5b5ef7",
    "Roster Days": "#8b5cf6", "Working Days": "#14b8a6",
    "Present": "#22c55e", "HalfDay": "#f59e0b", "Leave": "#3b82f6", "Absent": "#ef4444",
    "Week Off": "#a855f7", "Holiday": "#06b6d4", "Other": "#9ca3af", "Not Marked": "#9ca3af",
}
_SHADE_LOW = (30, 33, 96)      # dark indigo, same family as the dashboard background


def _shade_scale(col, hex_color):
    """Dark -> accent colour, scaled to the column's maximum."""
    hi = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    mx = col.max()
    out = []
    for v in col:
        t = 0 if mx <= 0 else min(max(v / mx, 0), 1)
        rgb = tuple(int(_SHADE_LOW[i] + (hi[i] - _SHADE_LOW[i]) * t) for i in range(3))
        out.append(f"background-color: rgb{rgb}; color: white; font-weight: 600")
    return out


def _shade_pct(col):
    """Red (0%) -> green (100%)."""
    red, green = (190, 45, 65), (25, 160, 110)
    out = []
    for v in col:
        t = min(max(v / 100, 0), 1)
        rgb = tuple(int(red[i] + (green[i] - red[i]) * t) for i in range(3))
        out.append(f"background-color: rgb{rgb}; color: white; font-weight: 700")
    return out


def style_summary(tbl, text_cols):
    sty = tbl.style
    if text_cols:
        sty = sty.set_properties(subset=text_cols, **{"background-color": "#262a75", "color": "#e6e8ff",
                                                       "font-weight": "600"})
    for c in tbl.columns:
        if c in COL_COLORS:
            sty = sty.apply(_shade_scale, hex_color=COL_COLORS[c], subset=[c])
    if "Attendance % (vs Roster)" in tbl.columns:
        sty = sty.apply(_shade_pct, subset=["Attendance % (vs Roster)"])
    return sty.format({"Working Days": "{:.1f}", "Attendance % (vs Roster)": "{:.1f}%"})


def build_summary(src, key, attr_cols):
    """key = 'EMP ID' -> one row per advisor; otherwise one row per value of that column."""
    if key != "EMP ID":
        src = src[src[key] != ""]
    counts = (
        src.pivot_table(index=key, columns="Status Group", values="Date", aggfunc="count", fill_value=0)
        .reindex(columns=STATUS_COLS, fill_value=0)
    )
    grp = src.groupby(key)
    if key == "EMP ID":
        attrs = src.sort_values("Date").groupby(key)[attr_cols].last()
        days = grp.agg(**{"Total Days": ("Date", "nunique"), "Roster Days": ("_roster_day", "sum")})
        tbl = attrs.join(days).join(counts)
        lead = ["EMP ID"] + attr_cols
        count_cols = ["Total Days", "Roster Days", "Working Days"]
    else:
        days = grp.agg(**{"Advisors": ("EMP ID", "nunique"), "Advisor-Days": ("Date", "count"),
                          "Roster Days": ("_roster_day", "sum")})
        tbl = days.join(counts)
        lead = [key]
        count_cols = ["Advisors", "Advisor-Days", "Roster Days", "Working Days"]

    tbl = tbl.reset_index()
    tbl["Working Days"] = tbl["Present"] + 0.5 * tbl["HalfDay"]
    tbl["Attendance % (vs Roster)"] = (
        (tbl["Working Days"] / tbl["Roster Days"] * 100).where(tbl["Roster Days"] > 0, 0).round(1)
    )
    for c in ["Other", "Not Marked"]:                      # hide catch-all columns when empty
        if tbl[c].sum() == 0:
            tbl = tbl.drop(columns=c)
    status_present = [c for c in STATUS_COLS if c in tbl.columns]
    tbl = tbl[lead + count_cols + status_present + ["Attendance % (vs Roster)"]]
    if key == "EMP ID":
        tbl = tbl.sort_values("Name" if "Name" in tbl.columns else "EMP ID")
    else:
        tbl = tbl.sort_values("Roster Days", ascending=False)
    return tbl, lead


if "Attendance Status" not in filtered.columns or "EMP ID" not in filtered.columns:
    st.info("These tables need the 'EMP ID' and 'Attendance Status' columns in the sheet.")
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

    st.caption(f"Period covered: {adv_src['Date'].min():%d %b %Y} – {adv_src['Date'].max():%d %b %Y}")

    adv_attr_cols = [c for c in ["Name", "TL", "POD Leader", "Location", "Lender"] if c in adv_src.columns]
    summary_views = [("👤 Advisor", "EMP ID", "advisor_attendance_summary.csv"),
                     ("🏦 Lender", "Lender", "lender_attendance_summary.csv"),
                     ("👔 TL", "TL", "tl_attendance_summary.csv"),
                     ("🧑‍💼 CM", "CM", "cm_attendance_summary.csv"),
                     ("🧭 POD Leader", "POD Leader", "pod_leader_attendance_summary.csv")]

    for tab, (tab_label, key_col, csv_name) in zip(st.tabs([v[0] for v in summary_views]), summary_views):
        with tab:
            if key_col not in adv_src.columns:
                st.info(f"Column '{key_col}' was not found in the sheet.")
                continue
            tbl, text_cols = build_summary(adv_src, key_col, adv_attr_cols)
            st.caption(f"{len(tbl):,} {'advisors' if key_col == 'EMP ID' else 'rows'}")
            st.dataframe(style_summary(tbl, text_cols), use_container_width=True, hide_index=True)
            st.download_button("⬇️ Download CSV", tbl.to_csv(index=False), csv_name, "text/csv",
                               key=f"dl_sum_{key_col.replace(' ', '_')}")

    if (adv_src["Status Group"] == "Other").any():
        _unk = sorted(_raw[adv_src["Status Group"] == "Other"].unique())
        st.warning("Some Attendance Status values are not in the mapping and are counted under 'Other': "
                   + ", ".join(_unk))

st.markdown("---")

# ---------------------------------------------------
# Chart 8 — Count Summary Table + Suggestions
# ---------------------------------------------------
import html as _html

st.subheader("🧾 Count Summary Table")
st.caption("Active Headcount, Rostered, Week Off and Present follow the same rules as the Overall Count Breakdown "
           "(counted in advisor-days over the selected dates). "
           "UPL (Unplanned Leave) = Rostered − Present, so the columns always add up. "
           "Shrinkage % = UPL ÷ Rostered (a negative UPL means more people were present than rostered).")

cs = filtered.copy()
if "Active Status" in cs.columns:
    _cs_act = cs["Active Status"].astype(str).str.strip().str.lower().eq(ACTIVE_VALUE)
else:
    _cs_act = pd.Series(True, index=cs.index)
_cs_r = cs["Roster Count"] > 0

cs["Active Headcount"] = _cs_act.astype(int)
cs["Rostered"] = (_cs_act & _cs_r).astype(int)
cs["Week Off"] = (_cs_act & ~_cs_r).astype(int)
cs["Present"] = (_cs_act & (cs["Attendance Count"] > 0)).astype(int)
CS_METRICS = ["Active Headcount", "Rostered", "Week Off", "Present"]

cs_dims = [c for c in ["TL", "AM", "CM", "POD Leader", "Lender", "Location", "City"] if c in cs.columns]
cs_dim = st.selectbox("Break down by:", cs_dims, key="cs_dim")

cs_tbl = (
    cs[cs[cs_dim] != ""]
    .groupby(cs_dim)[CS_METRICS].sum()
    .reset_index()
)
cs_tbl["UPL"] = cs_tbl["Rostered"] - cs_tbl["Present"]
cs_tbl["Shrinkage %"] = shrinkage(cs_tbl["Rostered"], cs_tbl["Present"])
cs_tbl = cs_tbl.sort_values("Active Headcount", ascending=False).reset_index(drop=True)

_tot = cs[CS_METRICS].sum()
_tot["UPL"] = _tot["Rostered"] - _tot["Present"]
_tot_shrink = ((_tot["Rostered"] - _tot["Present"]) / _tot["Rostered"] * 100) if _tot["Rostered"] > 0 else 0
st.caption(f"Overall: Active Headcount {int(_tot['Active Headcount']):,} · Rostered {int(_tot['Rostered']):,} · "
           f"Week Off {int(_tot['Week Off']):,} · Present {int(_tot['Present']):,} · "
           f"UPL {int(_tot['UPL']):,} · Shrinkage {_tot_shrink:.2f}%")

# Soft, minimal styling: dark cells, coloured numbers, light tints only where it carries meaning
_CS_BG = (21, 24, 70)            # #151846, same as the dashboard cards


def _mix(accent, t):
    return "rgb" + str(tuple(int(_CS_BG[i] + (accent[i] - _CS_BG[i]) * t) for i in range(3)))


def _plain(color):
    """Neutral dark cell with a coloured number."""
    return lambda col: [f"background-color: #151846; color: {color}; font-weight: 600" for _ in col]


def _upl_style(col):
    """Zero stays quiet; anything above zero gets a gentle red tint that grows with the value."""
    mx = col.max()
    out = []
    for v in col:
        if v <= 0:
            out.append("background-color: #151846; color: #6f75b0; font-weight: 500")
        else:
            out.append(f"background-color: {_mix((239, 68, 68), 0.18 + 0.27 * (v / mx))}; "
                       f"color: #fecaca; font-weight: 700")
    return out


def _shrink_style(col):
    """Below the overall shrinkage = soft green, above = soft red (stronger the further away)."""
    dist = (col - _tot_shrink).abs().max()
    out = []
    for v in col:
        d = (v - _tot_shrink) / dist if dist > 0 else 0
        if d <= 0:
            out.append(f"background-color: {_mix((34, 197, 94), 0.15 + 0.30 * abs(d))}; "
                       f"color: #bbf7d0; font-weight: 700")
        else:
            out.append(f"background-color: {_mix((239, 68, 68), 0.15 + 0.30 * d)}; "
                       f"color: #fecaca; font-weight: 700")
    return out


_cs_sty = (
    cs_tbl.style
    .set_properties(subset=[cs_dim], **{"background-color": "#1d2057", "color": "#cfd2ff", "font-weight": "600"})
    .apply(_plain("#e6e8ff"), subset=["Active Headcount", "Rostered"])
    .apply(_plain("#a5a9d6"), subset=["Week Off"])
    .apply(_plain("#86efac"), subset=["Present"])
    .apply(_upl_style, subset=["UPL"])
    .apply(_shrink_style, subset=["Shrinkage %"])
    .format({"Shrinkage %": "{:.1f}%"})
)

st.dataframe(_cs_sty, use_container_width=True, hide_index=True)
st.download_button("⬇️ Download Count Summary CSV", cs_tbl.to_csv(index=False),
                   f"count_summary_by_{cs_dim.replace(' ', '_').lower()}.csv", "text/csv", key="dl_cs_csv")

# ----- Suggestions: who is doing well / who needs attention -----
st.markdown("#### 💡 Suggestions")
min_roster = st.number_input(
    f"Ignore {cs_dim} values with fewer Rostered days than:", min_value=0, value=10, step=5,
    key="cs_min_roster",
    help="Tiny groups swing a lot, so they are left out of the good / bad lists.",
)
cs_s = cs_tbl[cs_tbl["Rostered"] >= min_roster].copy()
cs_s["UPL %"] = (cs_s["UPL"] / cs_s["Rostered"] * 100).where(cs_s["Rostered"] > 0, 0)

if len(cs_s) < 2:
    st.info("Not enough groups above the minimum Rostered days to compare. Lower the minimum above.")
else:
    n = min(3, len(cs_s) // 2)
    best = cs_s.nsmallest(n, "Shrinkage %")
    worst = cs_s.nlargest(n, "Shrinkage %")
    upl_top = cs_s[cs_s["UPL"] > 0].nlargest(n, "UPL")

    def _rows(df_, mode):
        parts = []
        for _, r in df_.iterrows():
            diff = r["Shrinkage %"] - _tot_shrink
            extra = (f"{r['Shrinkage %']:.1f}% of rostered days" if mode == "upl"
                     else f"{diff:+.1f} pts vs overall")
            val = f"{int(r['UPL']):,} days" if mode == "upl" else f"{r['Shrinkage %']:.1f}%"
            parts.append(
                f"<div style='margin:8px 0;'><b>{_html.escape(str(r[cs_dim]))}</b> — {val}"
                f"<br><span style='color:#b8bcff;font-size:13px;'>{extra} · {int(r['Rostered']):,} rostered · "
                f"{int(r['UPL']):,} UPL</span></div>")
        return "".join(parts) or "<div style='color:#b8bcff;'>None</div>"

    def _box(title, color, body):
        return (f"<div style='background:#17194c;border:1px solid {color};border-left:6px solid {color};"
                f"border-radius:14px;padding:16px 18px;height:100%;'>"
                f"<div style='color:{color};font-weight:700;font-size:16px;margin-bottom:6px;'>{title}</div>"
                f"{body}</div>")

    g1, g2, g3 = st.columns(3)
    with g1:
        st.markdown(_box("🏆 Doing well (lowest shrinkage)", "#22c55e", _rows(best, "shrink")),
                    unsafe_allow_html=True)
    with g2:
        st.markdown(_box("⚠️ Needs attention (highest shrinkage)", "#ef4444", _rows(worst, "shrink")),
                    unsafe_allow_html=True)
    with g3:
        st.markdown(_box("🚨 Most unplanned leave (UPL days)", "#f59e0b", _rows(upl_top, "upl")),
                    unsafe_allow_html=True)

    better = int((cs_s["Shrinkage %"] < _tot_shrink).sum())
    spread = cs_s["Shrinkage %"].max() - cs_s["Shrinkage %"].min()
    notes = [
        f"{better} of {len(cs_s)} {cs_dim} values are below the overall shrinkage of {_tot_shrink:.1f}%; "
        f"{len(cs_s) - better} are at or above it.",
        f"The gap between the best ({best.iloc[0][cs_dim]}, {best.iloc[0]['Shrinkage %']:.1f}%) and the worst "
        f"({worst.iloc[0][cs_dim]}, {worst.iloc[0]['Shrinkage %']:.1f}%) is {spread:.1f} pts — "
        f"learn from the best and focus coaching on the worst.",
    ]
    st.markdown("<br>" + "".join(f"<div style='margin:4px 0;'>• {_html.escape(x)}</div>" for x in notes),
                unsafe_allow_html=True)

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
