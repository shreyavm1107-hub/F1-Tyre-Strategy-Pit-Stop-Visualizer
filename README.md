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

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

First load for any given race will take 20–60 seconds while FastF1 downloads
and caches the session data from F1's timing API. Every load after that for
the same race is near-instant thanks to the local cache folder (`f1_cache/`).

## Deploy on Streamlit Community Cloud

1. Push this folder (`app.py`, `requirements.txt`) to a public GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io), connect the repo,
   and set `app.py` as the entry point.
3. Deploy. Note: Streamlit Cloud's free tier has a limited/ephemeral
   filesystem, so the FastF1 cache resets between deploys/reboots — this
   just means the first load of each race per session is a bit slower, not
   that anything breaks.

## Notes for extending this

- Swap the hardcoded 'R' session type for Qualifying/Sprint by adding a
  session-type selector and passing it into `load_session()`.
- The undercut logic here is intentionally simple (position 1 lap before vs.
  2 laps after a stop) — for a stronger version, compare against the driver's
  closest rival's gap at the same lap, not just raw position.
- Telemetry (speed/throttle/brake traces) isn't pulled here to keep load
  times fast — that's a natural follow-up project using
  `session.laps.pick_driver(...).pick_fastest().get_telemetry()`.
