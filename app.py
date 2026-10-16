"""AFR Loss Radar v4: public news and NYC 311 review dashboard."""
from datetime import datetime, timedelta, timezone
from news_sources import fetch_news
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="AFR Loss Radar", layout="wide")
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

st.title("AFR Loss Radar")
from notify_nyc import show_notify_nyc
show_notify_nyc()
st.caption("American Fire Restoration | Manhattan · Bronx · Brooklyn · Queens")
st.warning("PILOT — not a real-time dispatch service. This page checks sources when opened or refreshed; it does not monitor incidents continuously or send automatic alerts.")
st.subheader("Source connection status")
st.dataframe(pd.DataFrame([
    {"Source":"Google News RSS", "Status":"Connected — on-demand", "Notes":"Headline discovery; may be delayed"},
    {"Source":"NYC 311 Open Data", "Status":"Connected — on-demand", "Notes":"Supplementary water complaints; not confirmed losses"},
    {"Source":"NYC Fire Wire", "Status":"Not connected", "Notes":"Permission and machine-readable access must be established"},
    {"Source":"WEEWOO NYC", "Status":"Not connected", "Notes":"Technical access and reuse permissions unverified"},
    {"Source":"Notify NYC", "Status":"Not connected", "Notes":"Suitable public feed must be validated"},
]), hide_index=True, use_container_width=True)
st.caption("Email destination planned: afremployment@gmail.com · Automatic notifications not enabled. Do not place passwords in GitHub.")
st.divider()
st.subheader("Incident discovery — public news (experimental)")
st.caption("Google News RSS headlines only; not live FDNY dispatch, X/Twitter or verified losses. Coverage is incomplete and headlines can be wrong. News may arrive after contractors are engaged.")
news_days=st.selectbox("News lookback",[1,3,7],index=2)
if st.button("Refresh news feed"):
    fetch_news.clear()
news, news_errors=fetch_news(news_days)
if news_errors: st.warning("Some news sources were unavailable. Results may be incomplete.")
if news.empty:
    st.info("No matching headlines returned. This does not mean no fires or water losses occurred.")
else:
    news=news[news["borough"].isin(["Manhattan","Bronx","Brooklyn","Queens"])].copy()
    st.metric("Candidate incident headlines (unverified)",len(news))
    st.dataframe(news[["published_utc","borough","incident_type","priority","headline","source","source_link"]],column_config={"source_link":st.column_config.LinkColumn("Open source")},hide_index=True,use_container_width=True)
    st.download_button("Export news candidates",news.to_csv(index=False),"afr_loss_radar_news_candidates.csv","text/csv")
st.divider()
st.subheader("Supplementary 311 screening")
st.caption("AFR pilot v4 · Manhattan · Bronx · Brooklyn · Queens · 311 screening (unverified reports)")
st.warning("311 complaints and news headlines are unverified. FDNY dispatch, NYC Fire Wire, WEEWOO, Citizen and social-media live feeds are NOT connected. Notify NYC public homepage notices are screened experimentally, not continuously.")
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
                           "afr_loss_radar_311_review.csv", "text/csv")
        with st.expander("Data quality and scoring methodology"):
            st.write("Source: NYC Open Data 311 (erm2-nwe9). Retrieved on demand and cached 15 minutes. Reports are paginated to 20,000 maximum raw records per selected window. No persistent monitoring or automated notifications.")
            st.write("Only selected plumbing/sewer-related complaint categories are screened. Exclusion and scoring rules are conservative and require validation. High priority does not mean a high-dollar claim. No fire detection source is currently connected.")
except Exception as exc:
    st.error(f"NYC Open Data retrieval failed: {exc}")

from source_probe import show_source_lab
show_source_lab()
