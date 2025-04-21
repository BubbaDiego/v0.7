#!/usr/bin/env python3
import os
import sys
import time
import json
import logging
from datetime import datetime, timezone

import pytz
import urllib3

from common_monitor_utils import load_timer_config, update_timer_config, call_endpoint
from utils.unified_logger import UnifiedLogger

# ——— Setup logging in PST ———
PST = pytz.timezone("America/Los_Angeles")
logging.Formatter.converter = lambda *args: datetime.now(PST).timetuple()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Ensure BASE_DIR on path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

# Endpoints
JUPITER_URL = "http://www.deadlypanda.com/positions/update_jupiter"
MARKET_URL  = "http://www.deadlypanda.com/cyclone/api/run_market_updates"
CYCLE_URL   = "http://www.deadlypanda.com/cyclone/api/run_full_cycle"

# Initialize unified logger
u_logger = UnifiedLogger()
logger   = u_logger.logger

def heartbeat_ledger(loop_counter: int):
    """
    Append a heartbeat entry and update the last-run timestamp in timer_config.
    """
    ledger_file = os.path.join(BASE_DIR, "monitor", "sonic_ledger.json")
    os.makedirs(os.path.dirname(ledger_file), exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": "sonic_monitor",
        "operation": "heartbeat_update",
        "status": "Success",
        "metadata": {"loop_counter": loop_counter}
    }
    with open(ledger_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    logger.info("Ledger entry: %s", entry)

    cfg = load_timer_config()
    cfg["sonic_loop_start_time"] = entry["timestamp"]
    update_timer_config(cfg)

def do_cycle(loop_counter: int):
    """
    Perform one full monitor cycle: market, full cycle, jupiter, log & heartbeat.
    """
    logger.info("🔄 Sonic Monitor iteration #%d starting", loop_counter)

    # Market updates
    try:
        call_endpoint(MARKET_URL, method="post")
        logger.info("Market updates succeeded")
    except Exception as e:
        logger.error("Market update error: %s", e)

    time.sleep(3)

    # Full cycle
    try:
        call_endpoint(CYCLE_URL, method="post")
        logger.info("Full cycle succeeded")
    except Exception as e:
        logger.error("Full cycle error: %s", e)

    # Jupiter update
    try:
        call_endpoint(JUPITER_URL, method="get")
        logger.info("Jupiter update succeeded")
    except Exception as e:
        logger.error("Jupiter update error: %s", e)

    # Structured log entry
    u_logger.log_cyclone(
        operation_type="Monitor Loop",
        primary_text=f"Monitor Loop #{loop_counter} completed",
        source="SonicMonitor",
        file="sonic_monitor.py"
    )

    # Heartbeat + config timestamp
    heartbeat_ledger(loop_counter)

    # Your signature unicorn banner
    print("❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄❤️🦄")

def main():
    cfg = load_timer_config()
    interval = cfg.get("sonic_loop_interval", 120)
    loop_counter = 0

    while True:
        loop_counter += 1
        do_cycle(loop_counter)
        time.sleep(interval)

if __name__ == '__main__':
    main()
