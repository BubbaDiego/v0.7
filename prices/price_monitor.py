#!/usr/bin/env python3
import sys
import os
# Add the parent directory of this file to sys.path so that modules can be found.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import logging
from typing import Dict, List

from config.unified_config_manager import UnifiedConfigManager  # Updated to use the unified config manager.
from data.data_locker import DataLocker
from prices.coingecko_fetcher import fetch_current_coingecko
from prices.coinmarketcap_fetcher import fetch_current_cmc, fetch_historical_cmc
from prices.coinpaprika_fetcher import fetch_current_coinpaprika
from prices.binance_fetcher import fetch_current_binance
from config.config_constants import DB_PATH, CONFIG_PATH
from utils.operations_manager import OperationsLogger

logger = logging.getLogger("PriceMonitorLogger")

class PriceMonitor:
    def __init__(self, db_path: str = DB_PATH, config_path: str = CONFIG_PATH):
        self.db_path = db_path
        self.config_path = config_path

        # Setup DataLocker & DB connection.
        self.data_locker = DataLocker(self.db_path)
        self.db_conn = self.data_locker.get_db_connection()

        # Load configuration using UnifiedConfigManager.
        self.ucm = UnifiedConfigManager(self.config_path, db_conn=self.db_conn)
        self.config = self.ucm.load_config()

        # Read API settings.
        api_cfg = self.config.get("api_config", {})
        self.coinpaprika_enabled = (api_cfg.get("coinpaprika_api_enabled") == "ENABLE")
        self.binance_enabled = (api_cfg.get("binance_api_enabled") == "ENABLE")
        self.coingecko_enabled = (api_cfg.get("coingecko_api_enabled") == "ENABLE")
        self.cmc_enabled = (api_cfg.get("coinmarketcap_api_enabled") == "ENABLE")

        # Parse price configuration.
        price_cfg = self.config.get("price_config", {})
        self.assets = price_cfg.get("assets", ["BTC", "ETH", "SP500"])
        if "SP500" not in [asset.upper() for asset in self.assets]:
            self.assets.append("SP500")
        self.currency = price_cfg.get("currency", "USD")
        self.cmc_api_key = price_cfg.get("cmc_api_key")

    async def initialize_monitor(self):
        logger.info("PriceMonitor initialized with configuration.")

    async def update_prices(self, source: str = "API"):
        """
        Fetches prices from enabled APIs in parallel, averages them for each symbol,
        and stores one row per symbol. Logs start/completion events via OperationsLogger,
        including the provided source.
        """
        op_logger = OperationsLogger()
        try:

            tasks = []
            if self.coingecko_enabled:
                tasks.append(self._fetch_coingecko_prices())
            if self.cmc_enabled:
                tasks.append(self._fetch_cmc_prices())
            if self.coinpaprika_enabled:
                tasks.append(self._fetch_coinpaprika_prices())
            if self.binance_enabled:
                tasks.append(self._fetch_binance_prices())
            if "SP500" in [a.upper() for a in self.assets]:
                tasks.append(self._fetch_sp500_prices())

            if not tasks:
                logger.warning("No API sources enabled for update_prices.")
                return

            results_list = await asyncio.gather(*tasks)

            # Combine the results: e.g., { "BTC": [p1, p2, ...], ... }
            aggregated: Dict[str, List[float]] = {}
            for result_dict in results_list:
                for sym, price_val in result_dict.items():
                    aggregated.setdefault(sym.upper(), []).append(price_val)

            for sym, price_list in aggregated.items():
                if not price_list:
                    continue
                avg_price = sum(price_list) / len(price_list)
                self.data_locker.insert_or_update_price(sym, avg_price, "Averaged")

            logger.info("All price updates completed.")
            op_logger.log("Prices Updated",
                          source=source,
                          operation_type="Prices Updated",
                          file_name="price_monitor.py")
        except Exception as e:
            logger.error("Error updating prices: %s", e, exc_info=True)
            op_logger.log("Price Update Failed",
                          source=source,
                          operation_type="Price Update Failed",
                          file_name="price_monitor.py")
            raise e

    async def _fetch_coingecko_prices(self) -> Dict[str, float]:
        """
        Fetch prices from CoinGecko.
        """
        slug_map = {"BTC": "bitcoin", "ETH": "ethereum"}
        slugs = []
        for sym in self.assets:
            up_sym = sym.upper()
            if up_sym in slug_map:
                slugs.append(slug_map[up_sym])
            else:
                logger.warning(f"No slug found for {sym} in CoinGecko, skipping.")
        if not slugs:
            return {}

        logger.info("Fetching CoinGecko for assets: %s", slugs)
        cg_data = await fetch_current_coingecko(slugs, self.currency)
        results = {}
        for slug, price in cg_data.items():
            found_sym = next((s for s, slugval in slug_map.items() if slugval.lower() == slug.lower()), slug)
            results[found_sym.upper()] = price
        self.data_locker.increment_api_report_counter("CoinGecko")
        return results

    async def _fetch_coinpaprika_prices(self) -> Dict[str, float]:
        """
        Fetch prices from CoinPaprika.
        """
        logger.info("Fetching CoinPaprika for assets...")
        paprika_map = {"BTC": "btc-bitcoin", "ETH": "eth-ethereum", "SOL": "sol-solana"}
        ids = []
        for sym in self.assets:
            up_sym = sym.upper()
            if up_sym in paprika_map:
                ids.append(paprika_map[up_sym])
            else:
                logger.warning(f"No paprika ID found for {sym}, skipping.")
        if not ids:
            return {}
        data = await fetch_current_coinpaprika(ids)
        self.data_locker.increment_api_report_counter("CoinPaprika")
        return data

    async def _fetch_binance_prices(self) -> Dict[str, float]:
        """
        Fetch prices from Binance.
        """
        logger.info("Fetching Binance for assets...")
        binance_symbols = [sym.upper() + "USDT" for sym in self.assets if sym.upper() != "SP500"]
        bn_data = await fetch_current_binance(binance_symbols)
        self.data_locker.increment_api_report_counter("Binance")
        return bn_data

    async def _fetch_cmc_prices(self) -> Dict[str, float]:
        """
        Fetch prices from CoinMarketCap.
        """
        logger.info("Fetching CoinMarketCap for assets: %s", self.assets)
        cmc_data = await fetch_current_cmc(self.assets, self.currency, self.cmc_api_key)
        self.data_locker.increment_api_report_counter("CoinMarketCap")
        return cmc_data

    async def _fetch_sp500_prices(self) -> Dict[str, float]:
        """
        Fetch the current S&P500 index price using yfinance.
        """
        import yfinance as yf
        def get_sp500():
            ticker = yf.Ticker("^GSPC")
            data = ticker.history(period="1d")
            if data.empty:
                logger.warning("No data returned for S&P500 from yfinance.")
                return None
            return data['Close'].iloc[-1]
        price = await asyncio.to_thread(get_sp500)
        if price is None:
            last_entry = self.data_locker.get_latest_price("SP500")
            if last_entry and "current_price" in last_entry:
                price = float(last_entry["current_price"])
                logger.info("Reusing last known S&P500 price: %s", price)
            else:
                price = 4000.0
                logger.info("No last known S&P500 price available; using default price: %s", price)
        self.data_locker.increment_api_report_counter("SP500")
        logger.info("Fetched S&P500 price: %s", price)
        return {"SP500": price}

if __name__ == "__main__":
    async def main():
        pm = PriceMonitor()  # Uses DB_PATH and CONFIG_PATH from config_constants
        await pm.initialize_monitor()
        # Pass your source here; e.g., source="User" or "monitor"
        await pm.update_prices(source="User")
    asyncio.run(main())
