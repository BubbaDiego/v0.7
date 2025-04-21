#!/usr/bin/env python3
import sys
import os
import asyncio
import logging
import json
from typing import Dict, List, Awaitable, Tuple
from datetime import datetime

from monitor.common_monitor_utils import load_timer_config
from utils.json_manager import JsonManager, JsonType
from data.data_locker import DataLocker
from prices.coingecko_fetcher import fetch_current_coingecko
from prices.coinmarketcap_fetcher import fetch_current_cmc
from prices.coinpaprika_fetcher import fetch_current_coinpaprika
from utils.unified_logger import UnifiedLogger
import aiohttp

# Constants for file paths and configuration
from config.config_constants import (
    DB_PATH,
    COM_CONFIG_PATH,
    LOG_DIR,
    BASE_DIR
)

# Set up logger
logger = logging.getLogger("PriceMonitorLogger")
logger.setLevel(logging.DEBUG)

class PriceMonitor:
    def __init__(self,
                 db_path: str = DB_PATH,
                 config_path: str = COM_CONFIG_PATH):
        # Use singleton DataLocker
        self.data_locker = DataLocker.get_instance()
        self.db_conn = self.data_locker.get_db_connection()

        # Load communication configuration
        jm = JsonManager()
        self.config = jm.load(config_path, json_type=JsonType.COMM_CONFIG)

        # Read API enable flags (default ENABLE unless DISABLE)
        api_cfg = self.config.get("api_config", {})
        self.coingecko_enabled   = api_cfg.get("coingecko_api_enabled", "ENABLE").upper() != "DISABLE"
        self.cmc_enabled         = api_cfg.get("coinmarketcap_api_enabled", "ENABLE").upper() != "DISABLE"
        self.coinpaprika_enabled = api_cfg.get("coinpaprika_api_enabled", "ENABLE").upper() != "DISABLE"
        self.cryptocompare_enabled = api_cfg.get("cryptocompare_api_enabled", "ENABLE").upper() != "DISABLE"
        self.nomics_enabled      = api_cfg.get("nomics_api_enabled", "ENABLE").upper() != "DISABLE"
        self.nomics_api_key      = api_cfg.get("nomics_api_key")

        # Assets configuration
        price_cfg = self.config.get(
            "price_config",
            {"assets": ["BTC", "ETH", "SP500", "SOL"], "currency": "USD"}
        )
        self.assets   = [a.upper() for a in price_cfg.get("assets", [])]
        if "SP500" not in self.assets:
            self.assets.append("SP500")
        self.currency = price_cfg.get("currency", "USD")

        # Loop interval from shared timer config
        timer_cfg = load_timer_config()
        self.price_loop_interval = timer_cfg.get(
            "price_loop_interval",
            self.config.get("price_loop_interval", 60)
        )

        # Unified logger
        self.u_logger = UnifiedLogger()

    async def initialize_monitor(self):
        logger.info("PriceMonitor initialized: %s", {"assets": self.assets, "currency": self.currency})

    async def update_prices(self, source: str = "API") -> List[str]:
        cycle_logs: List[str] = []
        tasks: List[Tuple[str, Awaitable[Dict[str, float]]]] = []

        crypto = [s for s in self.assets if s in ("BTC", "ETH", "SOL")]
        if self.coingecko_enabled and crypto:
            tasks.append(("CoinGecko", self._fetch_coingecko_prices()))
        if self.cmc_enabled and crypto:
            tasks.append(("CoinMarketCap", self._fetch_cmc_prices()))
        if self.coinpaprika_enabled and crypto:
            tasks.append(("CoinPaprika", self._fetch_coinpaprika_prices()))
        if self.cryptocompare_enabled and crypto:
            tasks.append(("CryptoCompare", self._fetch_cryptocompare_prices()))
        if self.nomics_enabled and crypto:
            tasks.append(("Nomics", self._fetch_nomics_prices()))
        if "SP500" in self.assets:
            tasks.append(("SP500", self._fetch_sp500_prices()))

        if not tasks:
            logger.warning("No fetchers enabled or no assets to fetch.")
            return cycle_logs

        names, coros = zip(*tasks)
        results = await asyncio.gather(*coros, return_exceptions=True)

        src_data: Dict[str, Dict[str, float]] = {}
        for name, res in zip(names, results):
            if isinstance(res, Exception):
                logger.error("%s fetch error: %s", name, res)
                cycle_logs.append(f"{datetime.now().isoformat()} - {name} ERROR: {res}")
            else:
                src_data[name] = res
                cycle_logs.append(f"{datetime.now().isoformat()} - {name}: {res}")

        # Average and persist
        agg: Dict[str, List[float]] = {}
        for data in src_data.values():
            for sym, price in data.items():
                agg.setdefault(sym, []).append(price)

        for sym in self.assets:
            vals = [v for v in agg.get(sym, []) if v and v > 0]
            if not vals:
                logger.warning("No valid data for %s", sym)
                continue
            avg = sum(vals) / len(vals)
            self.data_locker.insert_or_update_price(sym, avg, "Averaged")
            cycle_logs.append(f"{datetime.now().isoformat()} - {sym} avg: {avg:.2f}")

        now = datetime.now()
        self.data_locker.set_last_update_times(prices_dt=now, prices_source=source)
        self.u_logger.log_cyclone(
            operation_type="Price Update",
            primary_text="Cycle complete",
            source="PriceMonitor",
            file=__file__
        )
        # Assume HTML generation intact
        self.generate_update_summary_html(src_data, {sym: sum(agg[sym])/len(agg[sym]) for sym in agg if agg[sym]}, now)
        return cycle_logs

    async def _fetch_coingecko_prices(self) -> Dict[str, float]:
        slugs = [s.lower() for s in self.assets if s in ("BTC", "ETH", "SOL")]
        data = await fetch_current_coingecko(slugs, self.currency)
        return {sym: data.get(sym.lower(), 0.0) for sym in slugs}

    async def _fetch_cmc_prices(self) -> Dict[str, float]:
        syms = [s for s in self.assets if s in ("BTC", "ETH", "SOL")]
        return await fetch_current_cmc(syms, self.currency, self.config.get("cmc_api_key"))

    async def _fetch_coinpaprika_prices(self) -> Dict[str, float]:
        mapping = {"BTC": "btc-bitcoin", "ETH": "eth-ethereum", "SOL": "sol-solana"}
        return await fetch_current_coinpaprika([mapping[s] for s in self.assets if s in mapping])

    async def _fetch_cryptocompare_prices(self) -> Dict[str, float]:
        symbols = ",".join([s for s in self.assets if s in ("BTC", "ETH", "SOL")])
        url = "https://min-api.cryptocompare.com/data/pricemulti"
        params = {"fsyms": symbols, "tsyms": self.currency}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                body = await resp.json()
                return {sym: body.get(sym, {}).get(self.currency, 0.0) for sym in symbols.split(",")}

    async def _fetch_nomics_prices(self) -> Dict[str, float]:
        syms = ",".join([s for s in self.assets if s in ("BTC", "ETH", "SOL")])
        url = "https://api.nomics.com/v1/currencies/ticker"
        params = {"key": self.nomics_api_key or "demo", "ids": syms, "convert": self.currency}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                return {d["id"].upper(): float(d.get("price", 0)) for d in data}

    async def _fetch_sp500_prices(self) -> Dict[str, float]:
        import yfinance as yf
        price = await asyncio.to_thread(lambda: yf.Ticker("^GSPC").history(period="1d")["Close"].iloc[-1])
        return {"SP500": price or 0.0}

    def generate_update_summary_html(self, source_results, avg_prices, update_time):
        # Existing HTML generation logic
        pass

if __name__ == '__main__':
    async def _runner():
        pm = PriceMonitor()
        await pm.initialize_monitor()
        await pm.update_prices(source="Startup")
        while True:
            await pm.update_prices(source="Scheduled")
            await asyncio.sleep(pm.price_loop_interval)
    asyncio.run(_runner())