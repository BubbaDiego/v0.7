#!/usr/bin/env python3
import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict

from monitor.common_monitor_utils import BaseMonitor
from data.data_locker import DataLocker
from utils.unified_logger import UnifiedLogger
import requests

# Constants
from config.config_constants import COM_CONFIG_PATH

# Module logger
logger = logging.getLogger("PriceMonitor")
logger.setLevel(logging.DEBUG)

class GPTIsFuckingStupid:
    """
    Simple helper to fetch BTC, ETH, and SOL prices from CoinGecko.
    """
    COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

    def __init__(self):
        self.params = {
            "ids": "bitcoin,ethereum,solana",
            "vs_currencies": "usd"
        }

    def get_prices(self) -> Dict[str, float]:
        try:
            resp = requests.get(self.COINGECKO_URL, params=self.params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return {
                "BTC": data.get("bitcoin", {}).get("usd"),
                "ETH": data.get("ethereum", {}).get("usd"),
                "SOL": data.get("solana", {}).get("usd"),
            }
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {}

class PriceMonitor(BaseMonitor):
    """
    Standalone price monitor using GPTIsFuckingStupid fetcher.
    """
    def __init__(self, timer_config_path: str = None, ledger_filename: str = None):
        super().__init__(
            name="price_monitor",
            timer_config_path=timer_config_path,
            ledger_filename=ledger_filename or "price_ledger.json"
        )
        self.data_locker = DataLocker.get_instance()
        self.u_logger = UnifiedLogger()
        self.fetcher = GPTIsFuckingStupid()

    def _do_work(self) -> dict:
        prices = self.fetcher.get_prices()
        count = 0
        for symbol, price in prices.items():
            if price is not None:
                self.data_locker.insert_or_update_price(symbol, price, "Fetched")
                count += 1
        # update last update time
        now = datetime.now(timezone.utc)
        self.data_locker.set_last_update_times(prices_dt=now, prices_source="GPTFetch")
        self.u_logger.log_cyclone(
            operation_type="Price Update",
            primary_text=f"Fetched {count} prices",
            source="PriceMonitor",
            file=__file__
        )
        return {"loop_counter": count}

    async def update_prices(self, source: str = "Manual") -> dict:
        loop = asyncio.get_event_loop()
        metadata = await loop.run_in_executor(None, self._do_work)
        return metadata

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    pm = PriceMonitor(timer_config_path=os.getenv("TIMER_CONFIG_PATH"))
    try:
        pm.run_cycle()
        logging.info("PriceMonitor cycle complete.")
    except Exception as e:
        logging.error(f"PriceMonitor error: {e}")
