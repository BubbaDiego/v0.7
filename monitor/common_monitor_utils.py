#!/usr/bin/env python3
import os
import json
from datetime import datetime, timezone
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

# Point this at your existing timer_config.json
TIMER_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "config", "timer_config.json"
)

def load_timer_config() -> dict:
    """
    Load and cache timer_config. Only hits disk once per process.
    """
    if hasattr(load_timer_config, "_cache"):
        return load_timer_config._cache

    try:
        with open(TIMER_CONFIG_PATH, "r") as f:
            cfg = json.load(f)
    except (IOError, json.JSONDecodeError):
        cfg = {}
    load_timer_config._cache = cfg
    return cfg

def update_timer_config(new_cfg: dict):
    """
    Persist timer_config and refresh in‑memory cache.
    """
    with open(TIMER_CONFIG_PATH, "w") as f:
        json.dump(new_cfg, f, indent=4)
    load_timer_config._cache = new_cfg

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_endpoint(url: str, method: str = "get", **kwargs) -> requests.Response:
    """
    Unified HTTP caller with retries.
    """
    func = getattr(requests, method.lower())
    resp = func(url, timeout=30, verify=False, **kwargs)
    resp.raise_for_status()
    return resp
