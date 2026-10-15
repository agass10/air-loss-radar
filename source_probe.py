"""Conservative diagnostics for published sources; no social media scraping."""
from datetime import datetime, timezone
import requests
import streamlit as st

SOURCES = [
    ("Notify NYC official public alerts", "https://a858-nycnotify.nyc.gov/notifynyc/", "Public page; availability only, not incident ingestion"),
    ("NYC Fire Wire", "https://nycfirewire.net/", "Website reachability only; automated incident feed not authorized"),
    ("WEEWOO", "https://weewoo.nyc/", "Website reachability only; incident feed not integrated"),
    ("FDNY official website", "https://www.nyc.gov/site/fdny/index.page", "Website reachability only; not live dispatch"),
    ("Notify NYC X", "https://x.com/NotifyNYC", "Reference link only; X API access required for integration"),
    ("FDNY Alerts X", "https://x.com/FDNYAlerts", "Reference link only; X API access required for integration"),
]

@st.cache_data(ttl=300, show_spinner=False)
def check_sources():
    results=[]
    for name,url,meaning in SOURCES:
        if " X" in name:
            results.append({"Source":name,"Test":"Not attempted","HTTP":"—","What this proves":meaning,"Website":url})
            continue
        try:
            response=requests.get(url,timeout=9,headers={"User-Agent":"AFRLossRadarPilot/4.1 (source availability check)"})
            status=response.status_code
            results.append({"Source":name,"Test":"Website reachable" if status==200 else "HTTP response received", "HTTP":str(status),"What this proves":meaning,"Website":url})
        except requests.RequestException as exc:
            results.append({"Source":name,"Test":"Unavailable from Streamlit","HTTP":"—","What this proves":f"{meaning}. {type(exc).__name__}","Website":url})
    return results

def show_source_lab():
    st.divider()
    st.header("Source connection lab · v4.1")
    st.caption("Tests whether public websites respond from the Streamlit server. A reachable website does NOT mean live incidents are available or integrated. X is not scraped. Tests run only when you press the button.")
    if st.button("Run source connection tests",key="source_lab_test"):
        check_sources.clear()
        st.session_state["source_lab_results"]=check_sources()
        st.session_state["source_lab_time"]=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if "source_lab_results" in st.session_state:
        st.caption("Last tested: "+st.session_state["source_lab_time"])
        st.dataframe(st.session_state["source_lab_results"],column_config={"Website":st.column_config.LinkColumn("Open website")},hide_index=True,use_container_width=True)
        st.warning("No live dispatch, Fire Wire, WEEWOO or X incident data is ingested by these tests. No automated monitoring or email alerts are running.")
