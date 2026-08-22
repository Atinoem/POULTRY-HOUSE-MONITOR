"""Configuration values shared by the CoopGuard dashboards."""

# Target temperature ranges by chick age: (Low Limit, High Limit, Serial Command)
AGE_THRESHOLDS = {
    "Week 1":  (32.0, 35.0, "WEEK1"),
    "Week 2":  (29.0, 32.0, "WEEK2"),
    "Week 3":  (26.0, 29.0, "WEEK3"),
    "Week 4":  (23.0, 26.0, "WEEK4"),
    "Week 5+": (20.0, 23.0, None),
}

DEFAULT_MAX_POINTS = 50
REFRESH_SECONDS = 2

DEFAULT_BAUD_RATE = 9600
BAUD_RATES = [9600, 19200, 38400, 57600, 115200]

# Port the Arduino is normally wired to; other ports are matched by description.
PREFERRED_PORT = "COM4"
PORT_DESCRIPTION_HINTS = ("arduino", "ch340", "usb serial")

SIREN_URL = "https://archive.org/download/Red_Library_Sirens/R18-27-Classic%20Emergency%20Siren.mp3"
WARNING_BEEP_URL = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
