#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import logging
import inspect
from typing import Dict
from datetime import datetime

from utils.json_manager import JsonManager  # Changed import
from data.data_locker import DataLocker
from prices.coingecko_fetcher import fetch_current_coingecko
from prices.coinmarketcap_fetcher import fetch_current_cmc, fetch_historical_cmc
from prices.coinpaprika_fetcher import fetch_current_coinpaprika
from prices.binance_fetcher import fetch_current_binance
from config.config_constants import DB_PATH, COM_CONFIG_PATH
from utils.unified_logger import UnifiedLogger

logger = logging.getLogger("PriceMonitorLogger")

class PriceMonitor:
    def __init__(self, db_path: str = DB_PATH, config_path: str = COM_CONFIG_PATH):
        self.db_path = db_path
        self.config_path = config_path

        # Setup DataLocker & DB connection.
        self.data_locker = DataLocker(self.db_path)
        self.db_conn = self.data_locker.get_db_connection()

        # Use JsonManager to load the configuration
        self.json_manager = JsonManager()
        self.config = self.json_manager.load(self.config_path)

        # Read API settings.
        api_cfg = self.config.get("api_config", {})
        self.coinpaprika_enabled = (api_cfg.get("coinpaprika_api_enabled") == "ENABLE")
        self.binance_enabled = (api_cfg.get("binance_api_enabled") == "ENABLE")
        self.coingecko_enabled = (api_cfg.get("coingecko_api_enabled") == "ENABLE")
        self.cmc_enabled = (api_cfg.get("coinmarketcap_api_enabled") == "ENABLE")

        # Parse price configuration.
        # Use a "price_config" section if available; otherwise, fallback to defaults.
        price_cfg = self.config.get("price_config", {
            "assets": ["BTC", "ETH", "SP500"],
            "currency": "USD",
            "cmc_api_key": self.config.get("cmc_api_key")
        })
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
        stores one row per symbol, and sets the update time for prices.
        Logs the successful update and any errors via UnifiedLogger.
        """
        u_logger = UnifiedLogger()  # Instantiate unified logger once
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

            # Combine results for each symbol.
            aggregated = {}
            for result_dict in results_list:
                for sym, price_val in result_dict.items():
                    aggregated.setdefault(sym.upper(), []).append(price_val)

            for sym, price_list in aggregated.items():
                if not price_list:
                    continue
                avg_price = sum(price_list) / len(price_list)
                self.data_locker.insert_or_update_price(sym, avg_price, "Averaged")

            # Set update time for prices.
            now = datetime.now()
            self.data_locker.set_last_update_times(prices_dt=now, prices_source=source)
            logger.info("All price updates completed at %s", now.isoformat())
            line_no = inspect.currentframe().f_lineno
            u_logger.logger.info("Prices Updated", extra={
                "source": source,
                "operation_type": "Prices Updated",
                "log_type": "operation",
                "file": "price_monitor.py"
            })
        except Exception as e:
            logger.error("Error updating prices: %s", e, exc_info=True)
            line_no = inspect.currentframe().f_lineno
            u_logger.logger.info("Price Update Failed", extra={
                "source": source,
                "operation_type": "Price Update Failed",
                "log_type": "operation",
                "file": "price_monitor.py",
                "linenum": line_no
            })
            raise e

    async def _fetch_coingecko_prices(self) -> Dict[str, float]:
        slug_map = {"BTC": "bitcoin", "ETH": "ethereum"}
        slugs = [slug_map[sym.upper()] for sym in self.assets if sym.upper() in slug_map]
        if not slugs:
            return {}
        logger.info("Fetching CoinGecko for assets: %s", slugs)
        cg_data = await fetch_current_coingecko(slugs, self.currency)
        logger.info("CoinGecko fetch successful: fetched %d entries", len(cg_data))
        results = {}
        for slug, price in cg_data.items():
            found_sym = next((s for s, slugval in slug_map.items() if slugval.lower() == slug.lower()), slug)
            results[found_sym.upper()] = price
        self.data_locker.increment_api_report_counter("CoinGecko")
        return results

    async def _fetch_coinpaprika_prices(self) -> Dict[str, float]:
        logger.info("Fetching CoinPaprika for assets...")
        paprika_map = {"BTC": "btc-bitcoin", "ETH": "eth-ethereum", "SOL": "sol-solana"}
        ids = [paprika_map[sym.upper()] for sym in self.assets if sym.upper() in paprika_map]
        if not ids:
            return {}
        data = await fetch_current_coinpaprika(ids)
        logger.info("CoinPaprika fetch successful: fetched %d entries", len(data))
        self.data_locker.increment_api_report_counter("CoinPaprika")
        return data

    async def _fetch_binance_prices(self) -> Dict[str, float]:
        logger.info("Fetching Binance for assets...")
        binance_symbols = [sym.upper() + "USDT" for sym in self.assets if sym.upper() != "SP500"]
        bn_data = await fetch_current_binance(binance_symbols)
        logger.info("Binance fetch successful: fetched %d entries", len(bn_data))
        self.data_locker.increment_api_report_counter("Binance")
        return bn_data

    async def _fetch_cmc_prices(self) -> Dict[str, float]:
        logger.info("Fetching CoinMarketCap for assets: %s", self.assets)
        cmc_data = await fetch_current_cmc(self.assets, self.currency, self.cmc_api_key)
        logger.info("CoinMarketCap fetch successful: fetched %d entries", len(cmc_data))
        self.data_locker.increment_api_report_counter("CoinMarketCap")
        return cmc_data

    async def _fetch_sp500_prices(self) -> Dict[str, float]:
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
        pm = PriceMonitor()  # Uses DB_PATH and COM_CONFIG_PATH from config_constants
        await pm.initialize_monitor()
        await pm.update_prices(source="User")
    asyncio.run(main())
