#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import requests
import logging
import urllib3
import json
from datetime import datetime, timezone
from utils.unified_logger import UnifiedLogger
from config.config_constants import HEARTBEAT_FILE, BASE_DIR

# Disable InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging to print to the console.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# URL Constants
JUPITER_URL = "http://www.deadlypanda.com/positions/update_jupiter"
MARKET_URL = "http://www.deadlypanda.com/cyclone/api/run_market_updates"
CYCLE_URL = "http://www.deadlypanda.com/cyclone/api/run_full_cycle"

SLEEP_INTERVAL = 120  # 2 minutes in seconds

# Define the ledger file using BASE_DIR from config_constants
LEDGER_FILE = os.path.join(BASE_DIR, "monitor", "sonic_ledger.json")


def call_jupiter():
    try:
        response = requests.get(JUPITER_URL, timeout=30, verify=False)
        response.raise_for_status()  # Raise an exception for HTTP errors.
        logging.info("Called update_jupiter successfully at URL %s. Status code: %s", JUPITER_URL, response.status_code)
    except Exception as e:
        logging.error("Error calling update_jupiter at URL %s: %s", JUPITER_URL, e)


def call_market_updates():
    try:
        response = requests.post(MARKET_URL, timeout=30, verify=False)
        response.raise_for_status()
        logging.info("Called run_market_updates successfully at URL %s. Status code: %s", MARKET_URL,
                     response.status_code)
    except Exception as e:
        logging.error("Error calling run_market_updates at URL %s: %s", MARKET_URL, e)


def call_run_cycle():
    try:
        response = requests.post(CYCLE_URL, timeout=30, verify=False)
        response.raise_for_status()
        logging.info("Called run_cycle successfully at URL %s. Status code: %s", CYCLE_URL, response.status_code)
    except Exception as e:
        logging.error("Error calling run_cycle at URL %s: %s", CYCLE_URL, e)


def main():
    loop_counter = 0
    logger = UnifiedLogger()  # Using UnifiedLogger

    def write_ledger():
        # Ensure the directory for the ledger file exists
        ledger_dir = os.path.dirname(LEDGER_FILE)
        os.makedirs(ledger_dir, exist_ok=True)

        # Use timezone-aware UTC time
        timestamp = datetime.now(timezone.utc).isoformat()
        ledger_entry = {
            "timestamp": timestamp,
            "component": "sonic_monitor",
            "operation": "heartbeat_update",
            "status": "Success",
            "message": "Heartbeat updated successfully.",
            "metadata": {
            "loop_counter": loop_counter  # Pass in the current loop_counter here
            }
        }

        try:
            with open(LEDGER_FILE, "a") as f:
                f.write(json.dumps(ledger_entry) + "\n")
            logging.info("Ledger updated.")
            logger.log_operation(
                operation_type="Heartbeat",
                primary_text=f"Ledger updated at {timestamp}",
                source="system",
                file="sonic_monitor.py"
            )
        except Exception as e:
            logging.error("Failed to update ledger: %s", e)

    while True:
        loop_counter += 1
        logging.info("Loop count: %d. Calling Cyclone endpoints", loop_counter)

        # Call the endpoints
        call_market_updates()
        time.sleep(10)
        call_run_cycle()
        call_jupiter()

        logger.log_operation(
            operation_type="Monitor Loop",
            primary_text=f"Monitor Loop # {loop_counter} - Called Cyclone endpoints",
            source="monitor",
            file="sonic_monitor.py"
        )
        write_ledger()
        print("❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄 ")
        time.sleep(SLEEP_INTERVAL)


if __name__ == '__main__':
    main()
