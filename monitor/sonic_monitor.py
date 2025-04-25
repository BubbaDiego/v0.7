#!/usr/bin/env python3
"""
===========================================================
|    Sonic Monitor - The Unified Heartbeat of Our System |
===========================================================

This file orchestrates market updates, position syncs,
price fetches, enrichment steps, alert creation, and
hedge updates in a single always-on loop.

"""
import os
import sys
import time
import asyncio
import logging
from datetime import datetime, timezone

import pytz
from cyclone.cyclone import Cyclone
from monitor.common_monitor_utils import load_timer_config, update_timer_config

# ——— Setup logging in PST ———
PST = pytz.timezone("America/Los_Angeles")
logging.Formatter.converter = lambda *args: datetime.now(PST).timetuple()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def heartbeat(loop_counter: int):
    """
    Record a heartbeat in timer_config for monitoring loops.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    cfg = load_timer_config()
    cfg["sonic_loop_start_time"] = timestamp
    update_timer_config(cfg)
    logging.info("Heartbeat #%d at %s", loop_counter, timestamp)

async def run_cycle(loop_counter: int, cyclone: Cyclone):
    """
    Execute the full SonicMonitor cycle using Cyclone steps.
    """
    logging.info("🔄 Sonic Monitor Loop #%d starting", loop_counter)
    await cyclone.run_cycle()
    heartbeat(loop_counter)
    logging.info("✔️ Sonic Monitor Loop #%d completed", loop_counter)
    print("❤️🦄" * 10)


def main():
    # Ensure project root is in sys.path
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    sys.path.insert(0, BASE_DIR)

    # Load loop interval from config (seconds)
    interval = load_timer_config().get("sonic_loop_interval", 60)
    cyclone = Cyclone(poll_interval=interval)
    loop = asyncio.get_event_loop()
    loop_counter = 0

    try:
        while True:
            loop_counter += 1
            loop.run_until_complete(run_cycle(loop_counter, cyclone))
            time.sleep(interval)
    except KeyboardInterrupt:
        logging.info("Sonic Monitor stopped by user")


if __name__ == "__main__":
    main()
