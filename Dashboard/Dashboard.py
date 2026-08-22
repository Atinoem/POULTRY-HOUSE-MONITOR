"""
===============================================================
Smart Poultry House Monitor - Streamlit Dashboard (COM4 Auto-Connect)
===============================================================
Reads live physical data from DHT22, LDR, MOSFET Fan, Bulb, and Buzzer.
Includes week preset synchronization and automatic audio alarms.

Shared serial, threshold and UI helpers live in the repository-level
``coopguard_core`` package.

Expected CSV format from Arduino:
    Temperature,Humidity,Light_Level,Fan_Status
    e.g.  28.5,60.2,512,1

Run with:
    streamlit run Dashboard.py
===============================================================
"""

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coopguard_core import (  # noqa: E402  (path bootstrap must run first)
    AGE_THRESHOLDS,
    CLASSIC_CARD_THEME,
    DEFAULT_BAUD_RATE,
    DEFAULT_MAX_POINTS,
    REFRESH_SECONDS,
    SIREN_URL,
    SerialManager,
    WARNING_BEEP_URL,
    card_html,
    detect_arduino_port,
    humidity_trend_chart,
    list_serial_ports,
    play_alarm_audio,
    render_connection_controls,
    render_offline_cards,
    sync_manager_targets,
)

st.set_page_config(
    page_title="Poultry House Monitor",
    page_icon="🐔",
    layout="wide",
)


@st.cache_resource
def get_manager():
    return SerialManager(max_points=DEFAULT_MAX_POINTS)


manager = get_manager()

# ---------------------------------------------------------------
# Automatic Port Detection & Startup Connection (Strict COM4)
# ---------------------------------------------------------------
ports_found = list_serial_ports()
detected_port = detect_arduino_port(ports_found)

if detected_port and not manager.connected_port and not manager.last_error:
    manager.connect_serial(detected_port, DEFAULT_BAUD_RATE)

# ---------------------------------------------------------------
# Sidebar - connection controls + chick age selector
# ---------------------------------------------------------------
st.sidebar.title("🐔 Poultry Monitor Setup")

st.sidebar.subheader("Chick Age Selection")
selected_age = st.sidebar.selectbox("Select chick age", list(AGE_THRESHOLDS.keys()), index=1)
target_low, target_high, week_cmd = AGE_THRESHOLDS[selected_age]

st.sidebar.caption(f"Optimal Range: **{target_low}°C – {target_high}°C**")
st.sidebar.caption(f"🔴 Overheat Alert: **>{target_high}°C** | 🟡 Cold Alert: **<{target_low}°C**")

sync_manager_targets(manager, target_low, target_high, week_cmd)

st.sidebar.divider()
render_connection_controls(
    manager,
    ports_found,
    detected_port,
    no_ports_caption="⚠️ No physical COM ports detected. Plug in your Arduino USB cable.",
)

# ---------------------------------------------------------------
# Main Dashboard
# ---------------------------------------------------------------
st.title("Smart Poultry House Monitor")
st.caption(f"Development Stage: **{selected_age}** | Target Range: **{target_low}°C to {target_high}°C**")


@st.fragment(run_every=REFRESH_SECONDS)
def live_dashboard():
    df = manager.get_dataframe()
    latest = manager.get_latest()

    # ---- metric cards ----
    c1, c2, c3, c4, c5 = st.columns(5)

    if latest is None or df.empty:
        render_offline_cards([c1, c2, c3, c4, c5], CLASSIC_CARD_THEME)
        st.info("🔌 Waiting for live physical data... Searching for COM4.")
        return

    temp = latest["temperature"]
    hum = latest["humidity"]
    light = latest["light_level"]
    fan_on = latest["fan_status"] == 1

    # Bulb status calculation matching Arduino logic:
    # ON only when Yellow LED is ON (temp < target_low) and activeWeekMode is Week 1-4
    bulb_on = (temp < target_low) and (week_cmd is not None)

    # Determine status color
    if temp > target_high:
        temp_status = "warn"
    elif temp < target_low:
        temp_status = "low"
    else:
        temp_status = "ok"

    c1.markdown(card_html("Temperature", f"{temp:.1f} °C", temp_status), unsafe_allow_html=True)
    c2.markdown(card_html("Humidity", f"{hum:.1f} %", "neutral"), unsafe_allow_html=True)
    c3.markdown(card_html("Light Level", f"{light} / 1023", "neutral"), unsafe_allow_html=True)
    c4.markdown(card_html("Fan Status", "ON" if fan_on else "OFF", "warn" if fan_on else "ok"), unsafe_allow_html=True)
    c5.markdown(card_html("Heating Bulb", "ON" if bulb_on else "OFF", "low" if bulb_on else "ok"), unsafe_allow_html=True)

    # ---------------------------------------------------------
    # Safety Check & Alarm Logic
    # ---------------------------------------------------------
    if temp > target_high:
        st.error(f"🔥 **OVERHEATING ALERT:** Temperature ({temp:.1f}°C) exceeds the maximum limit ({target_high}°C) for {selected_age}! Cooling fan active.")
        play_alarm_audio(SIREN_URL, "audio/mp3", loop=True)
    elif temp < target_low:
        st.warning(f"❄️ **LOW TEMPERATURE ALERT:** Temperature ({temp:.1f}°C) is below optimal threshold ({target_low}°C) for {selected_age}! Yellow LED & Heating bulb active.")
        play_alarm_audio(WARNING_BEEP_URL, "audio/ogg")

    st.divider()

    # ---- graphics trends ----
    left, right = st.columns(2)

    with left:
        st.subheader("Temperature & Weekly Limits")
        t_min = df["timestamp"].min()
        t_max = df["timestamp"].max()

        # High and Low target limit lines
        limit_df = pd.DataFrame({
            "timestamp": [t_min, t_max, t_min, t_max],
            "limit_val": [target_high, target_high, target_low, target_low],
            "type": ["Upper Limit", "Lower Limit", "Upper Limit", "Lower Limit"]
        })
        limit_lines = alt.Chart(limit_df).mark_line(strokeDash=[5, 5]).encode(
            x="timestamp:T",
            y="limit_val:Q",
            color=alt.Color("type:N", scale=alt.Scale(domain=["Upper Limit", "Lower Limit"], range=["#FF4B4B", "#FFC107"]))
        )

        # Temp line
        line = alt.Chart(df).mark_line(color="#FF8C00", point=True).encode(
            x=alt.X("timestamp:T", title="Time"),
            y=alt.Y("temperature:Q", title="Temperature (°C)", scale=alt.Scale(zero=False)),
            tooltip=["timestamp:T", "temperature:Q"],
        )
        st.altair_chart((limit_lines + line).properties(height=320), use_container_width=True)

    with right:
        st.subheader("Humidity Trend")
        st.altair_chart(humidity_trend_chart(df).properties(height=320), use_container_width=True)

    st.divider()
    st.subheader("Recent Readings")
    st.dataframe(
        df.sort_values("timestamp", ascending=False).reset_index(drop=True),
        use_container_width=True,
        height=250,
    )


live_dashboard()
