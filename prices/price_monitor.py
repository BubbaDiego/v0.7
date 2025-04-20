#!/usr/bin/env python3
import sys
import os
import asyncio
import logging
import json
from typing import Dict, List, Awaitable, Tuple
from datetime import datetime, timezone

from utils.json_manager import JsonManager, JsonType
from data.data_locker import DataLocker
from prices.coingecko_fetcher import fetch_current_coingecko
from prices.coinmarketcap_fetcher import fetch_current_cmc
from prices.coinpaprika_fetcher import fetch_current_coinpaprika
from prices.binance_fetcher import fetch_current_binance
from utils.unified_logger import UnifiedLogger
import aiohttp

# Constants for file paths and configuration
from config.config_constants import (
    DB_PATH,
    COM_CONFIG_PATH,
    LOG_DIR,
    BASE_DIR
)

# Path for timer configuration
TIMER_CONFIG_PATH = os.path.join(BASE_DIR, "config", "timer_config.json")

logger = logging.getLogger("PriceMonitorLogger")
logger.setLevel(logging.DEBUG)


def load_timer_config() -> dict:
    try:
        with open(TIMER_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Error loading timer config: %s", e)
        return {}


def update_timer_config(new_config: dict):
    try:
        with open(TIMER_CONFIG_PATH, "w") as f:
            json.dump(new_config, f, indent=4)
    except Exception as e:
        logger.error("Error updating timer config: %s", e)


class PriceMonitor:
    def __init__(self,
                 db_path: str = DB_PATH,
                 config_path: str = COM_CONFIG_PATH):
        # Database setup
        self.data_locker = DataLocker(db_path)
        self.db_conn = self.data_locker.get_db_connection()

        # Load communication configuration
        jm = JsonManager()
        self.config = jm.load(config_path, json_type=JsonType.COMM_CONFIG)

        # Read API enable flags (default ENABLE unless DISABLE)
        api_cfg = self.config.get("api_config", {})
        self.coingecko_enabled     = api_cfg.get("coingecko_api_enabled", "ENABLE").upper() != "DISABLE"
        self.cmc_enabled           = api_cfg.get("coinmarketcap_api_enabled", "ENABLE").upper() != "DISABLE"
        self.coinpaprika_enabled   = api_cfg.get("coinpaprika_api_enabled", "ENABLE").upper() != "DISABLE"
        self.binance_enabled       = api_cfg.get("binance_api_enabled", "ENABLE").upper() != "DISABLE"
        self.cryptocompare_enabled = api_cfg.get("cryptocompare_api_enabled", "ENABLE").upper() != "DISABLE"
        self.nomics_enabled        = api_cfg.get("nomics_api_enabled", "ENABLE").upper() != "DISABLE"
        self.nomics_api_key        = api_cfg.get("nomics_api_key")

        # Price configuration
        price_cfg = self.config.get(
            "price_config",
            {"assets": ["BTC", "ETH", "SP500", "SOL"], "currency": "USD", "cmc_api_key": None}
        )
        self.assets       = [a.upper() for a in price_cfg.get("assets", [])]
        if "SP500" not in self.assets:
            self.assets.append("SP500")
        self.currency     = price_cfg.get("currency", "USD")
        self.cmc_api_key  = price_cfg.get("cmc_api_key")

        # Loop interval
        self.price_loop_interval = self.config.get("price_loop_interval", 60)

        # Unified cycle logger
        self.u_logger = UnifiedLogger()

    async def initialize_monitor(self):
        logger.info("PriceMonitor initialized with config: %s", {"assets": self.assets, "currency": self.currency})

    async def update_prices(self, source: str = "API") -> List[str]:
        """
        Fetch enabled source prices concurrently, average, persist, and summarize.
        Returns log lines for this cycle.
        """
        cycle_logs: List[str] = []
        tasks: List[Tuple[str, Awaitable[Dict[str, float]]]] = []

        # Crypto assets filter
        crypto = [s for s in self.assets if s in ("BTC", "ETH", "SOL")]

        if self.coingecko_enabled and crypto:
            logger.debug("Adding CoinGecko fetch for %s", crypto)
            tasks.append(("CoinGecko", self._fetch_coingecko_prices()))
        if self.cmc_enabled and crypto:
            logger.debug("Adding CoinMarketCap fetch for %s", crypto)
            tasks.append(("CoinMarketCap", self._fetch_cmc_prices()))
        if self.coinpaprika_enabled and crypto:
            logger.debug("Adding CoinPaprika fetch for %s", crypto)
            tasks.append(("CoinPaprika", self._fetch_coinpaprika_prices()))
        if self.binance_enabled and crypto:
            logger.debug("Adding Binance fetch for %s", crypto)
            tasks.append(("Binance", self._fetch_binance_prices()))
        if self.cryptocompare_enabled and crypto:
            logger.debug("Adding CryptoCompare fetch for %s", crypto)
            tasks.append(("CryptoCompare", self._fetch_cryptocompare_prices()))
        if self.nomics_enabled and crypto:
            logger.debug("Adding Nomics fetch for %s", crypto)
            tasks.append(("Nomics", self._fetch_nomics_prices()))
        if "SP500" in self.assets:
            logger.debug("Adding S&P500 fetch")
            tasks.append(("SP500", self._fetch_sp500_prices()))

        if not tasks:
            logger.warning("No fetch tasks scheduled; check API flags and asset list.")
            return cycle_logs

        # Execute all fetchers
        names, coros = zip(*tasks)
        results = await asyncio.gather(*coros, return_exceptions=True)

        # Collate source results
        src_data: Dict[str, Dict[str, float]] = {}
        for name, res in zip(names, results):
            if isinstance(res, Exception):
                logger.error("%s fetch error: %s", name, res)
                cycle_logs.append(f"{datetime.now().isoformat()} - {name} ERROR: {res}")
            else:
                src_data[name] = res
                cycle_logs.append(f"{datetime.now().isoformat()} - {name}: {res}")

        # Compute averages and persist
        agg: Dict[str, List[float]] = {}
        for data in src_data.values():
            for sym, price in data.items():
                agg.setdefault(sym, []).append(price)

        averages: Dict[str, float] = {}
        for sym in self.assets:
            vals = agg.get(sym, [])
            # Filter out missing or zero prices
            valid_vals = [v for v in vals if v and v > 0]
            if valid_vals:
                avg = sum(valid_vals) / len(valid_vals)
                averages[sym] = avg
                # Persist only true averages
                self.data_locker.insert_or_update_price(sym, avg, "Averaged")
                cycle_logs.append(f"{datetime.now().isoformat()} - {sym} avg: {avg:.2f}")
            else:
                logger.warning("No valid data for %s; skipping update.", sym)
                cycle_logs.append(f"{datetime.now().isoformat()} - {sym} no valid data")

        # Finalize logging and summary
        now = datetime.now()
        self.data_locker.set_last_update_times(prices_dt=now, prices_source=source)
        self.u_logger.log_cyclone(
            operation_type="Price Update",
            primary_text="Cycle complete",
            source="PriceMonitor",
            file=__file__
        )
        self.generate_update_summary_html(src_data, averages, now)
        return cycle_logs  # Updated to average only valid prices

    async def _fetch_cmc_prices(self) -> Dict[str, float]:
        syms = [s for s in self.assets if s in ("BTC", "ETH", "SOL")]
        if not syms:
            return {}
        try:
            return await fetch_current_cmc(syms, self.currency, self.cmc_api_key)
        except Exception as e:
            logger.error("CMC fetch failed: %s", e)
            return {}

    async def _fetch_binance_prices(self) -> Dict[str,	float]:
        syms = [s + "USDT" for s in self.assets if s in ("BTC", "ETH", "SOL")]
        if not syms:
            return {}
        try:
            return await fetch_current_binance(syms)
        except Exception as e:
            logger.warning("Binance fetch failed: %s", e)
            return {}

    async def _fetch_coinpaprika_prices(self) -> Dict[str, float]:
        mapping = {"BTC": "btc-bitcoin", "ETH": "eth-ethereum", "SOL": "sol-solana"}
        ids = [mapping[s] for s in self.assets if s in mapping]
        if not ids:
            return {}
        try:
            return await fetch_current_coinpaprika(ids)
        except Exception as e:
            logger.error("Paprika fetch failed: %s", e)
            return {}

    async def _fetch_coingecko_prices(self) -> Dict[str, float]:
        slug_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
        slugs = [slug_map[s] for s in self.assets if s in slug_map]
        if not slugs:
            return {}
        try:
            data = await fetch_current_coingecko(slugs, self.currency)
            return {sym: data.get(slug, 0.0) for sym, slug in slug_map.items()}
        except Exception as e:
            logger.error("CoinGecko fetch failed: %s", e)
            return {}

    async def _fetch_cryptocompare_prices(self) -> Dict[str, float]:
        symbols = ",".join([s for s in self.assets if s in ("BTC", "ETH", "SOL")])
        if not symbols:
            return {}
        url = "https://min-api.cryptocompare.com/data/pricemulti"
        params = {"fsyms": symbols, "tsyms": self.currency}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    body = await resp.json()
                    return {sym: float(vals[self.currency]) for sym, vals in body.items() if self.currency in vals}
        except Exception as e:
            logger.error("CryptoCompare fetch failed: %s", e)
            return {}

    async def _fetch_nomics_prices(self) -> Dict[str, float]:
        syms = ",".join([s for s in self.assets if s in ("BTC", "ETH", "SOL")])
        if not syms:
            return {}
        url = "https://api.nomics.com/v1/currencies/ticker"
        params = {"key": self.nomics_api_key or "demo", "ids": syms, "convert": self.currency, "per-page": "100", "page": "1"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    return {e["id"].upper(): float(e["price"]) for e in data if e.get("id") and e.get("price")}  # type: ignore
        except Exception as e:
            logger.error("Nomics fetch failed: %s", e)
            return {}

    async def _fetch_sp500_prices(self) -> Dict[str,	float]:
        """
        Fetch S&P 500 price via yfinance. Returns a dict.
        """
        import yfinance as yf
        def get_price():
            t = yf.Ticker("^GSPC")
            d = t.history(period="1d")
            return d['Close'].iloc[-1] if not d.empty else None
        price = await asyncio.to_thread(get_price)
        if price is None:
            last = self.data_locker.get_latest_price("SP500")
            price = float(last.get("current_price", 4000.0))
        return {"SP500": price}

    def generate_update_summary_html(
        self,
        source_results: Dict[str, Dict[str, float]],
        avg_prices: Dict[str, float],
        update_time: datetime
    ):
        """
        Build and write an HTML summary including timestamps for each source entry and the update time.
        """
        asset_imgs = {
            "BTC": "https://cryptologos.cc/logos/bitcoin-btc-logo.png",
            "ETH": "https://cryptologos.cc/logos/ethereum-eth-logo.png",
            "SOL": "https://cryptologos.cc/logos/solana-sol-logo.png",
            "SP500": "https://upload.wikimedia.org/wikipedia/commons/2/2f/S%26P_500_logo.svg"
        }
        out = os.path.join(LOG_DIR, "price_cycle_update.html")
        lines = [
            "<html><head><meta charset='UTF-8'><title>Price Update</title></head><body>",
            f"<h1>Updated: {update_time:%Y-%m-%d %H:%M:%S}</h1>",
            "<h2>Source Data</h2><ul>"
        ]
        # Include a timestamp on each source entry
        for src, data in source_results.items():
            ts = update_time.strftime("%Y-%m-%d %H:%M:%S")
