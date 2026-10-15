"""AFR Air Loss Radar v2: four-borough, conservative 311 triage pilot."""
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Air Loss Radar | AFR", layout="wide")
BOROUGHS = ["MANHATTAN", "BRONX", "BROOKLYN", "QUEENS"]
API = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
PAGE_SIZE = 1000
MAX_ROWS = 20000
# Complaint categories are deliberately narrow. A complaint is NOT a confirmed loss.
TYPES = ["PLUMBING", "Sewer", "Water Conservation", "General Construction/Plumbing"]
EXCLUDE = ["hydrant", "catch basin", "dirty water", "drinking water", "water quality", "sidewalk", "tree", "street flooding", "street condition", "water main", "manhole", "water pressure", "no water", "water supply", "sewer odor", "sewer smell", "blocked drain", "clogged drain"]
HIGH = ["water leak", "leak from", "ceiling leak", "water entering", "flooding inside", "flooded basement", "sewage backup", "sewer backup", "sewage overflow", "water damage"]
MEDIUM = ["leak", "flood", "sewage", "backup", "water intrusion", "pipe burst", "burst pipe"]

@st.cache_data(ttl=900, show_spinner="Retrieving NYC 311 reports...")
def fetch(days):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    boroughs = ",".join("'" + b + "'" for b in BOROUGHS)
    # Filter server-side by date, borough and limited complaint types to avoid pulling every 311 record.
    type_expr = " OR ".join("complaint_type='" + x.replace("'", "''") + "'" for x in TYPES)
    where = f"created_date >= '{start}' AND borough IN ({boroughs}) AND ({type_expr})"
    rows = []
    truncated = False
    with requests.Session() as session:
        while len(rows) < MAX_ROWS:
            params = {"$where": where, "$limit": PAGE_SIZE, "$offset": len(rows),
                      "$order": "created_date DESC, unique_key DESC",
                      "$select": "unique_key,created_date,borough,incident_address,complaint_type,descriptor,status,latitude,longitude"}
            resp = session.get(API, params=params, timeout=35)
            resp.raise_for_status()
            batch = resp.json()
            rows.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
        else:
            truncated = True
    return pd.DataFrame(rows), truncated

def assess(row):
    kind = str(row.get("complaint_type", "")).lower()
    descriptor = str(row.get("descriptor", "")).lower()
    content = kind + " " + descriptor
    if any(word in content for word in EXCLUDE):
        return "Excluded", "Municipal / low-relevance report", 0
    if any(word in content for word in HIGH):
        return "High", "Possible interior water / sewage damage", 75
    if any(word in content for word in MEDIUM):
        return "Medium", "Possible water intrusion; verify", 45
    return "Excluded", "No clear restoration-loss indicator", 0

st.title("Air Loss Radar")
st.caption("AFR pilot v2 · Manhattan · Bronx · Brooklyn · Queens · 311 screening (unverified reports)")
st.warning("NYC 311 reports are NOT confirmed fire or water losses. This version does not monitor FDNY dispatch, X/Twitter, Citizen, or live emergency feeds. No fire incidents are independently verified here.")
days = st.sidebar.selectbox("Lookback (days)", [1, 3, 7, 14, 30], index=2)
selected = st.sidebar.multiselect("Boroughs", BOROUGHS, default=BOROUGHS)
levels = st.sidebar.multiselect("Opportunity priority", ["High", "Medium"], default=["High", "Medium"])
st.sidebar.caption("Scores are rule-based triage, NOT dollar-loss estimates. High means stronger complaint wording, not a confirmed large loss.")

try:
    raw, truncated = fetch(days)
    if truncated:
        st.error(f"Result cap reached ({MAX_ROWS:,} raw reports). Results may be incomplete; reduce lookback days.")
    if raw.empty:
        st.info("No matching 311 reports for this window.")
    else:
        raw = raw.drop_duplicates(subset=["unique_key"]).copy()
        raw = raw[raw["borough"].isin(selected)].copy()
        evaluated = raw.apply(assess, axis=1, result_type="expand")
        evaluated.columns = ["Priority", "Reason", "Score"]
        raw = pd.concat([raw, evaluated], axis=1)
        relevant = raw[raw["Priority"].isin(levels)].copy()
        relevant["created_date"] = pd.to_datetime(relevant["created_date"], errors="coerce")
        relevant = relevant.sort_values(["Score", "created_date"], ascending=[False, False])
        a, b, c, d = st.columns(4)
        a.metric("311 records screened", f"{len(raw):,}")
        b.metric("Potential water signals", f"{len(relevant):,}")
        c.metric("High-priority signals", f"{sum(relevant.Priority == 'High'):,}")
        d.metric("Excluded as irrelevant", f"{sum(raw.Priority == 'Excluded'):,}")
        st.subheader("Opportunity review queue")
        st.caption("Review each source report before outreach. Fire detection and property classification are not yet implemented.")
        cols = ["created_date", "borough", "incident_address", "Priority", "Score", "Reason", "complaint_type", "descriptor", "status", "unique_key"]
        st.dataframe(relevant[cols], hide_index=True, use_container_width=True)
        coords = relevant.copy()
        coords["lat"] = pd.to_numeric(coords.get("latitude"), errors="coerce")
        coords["lon"] = pd.to_numeric(coords.get("longitude"), errors="coerce")
        coords = coords.dropna(subset=["lat", "lon"])
        if not coords.empty:
            st.subheader("Mapped review signals")
            st.map(coords[["lat", "lon"]])
        st.download_button("Export review queue (CSV)", relevant.to_csv(index=False),
                           "air_loss_radar_v2_review.csv", "text/csv")
        with st.expander("Data quality and scoring methodology"):
            st.write("Source: NYC Open Data 311 (erm2-nwe9). Retrieved on demand and cached 15 minutes. Reports are paginated to 20,000 maximum raw records per selected window. No persistent monitoring or automated notifications.")
            st.write("Only selected plumbing/sewer-related complaint categories are screened. Exclusion and scoring rules are conservative and require validation. High priority does not mean a high-dollar claim. No fire detection source is currently connected.")
except Exception as exc:
    st.error(f"NYC Open Data retrieval failed: {exc}")
