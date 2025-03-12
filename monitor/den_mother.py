#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '/home/BubbaDiego/v0.7')

import time
import json
import logging
import argparse
from datetime import datetime, timedelta, timezone
from config.config_constants import HEARTBEAT_FILE, BASE_DIR  # Using the heartbeat file constant
from utils.unified_logger import UnifiedLogger
from alerts.alert_manager import trigger_twilio_flow

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
        unified_logger.log_alert("Heartbeat Failure", alert_msg, source="system", file="watchdog")
        # Trigger Twilio notification:
        try:
            twilio_config = sonic_config.get("twilio_config", {})
            execution_sid = trigger_twilio_flow(alert_msg, twilio_config)
            unified_logger.log_operation("Twilio Notification",
                                         f"Twilio alert sent (SID: {execution_sid})",
                                         source="system", file="den_mother")
        except Exception as twilio_e:
            unified_logger.log_operation("Notification Failed",
                                         f"Twilio notification failed: {twilio_e}",
                                         source="system", file="den_mother")
        return

    # Use timezone-aware current UTC time.
    now = datetime.now(timezone.utc)
    elapsed_minutes = (now - last_update).seconds // 60

    if now - last_update > timedelta(minutes=THRESHOLD_MINUTES):
        alert_msg = (f"\033[91mWatchdog alert: No heartbeat update for {elapsed_minutes} minutes! "
                     f"Notifications: email to {email_recipient}, SMS to {sms_recipient}\033[0m")
        if alert_monitor_enabled:
            unified_logger.log_alert("Heartbeat Failure", alert_msg, source="system", file="watchdog")
        else:
            unified_logger.log_operation("Heartbeat Failure", alert_msg, source="system", file="watchdog")
        # Also send a Twilio alert here if needed:
        try:
            twilio_config = sonic_config.get("twilio_config", {})
            execution_sid = trigger_twilio_flow(alert_msg, twilio_config)
            unified_logger.log_operation("Twilio Notification",
                                         f"Twilio alert sent (SID: {execution_sid})",
                                         source="system", file="den_mother")
        except Exception as twilio_e:
            unified_logger.log_operation("Notification Failed",
                                         f"Twilio notification failed: {twilio_e}",
                                         source="system", file="den_mother")
    else:
        success_msg = f"\033[92mHeartbeat is fresh. Last update was {elapsed_minutes} minutes ago.\033[0m"
        unified_logger.log_operation("Heartbeat Success", success_msg, source="system", file="den_mother")


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
