# Air Loss Radar — AFR pilot v1

Four boroughs only: Manhattan, Bronx, Brooklyn, Queens. Fire/water signals only.

## Run on your Mac
1. Install Python 3.10+ if needed.
2. Open Terminal in this folder.
3. Run `python3 -m pip install -r requirements.txt`.
4. Run `python3 -m streamlit run app.py`.
5. Open the local address displayed in Terminal (typically http://localhost:8501).

The app queries NYC Open Data 311 directly. It does not need a dedicated server for local testing. No credentials needed for basic API access. If you deploy publicly, add authentication and API rate-limit handling.

## Important limits
311 service requests are complaints, not confirmed restoration losses. Fire detection via 311 may be sparse or absent. Incident recency, address precision, and report accuracy vary. The app retrieves up to 5,000 recent matching records and does not paginate. This version does not include real-time FDNY dispatch, ownership lookup, email notifications, HubSpot, or persistent lead tracking. Those are subsequent phases contingent on signal quality.

## Suggested evaluation
Review 30–50 signals manually. Record whether each is an actual loss, whether the address is correct, property class, property manager, outreach feasibility, and estimated opportunity. Only automate alerts after validating precision and reporting lag.
