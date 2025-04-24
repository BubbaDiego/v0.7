#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime, timezone

from common_monitor_utils import BaseMonitor, call_endpoint
from positions.position_service import PositionService

# Module logger
logger = logging.getLogger(__name__)

class PositionMonitor(BaseMonitor):
    """
    Monitor for positions. Fetches positions, processes them, and writes ledger entries.
    """
    def __init__(self,
                 timer_config_path: str = None,
                 ledger_filename: str = None):
        super().__init__(
            name="position_monitor",
            timer_config_path=timer_config_path,
            ledger_filename=ledger_filename or "position_ledger.json"
        )
        self.service = PositionService()

    def _do_work(self) -> dict:
        """
        Fetches all positions, writes a detailed ledger entry, and returns metadata for heartbeat.
        """
        all_positions = self.service.get_all_positions() or []
        processed_count = len(all_positions)
        total_value = sum(float(p.get("value", 0)) for p in all_positions)

        # Manual ledger entry
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.name,
            "operation": "positions_update",
            "status": "Success",
            "metadata": {
                "processed_count": processed_count,
                "total_value": total_value
            }
        }
        # Write to ledger immediately
        self.ledger_writer.write(self.ledger_file, entry)

        # Return metadata for BaseMonitor heartbeat
        return {"processed_positions": processed_count}


if __name__ == "__main__":
    # Example usage
    monitor = PositionMonitor()
    try:
        monitor.run_cycle()
        logger.info("PositionMonitor cycle complete.")
    except Exception as e:
        logger.error(f"PositionMonitor encountered an error: {e}")
