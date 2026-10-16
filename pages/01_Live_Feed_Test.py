"""Read-only, on-demand OpenMHz feasibility test. Not a live fire incident feed."""
from datetime import datetime, timezone
import requests
import streamlit as st

st.title('AFR · FDNY live-feed feasibility test')
st.warning('Experimental: radio call metadata, NOT identified fires. No background monitoring, transcription, or alerts.')
st.write('This checks whether public OpenMHz NYC dispatch metadata can be reached from Streamlit Cloud. It does not scrape Fire Wire.')
API='https://api.openmhz.com'
SYSTEM='nyctemp'
HEADERS={'User-Agent':'AFR-Loss-Radar-Feasibility-Test/0.1'}

def fetch(path, params=None):
    r=requests.get(API+path,params=params,headers=HEADERS,timeout=12)
    r.raise_for_status()
    return r.json()

if st.button('Test NYC dispatch metadata connection'):
    st.write('Test run (UTC):', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    for label,path in [('NYC talkgroups',f'/{SYSTEM}/talkgroups'),('Recent NYC calls',f'/{SYSTEM}/calls')]:
        try:
            data=fetch(path)
            st.success(f'{label}: reachable')
            if isinstance(data,list):
                st.write('Records returned:',len(data))
                st.json(data[:3])
            elif isinstance(data,dict):
                st.write('Response keys:',list(data)[:12])
                for key in ('calls','talkgroups','results'):
                    if isinstance(data.get(key),list):
                        st.write(f'{key} records:',len(data[key]))
                        st.json(data[key][:3]);break
                else: st.json({k:str(v)[:200] for k,v in list(data.items())[:5]})
            else: st.write('Unexpected response type:',type(data).__name__)
        except requests.HTTPError as e:
            st.error(f'{label}: HTTP {e.response.status_code}. Endpoint may have changed or require access.')
        except requests.RequestException as e:
            st.error(f'{label}: connection failed: {type(e).__name__}: {e}')
        except ValueError:
            st.error(f'{label}: response was not JSON.')
st.caption('OpenMHz is independently operated. Its open-source server documents these endpoint patterns, but production access, licensing and NYC coverage must be verified before any operational integration. Keep requests manual and infrequent.')
