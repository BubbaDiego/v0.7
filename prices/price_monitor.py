#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import logging
import json
import inspect
from typing import Dict, List
from datetime import datetime

from utils.json_manager import JsonManager, JsonType
from data.data_locker import DataLocker
from prices.coingecko_fetcher import fetch_current_coingecko
from prices.coinmarketcap_fetcher import fetch_current_cmc  # , fetch_historical_cmc
from prices.coinpaprika_fetcher import fetch_current_coinpaprika
from prices.binance_fetcher import fetch_current_binance
from config.config_constants import DB_PATH, COM_CONFIG_PATH, LOG_DIR, BTC_LOGO_IMAGE, ETH_LOGO_IMAGE, SOL_LOGO_IMAGE, \
    LOG_DATE_FORMAT
from utils.unified_logger import UnifiedLogger
import aiohttp

logger = logging.getLogger("PriceMonitorLogger")
logger.setLevel(logging.DEBUG)


class PriceMonitor:
    def __init__(self, db_path: str = DB_PATH, config_path: str = COM_CONFIG_PATH):
        self.db_path = db_path
        self.config_path = config_path

        # Setup DataLocker & DB connection.
        self.data_locker = DataLocker(self.db_path)
        self.db_conn = self.data_locker.get_db_connection()

        # Use JsonManager to load the configuration.
        self.json_manager = JsonManager()
        self.config = self.json_manager.load(self.config_path, json_type=JsonType.COMM_CONFIG)

        # Read API settings.
        api_cfg = self.config.get("api_config", {})
        self.coinpaprika_enabled = (api_cfg.get("coinpaprika_api_enabled") == "ENABLE")
        self.binance_enabled = (api_cfg.get("binance_api_enabled") == "ENABLE")
        self.coingecko_enabled = (api_cfg.get("coingecko_api_enabled") == "ENABLE")
        self.cmc_enabled = (api_cfg.get("coinmarketcap_api_enabled") == "ENABLE")
        # New sources:
        self.cryptocompare_enabled = (api_cfg.get("cryptocompare_api_enabled") == "ENABLE")
        self.nomics_enabled = (api_cfg.get("nomics_api_enabled") == "ENABLE")
        self.nomics_api_key = api_cfg.get("nomics_api_key")  # may be None if not provided

        # Parse price configuration.
        price_cfg = self.config.get("price_config", {
            "assets": ["BTC", "ETH", "SP500", "SOL"],
            "currency": "USD",
            "cmc_api_key": self.config.get("cmc_api_key")
        })
        self.assets = price_cfg.get("assets", ["BTC", "ETH", "SP500", "SOL"])
        # Ensure SP500 is included
        if "SP500" not in [asset.upper() for asset in self.assets]:
            self.assets.append("SP500")
        self.currency = price_cfg.get("currency", "USD")
        self.cmc_api_key = price_cfg.get("cmc_api_key")

        # Prepare a unified logger for cycle updates.
        self.u_logger = UnifiedLogger()

    async def initialize_monitor(self):
        logger.info("PriceMonitor initialized with configuration.")

    async def update_prices(self, source: str = "API"):
        """
        Fetch prices from enabled APIs in parallel, average them per symbol,
        update the database, log source results, and generate an HTML summary.
        """
        cycle_log_lines = []  # We'll collect log lines here to write to file later.
        source_tasks = []
        # Build a list of (source_name, task) pairs.
        if self.coingecko_enabled:
            logger.debug("Adding CoinGecko fetch task for assets: %s", self.assets)
            source_tasks.append(("CoinGecko", self._fetch_coingecko_prices()))
        if self.cmc_enabled:
            logger.debug("Adding CoinMarketCap fetch task for assets: %s", self.assets)
            source_tasks.append(("CoinMarketCap", self._fetch_cmc_prices()))
        if self.coinpaprika_enabled:
            logger.debug("Adding CoinPaprika fetch task for assets: %s", self.assets)
            source_tasks.append(("CoinPaprika", self._fetch_coinpaprika_prices()))
        if self.binance_enabled:
            logger.debug("Adding Binance fetch task for assets: %s", self.assets)
            source_tasks.append(("Binance", self._fetch_binance_prices()))
        if "SP500" in [a.upper() for a in self.assets]:
            logger.debug("Adding S&P500 fetch task.")
            source_tasks.append(("SP500", self._fetch_sp500_prices()))
        # New sources:
        if self.cryptocompare_enabled:
            logger.debug("Adding CryptoCompare fetch task for assets: %s", self.assets)
            source_tasks.append(("CryptoCompare", self._fetch_cryptocompare_prices()))
        if self.nomics_enabled:
            logger.debug("Adding Nomics fetch task for assets: %s", self.assets)
            source_tasks.append(("Nomics", self._fetch_nomics_prices()))

        if not source_tasks:
            logger.warning("No API sources enabled for update_prices.")
            return

        # Run tasks in parallel.
        tasks = [task for (_, task) in source_tasks]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        # Map each source name to its result (or error)
        source_results = {}
        for idx, (source_name, _) in enumerate(source_tasks):
            result = results_list[idx]
            if isinstance(result, Exception):
                logger.error("Source %s failed with error: %s", source_name, result)
                cycle_log_lines.append(f"{datetime.now().isoformat()} - {source_name} FAILED: {result}")
            else:
                source_results[source_name] = result
                cycle_log_lines.append(f"{datetime.now().isoformat()} - {source_name} reported: {result}")

        # Aggregate results: For each asset, average the reported prices from all sources that returned a price.
        aggregated: Dict[str, List[float]] = {}
        for src, prices in source_results.items():
            for sym, price_val in prices.items():
                aggregated.setdefault(sym.upper(), []).append(price_val)

        avg_prices = {}
        for sym in self.assets:
            sym = sym.upper()
            if sym in aggregated and aggregated[sym]:
                avg = sum(aggregated[sym]) / len(aggregated[sym])
                avg_prices[sym] = avg
                cycle_log_lines.append(f"{datetime.now().isoformat()} - {sym} average price: {avg:.2f}")
                logger.debug("Updating %s with average price: %s", sym, avg)
                self.data_locker.insert_or_update_price(sym, avg, "Averaged")
            else:
                cycle_log_lines.append(
                    f"{datetime.now().isoformat()} - No new price data for {sym}; retaining last known price.")
                logger.warning(f"No new price data for {sym}. Retaining last known price from DB.")

        now = datetime.now()
        self.data_locker.set_last_update_times(prices_dt=now, prices_source=source)
        logger.info("All price updates completed at %s", now.isoformat())
        self.u_logger.log_cyclone(
            operation_type="Market Updates",
            primary_text="Prices updated successfully",
            source="Cyclone",
            file="price_monitor.py"
        )

        # Write cycle log to file.
        log_file_path = os.path.join(str(LOG_DIR), "price_cycle_log.txt")
        with open(log_file_path, "a", encoding="utf-8") as log_file:
            log_file.write("\n".join(cycle_log_lines) + "\n")

        # Generate HTML summary report.
        self.generate_update_summary_html(source_results, avg_prices, now)

    def generate_update_summary_html(self, source_results: Dict[str, Dict[str, float]], avg_prices: Dict[str, float],
                                     update_time: datetime):
        """
        Generate a pretty HTML summary of the update cycle including:
         - Time and date of update.
         - For each asset: display asset image (from web), each source’s price and the average price.
         - Write output to LOG_DIR/price_cycle_update.html.
        """
        # Define asset image URLs (using publicly available logos).
        asset_images = {
            "BTC": "https://cryptologos.cc/logos/bitcoin-btc-logo.png?v=023",
            "ETH": "https://cryptologos.cc/logos/ethereum-eth-logo.png?v=023",
            "SOL": "https://cryptologos.cc/logos/solana-sol-logo.png?v=023",
            "SP500": "https://upload.wikimedia.org/wikipedia/commons/2/2f/S%26P_500_logo.svg"
        }
        html_lines = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "  <meta charset='UTF-8'>",
            "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            "  <title>Price Cycle Update</title>",
            "  <style>",
            "    body { font-family: Arial, sans-serif; margin: 20px; }",
            "    table { width: 100%; border-collapse: collapse; margin-top: 20px; }",
            "    th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }",
            "    th { background-color: #f2f2f2; }",
            "    .asset-img { width: 40px; height: 40px; }",
            "    h1 { color: #007bff; }",
            "  </style>",
            "</head>",
            "<body>",
            f"  <h1>Price Cycle Update Summary</h1>",
            f"  <p><strong>Update Time:</strong> {update_time.strftime('%Y-%m-%d %I:%M:%S %p')}</p>",
            "  <h2>Source Prices</h2>",
            "  <table>",
            "    <tr><th>Source</th><th>Prices</th></tr>"
        ]
        for source, prices in source_results.items():
            price_str = "<br>".join([f"{sym}: ${price:.2f}" for sym, price in prices.items()])
            html_lines.append(f"    <tr><td>{source}</td><td>{price_str}</td></tr>")
        html_lines.extend([
            "  </table>",
            "  <h2>Average Prices</h2>",
            "  <table>",
            "    <tr><th>Asset</th><th>Image</th><th>Average Price</th></tr>"
        ])
        for asset, avg in avg_prices.items():
            img_url = asset_images.get(asset, "")
            html_lines.append(
                f"    <tr><td>{asset}</td><td><img class='asset-img' src='{img_url}' alt='{asset}'></td><td>${avg:.2f}</td></tr>"
            )
        html_lines.extend([
            "  </table>",
            "  <p>Cycle update completed successfully.</p>",
            "</body>",
            "</html>"
        ])
        output_file = os.path.join(str(LOG_DIR), "price_cycle_update.html")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(html_lines))
        logger.info("HTML summary generated at %s", output_file)

    # New fetch functions for additional sources
    async def _fetch_cryptocompare_prices(self) -> Dict[str, float]:
        """
        Fetch prices from CryptoCompare.
        Example endpoint: https://min-api.cryptocompare.com/data/pricemulti?fsyms=BTC,ETH,SOL&tsyms=USD
        """
        base_url = "https://min-api.cryptocompare.com/data/pricemulti"
        symbols = ",".join([sym.upper() for sym in self.assets if sym.upper() in ["BTC", "ETH", "SOL"]])
        params = {"fsyms": symbols, "tsyms": self.currency.upper()}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    data = await response.json()
                    # data is expected in format: {"BTC": {"USD": price}, ...}
                    result = {}
                    for sym, vals in data.items():
                        price = vals.get(self.currency.upper())
                        if price is not None:
                            result[sym] = float(price)
                    return result
        except Exception as e:
            logger.error("CryptoCompare fetch failed: %s", e, exc_info=True)
            return {}

    async def _fetch_nomics_prices(self) -> Dict[str, float]:
        """
        Fetch prices from Nomics.
        Example endpoint: https://api.nomics.com/v1/currencies/ticker?key=YOUR_KEY&ids=BTC,ETH,SOL&convert=USD
        For demo purposes, we use 'demo' as key if none provided.
        """
        base_url = "https://api.nomics.com/v1/currencies/ticker"
        key = self.nomics_api_key if self.nomics_api_key else "demo"
        ids = ",".join([sym.upper() for sym in self.assets if sym.upper() in ["BTC", "ETH", "SOL"]])
        params = {"key": key, "ids": ids, "convert": self.currency.upper(), "per-page": "100", "page": "1"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    data = await response.json()
                    # data is expected as a list of dicts.
                    result = {}
                    for entry in data:
                        sym = entry.get("id")
                        price = entry.get("price")
                        if sym and price:
                            result[sym] = float(price)
                    return result
        except Exception as e:
            logger.error("Nomics fetch failed: %s", e, exc_info=True)
            return {}

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

        logger.info("Fetched S&P500 price: %s", price)
        return {"SP500": price}

    async def _fetch_coingecko_prices(self) -> Dict[str, float]:
        slug_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
        slugs = [slug_map[sym.upper()] for sym in self.assets if sym.upper() in slug_map]
        if not slugs:
            logger.debug("No CoinGecko slugs found for assets: %s", self.assets)
            return {}
        logger.info("Fetching CoinGecko for assets: %s", slugs)
        cg_data = await fetch_current_coingecko(slugs, self.currency)
        logger.info("CoinGecko fetch successful: fetched %d entries", len(cg_data))
        results = {}
        for slug, price in cg_data.items():
            found_sym = next((s for s, slugval in slug_map.items() if slugval.lower() == slug.lower()), slug)
            results[found_sym.upper()] = price
        return results

    async def _fetch_coinpaprika_prices(self) -> Dict[str, float]:
        logger.info("Fetching CoinPaprika for assets...")
        paprika_map = {"BTC": "btc-bitcoin", "ETH": "eth-ethereum", "SOL": "sol-solana"}
        ids = [paprika_map[sym.upper()] for sym in self.assets if sym.upper() in paprika_map]
        if not ids:
            logger.debug("No CoinPaprika IDs found for assets: %s", self.assets)
            return {}
        data = await fetch_current_coinpaprika(ids)
        logger.info("CoinPaprika fetch successful: fetched %d entries", len(data))
        return data

    async def _fetch_binance_prices(self) -> Dict[str, float]:
        logger.info("Fetching Binance for assets...")
        binance_symbols = [sym.upper() + "USDT" for sym in self.assets if sym.upper() != "SP500"]
        bn_data = await fetch_current_binance(binance_symbols)
        logger.info("Binance fetch successful: fetched %d entries", len(bn_data))
        return bn_data

    async def _fetch_cmc_prices(self) -> Dict[str, float]:
        logger.info("Fetching CoinMarketCap for assets: %s", self.assets)
        cmc_data = await fetch_current_cmc(self.assets, self.currency, self.cmc_api_key)
        logger.info("CoinMarketCap fetch successful: fetched %d entries", len(cmc_data))
        return cmc_data


if __name__ == "__main__":
    async def main():
        pm = PriceMonitor()  # Uses DB_PATH and COM_CONFIG_PATH from config_constants
        await pm.initialize_monitor()
        await pm.update_prices(source="User")


    asyncio.run(main())
