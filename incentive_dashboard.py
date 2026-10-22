import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------
st.set_page_config(
    page_title="DPDzero Incentive Dashboard",
    page_icon="💰",
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
💰 DPDzero Incentive Dashboard
</h1>
<p style="color:#B8BCFF;">
Incentive Improvement Structure Analytics
</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.stApp { background: linear-gradient(180deg,#090a2f,#070726); color:white; }
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}
section[data-testid="stSidebar"]{ background:#10133d; border-right:1px solid #34396b; }
div[data-testid="metric-container"]{ background:#1a1d53; border:1px solid #4b52b6; padding:18px; border-radius:15px; box-shadow:0px 0px 15px rgba(97,91,255,.25); }
div[data-testid="metric-container"]:hover{ transform:translateY(-4px); transition:.3s; }
.stButton>button{ background:#5b5ef7; color:white; border:none; border-radius:10px; padding:10px; font-weight:600; }
.stButton>button:hover{ background:#7b7eff; }
.stSelectbox div[data-baseweb="select"]{ background:#17194c; color:white; }
[data-testid="stDataFrame"]{ background:#151846; border-radius:15px; }
.streamlit-expanderHeader{ background:#1d2057; border-radius:10px; }
.stProgress > div > div{ background:#7f63ff; }
h1{ color:white; font-weight:700; }
h2,h3{ color:#cfd2ff; }
</style>
""", unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------
# Config
# ---------------------------------------------------
SHEET_ID   = "1430d7TIua062Y6eepv17dBGGvCH9VDrGu1jWS65OOXE"
SHEET_TAB  = "Main"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

NUMERIC_COLS = [
    "Target", "Collected Count", "MTD Till Now",
    "Achieved %", "Current Incentive Value", "Next Incentive Value",
    "Target Gap", "Incentive Value Increased", "Next Target Value",
    "Current TL Incentive", "Next TL Incentive",
]


# ---------------------------------------------------
# Helper — KPI Card
# ---------------------------------------------------
def card(title, value):
    st.markdown(f"""
<div style="
background:#17194c; padding:20px; border-radius:18px; border:1px solid #545eff;
text-align:center; box-shadow:0px 0px 15px rgba(120,120,255,.2); height:160px;
width:100%; display:flex; flex-direction:column; justify-content:center;
align-items:center; box-sizing:border-box;
">
<p style="font-size:13px;color:#9da2ff;margin:0;padding:0;">{title}</p>
<h1 style="color:white;margin:8px 0 0 0;padding:0;font-size:32px;">{value}</h1>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------
# Load Data
# ---------------------------------------------------
@st.cache_data(ttl=10)
def load_data() -> pd.DataFrame:
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES,
        )
        client    = gspread.authorize(creds)
        worksheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
        df        = pd.DataFrame(worksheet.get_all_records())

        if df.empty:
            st.error("❌ No data found in the sheet.")
            st.stop()

        # Strip whitespace AND newlines from all column names
        df.columns = [c.strip().replace("\n", " ") for c in df.columns]

        # Use "Main Region" as the Region everywhere in the dashboard
        # (original Region column is kept as "Sub Region" so nothing is lost)
        df["Sub Region"] = df["Region"]
        df["Region"] = df["Main Region"].astype(str).str.strip()
        df["Region"] = df["Region"].replace("", pd.NA)  # blanks get dropped by .dropna()

        for col in NUMERIC_COLS:
            if col in df.columns:
                df[col] = (
                    df[col].astype(str)
                    .str.replace("%", "", regex=False)
                    .str.replace(",", "", regex=False)
                    .str.strip()
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.stop()


# ---------------------------------------------------
# Refresh Button
# ---------------------------------------------------
_, col_refresh = st.columns([5, 1])
with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.success("✅ Data refreshed!")
        st.rerun()

st.markdown("---")

# ---------------------------------------------------
# Fetch Data
# ---------------------------------------------------
df = load_data()

# ---------------------------------------------------
# View Type Toggle
# ---------------------------------------------------
st.subheader("🔍 Filters & Selection")

view_type = st.radio(
    "📊 Select View Type:",
    ["👤 Advisor View", "👥 TL / Team View", "📈 Region / Location View", "👔 TL Incentive Summary"],
    horizontal=True,
)

st.markdown("---")

# ===================================================
# ADVISOR VIEW
# ===================================================
if view_type == "👤 Advisor View":
    st.markdown("**Advisor View - Select Filters Below:**")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        region_list = ["All"] + sorted(df["Region"].dropna().unique().tolist())
        sel_region = st.selectbox("🔹 Region:", region_list, key="adv_region")

    with col2:
        loc_df = df[df["Region"] == sel_region] if sel_region != "All" else df
        loc_list = ["All"] + sorted(loc_df["Location"].dropna().unique().tolist())
        sel_location = st.selectbox("🔹 Location:", loc_list, key="adv_location")

    with col3:
        tl_df = loc_df[loc_df["Location"] == sel_location] if sel_location != "All" else loc_df
        tl_list = ["All"] + sorted(tl_df["TL Name"].dropna().unique().tolist())
        sel_tl = st.selectbox("🔹 TL Name:", tl_list, key="adv_tl")

    with col4:
        adv_df = tl_df[tl_df["TL Name"] == sel_tl] if sel_tl != "All" else tl_df
        adv_list = sorted(adv_df["Advisor Name"].dropna().unique().tolist())
        if adv_list:
            sel_advisor = st.selectbox("🔹 Advisor Name:", adv_list, key="adv_name")
            row = adv_df[adv_df["Advisor Name"] == sel_advisor].iloc[0]
        else:
            st.warning("⚠️ No advisors found with selected filters.")
            st.stop()

    st.markdown("---")
    st.success(f"✅ Selected: **{sel_advisor}** | Location: **{row['Location']}** | TL: **{row['TL Name']}**")

    # KPI Cards
    st.subheader("📈 Incentive Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: card("🎯 Target",           f"₹{int(row['Target']):,}")
    with c2: card("📦 Collected Count",  int(row["Collected Count"]))
    with c3: card("📊 MTD Till Now",     f"₹{int(row['MTD Till Now']):,}")
    with c4: card("✅ Achieved %",        f"{row['Achieved %']:.1f}%")
    with c5: card("💰 Current Incentive",f"₹{int(row['Current Incentive Value']):,}")
    with c6: card("🚀 Next Incentive",   f"₹{int(row['Next Incentive Value']):,}")

    st.markdown("---")

    left, right = st.columns(2)

    with left:
        st.subheader("👤 Advisor Details")
        st.write("**Advisor Name:**", row["Advisor Name"])
        st.write("**Region:**",       row["Region"])      # now = Main Region
        st.write("**Sub Region:**",   row["Sub Region"])  # original Region column
        st.write("**Location:**",     row["Location"])
        st.write("**DPD Bucket:**",   row["DPD Bucket"])

    with right:
        st.subheader("🎯 Incentive Targets")
        st.write("**Target Gap:**",           f"₹{int(row['Target Gap']):,}")
        st.write("**Next Target Value:**",    f"₹{int(row['Next Target Value']):,}")
        st.write("**TL Name:**",              row["TL Name"])
        st.write("**Current TL Incentive:**", f"₹{int(row['Current TL Incentive']):,}")
        st.write("**Next TL Incentive:**",    f"₹{int(row['Next TL Incentive']):,}")

    st.markdown("---")

    # Progress toward next incentive slab
    st.subheader("📊 Progress to Next Incentive Slab")
    target_gap   = float(row["Target Gap"])
    next_target  = float(row["Next Target Value"])
    mtd          = float(row["MTD Till Now"])

    if next_target > 0:
        progress_pct = min(mtd / next_target, 1.0)
        st.write(f"MTD Collected: **₹{mtd:,.0f}** / Next Target: **₹{next_target:,.0f}**")
        st.progress(progress_pct)
        st.write(f"Gap remaining: **₹{max(target_gap, 0):,.0f}**")

    st.markdown("---")

    # Incentive ladder bar chart
    st.subheader("💹 Current vs Next Incentive")
    inc_df = pd.DataFrame({
        "Slab":   ["Current Incentive", "Next Incentive"],
        "Amount": [row["Current Incentive Value"], row["Next Incentive Value"]],
    })
    fig = px.bar(inc_df, x="Slab", y="Amount", text="Amount", color="Amount",
                 color_continuous_scale="Blues")
    fig.update_layout(template="plotly_dark", paper_bgcolor="#090a2f",
                      plot_bgcolor="#090a2f", font=dict(color="white"),
                      height=400, coloraxis_showscale=False)
    fig.update_traces(texttemplate="₹%{text:,.0f}")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📄 View Full Advisor Record"):
        st.dataframe(row.to_frame(), use_container_width=True)


# ===================================================
# TL / TEAM VIEW
# ===================================================
elif view_type == "👥 TL / Team View":
    st.markdown("**TL / Team View - Select Filters Below:**")

    col1, col2, col3 = st.columns(3)

    with col1:
        region_list = ["All"] + sorted(df["Region"].dropna().unique().tolist())
        sel_region = st.selectbox("🔹 Region:", region_list, key="tl_region")

    with col2:
        loc_df = df[df["Region"] == sel_region] if sel_region != "All" else df
        loc_list = ["All"] + sorted(loc_df["Location"].dropna().unique().tolist())
        sel_location = st.selectbox("🔹 Location:", loc_list, key="tl_location")

    with col3:
        tl_df_f = loc_df[loc_df["Location"] == sel_location] if sel_location != "All" else loc_df
        tl_list = ["All"] + sorted(tl_df_f["TL Name"].dropna().unique().tolist())
        sel_tl = st.selectbox("🔹 TL Name:", tl_list, key="tl_name")

    team_df = tl_df_f[tl_df_f["TL Name"] == sel_tl] if sel_tl != "All" else tl_df_f

    if team_df.empty:
        st.warning("⚠️ No data matches the selected filters.")
        st.stop()

    st.markdown("---")
    st.success(f"✅ Showing **{len(team_df)}** advisors | TL: **{sel_tl}** | Location: **{sel_location}**")

    # Team KPI Cards
    st.subheader("📈 Team Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: card("👥 Team Size",         len(team_df))
    with c2: card("📊 Avg Achieved %",    f"{team_df['Achieved %'].mean():.1f}%")
    with c3: card("💰 Avg Curr Incentive",f"₹{team_df['Current Incentive Value'].mean():,.0f}")
    with c4: card("🚀 Avg Next Incentive",f"₹{team_df['Next Incentive Value'].mean():,.0f}")
    with c5: card("🎯 Total Target Gap",  f"₹{team_df['Target Gap'].sum():,.0f}")

    st.markdown("---")

    st.subheader("👥 Team Members")
    display_cols = ["Advisor Name", "Region", "Target", "Collected Count",
                    "MTD Till Now", "Achieved %", "DPD Bucket",
                    "Current Incentive Value", "Next Incentive Value", "Target Gap"]
    st.dataframe(team_df[[c for c in display_cols if c in team_df.columns]],
                 use_container_width=True)

    st.markdown("---")

    # Advisor-wise achieved % bar
    st.subheader("📊 Advisor-wise Achieved %")
    fig_team = px.bar(
        team_df.sort_values("Achieved %", ascending=False),
        x="Advisor Name", y="Achieved %", text="Achieved %",
        color="Achieved %", color_continuous_scale="Blues",
    )
    fig_team.update_layout(template="plotly_dark", paper_bgcolor="#090a2f",
                           plot_bgcolor="#090a2f", font=dict(color="white"),
                           height=420, coloraxis_showscale=False)
    fig_team.update_traces(texttemplate="%{text:.1f}%")
    st.plotly_chart(fig_team, use_container_width=True)

    st.markdown("---")

    # Top & bottom performers
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏆 Top 3 Performers")
        for i, (_, r) in enumerate(team_df.nlargest(3, "Achieved %").iterrows(), 1):
            st.write(f"{i}. **{r['Advisor Name']}** — {r['Achieved %']:.1f}% | "
                     f"₹{int(r['Current Incentive Value']):,} incentive")
    with col2:
        st.subheader("⚠️ Needs Improvement")
        for i, (_, r) in enumerate(team_df.nsmallest(3, "Achieved %").iterrows(), 1):
            st.write(f"{i}. **{r['Advisor Name']}** — {r['Achieved %']:.1f}% | "
                     f"Gap: ₹{int(r['Target Gap']):,}")

    st.markdown("---")
    with st.expander("📄 Export Team Data"):
        st.download_button("⬇️ Download CSV", team_df.to_csv(index=False),
                           "team_incentive.csv", "text/csv")


# ===================================================
# REGION / LOCATION VIEW
# ===================================================
elif view_type == "📈 Region / Location View":
    st.markdown("**Region / Location View - Select Filters Below:**")

    col1, col2 = st.columns(2)
    with col1:
        region_list = ["All"] + sorted(df["Region"].dropna().unique().tolist())
        sel_region = st.selectbox("🔹 Region:", region_list, key="reg_region")

    with col2:
        loc_df = df[df["Region"] == sel_region] if sel_region != "All" else df
        loc_list = ["All"] + sorted(loc_df["Location"].dropna().unique().tolist())
        sel_location = st.selectbox("🔹 Location:", loc_list, key="reg_location")

    reg_df = loc_df[loc_df["Location"] == sel_location] if sel_location != "All" else loc_df

    if reg_df.empty:
        st.warning("⚠️ No data matches the selected filters.")
        st.stop()

    st.markdown("---")
    st.success(f"✅ Showing **{len(reg_df)}** advisors | Region: **{sel_region}** | Location: **{sel_location}**")

    # Summary KPIs
    st.subheader("📈 Region / Location Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: card("👥 Advisors",           len(reg_df))
    with c2: card("📊 Avg Achieved %",     f"{reg_df['Achieved %'].mean():.1f}%")
    with c3: card("💰 Total Curr Incentive",f"₹{reg_df['Current Incentive Value'].sum():,.0f}")
    with c4: card("🚀 Total Next Incentive",f"₹{reg_df['Next Incentive Value'].sum():,.0f}")
    with c5: card("🎯 Total Target Gap",    f"₹{reg_df['Target Gap'].sum():,.0f}")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Achieved % by Location")
        loc_grp = reg_df.groupby("Location")["Achieved %"].mean().reset_index()
        fig_loc = px.bar(loc_grp.sort_values("Achieved %", ascending=False),
                         x="Location", y="Achieved %", text="Achieved %",
                         color="Achieved %", color_continuous_scale="Blues")
        fig_loc.update_layout(template="plotly_dark", paper_bgcolor="#090a2f",
                              plot_bgcolor="#090a2f", font=dict(color="white"),
                              height=380, coloraxis_showscale=False)
        fig_loc.update_traces(texttemplate="%{text:.1f}%")
        st.plotly_chart(fig_loc, use_container_width=True)

    with col2:
        st.subheader("💰 Total Incentive by Region")
        reg_grp = reg_df.groupby("Region")["Current Incentive Value"].sum().reset_index()
        fig_reg = px.pie(reg_grp, names="Region", values="Current Incentive Value",
                         color_discrete_sequence=px.colors.sequential.Blues_r)
        fig_reg.update_layout(template="plotly_dark", paper_bgcolor="#090a2f",
                              font=dict(color="white"), height=380)
        st.plotly_chart(fig_reg, use_container_width=True)

    st.markdown("---")

    st.subheader("📊 Achieved % by DPD Bucket")
    dpd_grp = reg_df.groupby("DPD Bucket")["Achieved %"].mean().reset_index()
    fig_dpd = px.bar(dpd_grp.sort_values("Achieved %", ascending=False),
                     x="DPD Bucket", y="Achieved %", text="Achieved %",
                     color="Achieved %", color_continuous_scale="Purples")
    fig_dpd.update_layout(template="plotly_dark", paper_bgcolor="#090a2f",
                          plot_bgcolor="#090a2f", font=dict(color="white"),
                          height=380, coloraxis_showscale=False)
    fig_dpd.update_traces(texttemplate="%{text:.1f}%")
    st.plotly_chart(fig_dpd, use_container_width=True)

    st.markdown("---")
    with st.expander("📄 View Full Data"):
        st.dataframe(reg_df, use_container_width=True)


# ===================================================
# TL INCENTIVE SUMMARY
# ===================================================
elif view_type == "👔 TL Incentive Summary":
    st.markdown("**TL Incentive Summary - Select Filters Below:**")

    col1, col2 = st.columns(2)
    with col1:
        region_list = ["All"] + sorted(df["Region"].dropna().unique().tolist())
        sel_region = st.selectbox("🔹 Region:", region_list, key="tlinc_region")

    with col2:
        loc_df = df[df["Region"] == sel_region] if sel_region != "All" else df
        loc_list = ["All"] + sorted(loc_df["Location"].dropna().unique().tolist())
        sel_location = st.selectbox("🔹 Location:", loc_list, key="tlinc_location")

    tlinc_df = loc_df[loc_df["Location"] == sel_location] if sel_location != "All" else loc_df

    if tlinc_df.empty:
        st.warning("⚠️ No data matches the selected filters.")
        st.stop()

    st.markdown("---")

    # TL-wise summary table
    tl_summary = tlinc_df.groupby("TL Name").agg(
        **{
            "No Of Advisors":            ("Advisor Name",         "count"),
            "Avg Achieved %":            ("Achieved %",           "mean"),
            "Total Curr TL Incentive":   ("Current TL Incentive", "sum"),
            "Total Next TL Incentive":   ("Next TL Incentive",    "sum"),
            "Total Target Gap":          ("Target Gap",           "sum"),
        }
    ).reset_index()
    tl_summary["Avg Achieved %"] = tl_summary["Avg Achieved %"].round(1)
    tl_summary = tl_summary.sort_values("Avg Achieved %", ascending=False).reset_index(drop=True)

    st.success(f"✅ Showing **{len(tl_summary)}** TL(s) | **{len(tlinc_df)}** advisors | "
               f"Region: **{sel_region}** | Location: **{sel_location}**")

    # KPI cards
    st.subheader("👔 TL Incentive Overview")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: card("👔 Total TLs",              len(tl_summary))
    with c2: card("👥 Total Advisors",         len(tlinc_df))
    with c3: card("💰 Total Curr TL Incentive",f"₹{tl_summary['Total Curr TL Incentive'].sum():,.0f}")
    with c4: card("🚀 Total Next TL Incentive",f"₹{tl_summary['Total Next TL Incentive'].sum():,.0f}")
    with c5: card("🎯 Total Target Gap",       f"₹{tl_summary['Total Target Gap'].sum():,.0f}")

    st.markdown("---")

    st.subheader("📋 TL-wise Incentive Summary")
    st.dataframe(
        tl_summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Avg Achieved %":          st.column_config.NumberColumn(format="%.1f%%"),
            "Total Curr TL Incentive": st.column_config.NumberColumn(format="₹%d"),
            "Total Next TL Incentive": st.column_config.NumberColumn(format="₹%d"),
            "Total Target Gap":        st.column_config.NumberColumn(format="₹%d"),
        },
    )

    st.markdown("---")

    # Current vs Next TL incentive chart
    st.subheader("💹 Current vs Next TL Incentive")
    chart_df = tl_summary.melt(
        id_vars="TL Name",
        value_vars=["Total Curr TL Incentive", "Total Next TL Incentive"],
        var_name="Type", value_name="Amount",
    )
    fig_tlinc = px.bar(chart_df, x="TL Name", y="Amount", color="Type",
                       barmode="group", text="Amount",
                       color_discrete_map={
                           "Total Curr TL Incentive": "#5b5ef7",
                           "Total Next TL Incentive": "#9da2ff",
                       })
    fig_tlinc.update_layout(template="plotly_dark", paper_bgcolor="#090a2f",
                            plot_bgcolor="#090a2f", font=dict(color="white"),
                            height=420, legend_title_text="")
    fig_tlinc.update_traces(texttemplate="₹%{text:,.0f}")
    st.plotly_chart(fig_tlinc, use_container_width=True)

    st.markdown("---")
    with st.expander("📄 Export TL Incentive Summary"):
        st.download_button("⬇️ Download CSV", tl_summary.to_csv(index=False),
                           "tl_incentive_summary.csv", "text/csv")
