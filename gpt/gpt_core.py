import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

from data.data_locker import DataLocker
from config.config_constants import DB_PATH


class GPTCore:
    """Core utilities for interacting with GPT."""

    def __init__(self, db_path: str = DB_PATH):
        load_dotenv()
        self.logger = logging.getLogger(__name__)
        self.data_locker = DataLocker.get_instance(db_path)
        self.client = OpenAI(api_key=os.getenv("OPEN_AI_KEY"))

    def _fetch_snapshots(self) -> Dict[str, Optional[dict]]:
        current = self.data_locker.get_latest_portfolio_snapshot()
        history = self.data_locker.get_portfolio_history()
        previous = history[-2] if len(history) >= 2 else None
        return {"current": current, "previous": previous}

    def build_payload(self, instructions: str = "") -> Dict[str, Any]:
        snaps = self._fetch_snapshots()
        payload = {
            "type": "gpt_analysis_bundle",
            "version": "1.0",
            "generated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "meta": {
                "type": "meta",
                "version": "1.0",
                "owner": "Geno",
                "strategy": "hedged, automated trading",
                "goal": "optimize exposure while minimizing risk",
                "notes": "Background context",
            },
            "definitions": {
                "type": "definitions",
                "metrics": {
                    "travel_percent": "Defines change from entry to current price",
                    "heat_index": "Composite risk metric",
                },
            },
            "alert_limits": {
                "alert_ranges": {
                    "heat_index_ranges": {
                        "enabled": True,
                        "low": 7.0,
                        "medium": 33.0,
                        "high": 66.0,
                    }
                }
            },
            "module_references": {
                "modules": {
                    "PositionCore": {"role": "Manages enrichment, snapshots, sync"},
                    "HedgeCalcServices": {"role": "Suggests hedge rebalancing"},
                }
            },
            "current_snapshot": snaps.get("current"),
            "previous_snapshot": snaps.get("previous"),
            "instructions_for_ai": instructions or "Analyze portfolio risk and improvements",
        }
        return payload

    def analyze(self, instructions: str = "") -> str:
        payload = self.build_payload(instructions)
        self.logger.debug("Sending payload to GPT")
        messages = [
            {"role": "system", "content": "You are a portfolio analysis assistant."},
            {"role": "user", "content": json.dumps(payload)},
        ]
        try:
            response = self.client.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
            reply = response.choices[0].message.content.strip()
            self.logger.debug("Received reply from GPT")
            return reply
        except Exception as e:
            self.logger.exception(f"GPT analysis failed: {e}")
            return f"Error: {e}"
