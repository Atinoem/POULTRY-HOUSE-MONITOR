"""
===============================================================
CoopGuard™️ - Smart Poultry House Monitoring System
===============================================================
Reads live physical data from DHT22, LDR, MOSFET Fan, Bulb, and Buzzer.
Includes week preset synchronization, manual target setpoint override,
time-aggregated telemetry visualization, and CSV report export.

Shared serial, threshold and UI helpers live in the repository-level
``coopguard_core`` package.

Expected CSV format from Arduino:
    Temperature,Humidity,Light_Level,Fan_Status
    e.g.  28.5,60.2,512,1

Run with:
    streamlit run Dashboard.py
===============================================================
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coopguard_core import (  # noqa: E402  (path bootstrap must run first)
    AGE_THRESHOLDS,
    COOPGUARD_CARD_THEME,
    DEFAULT_BAUD_RATE,
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

MAX_POINTS = 5000  # Increased capacity for historical aggregated telemetry

# Time window / resampling rule per filter option
TIME_FILTERS = {
    "All Live Points": (None, None),
    "Hourly (5-Min Averages)": (timedelta(hours=1), "5min"),
    "Daily (1-Hour Averages)": (timedelta(days=1), "1h"),
    "Weekly (Daily Averages)": (timedelta(days=7), "1D"),
    "Monthly (Weekly Averages)": (timedelta(days=30), "1W"),
    "Yearly (Monthly Averages)": (timedelta(days=365), "1ME"),
}

st.set_page_config(
    page_title="CoopGuard™️ | Smart Poultry Monitor",
    page_icon="🛡️",
    layout="wide",
)


@st.cache_resource
def get_manager():
    return SerialManager(max_points=MAX_POINTS)


manager = get_manager()

# ---------------------------------------------------------------
# Automatic Port Detection & Startup Connection (Strict COM4)
# ---------------------------------------------------------------
ports_found = list_serial_ports()
detected_port = detect_arduino_port(ports_found)

if detected_port and not manager.connected_port and not manager.last_error:
    manager.connect_serial(detected_port, DEFAULT_BAUD_RATE)

# ---------------------------------------------------------------
# Sidebar - Branding, Setup & Connection Controls
# ---------------------------------------------------------------
logo_file = "logo.png"
if os.path.exists(logo_file):
    st.sidebar.image(logo_file, use_container_width=True)

st.sidebar.markdown("<h1 style='font-size: 1.8rem; font-weight: 700; margin-bottom: 0.2rem;'>CoopGuard<span style='color:#2E6B20;'>™</span> Setup</h1>", unsafe_allow_html=True)
st.sidebar.caption("Smart Poultry House • Healthy Birds • Better Yield")

st.sidebar.divider()
st.sidebar.subheader("Chick Development Phase")
selected_age = st.sidebar.selectbox("Select Chick Age Stage", list(AGE_THRESHOLDS.keys()), index=1)

# Direct Target Override Toggle
use_target_override = st.sidebar.checkbox("Enable Direct Setpoint Override", value=False)

if use_target_override:
    st.sidebar.info("**Override Active:** Enter desired target value. The system maintains it dynamically.")
    desired_temp = st.sidebar.number_input("Target Temperature (°C)", value=28.0, step=0.5, format="%.1f")

    target_low = desired_temp - 0.5
    target_high = desired_temp + 0.5
    week_cmd = None
elif selected_age == "Week 5+":
    st.sidebar.info("**Manual Mode:** Customize low & high thermal limits.")
    col_low, col_high = st.sidebar.columns(2)
    target_low = col_low.number_input("Low Temp (°C)", value=20.0, step=0.5, format="%.1f")
    target_high = col_high.number_input("High Temp (°C)", value=23.0, step=0.5, format="%.1f")
    week_cmd = None
else:
    target_low, target_high, week_cmd = AGE_THRESHOLDS[selected_age]

# Calculate target average (midpoint)
target_mid = (target_low + target_high) / 2.0

st.sidebar.caption(f"Target Thermal Zone: **{target_low:.1f}°C – {target_high:.1f}°C** (Avg Target: **{target_mid:.1f}°C**)")
st.sidebar.caption(f"🔴 High Threshold: **>{target_high:.1f}°C** | 🟢 Optimal Zone: **{target_low:.1f}–{target_high:.1f}°C** | 🟡 Low Threshold: **<{target_low:.1f}°C**")

sync_manager_targets(manager, target_low, target_high, week_cmd, track_week_cmd=True)

st.sidebar.divider()
render_connection_controls(
    manager,
    ports_found,
    detected_port,
    no_ports_caption="No active COM ports detected. Connect Arduino USB cable.",
)

# ---------------------------------------------------------------
# Main Dashboard Header
# ---------------------------------------------------------------
st.markdown("<h1 style='font-size: 2.2rem; font-weight: 700;'>CoopGuard<span style='color:#2E6B20;'>™</span> Live Operations</h1>", unsafe_allow_html=True)
st.caption(f"Active Stage: **{selected_age}** {'(Target Override)' if use_target_override else ''} | Target Range: **{target_low:.1f}°C to {target_high:.1f}°C** | Mid Target: **{target_mid:.1f}°C**")


def branded_card(label, value_str, status):
    return card_html(label, value_str, status, COOPGUARD_CARD_THEME)


@st.fragment(run_every=REFRESH_SECONDS)
def live_dashboard():
    df = manager.get_dataframe()
    latest = manager.get_latest()

    # ---- Metric Cards ----
    c1, c2, c3, c4, c5 = st.columns(5)

    if latest is None or df.empty:
        render_offline_cards([c1, c2, c3, c4, c5], COOPGUARD_CARD_THEME)
        st.info("🛡️ **CoopGuard™️ Standby:** Waiting for hardware stream... Scanning serial ports.")
        return

    temp = latest["temperature"]
    hum = latest["humidity"]
    light = latest["light_level"]
    fan_on = latest["fan_status"] == 1

    # Heating Bulb & Green LED Range Hysteresis Logic
    if temp < target_low:
        manager.bulb_active = True
    elif temp >= target_mid:
        manager.bulb_active = False

    bulb_on = manager.bulb_active
    in_target_range = target_low <= temp <= target_high

    if temp > target_high:
        temp_status = "warn"
    elif in_target_range:
        temp_status = "ok"  # Green LED Indicator Active
    else:
        temp_status = "low"

    c1.markdown(branded_card("Temperature", f"{temp:.1f} °C", temp_status), unsafe_allow_html=True)
    c2.markdown(branded_card("Humidity", f"{hum:.1f} %", "neutral"), unsafe_allow_html=True)
    c3.markdown(branded_card("Light Level", f"{light} / 1023", "neutral"), unsafe_allow_html=True)
    c4.markdown(branded_card("Cooling Fan", "ON" if fan_on else "OFF", "warn" if fan_on else "ok"), unsafe_allow_html=True)
    c5.markdown(branded_card("Heating Bulb", "ON" if bulb_on else "OFF", "low" if bulb_on else "ok"), unsafe_allow_html=True)

    # ---------------------------------------------------------
    # Safety Check & Alarm Logic
    # ---------------------------------------------------------
    if temp > target_high:
        st.error(f"🔥 **OVERHEATING ALERT:** Temperature ({temp:.1f}°C) exceeds upper limit ({target_high:.1f}°C)! Cooling fan active.")
        play_alarm_audio(SIREN_URL, "audio/mp3", loop=True)
    elif temp < target_low:
        st.warning(f"❄️ **LOW TEMPERATURE ALERT:** Temperature ({temp:.1f}°C) is below lower limit ({target_low:.1f}°C)! Heating bulb active.")
        play_alarm_audio(WARNING_BEEP_URL, "audio/ogg")

    st.divider()

    # ---------------------------------------------------------
    # Telemetry Resampling & Filter Engine
    # ---------------------------------------------------------
    filter_col1, _ = st.columns([1, 3])
    with filter_col1:
        time_filter = st.selectbox("Filter", list(TIME_FILTERS.keys()))

    window, resample_rule = TIME_FILTERS[time_filter]
    raw_df = df.copy()

    if window is not None:
        filtered_df = raw_df[raw_df["timestamp"] >= datetime.now() - window]
    else:
        filtered_df = raw_df

    if filtered_df.empty:
        st.info("No historical telemetry data found for the selected time window.")
        return

    # Perform Averaging & Aggregation
    if resample_rule:
        display_df = (
            filtered_df.set_index("timestamp")
            .resample(resample_rule)
            .agg({
                "temperature": "mean",
                "humidity": "mean",
                "light_level": "mean",
                "fan_status": "max"  # Fan status is 1 if active at any point in interval
            })
            .dropna()
            .reset_index()
        )
    else:
        display_df = filtered_df

    if display_df.empty:
        st.info("Telemetry collection in progress... Waiting to compile interval averages.")
        return

    # ---- Graphic Trends (Averaged Intervals) ----
    left, right = st.columns(2)

    with left:
        st.subheader("Temperature Telemetry & Target Bounds")
        t_min = display_df["timestamp"].min()
        t_max = display_df["timestamp"].max()

        min_y = min(display_df["temperature"].min(), target_low) - 2.0
        max_y = max(display_df["temperature"].max(), target_high) + 2.0

        limit_df = pd.DataFrame({
            "timestamp": [t_min, t_max, t_min, t_max, t_min, t_max],
            "limit_val": [target_high, target_high, target_mid, target_mid, target_low, target_low],
            "Limit Type": ["Upper Limit", "Upper Limit", "Target Average", "Target Average", "Lower Limit", "Lower Limit"]
        })

        limit_lines = alt.Chart(limit_df).mark_line(strokeDash=[6, 4], strokeWidth=2).encode(
            x=alt.X("timestamp:T", title="Time Interval"),
            y=alt.Y("limit_val:Q", title="Avg Temperature (°C)", scale=alt.Scale(domain=[min_y, max_y])),
            color=alt.Color("Limit Type:N", scale=alt.Scale(
                domain=["Upper Limit", "Target Average", "Lower Limit"],
                range=["#FF4B4B", "#2E6B20", "#FFC107"]
            ))
        )

        line = alt.Chart(display_df).mark_line(color="#2E6B20", strokeWidth=2.5, point=True).encode(
            x=alt.X("timestamp:T", title="Time Interval"),
            y=alt.Y("temperature:Q", title="Avg Temp (°C)", scale=alt.Scale(domain=[min_y, max_y])),
            tooltip=["timestamp:T", "temperature:Q"],
        )

        st.altair_chart((limit_lines + line).properties(height=320), use_container_width=True)

    with right:
        st.subheader("Humidity Trend")
        hum_line = humidity_trend_chart(
            display_df,
            x_title="Time Interval",
            y_title="Avg Humidity (%)",
            stroke_width=2.5,
        )
        st.altair_chart(hum_line.properties(height=320), use_container_width=True)

    st.divider()

    # ---------------------------------------------------------
    # Aggregated Telemetry Summary & Report CSV Export
    # ---------------------------------------------------------
    st.subheader("Aggregated Telemetry Report")

    # Format telemetry dataframe for export
    formatted_export_df = display_df.copy()
    formatted_export_df["temperature"] = formatted_export_df["temperature"].round(2)
    formatted_export_df["humidity"] = formatted_export_df["humidity"].round(2)
    formatted_export_df["light_level"] = formatted_export_df["light_level"].round(0)

    st.dataframe(
        formatted_export_df.sort_values("timestamp", ascending=False).reset_index(drop=True),
        use_container_width=True,
        height=250,
    )

    # Download Button for Supervisor Report Export
    csv_data = formatted_export_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Aggregated Telemetry Report (CSV)",
        data=csv_data,
        file_name=f"CoopGuard_Telemetry_Report_{time_filter.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}",
        mime="text/csv",
    )


live_dashboard()
