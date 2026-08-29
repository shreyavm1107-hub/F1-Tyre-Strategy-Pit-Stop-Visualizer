"""
Run this ONCE on your own computer (not Streamlit Cloud) to download F1
race data and save it as local CSV files. Streamlit Cloud can't reliably
reach F1's live timing API, so we fetch the data here and commit the CSVs
to the repo instead of calling the API from the deployed app.

Usage:
    pip install fastf1 pandas
    python fetch_f1_data.py

This will create a "data/" folder with one CSV per race:
    data/2025_Australian_Grand_Prix_laps.csv
    data/2025_Australian_Grand_Prix_results.csv
    ... etc for each race in RACES_TO_FETCH below

Edit RACES_TO_FETCH to pick whichever races you want in your dashboard —
aim for races with an interesting strategy story (safety cars, wet-to-dry,
close undercut battles) since those make for the best portfolio talking
points.
"""

import os
import re
import time

import fastf1
import pandas as pd

# ----------------------------------------------------------------------------
# CONFIG — edit this list to choose which races to include
# ----------------------------------------------------------------------------
RACES_TO_FETCH = [
    (2025, "Australian Grand Prix"),
    (2025, "Monaco Grand Prix"),
    (2025, "Belgian Grand Prix"),
    (2024, "Brazilian Grand Prix"),   # wet-to-dry strategy chaos
    (2023, "Qatar Grand Prix"),
]

SESSION_TYPE = "R"  # Race. Could also use "Q" for Qualifying, "S" for Sprint.
OUTPUT_DIR = "data"


def safe_filename(name: str) -> str:
    """Turn 'Australian Grand Prix' into 'Australian_Grand_Prix'."""
    return re.sub(r"[^\w\-]", "_", name)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(os.path.join(OUTPUT_DIR, "_fastf1_cache"))

    for year, event_name in RACES_TO_FETCH:
        print(f"\n=== Fetching {year} {event_name} ({SESSION_TYPE}) ===")
        try:
            session = fastf1.get_session(year, event_name, SESSION_TYPE, backend="fastf1")
            session.load(laps=True, telemetry=False, weather=False, messages=False)

            if not session.f1_api_support:
                print(f"  ⚠️  Skipping — no lap/telemetry data available for this session.")
                continue

            laps_df = pd.DataFrame(session.laps)
            results_df = pd.DataFrame(session.results)

            # Add identifying columns so multiple races can later be combined
            laps_df["Year"] = year
            laps_df["EventName"] = event_name
            results_df["Year"] = year
            results_df["EventName"] = event_name

            fname = safe_filename(f"{year}_{event_name}")
            laps_path = os.path.join(OUTPUT_DIR, f"{fname}_laps.csv")
            results_path = os.path.join(OUTPUT_DIR, f"{fname}_results.csv")

            laps_df.to_csv(laps_path, index=False)
            results_df.to_csv(results_path, index=False)

            print(f"  ✅ Saved {len(laps_df)} laps -> {laps_path}")
            print(f"  ✅ Saved {len(results_df)} results -> {results_path}")

        except Exception as e:
            print(f"  ❌ Failed to fetch {year} {event_name}: {e}")

        time.sleep(1)  # be polite to the API between requests

    print("\nDone. Upload the entire 'data/' folder (CSV files only, skip _fastf1_cache) to your GitHub repo.")


if __name__ == "__main__":
    main()
