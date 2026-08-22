"""Background serial reader shared by the CoopGuard dashboards.

Expected CSV format from Arduino:
    Temperature,Humidity,Light_Level,Fan_Status
    e.g.  28.5,60.2,512,1
"""

import threading
import time
from collections import deque
from datetime import datetime

import pandas as pd
import serial

from coopguard_core.config import (
    AGE_THRESHOLDS,
    DEFAULT_BAUD_RATE,
    DEFAULT_MAX_POINTS,
)

_DEFAULT_LOW, _DEFAULT_HIGH, _DEFAULT_WEEK_CMD = AGE_THRESHOLDS["Week 2"]


class SerialManager:
    """Owns the serial port, a reader thread and the telemetry ring buffer."""

    def __init__(self, max_points=DEFAULT_MAX_POINTS):
        self.lock = threading.Lock()
        self.data = deque(maxlen=max_points)
        self.ser = None
        self.thread = None
        self.running = False
        self.connected_port = None
        self.last_error = None
        self.target_low = _DEFAULT_LOW
        self.target_high = _DEFAULT_HIGH
        self.current_week_cmd = _DEFAULT_WEEK_CMD
        self.bulb_active = False  # Hysteresis state for heating bulb

    # ---- connection control -------------------------------------------------
    def connect_serial(self, port, baud=DEFAULT_BAUD_RATE):
        self.stop()
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            self.connected_port = port
            self.running = True
            self.last_error = None
            self.thread = threading.Thread(target=self._serial_read_loop, daemon=True)
            self.thread.start()

            # Sync initial state down to Arduino
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

    # ---- commands & thresholds (thread-safe) --------------------------------
    def _write(self, payload):
        if self.ser is None:
            return
        try:
            with self.lock:
                if self.ser.is_open:
                    self.ser.write(payload.encode("utf-8"))
        except Exception as e:
            self.last_error = str(e)

    def send_command(self, cmd_str):
        self._write(f"{cmd_str}\n")

    def send_thresholds(self, low, high):
        self.target_low = low
        self.target_high = high
        self._write(f"SET_LOW:{low:.1f}\nSET_HIGH:{high:.1f}\n")

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

                reading = {
                    "timestamp": datetime.now(),
                    "temperature": float(parts[0]),
                    "humidity": float(parts[1]),
                    "light_level": int(parts[2]),
                    "fan_status": int(parts[3]),
                }

                with self.lock:
                    self.data.append(reading)
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
