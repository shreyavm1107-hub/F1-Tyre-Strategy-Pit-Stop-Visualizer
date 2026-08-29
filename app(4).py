import streamlit as st
import fastf1
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# ----------------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="F1 Tyre Strategy Visualizer",
    page_icon="🏎️",
    layout="wide",
)

# ----------------------------------------------------------------------------
# FASTF1 CACHE SETUP
# FastF1 caches downloaded session data locally so repeat loads are instant.
# On Streamlit Cloud this folder persists only for the life of the container,
# but it still saves you from re-downloading during a single session.
# ----------------------------------------------------------------------------
CACHE_DIR = "f1_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

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
# SIDEBAR — SESSION SELECTOR
# ----------------------------------------------------------------------------
st.sidebar.header("🏁 Select a Race")

year = st.sidebar.selectbox("Season", list(range(2026, 2017, -1)), index=1)


@st.cache_data(show_spinner="Loading race calendar...")
def load_schedule(year: int) -> pd.DataFrame:
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    return schedule[["RoundNumber", "EventName", "Country", "EventDate"]]


schedule = load_schedule(year)
event_names = schedule["EventName"].tolist()

if not event_names:
    st.sidebar.warning("No events found for this season yet.")
    st.stop()

event_name = st.sidebar.selectbox("Grand Prix", event_names)


# NOTE: We deliberately do NOT cache the raw fastf1 Session object with
# st.cache_data. Session keeps its "is this loaded yet" state in private
# attributes that don't survive Streamlit's pickle-based caching round-trip,
# which causes a DataNotLoadedError on cache hits. Instead we load a fresh
# Session every run (FastF1 has its own on-disk cache for the API calls, so
# this stays fast) and only cache the plain pandas DataFrames we pull out of it.
def _load_session_object(year: int, event_name: str, session_type: str = "R"):
    session = fastf1.get_session(year, event_name, session_type)
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    return session


@st.cache_data(show_spinner="Fetching race data from the F1 timing API...")
def load_laps_and_results(year: int, event_name: str, session_type: str = "R"):
    session = _load_session_object(year, event_name, session_type)
    laps_df = pd.DataFrame(session.laps)
    results_df = pd.DataFrame(session.results)
    return laps_df, results_df


laps, results = load_laps_and_results(year, event_name)

if laps.empty:
    st.error("No lap data available for this session. Try a different race — very recent or very old sessions sometimes have gaps.")
    st.stop()

drivers = laps["Driver"].unique().tolist()
driver_selection = st.sidebar.multiselect(
    "Drivers to compare (leave empty = all)",
    sorted(drivers),
    default=[],
)

if driver_selection:
    laps_filtered = laps[laps["Driver"].isin(driver_selection)]
else:
    laps_filtered = laps

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.title("🏎️ F1 Tyre Strategy & Pit Stop Visualizer")
st.caption(f"By Shreya Vishwakarma | {year} {event_name} — Race strategy breakdown from FastF1 timing data")

st.markdown(
    f"**{event_name} {year}** · {len(drivers)} drivers · {int(laps['LapNumber'].max())} laps"
)

# ----------------------------------------------------------------------------
# BUILD STINT SUMMARY
# A "stint" is a continuous run on one tyre compound between pit stops.
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

    driver_order = (
        results.sort_values("Position")["Abbreviation"].tolist()
        if not results.empty
        else sorted(stints["Driver"].unique())
    )
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

    # Manual legend (compound colors)
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
    deg_data = deg_data[deg_data["PitOutTime"].isna()]  # drop in/out laps for cleaner trend
    deg_data = deg_data[deg_data["LapTime"].notna()]
    deg_data["LapTimeSeconds"] = deg_data["LapTime"].dt.total_seconds()

    compound_focus = st.multiselect(
        "Filter by compound",
        sorted(deg_data["Compound"].dropna().unique().tolist()),
        default=sorted(deg_data["Compound"].dropna().unique().tolist()),
    )
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
        pit_laps["PitDuration"] = (
            pit_laps["PitOutTime"] - pit_laps["PitInTime"]
        ).dt.total_seconds()

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
        undercut_rows = []
        for _, stop in pit_laps.iterrows() if not pit_laps.empty else []:
            driver = stop["Driver"]
            pit_lap = stop["LapNumber"]

            before = laps[(laps["Driver"] == driver) & (laps["LapNumber"] == pit_lap - 1)]
            after = laps[(laps["Driver"] == driver) & (laps["LapNumber"] == pit_lap + 2)]

            if not before.empty and not after.empty:
                pos_before = before["Position"].values[0]
                pos_after = after["Position"].values[0]
                if pd.notna(pos_before) and pd.notna(pos_after):
                    undercut_rows.append(
                        {
                            "Driver": driver,
                            "Pit Lap": int(pit_lap),
                            "Position Before": int(pos_before),
                            "Position After (+2 laps)": int(pos_after),
                            "Places Gained": int(pos_before - pos_after),
                        }
                    )

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
st.caption("Data: FastF1 (official F1 live timing API) · Built with Streamlit & Plotly")
