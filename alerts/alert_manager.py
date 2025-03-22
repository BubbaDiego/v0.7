#!/usr/bin/env python
import os
import time
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from twilio.rest import Client
from config.unified_config_manager import UnifiedConfigManager
from config.config_constants import DB_PATH, CONFIG_PATH, ALERT_LIMITS_PATH, BASE_DIR
from pathlib import Path
import inspect
from utils.unified_logger import UnifiedLogger

# Instantiate the unified logger
u_logger = UnifiedLogger()

# Create a dedicated logger for travel percent check details
travel_logger = logging.getLogger("TravelCheckLogger")
travel_logger.setLevel(logging.DEBUG)
if not travel_logger.handlers:
    travel_handler = logging.FileHandler("travel_check.txt")
    travel_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    travel_handler.setFormatter(travel_formatter)
    travel_logger.addHandler(travel_handler)

def trigger_twilio_flow(custom_message: str, twilio_config: dict) -> str:
    """
    Trigger a Twilio Studio Flow to send a call notification.
    This function assumes that the twilio_config contains all required fields.
    """
    account_sid = twilio_config.get("account_sid")
    auth_token = twilio_config.get("auth_token")
    flow_sid = twilio_config.get("flow_sid")
    to_phone = twilio_config.get("to_phone")
    from_phone = twilio_config.get("from_phone")
    if not all([account_sid, auth_token, flow_sid, to_phone, from_phone]):
        raise ValueError("Missing Twilio configuration variables.")
    client = Client(account_sid, auth_token)
    execution = client.studio.v2.flows(flow_sid).executions.create(
        to=to_phone,
        from_=from_phone,
        parameters={"custom_message": custom_message}
    )
    u_logger.log_operation(
        operation_type="Twilio Notification",
        primary_text="Twilio alert sent",
        source="system",
        file="alert_manager.py",
        extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
    )
    return execution.sid

METRIC_DIRECTIONS = {
    "size": "increasing_bad",
}

def get_alert_class(value: float, low_thresh: float, med_thresh: float, high_thresh: float, metric: str) -> str:
    direction = METRIC_DIRECTIONS.get(metric, "increasing_bad")
    if direction == "increasing_bad":
        if value < low_thresh:
            return "alert-low"
        elif value < med_thresh:
            return "alert-medium"
        else:
            return "alert-high"
    elif direction == "decreasing_bad":
        if value > low_thresh:
            return "alert-low"
        elif value > med_thresh:
            return "alert-medium"
        else:
            return "alert-high"
    else:
        return "alert-low"

class AlertManager:
    ASSET_FULL_NAMES = {
        "BTC": "Bitcoin",
        "ETH": "Ethereum",
        "SOL": "Solana"
    }

    def __init__(self, db_path: Optional[str] = None, poll_interval: int = 60, config_path: Optional[str] = None):
        # Set default paths if not provided.
        if db_path is None:
            db_path = str(DB_PATH)
        if config_path is None:
            config_path = str(CONFIG_PATH)
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.config_path = config_path

        # Initialize internal state.
        self.last_profit: Dict[str, str] = {}
        self.last_triggered: Dict[str, float] = {}
        self.last_call_triggered: Dict[str, float] = {}
        self.suppressed_count = 0

        print("Initializing AlertManager...")  # Debug print

        # Initialize dependencies.
        from data.data_locker import DataLocker
        from utils.calc_services import CalcServices

        self.data_locker = DataLocker(self.db_path)
        self.calc_services = CalcServices()

        db_conn = self.data_locker.get_db_connection()
        from config.unified_config_manager import UnifiedConfigManager
        config_manager = UnifiedConfigManager(self.config_path, db_conn=db_conn)

        # Load the main configuration.
        try:
            self.config = config_manager.load_config()
        except Exception as e:
            u_logger.log_operation(
                operation_type="Alert Configuration Failed",
                primary_text="Initial Alert Config Load Failed",
                source="System",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
            self.config = {}

        # Reload configuration to ensure the latest settings.
        self.config = config_manager.load_config()

        # Directly load alert limits from file and merge into configuration.
        try:
            with open(str(ALERT_LIMITS_PATH), "r", encoding="utf-8") as f:
                alert_limits = json.load(f)
            if "alert_ranges" in alert_limits:
                self.config["alert_ranges"] = alert_limits["alert_ranges"]
                # Also load timer values from the alert_limits file
                self.config["alert_cooldown_seconds"] = alert_limits.get("alert_cooldown_seconds", 900.0)
                self.config["call_refractory_period"] = alert_limits.get("call_refractory_period", 3600.0)
                self.config["snooze_countdown"] = alert_limits.get("snooze_countdown", 300.0)
                # Timer start values (could be None)
                self.config["call_refractory_start"] = alert_limits.get("call_refractory_start")
                self.config["snooze_start"] = alert_limits.get("snooze_start")
                u_logger.log_operation(
                    operation_type="Alerts Configured",
                    primary_text="Alerts Config Successful",
                    source="System",
                    file="alert_manager.py",
                    extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
                )
            else:
                u_logger.log_operation(
                    operation_type="Alert Config Merge",
                    primary_text="No alert_ranges found in alert_limits.json.",
                    source="AlertManager",
                    file="alert_manager.py",
                    extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
                )
        except Exception as merge_exc:
            u_logger.log_operation(
                operation_type="Alert Config Merge",
                primary_text=f"Failed to load alert limits from file: {merge_exc}",
                source="AlertManager",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )

        # Load communication settings and thresholds.
        self.twilio_config = self.config.get("twilio_config", {})
        self.cooldown = self.config.get("alert_cooldown_seconds", 900)
        self.call_refractory_period = self.config.get("call_refractory_period", 3600)
        self.snooze_countdown = self.config.get("snooze_countdown", 300)
        self.monitor_enabled = self.config.get("system_config", {}).get("alert_monitor_enabled", True)

        u_logger.log_operation(
            operation_type="Alert Manager Initialized",
            primary_text="Alert Manager 🏃‍♂️",
            source="system",
            file="alert_manager.py",
            extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
        )

    def reload_config(self):
        from config.config_manager import load_config
        db_conn = self.data_locker.get_db_connection()
        try:
            self.config = load_config(self.config_path, db_conn)
            self.cooldown = self.config.get("alert_cooldown_seconds", 900)
            self.call_refractory_period = self.config.get("call_refractory_period", 3600)
            u_logger.log_operation(
                operation_type="Alerts Configuration Successful",
                primary_text="Alerts Config Successful",
                source="AlertManager",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
        except Exception as e:
            u_logger.log_operation(
                operation_type="Alert Configuration Failed",
                primary_text="Alert Config Failed",
                source="system",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )

    def create_all_alerts(self):
        # Chain together creation methods
        price_alerts = self.create_price_alerts()
        travel_alerts = self.create_travel_percent_alerts()
        profit_alerts = self.create_profit_alerts()
        heat_alerts = self.create_heat_index_alerts()
        return price_alerts + travel_alerts + profit_alerts + heat_alerts


    # New helper method to update alert state in the DB if an alert record exists for the position.
    # This method also updates the position_reference_id based on pos['id'].
    def _update_alert_state(self, pos: dict, new_state: str):
        alert_id = pos.get("alert_reference_id")
        if alert_id:
            update_fields = {"state": new_state}
            if pos.get("id"):
                update_fields["position_reference_id"] = pos.get("id")
            try:
                self.data_locker.update_alert_conditions(alert_id, update_fields)
            except Exception as e:
                logging.error(f"Error updating alert state for alert {alert_id}: {e}")

    def update_timer_states(self):
        now = time.time()
        updated = False
        call_start = self.config.get("call_refractory_start")
        if call_start is not None:
            if now - call_start >= self.call_refractory_period:
                self.config["call_refractory_start"] = None
                updated = True
                u_logger.log_operation(
                    operation_type="Timer Reset",
                    primary_text="Call refractory timer reset",
                    source="AlertManager",
                    file="alert_manager.py",
                    extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
                )
        snooze_start = self.config.get("snooze_start")
        if snooze_start is not None:
            if now - snooze_start >= self.snooze_countdown:
                self.config["snooze_start"] = None
                updated = True
                u_logger.log_operation(
                    operation_type="Timer Reset",
                    primary_text="Snooze timer reset",
                    source="AlertManager",
                    file="alert_manager.py",
                    extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
                )
        if updated:
            self.save_config(self.config, ALERT_LIMITS_PATH)

    def trigger_snooze(self):
        now = time.time()
        self.config["snooze_start"] = now
        self.save_config(self.config, ALERT_LIMITS_PATH)
        u_logger.log_operation(
            operation_type="Timer Set",
            primary_text="Snooze timer set",
            source="AlertManager",
            file="alert_manager.py",
            extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
        )

    def clear_snooze(self):
        self.config["snooze_start"] = None
        self.save_config(self.config, ALERT_LIMITS_PATH)
        u_logger.log_operation(
            operation_type="Timer Reset",
            primary_text="Snooze timer cleared",
            source="AlertManager",
            file="alert_manager.py",
            extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
        )

    def run(self):
        u_logger.log_operation(
            operation_type="Monitor Loop",
            primary_text="Starting alert monitoring loop",
            source="AlertManager",
            file="alert_manager.py",
            extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
        )
        while True:
            self.update_timer_states()
            self.check_alerts()
            time.sleep(self.poll_interval)

    def check_alerts(self, source: Optional[str] = None):
        if not self.monitor_enabled:
            u_logger.log_operation(
                operation_type="Monitor Loop",
                primary_text="Alert monitoring disabled",
                source="System",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
            return

        self.suppressed_count = 0
        aggregated_alerts: List[str] = []
        positions = self.data_locker.read_positions()

        u_logger.log_alert(
            operation_type="Alert Check",
            primary_text=f"Checking {len(positions)} positions for alerts",
            source="System",
            file="alert_manager.py",
            extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
        )

        for pos in positions:
            profit_alert = self.check_profit(pos)
            if profit_alert:
                aggregated_alerts.append(profit_alert)
            travel_alert = self.check_travel_percent_liquid(pos)
            if travel_alert:
                aggregated_alerts.append(travel_alert)
            swing_alert = self.check_swing_alert(pos)
            if swing_alert:
                aggregated_alerts.append(swing_alert)
            blast_alert = self.check_blast_alert(pos)
            if blast_alert:
                aggregated_alerts.append(blast_alert)
        price_alerts = self.check_price_alerts()
        aggregated_alerts.extend(price_alerts)

        if aggregated_alerts:
            u_logger.log_alert(
                operation_type="Alert Triggered",
                primary_text=f"{len(aggregated_alerts)} alerts triggered",
                source=source or "",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
            combined_message = "\n".join(aggregated_alerts)
            self.send_call(combined_message, "all_alerts")
        elif self.suppressed_count > 0:
            u_logger.log_alert(
                operation_type="Alert Silenced",
                primary_text=f"{self.suppressed_count} alerts suppressed",
                source=source or "",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
        else:
            u_logger.log_alert(
                operation_type="No Alerts Found",
                primary_text="No Alerts Found",
                source=source or "",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )

    def check_travel_percent_liquid(self, pos: Dict[str, Any]) -> str:
        asset_code = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset_code, asset_code)
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"

        try:
            current_val = float(pos.get("current_travel_percent", 0.0))
        except Exception as e:
            logging.error("%s %s (ID: %s): Error converting travel percent.", asset_full, position_type, position_id)
            return ""

        if current_val >= 0:
            self._update_alert_state(pos, "Normal")
            return ""

        neg_config = self.config.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
        if not neg_config.get("enabled", False):
            return ""

        low = float(neg_config.get("low", -10.0))
        medium = float(neg_config.get("medium", -60.0))
        high = float(neg_config.get("high", -75.0))

        if current_val <= high:
            alert_level = "High"
        elif current_val <= medium:
            alert_level = "Medium"
        elif current_val <= low:
            alert_level = "Low"
        else:
            self._update_alert_state(pos, "Normal")
            return ""

        self._update_alert_state(pos, alert_level)

        key = f"{asset_full}-{position_type}-{position_id}-travel-{alert_level}"
        now = time.time()
        last_time = self.last_triggered.get(key, 0)
        if now - last_time < self.cooldown:
            self.suppressed_count += 1
            return ""
        self.last_triggered[key] = now
        wallet_name = pos.get("wallet_name", "Unknown")
        msg = (f"Travel Percent Liquid ALERT: {asset_full} {position_type} (Wallet: {wallet_name}) - "
               f"Travel% = {current_val:.2f}%, Level = {alert_level}")
        return msg

    def check_profit(self, pos: Dict[str, Any]) -> str:
        asset_code = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset_code, asset_code)
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        try:
            profit_val = float(pos.get("profit", 0.0))
        except Exception:
            return ""
        if profit_val <= 0:
            self._update_alert_state(pos, "Normal")
            return ""
        profit_config = self.config.get("alert_ranges", {}).get("profit_ranges", {})
        if not profit_config.get("enabled", False):
            return ""
        try:
            low_thresh = float(profit_config.get("low", 46.23))
            med_thresh = float(profit_config.get("medium", 101.3))
            high_thresh = float(profit_config.get("high", 202.0))
        except Exception:
            return ""
        if profit_val < low_thresh:
            self._update_alert_state(pos, "Normal")
            return ""
        elif profit_val < med_thresh:
            current_level = "Low"
        elif profit_val < high_thresh:
            current_level = "Medium"
        else:
            current_level = "High"

        self._update_alert_state(pos, current_level)

        profit_key = f"profit-{asset_full}-{position_type}-{position_id}"
        now = time.time()
        last_time = self.last_triggered.get(profit_key, 0)
        if now - last_time < self.cooldown:
            self.suppressed_count += 1
            return ""
        self.last_triggered[profit_key] = now
        msg = f"Profit ALERT: {asset_full} {position_type} profit of {profit_val:.2f} (Level: {current_level})"
        return msg

    def check_swing_alert(self, pos: Dict[str, Any]) -> str:
        swing_config = self.config.get("alert_ranges", {}).get("swing_alerts", {"enabled": True, "notifications": {"call": True}})
        if not swing_config.get("enabled", True):
            return ""
        asset = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset, asset)
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        try:
            current_value = float(pos.get("liquidation_distance", 0.0))
        except Exception:
            logging.error("%s %s (ID: %s): Error converting liquidation distance.", asset_full, position_type, position_id)
            return ""
        hardcoded_swing_thresholds = {"BTC": 6.24, "ETH": 8.0, "SOL": 13.0}
        swing_threshold = hardcoded_swing_thresholds.get(asset, 0)
        logging.debug(f"[Swing Alert Debug] {asset_full} {position_type} (ID: {position_id}): Actual Value = {current_value:.2f} vs Hardcoded Swing Threshold = {swing_threshold:.2f}")
        if current_value >= swing_threshold:
            if not swing_config.get("notifications", {}).get("call", True):
                logging.debug("Swing alert call notification disabled in config.")
                return ""
            key = f"swing-{asset_full}-{position_type}-{position_id}"
            now = time.time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                return (f"Average Daily Swing ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                        f"Actual Value = {current_value:.2f} exceeds Hardcoded Swing Threshold of {swing_threshold:.2f}")
        return ""

    def check_blast_alert(self, pos: Dict[str, Any]) -> str:
        blast_config = self.config.get("alert_ranges", {}).get("blast_alerts", {"enabled": True, "notifications": {"call": True}})
        if not blast_config.get("enabled", True):
            return ""
        asset = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset, asset)
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        try:
            current_value = float(pos.get("liquidation_distance", 0.0))
        except Exception:
            logging.error("%s %s (ID: %s): Error converting liquidation distance.", asset_full, position_type, position_id)
            return ""
        try:
            blast_threshold = 11.2
        except Exception as e:
            logging.error("Error parsing blast threshold for %s: %s", asset_full, e)
            return ""
        logging.debug(f"[Blast Alert Debug] {asset_full} {position_type} (ID: {position_id}): Actual Value = {current_value:.2f} vs Blast Threshold = {blast_threshold:.2f}")
        if current_value >= blast_threshold:
            if not blast_config.get("notifications", {}).get("call", True):
                logging.debug("Blast alert call notification disabled in config.")
                return ""
            key = f"blast-{asset_full}-{position_type}-{position_id}"
            now = time.time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                return (f"One Day Blast Radius ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                        f"Actual Value = {current_value:.2f} exceeds Blast Threshold of {blast_threshold:.2f}")
        return ""

    def debug_price_alert_details(self, asset: str, asset_config: dict, current_price: float, trigger_val: float,
                                  condition: str, price_info: dict, result_message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html_snippet = f"""
        <div style="border:1px solid #ccc; padding:10px; margin:10px; font-family: Arial, sans-serif;">
          <h3 style="margin:0; padding:0 0 10px 0;">{asset} Price Alert Debug</h3>
          <p><strong>Timestamp:</strong> {timestamp}</p>
          <p><strong>Asset Configuration:</strong><br>
             <pre style="background: #f4f4f4; padding:10px;">{json.dumps(asset_config, indent=2)}</pre>
          </p>
          <p><strong>Condition:</strong> {condition}</p>
          <p><strong>Trigger Value:</strong> {trigger_val}</p>
          <p><strong>Current Price:</strong> {current_price}</p>
          <p><strong>Price Info:</strong><br>
             <pre style="background: #f4f4f4; padding:10px;">{json.dumps(price_info, indent=2)}</pre>
          </p>
          <p><strong>Result:</strong> {result_message}</p>
        </div>
        """
        with open("price_alert_debug_details.html", "a", encoding="utf-8") as f:
            f.write(html_snippet)

    def check_price_alerts(self) -> List[str]:
        price_alert_logger = logging.getLogger("PriceAlertLogger")
        if not price_alert_logger.handlers:
            handler = logging.FileHandler("price_alert_debug.txt")
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            price_alert_logger.addHandler(handler)

        price_alert_logger.debug("Entering check_price_alerts method")

        messages: List[str] = []
        price_alert_config = self.config.get("alert_ranges", {}).get("price_alerts", {})
        price_alert_logger.debug(f"Price alert config: {price_alert_config}")

        for asset in ["BTC", "ETH", "SOL"]:
            asset_config = price_alert_config.get(asset, {})
            result_message = ""
            price_alert_logger.debug(f"Processing asset {asset}: {asset_config}")

            if not asset_config.get("enabled", False):
                result_message = "Price alert disabled"
                price_alert_logger.debug(f"Price alert disabled for {asset}")
                self.debug_price_alert_details(asset, asset_config, 0.0, 0.0, "", {}, result_message)
                continue

            condition = asset_config.get("condition", "ABOVE").upper()
            try:
                trigger_val = float(asset_config.get("trigger_value", 0.0))
            except Exception as e:
                price_alert_logger.error(f"Error parsing trigger value for {asset}: {e}")
                result_message = f"Error parsing trigger value: {e}"
                trigger_val = 0.0
                self.debug_price_alert_details(asset, asset_config, 0.0, trigger_val, condition, {}, result_message)
                continue

            price_info = self.data_locker.get_latest_price(asset)
            if not price_info:
                result_message = "No price info available"
                price_alert_logger.debug(f"No price info available for asset {asset}")
                self.debug_price_alert_details(asset, asset_config, 0.0, trigger_val, condition, {}, result_message)
                continue

            try:
                current_price = float(price_info.get("current_price", 0.0))
            except Exception as e:
                price_alert_logger.error(f"Error parsing current price for {asset}: {e}")
                result_message = f"Error parsing current price: {e}"
                self.debug_price_alert_details(asset, asset_config, 0.0, trigger_val, condition, price_info, result_message)
                continue

            price_alert_logger.debug(
                f"{asset}: Condition = {condition}, Trigger Value = {trigger_val:.2f}, Current Price = {current_price:.2f}")

            if (condition == "ABOVE" and current_price >= trigger_val) or (condition == "BELOW" and current_price <= trigger_val):
                price_alert_logger.debug(f"Alert condition met for {asset}, processing trigger")
                msg = self.handle_price_alert_trigger_config(asset, current_price, trigger_val, condition)
                if msg:
                    messages.append(msg)
                    result_message = f"Alert triggered: {msg}"
                    price_alert_logger.debug(result_message)
                else:
                    result_message = f"Alert suppressed due to cooldown or other conditions"
                    price_alert_logger.debug(result_message)
            else:
                result_message = f"Alert condition not met: current_price {current_price:.2f} vs trigger {trigger_val:.2f}"
                price_alert_logger.debug(result_message)

            self.debug_price_alert_details(asset, asset_config, current_price, trigger_val, condition, price_info, result_message)

        price_alert_logger.debug(f"Exiting check_price_alerts with {len(messages)} triggered alerts")
        return messages

    def handle_price_alert_trigger_config(self, asset: str, current_price: float, trigger_val: float, condition: str) -> str:
        asset_full = self.ASSET_FULL_NAMES.get(asset, asset)
        key = f"price-alert-config-{asset}"
        now = time.time()
        last_time = self.last_triggered.get(key, 0)
        if now - last_time < self.cooldown:
            logging.info(f"{asset_full}: Price alert suppressed due to cooldown")
            u_logger.log_alert(
                operation_type="Price ALERT Suppressed",
                primary_text=f"{asset_full}: Price alert suppressed due to cooldown",
                source="system",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
            self.suppressed_count += 1
            return ""
        self.last_triggered[key] = now
        msg = f"Price ALERT: {asset_full} - Condition: {condition}, Trigger: {trigger_val}, Current: {current_price}"
        caller_line = inspect.currentframe().f_back.f_lineno
        alert_details = {
            "status": "Triggered",
            "type": "Price ALERT",
            "condition": condition,
            "trigger_value": trigger_val,
            "current_price": current_price,
            "log_line": caller_line
        }
        extra = {
            "source": "system",
            "operation_type": "Price ALERT",
            "log_type": "alert",
            "file": "alert_manager.py",
            "log_line": caller_line,
            "alert_details": alert_details
        }
        u_logger.logger.info(msg, extra=extra)
        return msg

    def send_call(self, body: str, key: str):
        now = time.time()
        last_call_time = self.last_call_triggered.get(key, 0)
        if now - last_call_time < self.call_refractory_period:
            logging.info("Call alert '%s' suppressed.", key)
            u_logger.log_operation(
                operation_type="Alert Silenced",
                primary_text=f"Alert Silenced: {key}",
                source="AlertManager",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
            return
        try:
            trigger_twilio_flow(body, self.twilio_config)
            self.last_call_triggered[key] = now
            self.config["call_refractory_start"] = now
            self.save_config(self.config, ALERT_LIMITS_PATH)
            u_logger.log_operation(
                operation_type="Timer Set",
                primary_text="Call refractory timer set",
                source="AlertManager",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
        except Exception as e:
            u_logger.log_operation(
                operation_type="Notification Failed",
                primary_text=f"Notification Failed: {key}",
                source="System",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
            logging.error("Error sending call for '%s'.", key, exc_info=True)

    def load_json_config(self, json_path: str) -> dict:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config(self, config: dict, json_path: str):
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

# Create a global AlertManager instance for use in other modules.
manager = AlertManager(
    db_path=str(DB_PATH),
    poll_interval=60,
    config_path=str(CONFIG_PATH)
)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    manager.run()
