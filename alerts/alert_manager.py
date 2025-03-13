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
#from utils.operations_manager import OperationsLogger
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
        file="alert_manager"
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
            u_logger.log_operation(
                operation_type="Alerts Configuration Successful",
                primary_text="Initial Alert Config Loaded Successfully",
                source="System",
                file="alert_manager"
            )
        except Exception as e:
            u_logger.log_operation(
                operation_type="Alert Configuration Failed",
                primary_text="Initial Alert Config Load Failed",
                source="System",
                file="alert_manager"
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
                u_logger.log_operation(
                    operation_type="Alerts Configuration Successful",
                    primary_text="Alerts Config Successful",
                    source="System",
                    file="alert_manager"
                )
            else:
                u_logger.log_operation(
                    operation_type="Alert Config Merge",
                    primary_text="No alert_ranges found in alert_limits.json.",
                    source="AlertManager",
                    file="alert_manager"
                )
        except Exception as merge_exc:
            u_logger.log_operation(
                operation_type="Alert Config Merge",
                primary_text=f"Failed to load alert limits from file: {merge_exc}",
                source="AlertManager",
                file="alert_manager"
            )

        # Load communication settings and thresholds.
        self.twilio_config = self.config.get("twilio_config", {})
        self.cooldown = self.config.get("alert_cooldown_seconds", 900)
        self.call_refractory_period = self.config.get("call_refractory_period", 3600)
        self.monitor_enabled = self.config.get("system_config", {}).get("alert_monitor_enabled", True)

        # Final initialization log.
        u_logger.log_operation(
            operation_type="Alert Manager Initialized",
            primary_text="Alert Manager 🏃‍♂️",
            source="system",
            file="alert_manager"
        )

    def reload_config(self):
        from config.config_manager import load_config
        db_conn = self.data_locker.get_db_connection()
        try:
            self.config = load_config(self.config_path, db_conn)
            self.cooldown = self.config.get("alert_cooldown_seconds", 900)
            self.call_refractory_period = self.config.get("call_refractory_period", 3600)
        except Exception as e:
            u_logger.log_operation(
                operation_type="Alert Configuration Failed",
                primary_text="Alert Config Failed",
                source="system",
                file="alert_manager"
            )

    def run(self):
        u_logger.log_operation(
            operation_type="Monitor Loop",
            primary_text="Starting alert monitoring loop",
            source="AlertManager",
            file="alert_manager"
        )
        while True:
            self.check_alerts()
            time.sleep(self.poll_interval)

    def check_alerts(self, source: Optional[str] = None):
        if not self.monitor_enabled:
            u_logger.log_operation(
                operation_type="Monitor Loop",
                primary_text="Alert monitoring disabled",
                source="System",
                file="alert_manager"
            )
            return

        self.suppressed_count = 0
        aggregated_alerts: List[str] = []
        positions = self.data_locker.read_positions()

        u_logger.log_alert(
            operation_type="Alert Check",
            primary_text=f"Checking {len(positions)} positions for alerts",
            source="System",
            file="alert_manager"
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
                file="alert_manager"
            )
            # Combine alerts and trigger the call notification if enabled.
            combined_message = "\n".join(aggregated_alerts)
            self.send_call(combined_message, "all_alerts")
        elif self.suppressed_count > 0:
            u_logger.log_alert(
                operation_type="Alert Silenced",
                primary_text=f"{self.suppressed_count} alerts suppressed",
                source=source or "",
                file="alert_manager"
            )
        else:
            u_logger.log_alert(
                operation_type="No Alerts Found",
                primary_text="No Alerts Found",
                source=source or "",
                file="alert_manager"
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
            travel_logger.error(f"{asset_full} {position_type} (ID: {position_id}): Error converting travel percent: {e}")
            return ""

        travel_logger.debug(f"Checking travel percent for {asset_full} {position_type} (ID: {position_id}): current_travel_percent = {current_val}")
        travel_logger.debug(f"Position Data: {json.dumps(pos)}")

        # Only process negative travel percentages (liquid alerts)
        if current_val >= 0:
            travel_logger.debug(f"{asset_full} {position_type} (ID: {position_id}): current_val {current_val} is non-negative; skipping liquid alert.")
            return ""

        # Check if travel percent liquid alerts are enabled in config.
        neg_config = self.config.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
        if not neg_config.get("enabled", False):
            travel_logger.debug("Travel percent liquid alerts are disabled in config.")
            return ""

        travel_logger.debug(f"Negative config used: {neg_config}")
        low = float(neg_config.get("low", -10.0))
        medium = float(neg_config.get("medium", -60.0))
        high = float(neg_config.get("high", -75.0))
        travel_logger.debug(f"Using negative thresholds: low={low}, medium={medium}, high={high}")

        if current_val <= high:
            alert_level = "High"
        elif current_val <= medium:
            alert_level = "Medium"
        elif current_val <= low:
            alert_level = "Low"
        else:
            travel_logger.debug(f"{asset_full} {position_type} (ID: {position_id}): Travel percent ({current_val}) does not trigger a negative alert.")
            return ""

        travel_logger.debug(f"Determined alert level: {alert_level} for current_val: {current_val}")

        # Check if the call notification for this alert level is enabled.
        if alert_level == "High" and not neg_config.get("high_notifications", {}).get("call", False):
            travel_logger.debug("High-level travel percent liquid alert call notification disabled in config.")
            return ""
        elif alert_level == "Medium" and not neg_config.get("medium_notifications", {}).get("call", False):
            travel_logger.debug("Medium-level travel percent liquid alert call notification disabled in config.")
            return ""
        elif alert_level == "Low" and not neg_config.get("low_notifications", {}).get("call", False):
            travel_logger.debug("Low-level travel percent liquid alert call notification disabled in config.")
            return ""

        key = f"{asset_full}-{position_type}-{position_id}-travel-{alert_level}"
        now = time.time()
        last_time = self.last_triggered.get(key, 0)
        time_since_last = now - last_time
        if time_since_last < self.cooldown:
            travel_logger.debug(f"{asset_full} {position_type} (ID: {position_id}): Alert for key '{key}' suppressed due to cooldown (time since last: {time_since_last:.2f} seconds).")
            self.suppressed_count += 1
            return ""
        self.last_triggered[key] = now
        wallet_name = pos.get("wallet_name", "Unknown")
        msg = (f"Travel Percent Liquid ALERT: {asset_full} {position_type} (Wallet: {wallet_name}) - "
               f"Travel% = {current_val:.2f}%, Level = {alert_level}")
        # Log this alert with our custom alert_details field.
        alert_details = {
            "status": alert_level,
            "type": "Travel Percent Liquid ALERT",
            "limit": f"{low}%",
            "current": f"{current_val:.2f}%"
        }
        u_logger.logger.info(msg, extra={"source": "System", "operation_type": "Travel Percent Liquid ALERT", "log_type": "alert", "file": "alert_manager", "alert_details": alert_details})
        travel_logger.debug(f"Triggered travel percent alert: {msg}")
        return msg

    def check_profit(self, pos: Dict[str, Any]) -> str:
        asset_code = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset_code, asset_code)
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        raw_profit = pos.get("profit")
        try:
            profit_val = float(raw_profit) if raw_profit is not None else 0.0
        except Exception:
            logging.error("%s %s (ID: %s): Error converting profit.", asset_full, position_type, position_id)
            return ""
        if profit_val <= 0:
            return ""
        profit_config = self.config.get("alert_ranges", {}).get("profit_ranges", {})
        if not profit_config.get("enabled", False):
            return ""
        try:
            low_thresh = float(profit_config.get("low", 46.23))
            med_thresh = float(profit_config.get("medium", 101.3))
            high_thresh = float(profit_config.get("high", 202.0))
        except Exception:
            logging.error("%s %s (ID: %s): Error parsing profit thresholds.", asset_full, position_type, position_id)
            return ""
        logging.debug(f"[Profit Alert Debug] {asset_full} {position_type} (ID: {position_id}): Profit = {profit_val:.2f}, Thresholds: Low = {low_thresh:.2f}, Medium = {med_thresh:.2f}, High = {high_thresh:.2f}")
        if profit_val < low_thresh:
            return ""
        elif profit_val < med_thresh:
            current_level = "Low"
        elif profit_val < high_thresh:
            current_level = "Medium"
        else:
            current_level = "High"

        # Check if profit alerts for this level are enabled.
        if current_level == "High" and not profit_config.get("high_notifications", {}).get("call", False):
            logging.debug("High-level profit alert call notification disabled in config.")
            return ""
        elif current_level == "Medium" and not profit_config.get("medium_notifications", {}).get("call", False):
            logging.debug("Medium-level profit alert call notification disabled in config.")
            return ""
        elif current_level == "Low" and not profit_config.get("low_notifications", {}).get("call", False):
            logging.debug("Low-level profit alert call notification disabled in config.")
            return ""

        profit_key = f"profit-{asset_full}-{position_type}-{position_id}"
        last_level = self.last_profit.get(profit_key, "none")
        level_order = {"none": 0, "Low": 1, "Medium": 2, "High": 3}
        if level_order[current_level] <= level_order.get(last_level, 0):
            self.last_profit[profit_key] = current_level
            return ""
        now = time.time()
        last_time = self.last_triggered.get(profit_key, 0)
        if now - last_time < self.cooldown:
            self.last_profit[profit_key] = current_level
            self.suppressed_count += 1
            return ""
        self.last_triggered[profit_key] = now
        msg = f"Profit ALERT: {asset_full} {position_type} profit of {profit_val:.2f} (Level: {current_level.upper()})"
        self.last_profit[profit_key] = current_level
        # Log this profit alert with alert_details.
        alert_details = {
            "status": current_level,
            "type": "Profit ALERT",
            "limit": f"{low_thresh} / {med_thresh} / {high_thresh}",
            "current": f"{profit_val:.2f}"
        }
        u_logger.logger.info(msg, extra={"source": "System", "operation_type": "Profit ALERT", "log_type": "alert", "file": "alert_manager", "alert_details": alert_details})
        return msg

    def check_swing_alert(self, pos: Dict[str, Any]) -> str:
        # Optional: Check configuration for swing alerts; default to enabled if not configured.
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
            # Check if call notification for swing alerts is enabled, if specified.
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
        # Optional: Check configuration for blast alerts; default to enabled if not configured.
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
            # Check if call notification for blast alerts is enabled, if specified.
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

    def check_price_alerts(self) -> List[str]:
        alerts = self.data_locker.get_alerts()
        messages: List[str] = []
        price_alerts = [a for a in alerts if a.get("alert_type") == "PRICE_THRESHOLD" and a.get("status", "").lower() == "active"]
        logging.info("Found %d active price alerts.", len(price_alerts))
        for alert in price_alerts:
            asset_code = alert.get("asset_type", "BTC").upper()
            asset_full = self.ASSET_FULL_NAMES.get(asset_code, asset_code)
            position_id = alert.get("position_id") or alert.get("id") or "unknown"
            try:
                trigger_val = float(alert.get("trigger_value", 0.0))
            except Exception:
                trigger_val = 0.0
            condition = alert.get("condition", "ABOVE").upper()
            price_info = self.data_locker.get_latest_price(asset_code)
            if not price_info:
                continue
            current_price = float(price_info.get("current_price", 0.0))
            logging.debug(f"[Price Alert Debug] {asset_full}: Condition = {condition}, Trigger Value = {trigger_val:.2f}, Current Price = {current_price:.2f}")
            if (condition == "ABOVE" and current_price >= trigger_val) or (condition != "ABOVE" and current_price <= trigger_val):
                msg = self.handle_price_alert_trigger(alert, current_price, asset_full)
                if msg:
                    messages.append(msg)
        return messages

    def handle_price_alert_trigger(self, alert: dict, current_price: float, asset_full: str) -> str:
        position_id = alert.get("position_id") or alert.get("id") or "unknown"
        key = f"price-alert-{asset_full}-{position_id}"
        now = time.time()
        last_time = self.last_triggered.get(key, 0)
        if now - last_time < self.cooldown:
            logging.info("%s: Price alert suppressed.", asset_full)
            self.suppressed_count += 1
            return ""
        self.last_triggered[key] = now
        cond = alert.get("condition", "ABOVE").upper()
        try:
            trig_val = float(alert.get("trigger_value", 0.0))
        except Exception:
            trig_val = 0.0
        position_type = alert.get("position_type", "").capitalize()
        wallet_name = alert.get("wallet_name", "Unknown")
        msg = f"Price ALERT: {asset_full} {position_type}"
        if wallet_name != "Unknown":
            msg += f", Wallet: {wallet_name}"
        msg += f" - Condition: {cond}, Trigger: {trig_val}, Current: {current_price}"
        return msg

    def send_call(self, body: str, key: str):
        """
        Sends a call notification via Twilio if call notifications are enabled.
        This method checks the refractory period before triggering the call.
        """
        now = time.time()
        last_call_time = self.last_call_triggered.get(key, 0)
        if now - last_call_time < self.call_refractory_period:
            logging.info("Call alert '%s' suppressed.", key)
            u_logger.log_operation(
                operation_type="Alert Silenced",
                primary_text=f"Alert Silenced: {key}",
                source="AlertManager",
                file="alert_manager"
            )
            return
        try:
            trigger_twilio_flow(body, self.twilio_config)
            self.last_call_triggered[key] = now
        except Exception as e:
            u_logger.log_operation(
                operation_type="Notification Failed",
                primary_text=f"Notification Failed: {key}",
                source="AlertManager",
                file="alert_manager"
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
    logging.basicConfig(level=logging.DEBUG)
    manager.run()
