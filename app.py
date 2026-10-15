import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title='Air Loss Radar | AFR',layout='wide')
st.title('Air Loss Radar')
st.caption('AFR pilot • Manhattan, Bronx, Brooklyn, Queens • Public 311 signals (not verified losses)')
BOROUGHS=['MANHATTAN','BRONX','BROOKLYN','QUEENS']
API='https://data.cityofnewyork.us/resource/erm2-nwe9.json'
@st.cache_data(ttl=900)
def fetch(days):
    start=(datetime.now()-timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
    where="created_date >= '{}' AND borough IN ('MANHATTAN','BRONX','BROOKLYN','QUEENS') AND (upper(complaint_type) like '%WATER%' OR upper(complaint_type) like '%PLUMB%' OR upper(complaint_type) like '%SEWER%' OR upper(complaint_type) like '%FIRE%' OR upper(descriptor) like '%LEAK%' OR upper(descriptor) like '%FLOOD%')".format(start)
    params={'$where':where,'$limit':5000,'$order':'created_date DESC','$select':'unique_key,created_date,borough,incident_address,complaint_type,descriptor,status,latitude,longitude'}
    r=requests.get(API,params=params,timeout=35);r.raise_for_status()
    return pd.DataFrame(r.json())

def classify(row):
    t=(str(row.get('complaint_type',''))+' '+str(row.get('descriptor',''))).lower()
    if any(x in t for x in ['fire','smoke']):return 'Fire signal'
    if any(x in t for x in ['leak','flood','sewer','plumb','water']):return 'Water signal'
    return 'Review'

days=st.sidebar.selectbox('Lookback (days)',[1,3,7,14,30],index=2)
selected=st.sidebar.multiselect('Boroughs',BOROUGHS,default=BOROUGHS)
st.sidebar.info('This is a research pilot. 311 complaints do not confirm a restoration loss or an available job.')
try:
    df=fetch(days)
    if df.empty: st.warning('No matching 311 records returned for this period.')
    else:
        df=df[df['borough'].isin(selected)].copy()
        df['Signal']=df.apply(classify,axis=1)
        df['created_date']=pd.to_datetime(df['created_date'],errors='coerce')
        c1,c2,c3=st.columns(3)
        c1.metric('Potential signals',len(df));c2.metric('Water-related',sum(df.Signal=='Water signal'));c3.metric('Fire-related',sum(df.Signal=='Fire signal'))
        st.subheader('Incident signal queue')
        st.dataframe(df[['created_date','borough','incident_address','Signal','complaint_type','descriptor','status','unique_key']],hide_index=True,use_container_width=True)
        coords=df.dropna(subset=['latitude','longitude']).copy()
        if len(coords):
            coords['lat']=pd.to_numeric(coords.latitude,errors='coerce');coords['lon']=pd.to_numeric(coords.longitude,errors='coerce')
            st.subheader('Mapped signals');st.map(coords.dropna(subset=['lat','lon'])[['lat','lon']])
        st.download_button('Export CSV for lead review',df.to_csv(index=False),'air_loss_radar_signals.csv','text/csv')
except Exception as e:
    st.error(f'Unable to retrieve NYC Open Data: {e}')
st.divider()
st.caption('Source: NYC Open Data 311 (erm2-nwe9). Data availability and reporting delays vary. No automated outreach or verified property ownership in v1.')
