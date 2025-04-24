# price_sources/coinmarketcap_fetcher.py
import aiohttp
import logging
from typing import Dict, List, Any
import datetime

logger = logging.getLogger("CoinMarketCapFetcher")

CMC_BASE_URL = "https://pro-api.coinmarketcap.com/v1"

import aiohttp
from typing import List, Dict

async def fetch_current_cmc(
    symbols: List[str],
    convert: str,
    api_key: str
) -> Dict[str, float]:
    # Make sure our API key isn’t None
    if not api_key:
        raise ValueError("CoinMarketCap API key is missing or empty.")

    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {
        "X-CMC_PRO_API_KEY": api_key  # guaranteed string key & value
    }
    params = {
        "symbol": ",".join(symbols),
        "convert": convert or "USD"      # default to USD if convert is falsy
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            resp.raise_for_status()
            payload = await resp.json()

    results: Dict[str, float] = {}
    for sym in symbols:
        try:
            price = payload["data"][sym]["quote"][convert]["price"]
        except KeyError:
            price = 0.0
        results[sym] = price

    return results


async def fetch_historical_cmc(symbol: str,
                               start_date: str,
                               end_date: str,
                               currency: str,
                               api_key: str) -> List[Dict[str, Any]]:
    """
    Fetch daily OHLCV data from /cryptocurrency/ohlcv/historical for a single symbol 
    over [start_date, end_date]. Return a list of records, e.g.:
    [ 
      {
        "time_open": "...",
        "time_close": "...",
        "open": 123.45,
        "high": ...,
        "low": ...,
        "close": ...,
        "volume": ...
      },
      ...
    ]
    """
    url = f"{CMC_BASE_URL}/cryptocurrency/ohlcv/historical"
    headers = {
        "Accept": "application/json",
        "X-CMC_PRO_API_KEY": api_key
    }
    params = {
        "symbol": symbol.upper(),
        "time_start": start_date,  # "2022-01-01"
        "time_end": end_date,      # "2022-02-01"
        "convert": currency,
        "interval": "daily"  # or "hourly", etc. if your plan supports
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"CMC fetch_historical_cmc failed: status {resp.status}")
                    return []
                data = await resp.json()
                logger.debug(f"CMC historical response: {data}")

                if "data" not in data or "quotes" not in data["data"]:
                    logger.error(f"CMC historical response missing data.quotes.")
                    return []
                quotes_list = data["data"]["quotes"]
                results = []
                for q in quotes_list:
                    record = {
                        "time_open": q.get("time_open"),
                        "time_close": q.get("time_close"),
                    }
                    # If we only do daily, these fields exist:
                    quote_for_currency = q["quote"].get(currency.upper(), {})
                    record["open"] = quote_for_currency.get("open", 0.0)
                    record["high"] = quote_for_currency.get("high", 0.0)
                    record["low"] = quote_for_currency.get("low", 0.0)
                    record["close"] = quote_for_currency.get("close", 0.0)
                    record["volume"] = quote_for_currency.get("volume", 0.0)
                    results.append(record)
                return results
    except Exception as e:
        logger.error(f"Error fetching historical from CMC: {e}", exc_info=True)
        return []
