"""Shared utilities for the CoopGuard poultry house monitoring dashboards."""

from coopguard_core.config import (
    AGE_THRESHOLDS,
    BAUD_RATES,
    DEFAULT_BAUD_RATE,
    DEFAULT_MAX_POINTS,
    PREFERRED_PORT,
    REFRESH_SECONDS,
    SIREN_URL,
    WARNING_BEEP_URL,
)
from coopguard_core.serial_manager import SerialManager
from coopguard_core.ui import (
    CLASSIC_CARD_THEME,
    COOPGUARD_CARD_THEME,
    CardTheme,
    card_html,
    detect_arduino_port,
    humidity_trend_chart,
    list_serial_ports,
    play_alarm_audio,
    render_connection_controls,
    render_offline_cards,
    sync_manager_targets,
)

__all__ = [
    "AGE_THRESHOLDS",
    "BAUD_RATES",
    "CLASSIC_CARD_THEME",
    "COOPGUARD_CARD_THEME",
    "CardTheme",
    "DEFAULT_BAUD_RATE",
    "DEFAULT_MAX_POINTS",
    "PREFERRED_PORT",
    "REFRESH_SECONDS",
    "SIREN_URL",
    "SerialManager",
    "WARNING_BEEP_URL",
    "card_html",
    "detect_arduino_port",
    "humidity_trend_chart",
    "list_serial_ports",
    "play_alarm_audio",
    "render_connection_controls",
    "render_offline_cards",
    "sync_manager_targets",
]
