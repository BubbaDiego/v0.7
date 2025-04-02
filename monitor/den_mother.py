#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, '/home/BubbaDiego/v0.7')

import time
import json
import logging
import argparse
import re
import inspect
from datetime import datetime, timedelta, timezone
from config.config_constants import HEARTBEAT_FILE, BASE_DIR  # Using the heartbeat file constant and BASE_DIR
from utils.unified_logger import UnifiedLogger
from alerts.alert_manager import trigger_twilio_flow

# Import xCom communication functions for fallback notifications
from xcom.xcom import send_email, send_sms, load_com_config

# Define ledger and HTML report file paths using BASE_DIR
LEDGER_FILE = os.path.join(BASE_DIR, "monitor", "sonic_ledger.json")
HTML_REPORT_FILE = os.path.join(BASE_DIR, "monitor", "sonic_monitor.html")


# Function to strip ANSI escape codes
def strip_ansi_codes(text: str) -> str:
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)


# Load sonic configuration from sonic_config.json
sonic_config_path = os.path.join(BASE_DIR, "sonic_config.json")
try:
    with open(sonic_config_path, "r") as f:
        sonic_config = json.load(f)
except Exception as e:
    logging.error("Error loading sonic configuration: %s", e)
    sonic_config = {}

# Retrieve notification settings from sonic_config.json
notification_config = sonic_config.get("notification_config", {})
email_config = notification_config.get("email", {})
sms_config = notification_config.get("sms", {})
email_recipient = email_config.get("recipient_email", "N/A")
sms_recipient = sms_config.get("recipient_number", "N/A")

# Retrieve system alert settings from sonic_config.json
system_config = sonic_config.get("system_config", {})
alert_monitor_enabled = system_config.get("alert_monitor_enabled", True)

# Set threshold (in minutes) for considering the monitor as down
THRESHOLD_MINUTES = 35

# Create an instance of the UnifiedLogger
unified_logger = UnifiedLogger()


def log_operation_with_line(operation_type: str, primary_text: str, source: str, file: str):
    """
    Helper function that logs an operation along with the caller's line number.
    Uses 'caller_lineno' to avoid overwriting the reserved 'lineno' attribute.
    """
    lineno = inspect.currentframe().f_back.f_lineno
    extra = {
        "source": source,
        "operation_type": operation_type,
        "log_type": "operation",
        "file": file,
        "caller_lineno": lineno
    }
    unified_logger.logger.info(primary_text, extra=extra)
    unified_logger.logger.debug("Logged operation entry with operation_type=%s at line %s", operation_type, lineno)


def write_ledger(component: str, operation: str, status: str, message: str, metadata: dict = None):
    """
    Appends a JSON ledger entry to the shared ledger file.
    """
    ledger_dir = os.path.dirname(LEDGER_FILE)
    os.makedirs(ledger_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    ledger_entry = {
        "timestamp": timestamp,
        "component": component,
        "operation": operation,
        "status": status,
        "message": message,
        "metadata": metadata if metadata is not None else {}
    }
    try:
        with open(LEDGER_FILE, "a") as f:
            f.write(json.dumps(ledger_entry) + "\n")
        logging.info("Ledger updated: %s", ledger_entry)
    except Exception as ex:
        logging.error("Failed to update ledger: %s", ex)


def generate_html_report():
    """
    Reads the ledger file, filters entries from the last 15 minutes, and generates
    a pretty HTML report that overwrites itself every update.
    """
    current_time = datetime.now(timezone.utc)
    entries = []
    try:
        with open(LEDGER_FILE, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entry_time = datetime.fromisoformat(entry.get("timestamp"))
                    if current_time - entry_time <= timedelta(minutes=15):
                        entries.append(entry)
                except Exception as e:
                    logging.error("Error parsing ledger entry: %s", e)
    except Exception as e:
        logging.error("Could not read ledger file: %s", e)

    html_content = """
    <html>
    <head>
      <title>Sonic Monitor Report</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
      </style>
    </head>
    <body>
      <h2>Sonic Monitor Report (Last 15 Minutes)</h2>
      <table>
        <tr>
          <th>Timestamp</th>
          <th>Component</th>
          <th>Operation</th>
          <th>Status</th>
          <th>Message</th>
          <th>Metadata</th>
        </tr>
    """
    for entry in entries:
        metadata_str = json.dumps(entry.get("metadata", {}))
        html_content += f"""
        <tr>
          <td>{entry.get("timestamp")}</td>
          <td>{entry.get("component")}</td>
          <td>{entry.get("operation")}</td>
          <td>{entry.get("status")}</td>
          <td>{entry.get("message")}</td>
          <td>{metadata_str}</td>
        </tr>
        """
    html_content += """
      </table>
    </body>
    </html>
    """
    try:
        with open(HTML_REPORT_FILE, "w") as f:
            f.write(html_content)
        logging.info("HTML report generated at %s", HTML_REPORT_FILE)
    except Exception as e:
        logging.error("Failed to write HTML report: %s", e)


def notify_failure_via_fallback(error_message: str):
    """
    Uses xCom's email and SMS functions to send fallback notifications if Twilio fails.
    Also logs the fallback notification via the ops log.
    """
    config = load_com_config()
    subject = "Holy shit batman.  Twilio Failure Alert"
    body = f"Twilio notification failed with error: {error_message}"
    email_success = send_email("", subject, body, config=config)
    sms_success = send_sms("", body, config=config)
    if email_success or sms_success:
        log_operation_with_line("Fallback Notification",
                                f"Fallback notifications sent via email and SMS. Error: {error_message}",
                                source="system", file="den_mother.py")
    else:
        log_operation_with_line("Fallback Notification",
                                f"Fallback notifications failed to send. Error: {error_message}",
                                source="system", file="den_mother.py")


def check_heartbeat():
    try:
        with open(HEARTBEAT_FILE, "r") as f:
            timestamp_str = f.read().strip()
            if not timestamp_str:
                raise ValueError("Heartbeat file is empty")
            last_update = datetime.fromisoformat(timestamp_str)
    except Exception as e:
        alert_msg = (
            f"\033[91mWatchdog alert: Could not read heartbeat file: {e}. "
            f"Notifications: email to {email_recipient}, SMS to {sms_recipient}\033[0m"
        )
        log_operation_with_line("Heartbeat Failure", alert_msg, source="system", file="den_mother.py")
        try:
            twilio_config = sonic_config.get("twilio_config", {})
            alert_msg_for_twilio = "Watchdog alert: Could not read heartbeat file: " + str(e)
            execution_sid = trigger_twilio_flow(strip_ansi_codes(alert_msg_for_twilio), twilio_config)
            log_operation_with_line("Twilio Notification",
                                    f"Twilio alert sent (SID: {execution_sid})",
                                    source="system", file="den_mother.py")
        except Exception as twilio_e:
            log_operation_with_line("Notification Failed",
                                    f"Twilio notification failed: {twilio_e}",
                                    source="system", file="den_mother.py")
            notify_failure_via_fallback(str(twilio_e))
        write_ledger("den_mother", "heartbeat_check", "error", f"Failed to read heartbeat: {e}", {"error": str(e)})
        return

    now = datetime.now(timezone.utc)
    elapsed_minutes = (now - last_update).seconds // 60

    if now - last_update > timedelta(minutes=THRESHOLD_MINUTES):
        alert_msg = (
            f"\033[91mOh Shit Alert: No heartbeat update for {elapsed_minutes} minutes! "
            f"Notifications: email to {email_recipient}, SMS to {sms_recipient}\033[0m"
        )
        log_operation_with_line("Heartbeat Failure", alert_msg, source="system", file="den_mother.py")
        try:
            twilio_config = sonic_config.get("twilio_config", {})
            clean_alert_msg = strip_ansi_codes(alert_msg)
            execution_sid = trigger_twilio_flow(clean_alert_msg, twilio_config)
            log_operation_with_line("Twilio Notification",
                                    f"Twilio alert sent (SID: {execution_sid})",
                                    source="system", file="den_mother.py")
        except Exception as twilio_e:
            log_operation_with_line("Notification Failed",
                                    f"Twilio notification failed: {twilio_e}",
                                    source="system", file="den_mother.py")
            notify_failure_via_fallback(str(twilio_e))
        write_ledger("den_mother", "heartbeat_check", "error", f"No heartbeat update for {elapsed_minutes} minutes.",
                     {"elapsed_minutes": elapsed_minutes})
    else:
        success_msg = f"Heartbeat is fresh. Last update was {elapsed_minutes} minutes ago."
        log_operation_with_line("Heartbeat Detected", success_msg, source="monitor", file="den_mother.py")
        write_ledger("den_mother", "heartbeat_check", "success", success_msg, {"elapsed_minutes": elapsed_minutes})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Watchdog Script for Jupiter Monitor.")
    parser.add_argument(
        '--mode',
        choices=['oneshot', 'monitor'],
        default='oneshot',
        help="Mode of operation: 'oneshot' to run once, 'monitor' to continuously check."
    )
    args = parser.parse_args()

    if args.mode == 'oneshot':
        check_heartbeat()
        generate_html_report()
    else:
        while True:
            check_heartbeat()
            generate_html_report()
            time.sleep(300)  # Check every 5 minutes
