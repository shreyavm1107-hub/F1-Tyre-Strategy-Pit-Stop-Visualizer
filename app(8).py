import glob
import os
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="F1 Tyre Strategy Visualizer",
    page_icon="🏎️",
    layout="wide",
)

DATA_DIR = "data"

# Timedelta-type columns FastF1 produces. When saved to CSV these become
# plain strings like "0 days 00:01:32.032000", so we convert them back to
# proper Timedelta objects after loading.
TIMEDELTA_COLUMNS = [
    "LapTime", "LapStartTime", "PitOutTime", "PitInTime",
    "Sector1Time", "Sector2Time", "Sector3Time",
    "Sector1SessionTime", "Sector2SessionTime", "Sector3SessionTime",
]

# Official-ish tyre compound colors (2018+ Pirelli scheme)
COMPOUND_COLORS = {
    "SOFT": "#DA291C",
    "MEDIUM": "#FFD400",
    "HARD": "#F0F0F0",
    "INTERMEDIATE": "#43B02A",
    "WET": "#0067AD",
    "UNKNOWN": "#888888",
    "TEST_UNKNOWN": "#888888",
}


# ----------------------------------------------------------------------------
# DISCOVER AVAILABLE RACES FROM THE data/ FOLDER
# Expects files named like: 2025_Australian_Grand_Prix_laps.csv
#                            2025_Australian_Grand_Prix_results.csv
# ----------------------------------------------------------------------------
@st.cache_data
def discover_races():
    laps_files = glob.glob(os.path.join(DATA_DIR, "*_laps.csv"))
    races = []
    for path in sorted(laps_files):
        base = os.path.basename(path).replace("_laps.csv", "")
        match = re.match(r"(\d{4})_(.+)", base)
        if not match:
            continue
        year, event_slug = match.groups()
        event_display = event_slug.replace("_", " ")
        results_path = os.path.join(DATA_DIR, f"{base}_results.csv")
        races.append({
            "year": int(year),
            "event": event_display,
            "laps_path": path,
            "results_path": results_path if os.path.exists(results_path) else None,
            "label": f"{year} — {event_display}",
        })
    return races


races = discover_races()

if not races:
    st.error(
        "No race data found in the `data/` folder. This app reads pre-fetched "
        "CSV files rather than calling the F1 timing API live. Run "
        "`fetch_f1_data.py` locally and upload the resulting `data/` folder "
        "to the repo — see the README for details."
    )
    st.stop()

# ----------------------------------------------------------------------------
# SIDEBAR — RACE SELECTOR
# ----------------------------------------------------------------------------
st.sidebar.header("🏁 Select a Race")
race_labels = [r["label"] for r in races]
selected_label = st.sidebar.selectbox("Race", race_labels)
selected_race = next(r for r in races if r["label"] == selected_label)


@st.cache_data
def load_race_data(laps_path: str, results_path):
    laps_df = pd.read_csv(laps_path)
    for col in TIMEDELTA_COLUMNS:
        if col in laps_df.columns:
            laps_df[col] = pd.to_timedelta(laps_df[col], errors="coerce")

    if results_path:
        results_df = pd.read_csv(results_path)
    else:
        results_df = pd.DataFrame()

    return laps_df, results_df


laps, results = load_race_data(selected_race["laps_path"], selected_race["results_path"])

if laps.empty:
    st.error("This race's data file is empty. Try a different race or re-run fetch_f1_data.py for it.")
    st.stop()

drivers = laps["Driver"].unique().tolist()
driver_selection = st.sidebar.multiselect(
    "Drivers to compare (leave empty = all)",
    sorted(drivers),
    default=[],
)

laps_filtered = laps[laps["Driver"].isin(driver_selection)] if driver_selection else laps

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.title("🏎️ F1 Tyre Strategy & Pit Stop Visualizer")
st.caption(
    f"By Shreya Vishwakarma | {selected_race['year']} {selected_race['event']} — "
    f"Race strategy breakdown from FastF1 timing data"
)
st.markdown(
    f"**{selected_race['event']} {selected_race['year']}** · {len(drivers)} drivers · "
    f"{int(laps['LapNumber'].max())} laps"
)

# ----------------------------------------------------------------------------
# BUILD STINT SUMMARY
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def build_stints(_laps: pd.DataFrame) -> pd.DataFrame:
    stints = (
        _laps[["Driver", "Stint", "Compound", "LapNumber"]]
        .groupby(["Driver", "Stint", "Compound"])
        .agg(StartLap=("LapNumber", "min"), EndLap=("LapNumber", "max"))
        .reset_index()
    )
    stints["StintLength"] = stints["EndLap"] - stints["StartLap"] + 1
    stints = stints.sort_values(["Driver", "StartLap"])
    return stints


stints = build_stints(laps_filtered)

# ----------------------------------------------------------------------------
# TAB LAYOUT
# ----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["🧵 Stint Timeline", "⏱️ Tyre Degradation", "🔧 Pit Stops", "🔀 Undercut Watch"]
)

# ---- TAB 1: STINT TIMELINE (Gantt-style) -----------------------------------
with tab1:
    st.subheader("Stint Timeline by Driver")
    st.markdown(
        "Each bar shows one continuous stint on a single tyre compound. "
        "Longer bars = longer stints; a new bar starts right after a pit stop."
    )

    if not results.empty and "Position" in results.columns:
        driver_order = results.sort_values("Position")["Abbreviation"].tolist()
    else:
        driver_order = sorted(stints["Driver"].unique())
    driver_order = [d for d in driver_order if d in stints["Driver"].unique()]

    fig = go.Figure()
    for _, row in stints.iterrows():
        color = COMPOUND_COLORS.get(str(row["Compound"]).upper(), "#888888")
        fig.add_trace(
            go.Bar(
                y=[row["Driver"]],
                x=[row["StintLength"]],
                base=[row["StartLap"] - 1],
                orientation="h",
                marker=dict(color=color, line=dict(color="black", width=0.5)),
                name=row["Compound"],
                showlegend=False,
                hovertemplate=(
                    f"<b>{row['Driver']}</b><br>"
                    f"Compound: {row['Compound']}<br>"
                    f"Laps: {int(row['StartLap'])}–{int(row['EndLap'])}<br>"
                    f"Stint length: {int(row['StintLength'])} laps<extra></extra>"
                ),
            )
        )

    for compound, color in COMPOUND_COLORS.items():
        if compound in stints["Compound"].str.upper().unique():
            fig.add_trace(
                go.Bar(
                    y=[None], x=[None], orientation="h",
                    marker=dict(color=color), name=compound, showlegend=True,
                )
            )

    fig.update_layout(
        barmode="stack",
        yaxis=dict(categoryorder="array", categoryarray=driver_order[::-1], title=None),
        xaxis=dict(title="Lap Number"),
        height=max(400, 28 * len(driver_order)),
        legend_title="Compound",
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

# ---- TAB 2: TYRE DEGRADATION ------------------------------------------------
with tab2:
    st.subheader("Pace Drop-off Within Each Stint")
    st.markdown(
        "Lap time vs. tyre age (laps since fitted). Rising lines show degradation; "
        "flatter lines mean the compound is holding pace well."
    )

    deg_data = laps_filtered.copy()
    deg_data = deg_data[deg_data["PitOutTime"].isna()]
    deg_data = deg_data[deg_data["LapTime"].notna()]
    deg_data["LapTimeSeconds"] = deg_data["LapTime"].dt.total_seconds()

    compound_options = sorted(deg_data["Compound"].dropna().unique().tolist())
    compound_focus = st.multiselect("Filter by compound", compound_options, default=compound_options)
    deg_data = deg_data[deg_data["Compound"].isin(compound_focus)]

    if deg_data.empty:
        st.info("No clean lap data to plot for this selection.")
    else:
        fig2 = px.scatter(
            deg_data,
            x="TyreLife",
            y="LapTimeSeconds",
            color="Compound",
            symbol="Driver" if len(driver_selection) <= 6 and driver_selection else None,
            trendline="lowess",
            color_discrete_map=COMPOUND_COLORS,
            labels={"TyreLife": "Tyre Age (laps)", "LapTimeSeconds": "Lap Time (s)"},
            hover_data=["Driver", "LapNumber"],
        )
        fig2.update_layout(height=550, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig2, use_container_width=True)

# ---- TAB 3: PIT STOPS -------------------------------------------------------
with tab3:
    st.subheader("Pit Stop Log")

    pit_laps = laps_filtered[laps_filtered["PitInTime"].notna()].copy()
    if pit_laps.empty:
        st.info("No pit stops recorded for the current selection.")
    else:
        pit_laps["PitDuration"] = (pit_laps["PitOutTime"] - pit_laps["PitInTime"]).dt.total_seconds()

        pit_table = pit_laps[["Driver", "LapNumber", "Compound", "Stint", "PitDuration"]].rename(
            columns={
                "LapNumber": "Lap",
                "Compound": "New Compound",
                "Stint": "New Stint #",
                "PitDuration": "Time in Pit (s)",
            }
        ).sort_values(["Lap", "Driver"])
        pit_table["Time in Pit (s)"] = pit_table["Time in Pit (s)"].round(2)

        st.dataframe(pit_table, use_container_width=True, hide_index=True)

        fig3 = px.bar(
            pit_table.sort_values("Time in Pit (s)"),
            x="Time in Pit (s)",
            y="Driver",
            color="New Compound",
            orientation="h",
            color_discrete_map=COMPOUND_COLORS,
            hover_data=["Lap"],
        )
        fig3.update_layout(height=max(400, 22 * len(pit_table)), margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig3, use_container_width=True)

# ---- TAB 4: UNDERCUT WATCH --------------------------------------------------
with tab4:
    st.subheader("Undercut / Overcut Position Swings")
    st.markdown(
        "Compares track position 1 lap before a pit stop vs. 2 laps after the driver "
        "rejoins. A positive swing means the driver gained places around their stop — "
        "a sign the undercut (or a rival's mistake) worked."
    )

    if laps_filtered.empty or "Position" not in laps_filtered.columns:
        st.info("Position data not available for this session.")
    else:
        pit_laps_all = laps_filtered[laps_filtered["PitInTime"].notna()]
        undercut_rows = []
        for _, stop in pit_laps_all.iterrows():
            driver = stop["Driver"]
            pit_lap = stop["LapNumber"]

            before = laps[(laps["Driver"] == driver) & (laps["LapNumber"] == pit_lap - 1)]
            after = laps[(laps["Driver"] == driver) & (laps["LapNumber"] == pit_lap + 2)]

            if not before.empty and not after.empty:
                pos_before = before["Position"].values[0]
                pos_after = after["Position"].values[0]
                if pd.notna(pos_before) and pd.notna(pos_after):
                    undercut_rows.append({
                        "Driver": driver,
                        "Pit Lap": int(pit_lap),
                        "Position Before": int(pos_before),
                        "Position After (+2 laps)": int(pos_after),
                        "Places Gained": int(pos_before - pos_after),
                    })

        if not undercut_rows:
            st.info("Not enough surrounding lap data to compute position swings for this selection.")
        else:
            undercut_df = pd.DataFrame(undercut_rows).sort_values("Places Gained", ascending=False)
            st.dataframe(undercut_df, use_container_width=True, hide_index=True)

            fig4 = px.bar(
                undercut_df,
                x="Places Gained",
                y="Driver",
                orientation="h",
                color="Places Gained",
                color_continuous_scale="RdYlGn",
                hover_data=["Pit Lap"],
            )
            fig4.update_layout(height=max(400, 22 * len(undercut_df)), margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig4, use_container_width=True)

st.markdown("---")
st.caption("Data: FastF1 (official F1 live timing API), pre-fetched · Built with Streamlit & Plotly")
