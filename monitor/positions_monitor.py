#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
import json
from datetime import datetime, timezone

# Ensure BASE_DIR in path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from common_monitor_utils import load_timer_config, update_timer_config, call_endpoint
from utils.unified_logger import UnifiedLogger
from data.data_locker import DataLocker
from positions.position_service import PositionService

# Constants
JUPITER_URL = "http://www.deadlypanda.com/positions/update_jupiter"
LEDGER_DIR = os.path.join(BASE_DIR, "monitor")
LEDGER_FILE = os.path.join(LEDGER_DIR, "position_ledger.json")

# Setup logging
logger = logging.getLogger("PositionMonitorLogger")
logger.setLevel(logging.INFO)

class PositionMonitor:
    def __init__(self):
        # Singleton DB access
        self.data_locker = DataLocker.get_instance()
        # Unified logger
        self.u_logger = UnifiedLogger()

        # Load loop interval
        cfg = load_timer_config()
        self.position_loop_interval = cfg.get("position_loop_interval", 60)

    async def update_positions(self, source: str = "Scheduled"):
        """
        Update positions by calling Jupiter API and internal service, then log and ledger.
        """
        logger.info("Starting position update [%s]", source)

        # 1) External HTTP call
        try:
            call_endpoint(JUPITER_URL, method="get")  # retries built-in
            logger.info("Called external Jupiter endpoint successfully")
        except Exception as e:
            logger.error("Error calling Jupiter endpoint: %s", e)

        # 2) Internal service update
        try:
            result = PositionService.update_jupiter_positions()
            msg = result.get('message', 'No message')
            self.u_logger.log_cyclone(
                operation_type="Position Update",
                primary_text=f"Internal update: {msg}",
                source="PositionMonitor",
                file=__file__
            )
            logger.info("Internal position update result: %s", msg)
        except Exception as e:
            logger.error("PositionService error: %s", e)
            self.u_logger.log_cyclone(
                operation_type="Position Update Failed",
                primary_text=str(e),
                source="PositionMonitor",
                file=__file__
            )

        # 3) Heartbeat ledger
        self._write_ledger(source)

    def _write_ledger(self, operation: str):
        os.makedirs(LEDGER_DIR, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "timestamp": timestamp,
            "component": "PositionMonitor",
            "operation": operation,
            "status": "Success",
        }
        with open(LEDGER_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info("Ledger entry written: %s", entry)

        # Update timer_config timestamp
        cfg = load_timer_config()
        cfg["position_loop_start_time"] = timestamp
        update_timer_config(cfg)

    async def start_position_loop(self):
        """
        Kick off continuous position updates.
        """
        # Optional initial run
        await self.update_positions(source="Initial")
        while True:
            await self.update_positions(source="Scheduled")
            await asyncio.sleep(self.position_loop_interval)

if __name__ == '__main__':
    monitor = PositionMonitor()
    asyncio.run(monitor.start_position_loop())
