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
    page_title="DPDzero Lender Coverage Dashboard",
    page_icon="🏦",
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
🏦 DPDzero Lender Coverage Dashboard
</h1>
<p style="color:#B8BCFF;">
Lender-wise Roster, Attendance, Login &amp; Shrinkage Analytics
</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.stApp { background: linear-gradient(180deg,#090a2f,#070726); color:white; }
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}

/* Hide sidebar and multipage nav */
section[data-testid="stSidebar"] {display:none;}
[data-testid="stSidebarNav"] {display:none;}
[data-testid="collapsedControl"] {display:none;}

.stButton>button{ background:#5b5ef7; color:white; border:none; border-radius:10px; padding:10px; font-weight:600; }
.stButton>button:hover{ background:#7b7eff; }
.stSelectbox div[data-baseweb="select"]{ background:#17194c; color:white; }
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
SHEET_ID = "1xAaF9LScN_24Yn59oJq5haEDABu-id642okFbeg1Fac"   # read from your screenshot - verify
SHEET_TAB = "Summery"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# keyword in the sheet's metric header -> clean metric name
METRIC_KEYS = {
    "approved": "Approved Count",
    "actual": "Actual Count",
    "roster": "Roster Count",
    "attendance": "Attendance Present",
    "login": "Login Count",
}

PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#090a2f",
    plot_bgcolor="#090a2f",
    font=dict(color="white"),
)


# ---------------------------------------------------
# Helpers
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


def shrinkage(roster, attendance):
    """(Roster - Attendance) / Roster * 100 ; NaN where nobody was rostered."""
    return ((roster - attendance) / roster * 100).where(roster > 0).round(2)


def norm_metric(header):
    h = str(header).strip().lower().replace("\n", " ")
    for key, name in METRIC_KEYS.items():
        if key in h:
            return name
    return None   # Difference / Shrinkage % are recomputed, so ignored


def parse_wide(values):
    """
    Sheet layout: row 1 = date (merged across a 7-column block),
    row 2 = metric names, rows 3+ = one lender per row, column A = lender.
    Returns a long DataFrame: one row per (Lender, Date).
    """
    if len(values) < 3:
        return pd.DataFrame()

    top, hdr = values[0], values[1]
    width = max(len(top), len(hdr))

    # Merged date cells only hold the date in their first column -> forward fill
    dates, cur = [], None
    for j in range(width):
        cell = top[j].strip() if j < len(top) else ""
        if j > 0 and cell:
            cur = cell
        dates.append(cur if j > 0 else None)

    records = {}
    for row in values[2:]:
        lender = row[0].strip() if row else ""
        if not lender or lender.lower().startswith(("total", "grand total")):
            continue
        for j in range(1, width):
            metric = norm_metric(hdr[j]) if j < len(hdr) else None
            d = dates[j]
            if metric is None or d is None:
                continue
            records.setdefault((lender, d), {})[metric] = row[j] if j < len(row) else ""

    rows = [{"Lender": k[0], "DateRaw": k[1], **v} for k, v in records.items()]
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["Date"] = pd.to_datetime(df["DateRaw"], format="%d/%m/%Y", errors="coerce")
    if df["Date"].isna().all():
        df["Date"] = pd.to_datetime(df["DateRaw"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"])

    for m in METRIC_KEYS.values():
        if m not in df.columns:
            df[m] = 0
        df[m] = pd.to_numeric(
            df[m].astype(str).str.replace("%", "", regex=False)
                 .str.replace(",", "", regex=False).str.strip(),
            errors="coerce",
        ).fillna(0)

    return df.drop(columns=["DateRaw"])


@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES,
        )
        client = gspread.authorize(creds)
        book = client.open_by_key(SHEET_ID)
        try:
            ws = book.worksheet(SHEET_TAB)
        except gspread.exceptions.WorksheetNotFound:
            ws = book.sheet1          # fall back to the first tab

        df = parse_wide(ws.get_all_values())
        if df.empty:
            st.error("❌ Could not read any lender/date data from the sheet. "
                     "Expected: dates in row 1, metric names in row 2, lenders from row 3.")
            st.stop()
        return df

    except Exception as e:
        st.error(f"❌ Error loading data: {type(e).__name__}: {e!r}")
        name = type(e).__name__
        if name == "SpreadsheetNotFound":
            st.info("The sheet isn't shared with the service account (or the sheet ID is wrong). "
                    "Share it with advisor-dashboard@advisor-dashboard-500613.iam.gserviceaccount.com as Viewer.")
        elif name == "KeyError":
            st.info("Secrets look missing: add [gcp_service_account] in the app's Settings → Secrets.")
        st.stop()


def agg_sum(data, by):
    g = data.groupby(by).agg(
        Approved=("Approved Count", "sum"),
        Actual=("Actual Count", "sum"),
        Roster=("Roster Count", "sum"),
        Attendance=("Attendance Present", "sum"),
        Login=("Login Count", "sum"),
    ).reset_index()
    g["Shrinkage %"] = shrinkage(g["Roster"], g["Attendance"])
    return g


# ---------------------------------------------------
# Refresh + Load
# ---------------------------------------------------
_, col_refresh = st.columns([5, 1])
with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

df = load_data()

# ---------------------------------------------------
# Filters
# ---------------------------------------------------
st.subheader("🔍 Filters")

f1, f2, f3 = st.columns([2, 2, 2])

with f1:
    lenders_all = sorted(df["Lender"].unique())
    sel_lenders = st.multiselect("🔹 Lender(s) (leave empty for all):", lenders_all, key="f_lender")

with f2:
    min_d, max_d = df["Date"].min().date(), df["Date"].max().date()
    date_range = st.date_input("🔹 Date Range:", value=(min_d, max_d),
                               min_value=min_d, max_value=max_d, key="f_date")

with f3:
    hide_empty = st.checkbox(
        "Hide days with no attendance / login data (e.g. future days)", value=True, key="f_hide",
    )

filtered = df.copy()

if sel_lenders:
    filtered = filtered[filtered["Lender"].isin(sel_lenders)]

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    filtered = filtered[(filtered["Date"].dt.date >= date_range[0]) &
                        (filtered["Date"].dt.date <= date_range[1])]

if hide_empty:
    day_tot = df.groupby("Date")[["Attendance Present", "Login Count"]].sum().sum(axis=1)
    empty_days = day_tot[day_tot == 0].index
    filtered = filtered[~filtered["Date"].isin(empty_days)]

st.markdown("---")

if filtered.empty:
    st.warning("⚠️ No data matches the selected filters.")
    st.stop()

# ---------------------------------------------------
# KPI Cards
# ---------------------------------------------------
daily = agg_sum(filtered, "Date").sort_values("Date")

tot_roster, tot_att = daily["Roster"].sum(), daily["Attendance"].sum()
overall = ((tot_roster - tot_att) / tot_roster * 100) if tot_roster > 0 else 0

st.subheader("📈 Summary")
c1, c2, c3, c4, c5 = st.columns(5)
with c1: card("📉 Overall Shrinkage %", f"{overall:.2f}%")
with c2: card("👥 Avg Daily Roster", f"{daily['Roster'].mean():,.0f}")
with c3: card("✅ Avg Daily Attendance", f"{daily['Attendance'].mean():,.0f}")
with c4: card("🔑 Avg Daily Login", f"{daily['Login'].mean():,.0f}")
with c5: card("🏦 Lenders in View", filtered["Lender"].nunique())

st.markdown("---")

# ---------------------------------------------------
# Chart 1 — Day-level overall shrinkage %
# ---------------------------------------------------
st.subheader("📉 Day-Level Shrinkage %")

fig1 = px.line(daily, x="Date", y="Shrinkage %", markers=True)
fig1.update_traces(line_color="#7f63ff", marker=dict(size=8))
fig1.update_layout(**PLOT_LAYOUT, height=400, yaxis_title="Shrinkage %")
st.plotly_chart(fig1, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Chart 2 — Roster vs Attendance vs Login
# ---------------------------------------------------
st.subheader("👥 Day-Level Roster vs Attendance vs Login")

fig2 = go.Figure()
for col, color in [("Roster", "#5b5ef7"), ("Attendance", "#38d9a9"), ("Login", "#ffb347")]:
    fig2.add_trace(go.Scatter(x=daily["Date"], y=daily[col], mode="lines+markers",
                              name=col, line=dict(color=color)))
fig2.update_layout(**PLOT_LAYOUT, height=400, yaxis_title="Headcount",
                   legend=dict(orientation="h", y=1.1))
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Lender summary (used by next charts + table)
# ---------------------------------------------------
ls = filtered.groupby("Lender").agg(
    Approved=("Approved Count", "mean"),
    Actual=("Actual Count", "mean"),
    Roster=("Roster Count", "mean"),
    Attendance=("Attendance Present", "mean"),
    Login=("Login Count", "mean"),
    RosterSum=("Roster Count", "sum"),
    AttSum=("Attendance Present", "sum"),
).reset_index()
ls["Shrinkage %"] = shrinkage(ls["RosterSum"], ls["AttSum"])
ls["Headcount Gap (Approved - Actual)"] = ls["Approved"] - ls["Actual"]

# ---------------------------------------------------
# Chart 3 — Lender-wise shrinkage %
# ---------------------------------------------------
st.subheader("🏦 Lender-wise Shrinkage %")

bar_df = ls.dropna(subset=["Shrinkage %"]).sort_values("Shrinkage %", ascending=True)
fig3 = px.bar(bar_df, x="Shrinkage %", y="Lender", orientation="h", text="Shrinkage %",
              color="Shrinkage %", color_continuous_scale="RdYlGn_r")
fig3.update_traces(texttemplate="%{text:.1f}%")
fig3.update_layout(**PLOT_LAYOUT, height=max(420, 26 * len(bar_df) + 100),
                   coloraxis_showscale=False, yaxis_title="")
st.plotly_chart(fig3, use_container_width=True)

hi, lo = st.columns(2)
valid = ls[ls["RosterSum"] > 0].dropna(subset=["Shrinkage %"])
with hi:
    st.markdown("**⚠️ Highest shrinkage (top 5)**")
    for _, r in valid.nlargest(5, "Shrinkage %").iterrows():
        st.write(f"• **{r['Lender']}** - {r['Shrinkage %']:.1f}% (avg roster {r['Roster']:.0f})")
with lo:
    st.markdown("**✅ Lowest shrinkage (top 5)**")
    for _, r in valid.nsmallest(5, "Shrinkage %").iterrows():
        st.write(f"• **{r['Lender']}** - {r['Shrinkage %']:.1f}% (avg roster {r['Roster']:.0f})")

st.markdown("---")

# ---------------------------------------------------
# Chart 4 — Heatmap: Lender x Date
# ---------------------------------------------------
st.subheader("🔥 Shrinkage % Heatmap — Lender × Date")

hm_src = filtered.assign(S=shrinkage(filtered["Roster Count"], filtered["Attendance Present"]))
hm = hm_src.pivot_table(index="Lender", columns="Date", values="S", aggfunc="mean")
hm = hm.loc[hm.mean(axis=1).sort_values(ascending=False).index]
hm.columns = [d.strftime("%d %b") for d in hm.columns]

fig4 = px.imshow(hm, aspect="auto", color_continuous_scale="RdYlGn_r",
                 zmin=-50, zmax=100, text_auto=".0f")
fig4.update_layout(**PLOT_LAYOUT, height=max(450, 24 * len(hm) + 140),
                   coloraxis_colorbar=dict(title="Shrinkage %"))
st.plotly_chart(fig4, use_container_width=True)
st.caption("Colour scale is capped at -50% to 100%. Blank cells = nobody rostered that day. "
           "Negative values mean more people attended than were rostered.")

st.markdown("---")

# ---------------------------------------------------
# Chart 5 — Day-level shrinkage lines per lender
# ---------------------------------------------------
st.subheader("📉 Day-Level Shrinkage % by Lender")

lend_day = agg_sum(filtered, ["Date", "Lender"])
lend_day = lend_day[lend_day["Roster"] > 0]

top_lenders = (lend_day.groupby("Lender")["Roster"].sum()
               .sort_values(ascending=False).index.tolist())
picked = st.multiselect("Select lenders to plot (top 5 by roster shown by default):",
                        top_lenders, default=top_lenders[:5], key="trend_lenders")

if picked:
    fig5 = px.line(lend_day[lend_day["Lender"].isin(picked)].sort_values("Date"),
                   x="Date", y="Shrinkage %", color="Lender", markers=True)
    fig5.update_layout(**PLOT_LAYOUT, height=450, yaxis_title="Shrinkage %")
    st.plotly_chart(fig5, use_container_width=True)
else:
    st.warning("Select at least one lender.")

st.markdown("---")

# ---------------------------------------------------
# Chart 6 — Headcount coverage
# ---------------------------------------------------
st.subheader("🧑‍🤝‍🧑 Headcount Coverage — Approved vs Actual vs Roster (daily average)")

cov = ls.sort_values("Approved", ascending=False)
fig6 = go.Figure()
fig6.add_bar(x=cov["Lender"], y=cov["Approved"].round(1), name="Approved", marker_color="#5b5ef7")
fig6.add_bar(x=cov["Lender"], y=cov["Actual"].round(1), name="Actual", marker_color="#7f63ff")
fig6.add_bar(x=cov["Lender"], y=cov["Roster"].round(1), name="Roster", marker_color="#38d9a9")
fig6.update_layout(**PLOT_LAYOUT, height=450, barmode="group", yaxis_title="Avg headcount",
                   legend=dict(orientation="h", y=1.1))
st.plotly_chart(fig6, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------
# Table + download
# ---------------------------------------------------
with st.expander("📄 Lender Summary Table"):
    table = ls.drop(columns=["RosterSum", "AttSum"]).round(2).sort_values("Shrinkage %", ascending=False)
    st.dataframe(table, use_container_width=True)
    st.download_button("⬇️ Download Lender Summary CSV", table.to_csv(index=False),
                       "lender_summary.csv", "text/csv")

with st.expander("📄 Day-Level Data Table"):
    d_tbl = daily.assign(Date=daily["Date"].dt.strftime("%d %b %Y"))
    st.dataframe(d_tbl, use_container_width=True)
