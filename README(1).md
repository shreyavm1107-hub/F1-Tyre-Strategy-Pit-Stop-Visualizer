# F1 Tyre Strategy & Pit Stop Visualizer

An interactive Streamlit dashboard that breaks down race strategy for any
Formula 1 Grand Prix from 2018 onward — tyre stints, degradation trends,
pit stop timing, and undercut/overcut position swings — built on live
official timing data via [FastF1](https://docs.fastf1.dev).

## What it shows

- **Stint Timeline** — a Gantt-style chart of every driver's tyre stints,
  color-coded by compound (soft/medium/hard/inter/wet).
- **Tyre Degradation** — lap time vs. tyre age, so you can see how fast each
  compound falls off pace during a stint.
- **Pit Stops** — a sortable log of every pit stop with time lost in the pits.
- **Undercut Watch** — automatically flags position swings around each pit
  stop to spot successful undercuts/overcuts.

## ⚠️ Important: data is pre-fetched, not loaded live

Streamlit Cloud can't reliably reach F1's live timing API (every field
consistently failed to load in testing — session info, driver list, lap
timing, etc.). So instead of calling FastF1 live from the deployed app, this
project fetches race data **once, locally**, saves it as CSV files, and the
deployed app just reads those static files. No live network dependency, no
Cloud firewall issues, and it loads instantly for users.

## Step 1 — Fetch the data (run this on your own computer, not Streamlit Cloud)

```bash
pip install fastf1 pandas
python fetch_f1_data.py
```

Edit the `RACES_TO_FETCH` list at the top of `fetch_f1_data.py` to choose
which races to include — pick ones with an interesting strategy story
(safety cars, wet-to-dry races, close undercut battles).

This creates a `data/` folder with CSV pairs like:
```
data/2025_Australian_Grand_Prix_laps.csv
data/2025_Australian_Grand_Prix_results.csv
```

## Step 2 — Run it locally to check it works

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Step 3 — Deploy on Streamlit Community Cloud

1. Push `app.py`, `requirements.txt`, and the entire `data/` folder (CSV
   files only — skip the `_fastf1_cache` subfolder inside `data/`, that's
   just FastF1's local download cache and isn't needed) to a public GitHub
   repo.
2. Go to [share.streamlit.io](https://share.streamlit.io), connect the repo,
   and set `app.py` as the entry point.
3. Deploy.

To add more races later, just re-run `fetch_f1_data.py` with an updated
`RACES_TO_FETCH` list and upload the new CSVs — the app automatically
detects any race present in the `data/` folder.

## Notes for extending this

- Swap the hardcoded 'R' session type for Qualifying/Sprint by adding a
  session-type selector and passing it into `load_session()`.
- The undercut logic here is intentionally simple (position 1 lap before vs.
  2 laps after a stop) — for a stronger version, compare against the driver's
  closest rival's gap at the same lap, not just raw position.
- Telemetry (speed/throttle/brake traces) isn't pulled here to keep load
  times fast — that's a natural follow-up project using
  `session.laps.pick_driver(...).pick_fastest().get_telemetry()`.
