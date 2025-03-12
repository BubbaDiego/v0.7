import os
import json
import re
from datetime import datetime
import pytz
import sys
from fuzzywuzzy import fuzz
from config.config_constants import BASE_DIR


DATE_FORMAT = "%m-%d-%y : %I:%M:%S %p"


# Unified configuration for display: mapping messages to icons/colors.
UNIFIED_LOG_CONFIG = {
    "Launch pad started": {"icon": "🚀", "color": "blue"},
    "Jupiter Updated": {"icon": "🪐", "color": "blue"},
    "Alerts Config Successful": {"icon": "✅", "color": "green"},
    "Alert Manager Initialized": {"icon": "✅", "color": "blue"},
    "Alert Config Failed": {"icon": "💀", "color": "red"},
    "Alert Triggered": {"icon": "🚨", "color": "red"},
    "Alert Silenced": {"icon": "🔕", "color": "yellow"},
    "Monitor Loop": {"icon": "🔁", "color": "blue"},
    "No Alerts Found": {"icon": "✅", "color": "green"},
    "Heartbeat Success": {"icon": "❤️", "color": "green"},
    "Heartbeat Failure": {"icon": " ♥", "color": "red"},
    "Notification Sent": {"icon": "📱", "color": "blue"},
    "Notification Failed": {"icon": "💀", "color": "red"},
    "Prices Updated": {"icon": "📈", "color": "blue"},
    "Price Update Failed": {"icon": "📉", "color": "red"},
    "Travel Percent Liquid ALERT": {"icon": "🛟", "color": "red"},
    "Profit ALERT": {"icon": "💰", "color": "green"},
    "Price ALERT": {"icon": "🔔", "color": "blue"},
    "One Day Blast Radius ALERT": {"icon": "💥", "color": "red"},
    "Average Daily Swing ALERT": {"icon": "🌊", "color": "orange"},
    "Alert Check": {"icon": "🔍", "color": "orange"},
}

# New configuration for alert log entries.
ALERT_VIEW_CONFIG = {
    "Alert Check": {"icon": "🔍", "color": "orange"},
    "Alert Triggered": {"icon": "🚨", "color": "orange"},
    "Alert Silenced": {"icon": "🔕", "color": "orange"},
    "No Alerts Found": {"icon": "❗", "color": "orange"},
    # Additional mappings can be added here.
}

# Source icons for unified view.
SOURCE_ICONS = {
    "system": "⚙️",
    "user": "👤",
    "monitor": "📺"
}
DEFAULT_SOURCE_ICON = "❓"


def fuzzy_find_log_type(message_text: str, config_keys) -> str:
    def normalize(s):
        return re.sub(r'[^a-z0-9]+', '', s.lower())
    msg_norm = normalize(message_text)
    best_key = None
    best_score = 0
    for k in config_keys:
        k_norm = normalize(k)
        score = fuzz.ratio(msg_norm, k_norm)
        if score > best_score:
            best_score = score
            best_key = k
    if best_score >= 60:
        return best_key
    return None


class UnifiedLogViewer:
    def __init__(self, log_files):
        """
        log_files: list of file paths to unified log files.
        """
        self.log_files = log_files
        self.entries = []
        self.pst = pytz.timezone("US/Pacific")
        self._read_logs()

    def _read_logs(self):
        for file_path in self.log_files:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            record = {"raw": line}
                        ts = record.get("timestamp", "")
                        try:
                            record["parsed_time"] = datetime.strptime(ts, DATE_FORMAT)
                        except Exception:
                            record["parsed_time"] = datetime.min
                        self.entries.append(record)
        # Sort entries so that the newest logs are first.
        self.entries.sort(key=lambda r: r.get("parsed_time", datetime.min), reverse=True)

    def get_line_color_class(self, color_name: str) -> str:
        color_map = {
            "red": "alert-danger",
            "blue": "alert-primary",
            "green": "alert-success",
            "yellow": "alert-warning",
            "orange": "alert-warning"  # Change this if you want a custom true orange class.
        }
        return color_map.get(color_name.lower(), "alert-secondary")

    def get_alert_status_line(self, record: dict) -> str:
        """
        If the log record includes 'alert_details', create a custom status line.
        Expected keys in alert_details: 'status', 'type', 'limit', 'current'
        """
        details = record.get("alert_details")
        if not details:
            return ""
        status = details.get("status", "Low")
        alert_type = details.get("type", "Alert")
        limit_value = details.get("limit", "")
        current_value = details.get("current", "")
        if status.lower() == "low":
            bg_color = "#ffff99"  # Yellow
        elif status.lower() == "medium":
            bg_color = "#ffcc80"  # Orange
        elif status.lower() == "high":
            bg_color = "#ff9999"  # Red
        elif status.lower() == "liquidated":
            bg_color = "#000000"  # Black
        else:
            bg_color = "#eeeeee"
        if status.lower() == "liquidated":
            status_text = "💀 Liquidated 💀"
            text_color = "#ffffff"
        else:
            status_text = status
            text_color = "#000000"
        html = f"""
<div class="alert-status-line" style="background-color: {bg_color}; padding: 8px; margin-bottom: 5px; border-radius: 4px; color: {text_color}; display: flex; align-items: center;">
  <span style="font-weight: bold; margin-right: 12px;">{status_text}</span>
  <span style="margin-right: 12px;">Type: {alert_type}</span>
  <span style="margin-right: 12px;">Limit: {limit_value}</span>
  <span>Current: {current_value}</span>
</div>
""".strip()
        return html

    def get_display_string(self, record: dict) -> str:
        # Determine which configuration mapping to use based on log_type.
        if record.get("log_type", "").lower() == "alert":
            config_source = ALERT_VIEW_CONFIG
        else:
            config_source = UNIFIED_LOG_CONFIG

        operation_type = record.get("operation_type", "").strip()
        if operation_type:
            if operation_type in config_source:
                best_key = operation_type
            else:
                best_key = fuzzy_find_log_type(operation_type, config_source.keys())
            display_text = operation_type
        else:
            message_text = record.get("message", "")
            raw_text = record.get("raw", "")
            display_text = message_text or raw_text
            best_key = fuzzy_find_log_type(display_text, config_source.keys())

        config = config_source.get(best_key, {}) if best_key else {}
        icon = config.get("icon", "")
        color_name = config.get("color", "secondary")
        line_color_class = self.get_line_color_class(color_name)

        source_text = record.get("source", "")
        source_icon = SOURCE_ICONS.get(source_text.lower(), DEFAULT_SOURCE_ICON) if source_text else DEFAULT_SOURCE_ICON

        ts = record.get("timestamp", "")
        if " : " in ts:
            date_part, time_part = ts.split(" : ", 1)
        else:
            date_part, time_part = ts, ""

        line_html = f"""
    <div class="alert {line_color_class} d-flex align-items-center justify-content-between mb-1" 
         style="margin: 2px 0; padding: 3px; white-space: nowrap;">
      <div style="flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis;">
        <span style="font-size: 1rem;">{icon}</span>
        <strong>{display_text}</strong>
      </div>
      <div style="flex: 0 0 auto; margin: 0 16px; text-align: center; min-width: 30px;">
        <span style="font-size: 1rem;">{source_icon}</span>
      </div>
      <div style="flex: 0 0 auto; text-align: right; min-width: 120px;">
        <span style="font-weight: normal;">{date_part}</span>
        &nbsp;
        <span style="font-weight: bold;">{time_part}</span>
      </div>
    </div>
    """.strip()
        return line_html

    def get_all_display_strings(self) -> str:
        display_list = [self.get_display_string(e) for e in self.entries]
        final_html = f"""
<div style="background-color: white; padding: 8px;">
  {''.join(display_list)}
</div>
""".strip()
        return final_html


# Example usage:
if __name__ == "__main__":
    log_files = [
        os.path.join(str(BASE_DIR), "operations_log.txt"),
        os.path.join(str(BASE_DIR), "alert_monitor_log.txt")
    ]
    viewer = UnifiedLogViewer(log_files)
    html_output = viewer.get_all_display_strings()
    print(html_output)
