"""On-demand, conservative consolidation of public incident candidates."""
import re
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from news_sources import fetch_news
from notify_nyc import fetch_notify, URL as NOTIFY_URL

VALID = {'Manhattan', 'Bronx', 'Brooklyn', 'Queens'}
FIRE = re.compile(r'\b(?:structure fire|building fire|apartment fire|commercial fire|fire at|fire in|fdny|blaze|explosion|smoke condition|multi.alarm|\d.alarm)\b', re.I)
WATER = re.compile(r'\b(?:flooded building|building flood|water main break|water main rupture|burst pipe|water damage|sewage backup)\b', re.I)
EXCLUDE = re.compile(r'\b(?:planned|training|drill|fireworks|wildfire|weather update|clear catch basins|traffic delays)\b', re.I)

def _key(title):
    # Only collapse effectively identical titles; different reports may be distinct events.
    return re.sub(r'[^a-z0-9]+', ' ', str(title).lower()).strip()

def build_queue(news, notices, now=None):
    now = now or datetime.now(timezone.utc)
    records = []
    if news is not None and not news.empty:
        for _, row in news.iterrows():
            borough = str(row.get('borough', ''))
            if borough not in VALID:
                continue
            title = str(row.get('headline', ''))
            dt = pd.to_datetime(row.get('published_utc'), utc=True, errors='coerce')
            age = round(max(0, (now - dt.to_pydatetime()).total_seconds() / 60)) if pd.notna(dt) else None
            records.append({'Reported (UTC)':dt.isoformat() if pd.notna(dt) else 'Unknown',
                            'Age (minutes)':age, 'Borough':borough,
                            'Incident':str(row.get('incident_type', 'Review')),
                            'Priority':str(row.get('priority', 'Review')),
                            'Headline':title, 'Source':f"Google News / {row.get('source','publisher')}",
                            'Source link':str(row.get('source_link', '')), '_key':_key(title)})
    if notices is not None and not notices.empty:
        for _, row in notices.iterrows():
            borough = str(row.get('Borough', ''))
            if borough not in VALID or not bool(row.get('Potential incident', False)):
                continue
            title = str(row.get('Title', ''))
            details = str(row.get('Details', ''))
            if EXCLUDE.search(title) or not (FIRE.search(title+' '+details) or WATER.search(title+' '+details)):
                continue
            records.append({'Reported (UTC)':'Unknown', 'Age (minutes)':None,
                            'Borough':borough, 'Incident':'Fire' if FIRE.search(title+' '+details) else 'Water',
                            'Priority':'Review', 'Headline':title, 'Source':'Notify NYC',
                            'Source link':NOTIFY_URL, '_key':_key(title)})
    if not records:
        return pd.DataFrame(columns=['Reported (UTC)','Age (minutes)','Borough','Incident','Priority','Headline','Source','Source link'])
    result = pd.DataFrame(records).drop_duplicates(subset=['Borough','_key'], keep='first')
    return result.drop(columns=['_key']).sort_values('Age (minutes)', ascending=True, na_position='last').reset_index(drop=True)

def show_queue():
    st.subheader('Combined incident review queue')
    st.caption('Google News and Notify NYC public notices, retrieved on demand. Candidates are unverified; not live dispatch. Unknown publication times are never treated as fresh.')
    days = st.selectbox('Incident lookback (days)', [1, 3, 7], index=1, key='combined_days')
    if st.button('Refresh combined sources', key='combined_refresh'):
        fetch_news.clear()
        fetch_notify.clear()
    news, news_errors = None, []
    notices = None
    try:
        news, news_errors = fetch_news(days)
    except Exception as exc:
        st.warning(f'Google News unavailable ({type(exc).__name__}); other sources can still load.')
    try:
        notices, _ = fetch_notify()
    except Exception as exc:
        st.warning(f'Notify NYC unavailable ({type(exc).__name__}); other sources can still load.')
    if news_errors:
        st.warning('Some Google News searches failed; coverage may be incomplete.')
    queue = build_queue(news, notices)
    a,b,c = st.columns(3)
    a.metric('Candidate incidents', len(queue))
    b.metric('Under 60 minutes old', int((queue['Age (minutes)'] < 60).sum()) if not queue.empty else 0)
    c.metric('Time unknown', int(queue['Age (minutes)'].isna().sum()) if not queue.empty else 0)
    if queue.empty:
        st.info('No matching candidates in the returned reports. This does not mean no incidents occurred.')
    else:
        st.dataframe(queue, hide_index=True, use_container_width=True,
                     column_config={'Source link':st.column_config.LinkColumn('Original report')})
        st.download_button('Export combined queue', queue.to_csv(index=False),
                           'afr_loss_radar_incidents.csv', 'text/csv', key='queue_export')
    st.caption('Deduplication removes identical headlines in the same borough only. It does not yet reliably match differently worded reports about the same event.')
