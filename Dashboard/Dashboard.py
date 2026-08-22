"""
===============================================================
Smart Poultry House Monitor - Streamlit Dashboard (COM4 Auto-Connect)
===============================================================
Reads live physical data from DHT22, LDR, MOSFET Fan, Bulb, and Buzzer.
Includes week preset synchronization and automatic audio alarms.

Expected CSV format from Arduino:
    Temperature,Humidity,Light_Level,Fan_Status
    e.g.  28.5,60.2,512,1

Run with:
    streamlit run Dashboard.py
===============================================================
"""

import hmac
import os
import re
import time
import threading
from collections import deque
from datetime import datetime

import altair as alt
import pandas as pd
import serial
import serial.tools.list_ports
import streamlit as st

# ---------------------------------------------------------------
# Config
# ---------------------------------------------------------------
MAX_POINTS = 50
REFRESH_SECONDS = 2

# Target temperature ranges by chick age: (Low Limit, High Limit, Serial Command)
AGE_THRESHOLDS = {
    "Week 1":  (32.0, 35.0, "WEEK1"),
    "Week 2":  (29.0, 32.0, "WEEK2"),
    "Week 3":  (26.0, 29.0, "WEEK3"),
    "Week 4":  (23.0, 26.0, "WEEK4"),
    "Week 5+": (20.0, 23.0, None),
}

# Setpoints outside this band are never sent to the hardware: a heating bulb
# driven to an out-of-range target can kill the flock.
SAFE_TEMP_MIN = 15.0
SAFE_TEMP_MAX = 40.0
MIN_TEMP_SPAN = 0.5

# Only these literal strings may be written to the serial link as commands.
ALLOWED_COMMANDS = {"WEEK1", "WEEK2", "WEEK3", "WEEK4"}

# Windows COM port or a POSIX tty device; anything else is rejected so an
# operator cannot make the app open an arbitrary file on the host.
PORT_PATTERN = re.compile(r"^(COM[0-9]{1,3}|/dev/[A-Za-z0-9._-]{1,32})$")

st.set_page_config(
    page_title="Poultry House Monitor",
    page_icon="🐔",
    layout="wide",
)

# ---------------------------------------------------------------
# Background Serial Manager
# ---------------------------------------------------------------
class SerialManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = deque(maxlen=MAX_POINTS)
        self.ser = None
        self.thread = None
        self.running = False
        self.connected_port = None
        self.last_error = None
        self.target_low = 29.0   # Default Week 2 Low
        self.target_high = 32.0  # Default Week 2 High
        self.current_week_cmd = "WEEK2"

    # ---- connection control -------------------------------------------------
    def connect_serial(self, port, baud=9600):
        if not PORT_PATTERN.match(str(port).strip()):
            self.last_error = f"Invalid serial port name: {port!r}"
            return False
        self.stop()
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            self.connected_port = port
            self.running = True
            self.last_error = None
            self.thread = threading.Thread(target=self._serial_read_loop, daemon=True)
            self.thread.start()
            
            # Sync initial week selection down to Arduino
            if self.current_week_cmd:
                self.send_command(self.current_week_cmd)
            else:
                self.send_thresholds(self.target_low, self.target_high)
            return True
        except Exception as e:
            self.last_error = str(e)
            return False

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.5)
        if self.ser is not None:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.thread = None
        self.connected_port = None

    # ---- commands & thresholds (Thread-Safe) --------------------------------
    def send_command(self, cmd_str):
        if cmd_str not in ALLOWED_COMMANDS:
            self.last_error = f"Refused unknown serial command: {cmd_str!r}"
            return False
        if self.ser is None:
            return False
        try:
            cmd = f"{cmd_str}\n"
            with self.lock:
                if self.ser.is_open:
                    self.ser.write(cmd.encode("utf-8"))
            return True
        except Exception as e:
            self.last_error = str(e)
            return False

    def send_thresholds(self, low, high):
        if not valid_setpoints(low, high):
            self.last_error = (
                f"Refused unsafe thresholds: {low}\u2013{high} \u00b0C outside "
                f"{SAFE_TEMP_MIN}\u2013{SAFE_TEMP_MAX} \u00b0C"
            )
            return False
        self.target_low = low
        self.target_high = high
        if self.ser is None:
            return False
        try:
            cmd = f"SET_LOW:{low}\nSET_HIGH:{high}\n"
            with self.lock:
                if self.ser.is_open:
                    self.ser.write(cmd.encode("utf-8"))
            return True
        except Exception as e:
            self.last_error = str(e)
            return False

    # ---- read loop ---------------------------------------------------------
    def _serial_read_loop(self):
        while self.running and self.ser is not None:
            try:
                if not self.ser.is_open:
                    break
                raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue
                parts = raw.split(",")
                if len(parts) != 4:
                    continue
                
                temp = float(parts[0])
                hum = float(parts[1])
                light = int(parts[2])
                fan = int(parts[3])
                
                with self.lock:
                    self.data.append({
                        "timestamp": datetime.now(),
                        "temperature": temp,
                        "humidity": hum,
                        "light_level": light,
                        "fan_status": fan,
                    })
            except Exception as e:
                self.last_error = str(e)
                time.sleep(0.5)

    # ---- data access --------------------------------------------------------
    def get_dataframe(self):
        with self.lock:
            return pd.DataFrame(list(self.data))

    def get_latest(self):
        with self.lock:
            if not self.data:
                return None
            return self.data[-1]


def valid_setpoints(low, high):
    return (
        SAFE_TEMP_MIN <= low <= SAFE_TEMP_MAX
        and SAFE_TEMP_MIN <= high <= SAFE_TEMP_MAX
        and high - low >= MIN_TEMP_SPAN
    )


def configured_password():
    env_password = os.environ.get("COOPGUARD_DASHBOARD_PASSWORD", "")
    if env_password:
        return env_password
    try:
        return st.secrets.get("dashboard_password", "")
    except Exception:
        return ""


def require_authentication():
    """Gate the dashboard behind a shared password when one is configured.

    The dashboard can switch heating and cooling hardware on and off, so it must
    not be reachable by anyone who can open its port.
    """
    expected = configured_password()
    if not expected:
        st.sidebar.warning(
            "No dashboard password set. Export COOPGUARD_DASHBOARD_PASSWORD and "
            "bind Streamlit to localhost before exposing this dashboard."
        )
        return
    if st.session_state.get("coopguard_authenticated"):
        return

    st.title("Poultry House Monitor Sign In")
    entered = st.text_input("Dashboard password", type="password")
    if st.button("Sign in"):
        if hmac.compare_digest(entered, expected):
            st.session_state["coopguard_authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


require_authentication()


@st.cache_resource
def get_manager():
    return SerialManager()


manager = get_manager()

# ---------------------------------------------------------------
# Automatic Port Detection & Startup Connection (Strict COM4)
# ---------------------------------------------------------------
ports_found = list(serial.tools.list_ports.comports())
detected_port = None
active_device_names = [p.device for p in ports_found]

if "COM4" in active_device_names:
    detected_port = "COM4"
else:
    for p in ports_found:
        desc = p.description.lower()
        if "arduino" in desc or "ch340" in desc or "usb serial" in desc:
            detected_port = p.device
            break

# Auto-connect on startup
if detected_port and not manager.connected_port and not manager.last_error:
    manager.connect_serial(detected_port, 9600)

# ---------------------------------------------------------------
# Sidebar - connection controls + chick age selector
# ---------------------------------------------------------------
st.sidebar.title("🐔 Poultry Monitor Setup")

st.sidebar.subheader("Chick Age Selection")
selected_age = st.sidebar.selectbox("Select chick age", list(AGE_THRESHOLDS.keys()), index=1)
target_low, target_high, week_cmd = AGE_THRESHOLDS[selected_age]

st.sidebar.caption(f"Optimal Range: **{target_low}°C – {target_high}°C**")
st.sidebar.caption(f"🔴 Overheat Alert: **>{target_high}°C** | 🟡 Cold Alert: **<{target_low}°C**")

# Push presets down serial if changed
if manager.target_high != target_high or manager.target_low != target_low:
    manager.target_low = target_low
    manager.target_high = target_high
    manager.current_week_cmd = week_cmd
    if week_cmd:
        manager.send_command(week_cmd)
    else:
        manager.send_thresholds(target_low, target_high)

st.sidebar.divider()
st.sidebar.subheader("Hardware Connection")

available_ports = [p.device for p in ports_found]
port_options = available_ports + ["Custom / manual entry..."]

if not available_ports:
    st.sidebar.caption("⚠️ No physical COM ports detected. Plug in your Arduino USB cable.")

default_index = 0
if detected_port in available_ports:
    default_index = available_ports.index(detected_port)

port_choice = st.sidebar.selectbox("Serial port", port_options, index=default_index if available_ports else 0)
if port_choice == "Custom / manual entry...":
    port_choice = st.sidebar.text_input("Enter port manually", value="COM4")

baud_rate = st.sidebar.selectbox("Baud rate", [9600, 19200, 38400, 57600, 115200], index=0)

col_a, col_b = st.sidebar.columns(2)
connect_clicked = col_a.button("🔌 Connect", use_container_width=True)
disconnect_clicked = col_b.button("⏹ Disconnect", use_container_width=True)

if connect_clicked:
    ok = manager.connect_serial(port_choice, baud_rate)
    if ok:
        st.sidebar.success(f"Connected to {port_choice}!")
        st.rerun()
    else:
        st.sidebar.error(f"Could not connect: {manager.last_error}")

if disconnect_clicked:
    manager.stop()
    st.sidebar.info("Disconnected hardware.")
    st.rerun()

if manager.connected_port:
    st.sidebar.success(f"🟢 Connected to {manager.connected_port} @ {baud_rate} baud")
else:
    st.sidebar.caption("🔴 Disconnected")

# ---------------------------------------------------------------
# Main Dashboard
# ---------------------------------------------------------------
st.title("Smart Poultry House Monitor")
st.caption(f"Development Stage: **{selected_age}** | Target Range: **{target_low}°C to {target_high}°C**")


def card_html(label, value_str, status):
    colors = {
        "ok":      ("#1e3d2f", "#1DB954"),
        "warn":    ("#3d1e1e", "#FF4B4B"),
        "low":     ("#3d331e", "#FFC107"),
        "neutral": ("#1e2a3d", "#4FA3E3"),
    }
    bg, accent = colors.get(status, colors["neutral"])
    return f"""
    <div style="background-color:{bg}; border-left: 6px solid {accent};
                border-radius: 10px; padding: 16px 18px; text-align:left;">
        <div style="font-size:14px; color:#cccccc; margin-bottom:4px;">{label}</div>
        <div style="font-size:30px; font-weight:700; color:{accent};">{value_str}</div>
    </div>
    """


@st.fragment(run_every=REFRESH_SECONDS)
def live_dashboard():
    df = manager.get_dataframe()
    latest = manager.get_latest()

    # ---- metric cards ----
    c1, c2, c3, c4, c5 = st.columns(5)

    if latest is None or df.empty:
        c1.markdown(card_html("Temperature", "-- °C", "neutral"), unsafe_allow_html=True)
        c2.markdown(card_html("Humidity", "-- %", "neutral"), unsafe_allow_html=True)
        c3.markdown(card_html("Light Level", "-- / 1023", "neutral"), unsafe_allow_html=True)
        c4.markdown(card_html("Fan Status", "OFFLINE", "neutral"), unsafe_allow_html=True)
        c5.markdown(card_html("Bulb Status", "OFFLINE", "neutral"), unsafe_allow_html=True)
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
        siren_url = "https://archive.org/download/Red_Library_Sirens/R18-27-Classic%20Emergency%20Siren.mp3"
        st.components.v1.html(
            f"""
            <audio autoplay loop style="display:none;">
                <source src="{siren_url}" type="audio/mp3">
            </audio>
            """,
            height=0,
        )
    elif temp < target_low:
        st.warning(f"❄️ **LOW TEMPERATURE ALERT:** Temperature ({temp:.1f}°C) is below optimal threshold ({target_low}°C) for {selected_age}! Yellow LED & Heating bulb active.")
        warning_beep_url = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
        st.components.v1.html(
            f"""
            <audio autoplay style="display:none;">
                <source src="{warning_beep_url}" type="audio/ogg">
            </audio>
            """,
            height=0,
        )

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
        hum_line = alt.Chart(df).mark_line(color="#4FA3E3", point=True).encode(
            x=alt.X("timestamp:T", title="Time"),
            y=alt.Y("humidity:Q", title="Humidity (%)", scale=alt.Scale(zero=False)),
            tooltip=["timestamp:T", "humidity:Q"],
        )
        st.altair_chart(hum_line.properties(height=320), use_container_width=True)

    st.divider()
    st.subheader("Recent Readings")
    st.dataframe(
        df.sort_values("timestamp", ascending=False).reset_index(drop=True),
        use_container_width=True,
        height=250,
    )


live_dashboard()