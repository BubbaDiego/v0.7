#!/usr/bin/env python3
import os
import sys
import time
import json
import logging
import requests
import urllib3
from datetime import datetime, timezone
import pytz

# Set logging to use Pacific Standard Time (PST)
PST = pytz.timezone("America/Los_Angeles")
logging.Formatter.converter = lambda *args: datetime.now(PST).timetuple()

# Ensure BASE_DIR is added to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.config_constants import HEARTBEAT_FILE, BASE_DIR
from utils.unified_logger import UnifiedLogger

# Disable InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# URL Constants for sonic_monitor
JUPITER_URL = "http://www.deadlypanda.com/positions/update_jupiter"
MARKET_URL = "http://www.deadlypanda.com/cyclone/api/run_market_updates"
CYCLE_URL = "http://www.deadlypanda.com/cyclone/api/run_full_cycle"

# Define timer config file path (assumes timer_config.json is in the config folder)
TIMER_CONFIG_PATH = os.path.join(BASE_DIR, "config", "timer_config.json")

def load_timer_config():
    try:
        with open(TIMER_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error("Error loading timer config: %s", e)
        return {}

def update_timer_config(new_config: dict):
    try:
        with open(TIMER_CONFIG_PATH, "w") as f:
            json.dump(new_config, f, indent=4)
    except Exception as e:
        logging.error("Error updating timer config: %s", e)

# Load timer configuration for sonic_monitor (using sonic_loop_interval in seconds)
timer_config = load_timer_config()
sonic_loop_interval = timer_config.get("sonic_loop_interval", 120)  # default to 120 seconds

# Create a UnifiedLogger instance
unified_logger = UnifiedLogger()

def log_operation_with_line(operation_type: str, primary_text: str, source: str, file: str):
    import inspect
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

def call_jupiter():
    try:
        response = requests.get(JUPITER_URL, timeout=30, verify=False)
        response.raise_for_status()
        logging.info("Called update_jupiter successfully. Status code: %s", response.status_code)
    except Exception as e:
        logging.error("Error calling update_jupiter: %s", e)

def call_market_updates():
    try:
        response = requests.post(MARKET_URL, timeout=30, verify=False)
        response.raise_for_status()
        logging.info("Called run_market_updates successfully. Status code: %s", response.status_code)
    except Exception as e:
        logging.error("Error calling run_market_updates: %s", e)

def call_run_cycle():
    try:
        response = requests.post(CYCLE_URL, timeout=30, verify=False)
        response.raise_for_status()
        logging.info("Called run_cycle successfully. Status code: %s", response.status_code)
    except Exception as e:
        logging.error("Error calling run_cycle: %s", e)

def write_ledger(loop_counter):
    LEDGER_FILE = os.path.join(BASE_DIR, "monitor", "sonic_ledger.json")
    ledger_dir = os.path.dirname(LEDGER_FILE)
    os.makedirs(ledger_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    ledger_entry = {
        "timestamp": timestamp,
        "component": "sonic_monitor",
        "operation": "heartbeat_update",
        "status": "Success",
        "message": "Heartbeat updated successfully.",
        "metadata": {
            "loop_counter": loop_counter
        }
    }
    try:
        with open(LEDGER_FILE, "a") as f:
            f.write(json.dumps(ledger_entry) + "\n")
        logging.info("Ledger updated: %s", ledger_entry)
        current_timer_config = load_timer_config()
        current_timer_config["sonic_loop_start_time"] = timestamp
        update_timer_config(current_timer_config)
    except Exception as e:
        logging.error("Failed to update ledger: %s", e)

def main():
    loop_counter = 0
    while True:
        current_timer_config = load_timer_config()
        current_timestamp = datetime.now(timezone.utc).isoformat()
        current_timer_config["sonic_loop_start_time"] = current_timestamp
        update_timer_config(current_timer_config)

        loop_counter += 1
        logging.info("Sonic Monitor Loop count: %d. Calling endpoints...", loop_counter)
        call_market_updates()
        time.sleep(10)
        call_run_cycle()
        call_jupiter()
        log_operation_with_line("Monitor Loop", f"Monitor Loop #{loop_counter} - Endpoints called", "Cyclone", "sonic_monitor.py")
        write_ledger(loop_counter)
        print("❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄")
        time.sleep(sonic_loop_interval)

if __name__ == '__main__':
    main()
