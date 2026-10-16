"""Experimental, on-demand extraction of publicly displayed Notify NYC notices.

This is NOT the Notify NYC RSS endpoint or a live dispatch feed.
"""
from datetime import datetime, timezone
import re
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

URL = 'https://a858-nycnotify.nyc.gov/notifynyc/'
KEYWORDS = re.compile(r'\b(?:fire|fdny|smoke|explosion|building collapse|structural collapse|water main break|water main rupture|flooded building|building flood|gas explosion)\b', re.I)
EXCLUDE = re.compile(r'\b(?:staten island|\(si\)|richmond county)\b', re.I)
BOROUGHS = {'(MN)':'Manhattan','(BK)':'Brooklyn','(BX)':'Bronx','(QN)':'Queens'}

@st.cache_data(ttl=300, show_spinner=False)
def fetch_notify():
    response = requests.get(URL, timeout=15, headers={'User-Agent':'Mozilla/5.0 (compatible; AFRLossRadarPilot/4.2)'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    notices = []
    seen = set()
    # Only capture actual alert headings, not unrelated navigation or general site copy.
    for heading in soup.find_all(['h2','h3','h4','h5']):
        title = heading.get_text(' ', strip=True)
        if not title.lower().startswith('notify nyc -'):
            continue
        parent = heading.parent
        snippet = parent.get_text(' ', strip=True)[:1200] if parent else title
        if len(snippet) < len(title) + 20:
            next_node = heading.find_next(['p','div'])
            if next_node:
                snippet = (title + ' ' + next_node.get_text(' ', strip=True))[:1200]
        if title in seen:
            continue
        seen.add(title)
        borough = next((v for k,v in BOROUGHS.items() if k.lower() in title.lower()), 'Unspecified')
        notices.append({'Title':title,'Borough':borough,'Potential incident':bool(KEYWORDS.search(title+' '+snippet)) and not bool(EXCLUDE.search(title+' '+snippet)), 'Details':snippet,'Source':URL})
    return pd.DataFrame(notices), response.status_code

def show_notify_nyc():
    st.divider()
    st.header('Notify NYC · public notice extraction (experimental)')
    st.caption('Reads notices displayed on the official public homepage on demand. Not a verified RSS feed, live FDNY dispatch, or continuous monitoring. A blank result can reflect a site-layout change.')
    if st.button('Retrieve Notify NYC public notices', key='retrieve_notify'):
        fetch_notify.clear()
    try:
        df, status = fetch_notify()
        st.caption(f'Homepage HTTP status: {status} · Retrieved at {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} (page fetch may be cached up to 5 minutes)')
        if df.empty:
            st.warning('No notices could be extracted from the page. This is NOT evidence of zero incidents. The page layout or response may have changed.')
            return
        st.metric('Public notices extracted', len(df))
        st.dataframe(df[['Title','Borough','Potential incident','Details','Source']], hide_index=True, use_container_width=True, column_config={'Source':st.column_config.LinkColumn('Official site')})
        candidates = df[df['Potential incident'] & df['Borough'].isin(['Manhattan','Brooklyn','Queens','Bronx'])]
        st.metric('Potential AFR candidates (title/wording only)', len(candidates))
        if candidates.empty:
            st.info('No matching four-borough fire or major-water candidates among the displayed notices. This does NOT mean there are no active incidents.')
    except requests.RequestException as exc:
        st.error(f'Notify NYC page request failed: {type(exc).__name__}. Other dashboard feeds are unaffected.')
    except Exception as exc:
        st.error(f'Notify NYC extraction failed: {type(exc).__name__}. Other dashboard feeds are unaffected.')
