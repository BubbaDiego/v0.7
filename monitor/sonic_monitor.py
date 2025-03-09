#!/usr/bin/env python3
import time
import requests
import logging
import urllib3
import os
from datetime import datetime, timezone
from utils.operations_manager import OperationsLogger  # Import from external module
from config.config_constants import HEARTBEAT_FILE  # Import heartbeat constant

# Disable InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging to print to the console.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# URL for the update call
URL = "http://www.deadlypanda.com/positions/update_jupiter"
#URL = "http://127.0.0.1:5001/positions/update_jupiter"
SLEEP_INTERVAL = 120  # 2 minutes in seconds


def call_update_jupiter():
    try:
        response = requests.get(URL, timeout=30, verify=False)
        response.raise_for_status()  # Raise an exception for HTTP errors.
        logging.info("Called update_jupiter successfully at URL %s. Status code: %s", URL, response.status_code)
    except Exception as e:
        logging.error("Error calling update_jupiter at URL %s: %s", URL, e)


def main():
    loop_counter = 0
    op_logger = OperationsLogger()
    logging.info("Starting always‑on task for update_jupiter. URL: %s", URL)

    def write_heartbeat():
        # Ensure the directory for the heartbeat file exists
        heartbeat_dir = os.path.dirname(HEARTBEAT_FILE)
        os.makedirs(heartbeat_dir, exist_ok=True)

        # Use timezone-aware UTC time
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with open(HEARTBEAT_FILE, "w") as f:
                f.write(timestamp)
            logging.info("Heartbeat updated.")
            op_logger.log(f"Heartbeat updated at {timestamp}", source="system", operation_type="Heartbeat")
        except Exception as e:
            logging.error("Failed to update heartbeat: %s", e)

    while True:
        loop_counter += 1
        logging.info("Loop count: %d. Calling URL: %s", loop_counter, URL)
        call_update_jupiter()
        op_logger.log(f"Monitor Loop # {loop_counter}", source="system", operation_type="Monitor Loop")

        write_heartbeat()

        time.sleep(SLEEP_INTERVAL)


if __name__ == '__main__':
    main()
