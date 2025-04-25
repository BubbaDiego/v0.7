#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

# Base directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_TIMER_CONFIG = os.path.join(BASE_DIR, "config", "timer_config.json")
DEFAULT_LEDGER_DIR = os.path.join(BASE_DIR, "monitor")

# Module logger
logger = logging.getLogger(__name__)


def load_timer_config(path=None):
    """
    Convenience: load the entire timer config JSON as a dict.
    """
    return TimerConfig(path).load()

def update_timer_config(config_data, path=None):
    """
    Convenience: overwrite timer config with the given dict.
    """
    tc = TimerConfig(path)
    tc._cache = config_data
    tc.save()

class TimerConfig:
    """
    Wraps loading and saving of timer configuration JSON.
    Uses atomic writes to avoid partial files.
    """
    def __init__(self, path=None):
        self.path = path or DEFAULT_TIMER_CONFIG
        self._cache = None

    def load(self) -> dict:
        if self._cache is None:
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
            except Exception as e:
                logger.error(f"Error loading timer config: {e}")
                self._cache = {}
        return self._cache

    def save(self) -> None:
        tmp = self.path + '.tmp'
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2)
            os.replace(tmp, self.path)
            # Reset cache so subsequent loads reflect the latest
            self._cache = None
        except Exception as e:
            logger.error(f"Error saving timer config: {e}")

    def get(self, key, default=None):
        return self.load().get(key, default)

    def set(self, key, value):
        cfg = self.load()
        cfg[key] = value
        self.save()

class LedgerWriter:
    """
    Centralized ledger writer. Appends JSON entries to files.
    Ensures the ledger directory exists before writing.
    """
    def __init__(self, ledger_dir=None):
        self.ledger_dir = ledger_dir or DEFAULT_LEDGER_DIR
        os.makedirs(self.ledger_dir, exist_ok=True)

    def write(self, filename: str, entry: dict) -> None:
        path = os.path.join(self.ledger_dir, filename)
        try:
            with open(path, 'a', encoding='utf-8') as f:
                json.dump(entry, f)
                f.write("\n")
        except Exception as e:
            logger.error(f"Error writing to ledger {path}: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def call_endpoint(url: str, method: str = "get", verify: bool = True, **kwargs) -> dict:
    """
    HTTP request with retry/backoff. Returns parsed JSON.
    Verifies SSL by default; configurable via `verify`.
    """
    func = getattr(requests, method.lower())
    resp = func(url, timeout=30, verify=verify, **kwargs)
    resp.raise_for_status()
    return resp.json()

class BaseMonitor:
    """
    Abstract base class for monitors. Handles heartbeat, timers, and ledgers.
    """
    def __init__(self,
                 name: str,
                 timer_config_path: str = None,
                 ledger_filename: str = None):
        self.name = name
        # Per-monitor logger
        self.logger = logging.getLogger(self.name)
        # Timer config wrapper
        self.timer = TimerConfig(timer_config_path)
        # Ledger writer
        self.ledger_writer = LedgerWriter()
        self.ledger_file = ledger_filename or f"{name}_ledger.json"

    def write_heartbeat(self, status: str = "Success", metadata: dict = None) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.name,
            "operation": "heartbeat",
            "status": status,
            "metadata": metadata or {}
        }
        self.ledger_writer.write(self.ledger_file, entry)

    def run_cycle(self) -> None:
        """Executes one work cycle: do work, write heartbeat, update timer config."""
        try:
            meta = self._do_work()
            self.write_heartbeat(status="Success", metadata=meta)
        except Exception as e:
            self.write_heartbeat(status="Error", metadata={"error": str(e)})
            raise
        # record run time
        self.timer.set(f"{self.name}_last_run",
                       datetime.now(timezone.utc).isoformat())

    def _do_work(self) -> dict:
        """Override in subclasses with actual work. Return metadata dict."""
        raise NotImplementedError("_do_work must be implemented by subclass")
