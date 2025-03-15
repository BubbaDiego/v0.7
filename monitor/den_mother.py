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
from config.config_constants import HEARTBEAT_FILE, BASE_DIR  # Using the heartbeat file constant
from utils.unified_logger import UnifiedLogger
from alerts.alert_manager import trigger_twilio_flow

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
THRESHOLD_MINUTES = 5

# Create an instance of the UnifiedLogger
unified_logger = UnifiedLogger()

def log_operation_with_line(operation_type: str, primary_text: str, source: str, file: str):
    """
    Helper function that logs an operation along with the caller's line number.
    """
    # Get the line number of the caller from the previous stack frame.
    lineno = inspect.currentframe().f_back.f_lineno
    extra = {
        "source": source,
        "operation_type": operation_type,
        "log_type": "operation",
        "file": file,
        "lineno": lineno
    }
    unified_logger.logger.info(primary_text, extra=extra)
    unified_logger.logger.debug("Logged operation entry with operation_type=%s at line %s", operation_type, lineno)

def check_heartbeat():
    try:
        with open(HEARTBEAT_FILE, "r") as f:
            timestamp_str = f.read().strip()
            if not timestamp_str:
                raise ValueError("Heartbeat file is empty")
            # Parse the heartbeat timestamp as an offset-aware datetime.
            last_update = datetime.fromisoformat(timestamp_str)
    except Exception as e:
        alert_msg = (f"\033[91mWatchdog alert: Could not read heartbeat file: {e}. "
                     f"Notifications: email to {email_recipient}, SMS to {sms_recipient}\033[0m")
        # Strip ANSI codes before sending to Twilio
        clean_alert_msg = strip_ansi_codes(alert_msg)
        log_operation_with_line("Heartbeat Failure", alert_msg, source="system", file="den_mother.py")
        # Trigger Twilio notification:
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
        return

    # Use timezone-aware current UTC time.
    now = datetime.now(timezone.utc)
    elapsed_minutes = (now - last_update).seconds // 60

    if now - last_update > timedelta(minutes=THRESHOLD_MINUTES):
        alert_msg = (f"\033[91mOh Shit Alert: No heartbeat update for {elapsed_minutes} minutes! "
                     f"Notifications: email to {email_recipient}, SMS to {sms_recipient}\033[0m")
        log_operation_with_line("Heartbeat Failure", alert_msg, source="system", file="den_mother.py")
        # Also send a Twilio alert here if needed:
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
    else:
        success_msg = f"\033[92mHeartbeat is fresh. Last update was {elapsed_minutes} minutes ago.\033[0m"
        log_operation_with_line("Heartbeat Detected", success_msg, source="monitor", file="den_mother.py")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Watchdog Script for Jupiter Monitor.")
    parser.add_argument('--mode', choices=['oneshot', 'monitor'], default='oneshot',
                        help="Mode of operation: 'oneshot' to run once, 'monitor' to continuously check.")
    args = parser.parse_args()

    if args.mode == 'oneshot':
        check_heartbeat()
    else:  # Monitor mode: continuously check
        while True:
            check_heartbeat()
            time.sleep(300)  # Check every 5 minutes
