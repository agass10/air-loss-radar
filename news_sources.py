"""Public news RSS discovery; unverified, not a dispatch or real-time feed."""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import requests
import pandas as pd

BOROUGHS = {'Manhattan':['manhattan','harlem','upper east side','upper west side','midtown','lower east side','chelsea','financial district','washington heights','inwood'], 'Bronx':['bronx'], 'Brooklyn':['brooklyn'], 'Queens':['queens','astoria','flushing','jamaica queens','long island city','forest hills']}
SEARCHES = [
 '"Manhattan" ("building fire" OR "apartment fire" OR "commercial fire" OR "water main break" OR "flooded building") when:7d',
 '"Bronx" ("building fire" OR "apartment fire" OR "commercial fire" OR "water main break" OR "flooded building") when:7d',
 '"Brooklyn" ("building fire" OR "apartment fire" OR "commercial fire" OR "water main break" OR "flooded building") when:7d',
 '"Queens" ("building fire" OR "apartment fire" OR "commercial fire" OR "water main break" OR "flooded building") when:7d',
]
EXCLUSIONS = ['firefighter injured in training','fire department hiring','fire safety tips','wildfire smoke','fireworks','firearm','fire station','fire drill','water bill','water quality','fire hydrant']

def classify(text):
    t=text.lower()
    if any(x in t for x in EXCLUSIONS): return None
    boroughs=[b for b,words in BOROUGHS.items() if any(w in t for w in words)]
    if not boroughs: return None
    fire=any(x in t for x in ['building fire','apartment fire','structure fire','commercial fire','two-alarm','three-alarm','2-alarm','3-alarm','fire rips','fire breaks out','blaze'])
    water=any(x in t for x in ['water main break','flooded building','basement flooding','burst pipe','water damage','sewage backup'])
    if not (fire or water): return None
    high=any(x in t for x in ['two-alarm','three-alarm','2-alarm','3-alarm','multiple buildings','dozens displaced','multiple floors','commercial building','high-rise'])
    return {'borough':boroughs[0] if len(boroughs)==1 else 'Needs location review','incident_type':'Fire' if fire else 'Water','priority':'High' if high else 'Review','score':75 if high else 45}

@__import__('streamlit').cache_data(ttl=900,show_spinner='Checking public news RSS...')
def fetch_news(days=7):
    rows=[]; errors=[]
    for q in SEARCHES:
        try:
            r=requests.get('https://news.google.com/rss/search',params={'q':q,'hl':'en-US','gl':'US','ceid':'US:en'},timeout=18,headers={'User-Agent':'AFRLossRadarPilot/0.4 (public RSS research)'})
            r.raise_for_status()
            root=ET.fromstring(r.content)
            for item in root.findall('./channel/item'):
                title=item.findtext('title',''); link=item.findtext('link',''); pub=item.findtext('pubDate','')
                source=item.findtext('source','')
                try: published=parsedate_to_datetime(pub).astimezone(timezone.utc)
                except Exception: continue
                if published < datetime.now(timezone.utc)-timedelta(days=days):continue
                found=classify(title)
                if found:rows.append({'published_utc':published.isoformat(timespec='minutes'),'headline':title,'source':source,'source_link':link,**found})
        except Exception as e:errors.append(f'News RSS request failed: {type(e).__name__}')
    df=pd.DataFrame(rows)
    if not df.empty: df=df.drop_duplicates(subset=['source_link']).sort_values('published_utc',ascending=False)
    return df, errors
