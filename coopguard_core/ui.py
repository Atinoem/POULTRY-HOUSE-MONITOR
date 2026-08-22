"""Streamlit UI helpers shared by the CoopGuard dashboards."""

from dataclasses import dataclass

import altair as alt
import serial.tools.list_ports
import streamlit as st

from coopguard_core.config import (
    BAUD_RATES,
    DEFAULT_BAUD_RATE,
    PORT_DESCRIPTION_HINTS,
    PREFERRED_PORT,
)

CUSTOM_PORT_OPTION = "Custom / manual entry..."


# ---------------------------------------------------------------
# Port discovery
# ---------------------------------------------------------------
def list_serial_ports():
    return list(serial.tools.list_ports.comports())


def detect_arduino_port(ports):
    """Return the preferred port if present, else the first Arduino-like port."""
    if PREFERRED_PORT in [p.device for p in ports]:
        return PREFERRED_PORT
    for p in ports:
        desc = p.description.lower()
        if any(hint in desc for hint in PORT_DESCRIPTION_HINTS):
            return p.device
    return None


# ---------------------------------------------------------------
# Metric cards
# ---------------------------------------------------------------
@dataclass(frozen=True)
class CardTheme:
    """Background/accent colour pairs plus typography for the metric cards."""

    colors: dict
    label_css: str = "font-size:14px; color:#cccccc; margin-bottom:4px;"
    value_css: str = "font-size:30px; font-weight:700;"


CLASSIC_CARD_THEME = CardTheme(
    colors={
        "ok":      ("#1e3d2f", "#1DB954"),
        "warn":    ("#3d1e1e", "#FF4B4B"),
        "low":     ("#3d331e", "#FFC107"),
        "neutral": ("#1e2a3d", "#4FA3E3"),
    }
)

COOPGUARD_CARD_THEME = CardTheme(
    colors={
        "ok":      ("#1a331c", "#2E6B20"),  # CoopGuard Forest Green / Green LED
        "warn":    ("#3d1e1e", "#FF4B4B"),  # Red Alert
        "low":     ("#3d331e", "#FFC107"),  # Yellow Alert
        "neutral": ("#1e2530", "#4FA3E3"),  # Neutral Blue
    },
    label_css=(
        "font-size:13px; font-weight:600; color:#cccccc; margin-bottom:4px; "
        "text-transform:uppercase; letter-spacing:0.5px;"
    ),
    value_css="font-size:28px; font-weight:700;",
)


def card_html(label, value_str, status, theme=CLASSIC_CARD_THEME):
    bg, accent = theme.colors.get(status, theme.colors["neutral"])
    return f"""
    <div style="background-color:{bg}; border-left: 6px solid {accent};
                border-radius: 10px; padding: 16px 18px; text-align:left;">
        <div style="{theme.label_css}">{label}</div>
        <div style="{theme.value_css} color:{accent};">{value_str}</div>
    </div>
    """


def render_offline_cards(columns, theme=CLASSIC_CARD_THEME):
    """Render the placeholder cards shown while no telemetry has arrived."""
    placeholders = [
        ("Temperature", "-- °C"),
        ("Humidity", "-- %"),
        ("Light Level", "-- / 1023"),
        ("Fan Status", "OFFLINE"),
        ("Bulb Status", "OFFLINE"),
    ]
    for column, (label, value) in zip(columns, placeholders):
        column.markdown(card_html(label, value, "neutral", theme), unsafe_allow_html=True)


# ---------------------------------------------------------------
# Alarms
# ---------------------------------------------------------------
def play_alarm_audio(url, mime, loop=False):
    st.components.v1.html(
        f"""
        <audio autoplay {"loop" if loop else ""} style="display:none;">
            <source src="{url}" type="{mime}">
        </audio>
        """,
        height=0,
    )


# ---------------------------------------------------------------
# Threshold synchronisation
# ---------------------------------------------------------------
def sync_manager_targets(manager, target_low, target_high, week_cmd, track_week_cmd=False):
    """Push preset or manual thresholds to the Arduino when the selection changed."""
    changed = manager.target_low != target_low or manager.target_high != target_high
    if track_week_cmd:
        changed = changed or manager.current_week_cmd != week_cmd
    if not changed:
        return

    manager.target_low = target_low
    manager.target_high = target_high
    manager.current_week_cmd = week_cmd
    if week_cmd:
        manager.send_command(week_cmd)
    else:
        manager.send_thresholds(target_low, target_high)


# ---------------------------------------------------------------
# Connection sidebar
# ---------------------------------------------------------------
def render_connection_controls(manager, ports, detected_port, no_ports_caption):
    """Draw the sidebar port/baud pickers and connect buttons; return the baud rate."""
    st.sidebar.subheader("Hardware Connection")

    available_ports = [p.device for p in ports]
    port_options = available_ports + [CUSTOM_PORT_OPTION]

    if not available_ports:
        st.sidebar.caption(no_ports_caption)

    default_index = 0
    if detected_port in available_ports:
        default_index = available_ports.index(detected_port)

    port_choice = st.sidebar.selectbox(
        "Serial Port", port_options, index=default_index if available_ports else 0
    )
    if port_choice == CUSTOM_PORT_OPTION:
        port_choice = st.sidebar.text_input("Enter Port Manually", value=PREFERRED_PORT)

    baud_rate = st.sidebar.selectbox(
        "Baud Rate", BAUD_RATES, index=BAUD_RATES.index(DEFAULT_BAUD_RATE)
    )

    col_a, col_b = st.sidebar.columns(2)
    connect_clicked = col_a.button("🔌 Connect", use_container_width=True)
    disconnect_clicked = col_b.button("⏹ Disconnect", use_container_width=True)

    if connect_clicked:
        if manager.connect_serial(port_choice, baud_rate):
            st.sidebar.success(f"Connected to {port_choice}!")
            st.rerun()
        else:
            st.sidebar.error(f"Could not connect: {manager.last_error}")

    if disconnect_clicked:
        manager.stop()
        st.sidebar.info("Disconnected hardware.")
        st.rerun()

    if manager.connected_port:
        st.sidebar.success(f"Active on {manager.connected_port} @ {baud_rate} baud")
    else:
        st.sidebar.caption("Disconnected")

    return baud_rate


# ---------------------------------------------------------------
# Charts
# ---------------------------------------------------------------
def humidity_trend_chart(df, x_title="Time", y_title="Humidity (%)", stroke_width=None):
    mark_kwargs = {"color": "#4FA3E3", "point": True}
    if stroke_width is not None:
        mark_kwargs["strokeWidth"] = stroke_width
    return (
        alt.Chart(df)
        .mark_line(**mark_kwargs)
        .encode(
            x=alt.X("timestamp:T", title=x_title),
            y=alt.Y("humidity:Q", title=y_title, scale=alt.Scale(zero=False)),
            tooltip=["timestamp:T", "humidity:Q"],
        )
    )
