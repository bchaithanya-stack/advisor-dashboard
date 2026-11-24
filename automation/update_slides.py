
"""
Hourly job (runs on GitHub Actions): reads the shrinkage Google Sheet and keeps three
slides in a Google Slides deck up to date:

  1. Shrinkage Summary          - 5 KPI cards (text is rewritten every run)
  2. POD Leader wise            - linked Google Sheets chart (refreshed every run)
  3. Location wise              - linked Google Sheets chart (refreshed every run)

First run: creates the three slides at the end of the deck.
Later runs: only refresh the numbers and charts. Numbers match the dashboard's default
view (all data, no filters).

Required environment variables
  GCP_SERVICE_ACCOUNT_JSON  full JSON key of the service account
  SHRINKAGE_SHEET_ID        source sheet (the one the dashboard reads, tab "Main")
  DATA_SHEET_ID             helper Google Sheet that feeds the charts (service account = Editor)
  SLIDES_DECK_ID            Google Slides deck (service account = Editor)
Optional
  SHRINKAGE_TAB (default Main), SLIDES_THEME (dark | light, default dark), TIMEZONE (default Asia/Kolkata)
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
]

DATA_TAB = "Slides_Data"
EXPECTED_COLS = ["EMP ID", "Name", "Email ID", "Date", "DOJ", "TL", "AM", "CM", "Final", "POD Leader",
                 "Location", "Active Status", "Roster Status", "Attendance Status",
                 "Roster Count", "Attendance Count", "Shrinkage %"]

THEMES = {
    "dark": dict(bg="#090a2f", card="#17194c", border="#545eff", muted="#9da2ff", text="#ffffff", bar="#7f63ff"),
    "light": dict(bg="#ffffff", card="#eef0ff", border="#5058d4", muted="#4b52b6", text="#1a1d53", bar="#5058d4"),
}

# Object IDs we assign ourselves so later runs can find the same shapes
SLIDE_IDS = ["shrink_s1", "shrink_s2", "shrink_s3"]
SLIDE_TITLES = ["Shrinkage Summary", "Shrinkage % — POD Leader wise", "Shrinkage % — Location wise"]
KPI_LABELS = ["Overall Shrinkage %", "Avg Daily Shrinkage %", "Avg Daily Roster",
              "Avg Daily Attendance", "Advisors in View"]
CHARTS = {  # key -> (slide object id, chart object id, anchor row in the data sheet, first data column)
    "pod": ("shrink_s2", "shrink_chart_pod", 2, 0),
    "loc": ("shrink_s3", "shrink_chart_loc", 26, 3),
}


# ---------------------------------------------------
# Data (same logic as the Streamlit dashboard)
# ---------------------------------------------------
def shrink(roster, attendance):
    return ((roster - attendance) / roster * 100).where(roster > 0, 0).round(2)


def load_source(gc, sheet_id, tab):
    ws = gc.open_by_key(sheet_id).worksheet(tab)
    values = ws.get_all_values()
    headers = [str(h).strip().replace("\n", " ") for h in values[0]]
    df = pd.DataFrame(values[1:], columns=headers)
    df = df[[c for c in EXPECTED_COLS if c in df.columns]].copy()

    df["Date"] = pd.to_datetime(df["Date"], format="%d %b %Y", errors="coerce")
    if df["Date"].isna().all():
        df["Date"] = pd.to_datetime(pd.DataFrame(values[1:], columns=headers)["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"])
    for col in ["Roster Count", "Attendance Count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ["POD Leader", "Location"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


def breakdown(df, col):
    d = (df.groupby(col).agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
         .reset_index())
    d = d[(d[col] != "") & (d["Roster"] > 0)]
    d["Shrinkage %"] = shrink(d["Roster"], d["Attendance"])
    return d.sort_values("Shrinkage %", ascending=False)


def compute(df):
    daily = (df.groupby("Date").agg(Roster=("Roster Count", "sum"), Attendance=("Attendance Count", "sum"))
             .reset_index())
    daily["S"] = shrink(daily["Roster"], daily["Attendance"])
    tot_r, tot_a = daily["Roster"].sum(), daily["Attendance"].sum()
    overall = (tot_r - tot_a) / tot_r * 100 if tot_r > 0 else 0
    advisors = df["EMP ID"].nunique() if "EMP ID" in df.columns else 0
    return {
        "kpis": [f"{overall:.2f}%", f"{daily['S'].mean():.2f}%", f"{daily['Roster'].mean():,.1f}",
                 f"{daily['Attendance'].mean():,.1f}", f"{advisors}"],
        "pod": breakdown(df, "POD Leader") if "POD Leader" in df.columns else pd.DataFrame(),
        "loc": breakdown(df, "Location") if "Location" in df.columns else pd.DataFrame(),
        "period": f"Period: {df['Date'].min():%d %b %Y} – {df['Date'].max():%d %b %Y}",
    }


# ---------------------------------------------------
# Helper Google Sheet (feeds the linked charts)
# ---------------------------------------------------
def rgb(hex_color):
    h = hex_color.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def write_data(gc, data_sheet_id, data):
    ss = gc.open_by_key(data_sheet_id)
    try:
        ws = ss.worksheet(DATA_TAB)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(DATA_TAB, 100, 12)
    ws.clear()
    for key, col_letter, label in (("pod", "A", "POD Leader"), ("loc", "D", "Location")):
        d = data[key]
        rows = [[label, "Shrinkage %"]] + [[str(r[label]), float(r["Shrinkage %"])] for _, r in d.iterrows()]
        ws.update(range_name=f"{col_letter}1", values=rows)
    return ws.id


def chart_spec(sheet_id, first_col, n_rows, th):
    def src(col):
        return {"sourceRange": {"sources": [{"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 1 + max(n_rows, 1),
                                              "startColumnIndex": col, "endColumnIndex": col + 1}]}}
    text = {"foregroundColorStyle": {"rgbColor": rgb(th["text"])}, "fontSize": 12}
    return {
        "backgroundColorStyle": {"rgbColor": rgb(th["bg"])},
        "basicChart": {
            "chartType": "COLUMN",
            "legendPosition": "NO_LEGEND",
            "axis": [
                {"position": "BOTTOM_AXIS", "format": text},
                {"position": "LEFT_AXIS", "title": "Shrinkage %", "format": text},
            ],
            "domains": [{"domain": src(first_col)}],
            "series": [{
                "series": src(first_col + 1),
                "targetAxis": "LEFT_AXIS",
                "colorStyle": {"rgbColor": rgb(th["bar"])},
                "dataLabel": {"type": "DATA", "placement": "OUTSIDE_END", "textFormat": text},
            }],
            "headerCount": 0,
        },
    }


def ensure_sheet_charts(sheets, sheet_id, data, th, chart_px):
    """Create the two charts in the helper sheet if missing; otherwise resize their ranges."""
    meta = sheets.spreadsheets().get(
        spreadsheetId=DATA_SHEET_ID, fields="sheets(properties(sheetId),charts(chartId,position))").execute()
    found = {}
    for sh in meta.get("sheets", []):
        if sh["properties"]["sheetId"] != sheet_id:
            continue
        for ch in sh.get("charts", []):
            row = ch.get("position", {}).get("overlayPosition", {}).get("anchorCell", {}).get("rowIndex", 0)
            found[row] = ch["chartId"]

    requests, order, ids = [], [], {}
    for key, (_, _, row, col) in CHARTS.items():
        spec = chart_spec(sheet_id, col, len(data[key]), th)
        if row in found:
            ids[key] = found[row]
            requests.append({"updateChartSpec": {"chartId": found[row], "spec": spec}})
        else:
            order.append(key)
            requests.append({"addChart": {"chart": {
                "spec": spec,
                "position": {"overlayPosition": {
                    "anchorCell": {"sheetId": sheet_id, "rowIndex": row, "columnIndex": 7},
                    "widthPixels": chart_px[0], "heightPixels": chart_px[1]}},
            }}})
    resp = sheets.spreadsheets().batchUpdate(spreadsheetId=DATA_SHEET_ID, body={"requests": requests}).execute()
    new_keys = iter(order)
    for req, reply in zip(requests, resp.get("replies", [])):
        if "addChart" in req:
            ids[next(new_keys)] = reply["addChart"]["chart"]["chartId"]
    return ids


# ---------------------------------------------------
# Google Slides requests
# ---------------------------------------------------
def page_size_pt(pres):
    ps = pres["pageSize"]
    conv = lambda d: d["magnitude"] / 12700 if d["unit"] == "EMU" else d["magnitude"]
    return conv(ps["width"]), conv(ps["height"])


def layout(W, H):
    m = W * 0.045
    return {"W": W, "H": H, "m": m,
            "title": (m, H * 0.05, W - 2 * m, H * 0.12),
            "sub": (m, H * 0.165, W - 2 * m, H * 0.07),
            "foot": (m, H * 0.925, W - 2 * m, H * 0.06),
            "chart": (m, H * 0.24, W - 2 * m, H * 0.66)}


def props(page, rect):
    x, y, w, h = rect
    return {"pageObjectId": page,
            "size": {"width": {"magnitude": w, "unit": "PT"}, "height": {"magnitude": h, "unit": "PT"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}


def style_text(oid, size, color, bold=False, align="START"):
    return [
        {"updateTextStyle": {"objectId": oid, "textRange": {"type": "ALL"},
                             "style": {"fontFamily": "Calibri", "fontSize": {"magnitude": size, "unit": "PT"},
                                       "bold": bold, "foregroundColor": {"opaqueColor": {"rgbColor": rgb(color)}}},
                             "fields": "fontFamily,fontSize,bold,foregroundColor"}},
        {"updateParagraphStyle": {"objectId": oid, "textRange": {"type": "ALL"},
                                  "style": {"alignment": align}, "fields": "alignment"}},
    ]


def new_text(oid, page, rect, text, size, color, bold=False, align="START"):
    return ([{"createShape": {"objectId": oid, "shapeType": "TEXT_BOX", "elementProperties": props(page, rect)}},
             {"insertText": {"objectId": oid, "insertionIndex": 0, "text": text}}]
            + style_text(oid, size, color, bold, align))


def replace_text(oid, text, size, color, bold=False, align="START"):
    return ([{"deleteText": {"objectId": oid, "textRange": {"type": "ALL"}}},
             {"insertText": {"objectId": oid, "insertionIndex": 0, "text": text}}]
            + style_text(oid, size, color, bold, align))


def kpi_geometry(L):
    W, H, m = L["W"], L["H"], L["m"]
    n, gap = 5, W * 0.015
    cw = (W - 2 * m - gap * (n - 1)) / n
    cy, ch = H * 0.34, H * 0.36
    out = []
    for i in range(n):
        x = m + i * (cw + gap)
        out.append({"card": (x, cy, cw, ch),
                    "label": (x, cy + ch * 0.18, cw, ch * 0.22),
                    "value": (x, cy + ch * 0.45, cw, ch * 0.35)})
    return out


def setup_requests(th, L, data, footer):
    reqs = []
    for sid in SLIDE_IDS:
        reqs.append({"createSlide": {"objectId": sid, "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        reqs.append({"updatePageProperties": {
            "objectId": sid, "fields": "pageBackgroundFill.solidFill.color",
            "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(th["bg"])}}}}}})
    for n, sid in enumerate(SLIDE_IDS, start=1):
        reqs += new_text(f"shrink_title_{n}", sid, L["title"], SLIDE_TITLES[n - 1], 26, th["text"], bold=True)
        reqs += new_text(f"shrink_sub_{n}", sid, L["sub"], data["period"], 13, th["muted"])
        reqs += new_text(f"shrink_foot_{n}", sid, L["foot"], footer, 10, th["muted"])
    for i, g in enumerate(kpi_geometry(L)):
        card = f"shrink_card_{i}"
        reqs.append({"createShape": {"objectId": card, "shapeType": "ROUND_RECTANGLE",
                                     "elementProperties": props("shrink_s1", g["card"])}})
        reqs.append({"updateShapeProperties": {
            "objectId": card,
            "fields": "shapeBackgroundFill.solidFill.color,outline.outlineFill.solidFill.color,outline.weight",
            "shapeProperties": {
                "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(th["card"])}}},
                "outline": {"outlineFill": {"solidFill": {"color": {"rgbColor": rgb(th["border"])}}},
                            "weight": {"magnitude": 1.5, "unit": "PT"}}}}})
        reqs += new_text(f"shrink_klabel_{i}", "shrink_s1", g["label"], KPI_LABELS[i], 12, th["muted"], align="CENTER")
        reqs += new_text(f"shrink_kval_{i}", "shrink_s1", g["value"], data["kpis"][i], 26, th["text"],
                         bold=True, align="CENTER")
    return reqs


def update_requests(th, L, data, footer):
    reqs = []
    for i in range(5):
        reqs += replace_text(f"shrink_kval_{i}", data["kpis"][i], 26, th["text"], bold=True, align="CENTER")
    for n in (1, 2, 3):
        reqs += replace_text(f"shrink_sub_{n}", data["period"], 13, th["muted"])
        reqs += replace_text(f"shrink_foot_{n}", footer, 10, th["muted"])
    return reqs


def existing_ids(pres):
    ids = set()
    for s in pres.get("slides", []):
        ids.add(s["objectId"])
        for el in s.get("pageElements", []):
            ids.add(el["objectId"])
    return ids


# ---------------------------------------------------
# Main
# ---------------------------------------------------
def main():
    global DATA_SHEET_ID
    source_id = os.environ["SHRINKAGE_SHEET_ID"]
    DATA_SHEET_ID = os.environ["DATA_SHEET_ID"]
    deck_id = os.environ["SLIDES_DECK_ID"]
    th = THEMES[os.environ.get("SLIDES_THEME", "dark")]
    tz = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Kolkata"))

    creds = Credentials.from_service_account_info(json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"]), scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    slides = build("slides", "v1", credentials=creds, cache_discovery=False)

    data = compute(load_source(gc, source_id, os.environ.get("SHRINKAGE_TAB", "Main")))
    footer = f"Filters: None (all data)   |   Last updated: {datetime.now(tz):%d %b %Y, %I:%M %p}"

    pres = slides.presentations().get(presentationId=deck_id).execute()
    W, H = page_size_pt(pres)
    L = layout(W, H)
    chart_w, chart_h = L["chart"][2], L["chart"][3]
    chart_px = (1000, int(1000 * chart_h / chart_w))        # same aspect ratio as the slide area

    sheet_id = write_data(gc, DATA_SHEET_ID, data)
    chart_ids = ensure_sheet_charts(sheets, sheet_id, data, th, chart_px)

    ids = existing_ids(pres)
    first_time = SLIDE_IDS[0] not in ids
    reqs = setup_requests(th, L, data, footer) if first_time else update_requests(th, L, data, footer)

    for key, (page, oid, _, _) in CHARTS.items():
        if oid in ids:
            reqs.append({"refreshSheetsChart": {"objectId": oid}})
        else:
            reqs.append({"createSheetsChart": {"objectId": oid, "spreadsheetId": DATA_SHEET_ID,
                                               "chartId": chart_ids[key], "linkingMode": "LINKED",
                                               "elementProperties": props(page, L["chart"])}})

    slides.presentations().batchUpdate(presentationId=deck_id, body={"requests": reqs}).execute()
    print(("Created slides" if first_time else "Updated slides"),
          "| KPIs:", data["kpis"], "| POD rows:", len(data["pod"]), "| Location rows:", len(data["loc"]))


if __name__ == "__main__":
    main()
