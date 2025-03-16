import os
import json
import re
from datetime import datetime
import pytz
import sys
from fuzzywuzzy import fuzz
from config.config_constants import BASE_DIR, LOG_DATE_FORMAT

# Unified configuration for display: mapping messages to icons/colors.
UNIFIED_LOG_CONFIG = {
    "Launch pad started": {"icon": "🚀", "color": "blue"},
    "Jupiter Updated": {"icon": "🪐", "color": "blue"},
    "Alerts Configuration Successful": {"icon": "✅", "color": "green"},
    "Alert Manager Initialized": {"icon": "✅", "color": "blue"},
    "Alert Configuration Failed": {"icon": "💀", "color": "red"},
    "Alert Triggered": {"icon": "🚨", "color": "red"},
    "Alert Silenced": {"icon": "🔕", "color": "yellow"},
    "Monitor Loop": {"icon": "🔁", "color": "blue"},
    "No Alerts Found": {"icon": "✅", "color": "green"},
    "Heartbeat": {"icon": "❤️⚡", "color": "green"},
    "Heartbeat Detected": {"icon": "❤️🩺", "color": "green"},
    "Heartbeat Failure": {"icon": " ♥", "color": "red"},
    "JSON Verified": {"icon": "✅->📄", "color": "green"},
    "JSON Verification Failed": {"icon": "💀📄", "color": "red"},
    "JSON Saved": {"icon": "✅->💾", "color": "green"},
    "Save JSON Failed": {"icon": "💀->💾", "color": "red"},
    "Notification Sent": {"icon": "📱", "color": "blue"},
    "Notification Failed": {"icon": "💀->📱", "color": "red"},
    "Prices Updated": {"icon": "📈", "color": "blue"},
    "Price Update Failed": {"icon": "📉", "color": "red"},
    "Alert Check": {"icon": "🔍", "color": "orange"},
}

# New configuration for alert log entries.
ALERT_VIEW_CONFIG = {
    "Alert Check": {"icon": "🔍", "color": "orange"},
    "Alert Triggered": {"icon": "🚨", "color": "orange"},
    "Alert Silenced": {"icon": "🔕", "color": "orange"},
    "No Alerts Found": {"icon": "❗", "color": "orange"},
    "Travel Percent Liquid ALERT": {"icon": "🛟", "color": "red"},
    "Profit ALERT": {"icon": "💰", "color": "green"},
    "Price ALERT": {"icon": "🔔", "color": "blue"},
    "One Day Blast Radius ALERT": {"icon": "💥", "color": "red"},
    "Average Daily Swing ALERT": {"icon": "🌊", "color": "orange"},
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
                        self.entries.append(record)
        # Reverse the order so that the newest entries appear first.
        self.entries.reverse()

    def get_line_color_class(self, color_name: str) -> str:
        color_map = {
            "red": "alert-danger",
            "blue": "alert-primary",
            "green": "alert-success",
            "yellow": "alert-warning",
            "orange": "alert-warning"
        }
        return color_map.get(color_name.lower(), "alert-secondary")

    def get_alert_status_line(self, record: dict) -> str:
        details = record.get("alert_details")
        if not details:
            return ""
        status = details.get("status", "Low")
        alert_type = details.get("type", "Alert")
        limit_value = details.get("limit", "")
        current_value = details.get("current", "")
        if status.lower() == "low":
            bg_color = "#ffff99"
        elif status.lower() == "medium":
            bg_color = "#ffcc80"
        elif status.lower() == "high":
            bg_color = "#ff9999"
        elif status.lower() == "liquidated":
            bg_color = "#000000"
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
        # Determine configuration mapping based on log type.
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

        file_name = record.get("file", record.get("filename", "unknown_file.py"))
        if not file_name:
            file_name = "unknown_file.py"
        lineno = record.get("lineno", "")
        file_line_info = file_name
        if lineno:
            file_line_info += f":{lineno}"

        ts = record.get("timestamp", "")
        if " : " in ts:
            date_part, time_part = ts.split(" : ", 1)
            # Remove any trailing timezone abbreviation (e.g., "PDT")
            time_part = re.sub(r'\s*[A-Z]{3,4}$', '', time_part)
        else:
            date_part, time_part = ts, ""

        # Build the main HTML for the title bar.
        let_main_html = (
            f'<div class="alert {line_color_class} d-flex align-items-center justify-content-between mb-1" '
            f'style="margin: 2px 0; padding: 3px; white-space: nowrap; cursor: pointer;" '
            f'title="File: {file_line_info}">'
            f'<div style="flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis;">'
            f'<span style="font-size: 1rem;">{icon}</span> '
            f'<strong>{display_text}</strong>'
        )

        # If alert_details exist and operation_type is "Price ALERT", append countdown timers.
        details = record.get("alert_details")
        if details and record.get("operation_type", "").strip() == "Price ALERT":
            alert_trigger_time = details.get("alert_trigger_time", 0)
            cooldown_duration = details.get("cooldown_duration", 0)
            refractory_duration = details.get("refractory_duration", 0)
            # Add two countdown timer spans with data attributes.
            countdown_html = (
                f'<span class="countdown-timer" style="margin-left:10px; font-size:0.8rem; color:blue; cursor:pointer;" '
                f'data-trigger-time="{alert_trigger_time}" data-duration="{cooldown_duration}" '
                f'data-timer-type="cooldown">'
                f'Cooldown: {cooldown_duration}s</span> '
                f'<span class="countdown-timer refractory" style="margin-left:10px; font-size:0.8rem; color:green; cursor:pointer;" '
                f'data-trigger-time="{alert_trigger_time}" data-duration="{refractory_duration}" '
                f'data-timer-type="refractory">'
                f'Refractory: {refractory_duration}s</span>'
            )
            let_main_html += countdown_html

        let_main_html += (
            f'</div>'
            f'<div style="flex: 0 0 auto; margin: 0 16px; text-align: center; min-width: 30px;">'
            f'<span style="font-size: 1rem;">{source_icon}</span>'
            f'</div>'
            f'<div style="flex: 0 0 auto; text-align: right; min-width: 120px;">'
            f'<span style="font-weight: normal;">{date_part}</span>&nbsp;'
            f'<span style="font-weight: bold;">{time_part}</span>'
            f'</div>'
            f'</div>'
        )

        if details:
            details_html = '<div class="alert-extra-details" style="display: none; margin: 5px 0; padding: 5px; background: #f9f9f9; border: 1px solid #ddd; border-radius: 4px;">'
            details_html += '<ul style="margin:0; padding: 0 15px;">'
            for k, value in details.items():
                details_html += f'<li><strong>{k.capitalize()}:</strong> {value}</li>'
            details_html += '</ul></div>'
            return let_main_html + details_html
        else:
            return let_main_html

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
