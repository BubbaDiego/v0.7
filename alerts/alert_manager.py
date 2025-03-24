#!/usr/bin/env python
import os
import time
from time import time as current_time
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from config.unified_config_manager import UnifiedConfigManager
from config.config_constants import DB_PATH, CONFIG_PATH, ALERT_LIMITS_PATH, BASE_DIR
from pathlib import Path
import inspect
from utils.unified_logger import UnifiedLogger
from alerts.alert_controller import AlertController

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
    Triggers the Twilio Studio flow to send a notification.
    Raises a ValueError if required configuration is missing.
    """
    account_sid = twilio_config.get("account_sid")
    auth_token = twilio_config.get("auth_token")
    flow_sid = twilio_config.get("flow_sid")
    to_phone = twilio_config.get("to_phone")
    from_phone = twilio_config.get("from_phone")
    if not all([account_sid, auth_token, flow_sid, to_phone, from_phone]):
        raise ValueError("Missing Twilio configuration variables.")
    client = Client(account_sid, auth_token)
    try:
        execution = client.studio.v2.flows(flow_sid).executions.create(
            to=to_phone,
            from_=from_phone,
            parameters={"custom_message": custom_message}
        )
    except TwilioRestException as tre:
        logging.error("Twilio API call failed: %s", tre, exc_info=True)
        raise
    u_logger.log_operation(
        operation_type="Twilio Notification",
        primary_text="Twilio alert sent",
        source="system",
        file="alert_manager.py",
        extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
    )
    return execution.sid


class AlertManager:
    ASSET_FULL_NAMES = {
        "BTC": "Bitcoin",
        "ETH": "Ethereum",
        "SOL": "Solana"
    }

    def __init__(self, db_path: Optional[str] = None, poll_interval: int = 60, config_path: Optional[str] = None):
        if db_path is None:
            db_path = str(DB_PATH)
        if config_path is None:
            config_path = str(CONFIG_PATH)
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.config_path = config_path

        self.last_profit: Dict[str, str] = {}
        self.last_triggered: Dict[str, float] = {}
        self.last_call_triggered: Dict[str, float] = {}
        self.suppressed_count = 0

        print("Initializing AlertManager...")  # Debug print

        from data.data_locker import DataLocker
        from utils.calc_services import CalcServices
        self.data_locker = DataLocker(self.db_path)
        self.calc_services = CalcServices()

        db_conn = self.data_locker.get_db_connection()
        from config.unified_config_manager import UnifiedConfigManager
        config_manager = UnifiedConfigManager(self.config_path, db_conn=db_conn)

        self.logger = logging.getLogger("AlertManagerLogger")

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

        self.config = config_manager.load_config()

        try:
            with open(str(ALERT_LIMITS_PATH), "r", encoding="utf-8") as f:
                alert_limits = json.load(f)
            if "alert_ranges" in alert_limits:
                self.config["alert_ranges"] = alert_limits["alert_ranges"]
                self.config["alert_cooldown_seconds"] = alert_limits.get("alert_cooldown_seconds", 900.0)
                self.config["call_refractory_period"] = alert_limits.get("call_refractory_period", 3600.0)
                self.config["snooze_countdown"] = alert_limits.get("snooze_countdown", 300.0)
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

        self.alert_controller = AlertController(db_path=self.db_path)

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
        """
        Delegates the creation of all alerts to the AlertController.
        """
        return self.alert_controller.create_all_alerts()

    def _update_alert_state(self, pos: dict, new_state: str, evaluated_value: Optional[float] = None):
        """
        Update the state of the matching alert record in the DB (if found).
        We use `alert_reference_id` if present, else `pos["id"]`.
        """
        alert_id = pos.get("alert_reference_id") or pos.get("id")
        if not alert_id:
            self.logger.warning("[_update_alert_state] No alert identifier found; update skipped.")
            return

        update_fields = {"state": new_state}
        if evaluated_value is not None:
            update_fields["evaluated_value"] = evaluated_value

        # Optionally store the position reference if both are available.
        if pos.get("alert_reference_id") and pos.get("id"):
            update_fields["position_reference_id"] = pos.get("id")

        self.logger.debug(f"[_update_alert_state] Attempting to update alert '{alert_id}' with fields: {update_fields}")
        try:
            num_updated = self.data_locker.update_alert_conditions(alert_id, update_fields)
            if num_updated == 0:
                self.logger.warning(f"[_update_alert_state] No alert record found for id '{alert_id}'.")
                # Optionally, you might create the alert record here if needed.
            else:
                self.logger.info(
                    f"[_update_alert_state] Successfully updated alert '{alert_id}' to state '{new_state}' with evaluated value '{evaluated_value}'."
                )
        except Exception as e:
            self.logger.error(f"[_update_alert_state] Error updating alert state for id '{alert_id}': {e}", exc_info=True)

    def reevaluate_alerts(self):
        """
        Reevaluate all alert conditions by iterating over current positions.
        This method updates the persistent alert records (via _update_alert_state)
        based on the latest position data.
        """
        positions = self.data_locker.read_positions()
        for pos in positions:
            # Evaluate the various alert checks (profit, travel, etc.).
            self.check_profit(pos)
            self.check_travel_percent_liquid(pos)
            self.check_swing_alert(pos)
            self.check_blast_alert(pos)

        # Also run price alerts evaluation (updates states for price-threshold alerts).
        self.check_price_alerts()

    def check_alerts(self, source: Optional[str] = None):
        """
        Called typically by the 'Refresh' route or the background loop.
        1. Reevaluate conditions for each position/alert (update DB).
        2. Retrieve updated alerts from DB and see which are triggered.
        3. If any triggered, call Twilio, else do nothing or log.
        """
        if not self.monitor_enabled:
            u_logger.log_operation(
                operation_type="Monitor Loop",
                primary_text="Alert monitoring disabled",
                source="System",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
            return

        # Re-check all alert conditions, storing results in DB
        self.reevaluate_alerts()

        # Now fetch the persistent alerts from DB
        alerts = self.data_locker.get_alerts()
        triggered_alerts = [a for a in alerts if a.get("state", "Normal") != "Normal"]

        if triggered_alerts:
            combined_message = "\n".join(
                f"{a.get('alert_type', 'Alert')} ALERT for {a.get('asset_type', 'Asset')} - "
                f"State: {a.get('state')}, Value: {a.get('evaluated_value')}"
                for a in triggered_alerts
            )
            u_logger.log_alert(
                operation_type="Alert Triggered",
                primary_text=f"{len(triggered_alerts)} alerts triggered",
                source=source or "",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
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
                primary_text="No alerts found in DB",
                source=source or "",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )

    def update_timer_states(self):
        now = current_time()
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
        now = current_time()
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
        """
        Background loop if run as a main script. Typically, you'll rely on
        manual or scheduled refresh calls, but this is still available.
        """
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

    def check_travel_percent_liquid(self, pos: Dict[str, Any]) -> str:
        """
        Evaluates the current travel percent for a position.
        Returns an alert message string if conditions are met, otherwise returns an empty string.
        """
        asset_code = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset_code, asset_code)
        position_type = pos.get("position_type", "Unknown")
        pos_id = pos.get("position_id") or pos.get("id") or "unknown"

        try:
            raw_val = pos.get("current_travel_percent", 0.0)
            current_val = float(raw_val)
        except Exception as e:
            self.logger.error(
                f"{asset_full} {position_type} (ID: {pos_id}): Error converting travel percent. Raw value: {raw_val}",
                exc_info=True
            )
            return ""

        self.logger.debug(
            f"[check_travel_percent_liquid] Asset: {asset_full}, Position ID: {pos_id}, "
            f"raw current_travel_percent: {raw_val}, converted: {current_val}, "
            f"enriched travel_percent: {pos.get('travel_percent')}"
        )

        # If travel percent is >= 0, no negative alert needed.
        if current_val >= 0:
            self._update_alert_state(pos, "Normal", evaluated_value=current_val)
            return ""

        tp_config = self.config.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
        if not tp_config.get("enabled", False):
            self.logger.debug("Travel percent liquid alerts are disabled in configuration.")
            return ""

        try:
            low_threshold = float(tp_config.get("low", -4.0))
            medium_threshold = float(tp_config.get("medium", -7.0))
            high_threshold = float(tp_config.get("high", -10.0))
        except Exception as e:
            self.logger.error("Error parsing travel percent thresholds from config.", exc_info=True)
            return ""

        # Determine alert level
        if current_val <= high_threshold:
            alert_level = "High"
        elif current_val <= medium_threshold:
            alert_level = "Medium"
        elif current_val <= low_threshold:
            alert_level = "Low"
        else:
            self._update_alert_state(pos, "Normal", evaluated_value=current_val)
            return ""

        self._update_alert_state(pos, alert_level, evaluated_value=current_val)

        # Handle suppression cooldown
        key = f"{asset_full}-{position_type}-{pos_id}-travel-{alert_level}"
        now = current_time()
        last_time = self.last_triggered.get(key, 0)
        if now - last_time < self.cooldown:
            self.suppressed_count += 1
            self.logger.debug(
                f"Alert for key {key} suppressed due to cooldown. Time since last trigger: {now - last_time:.2f} sec"
            )
            return ""

        self.last_triggered[key] = now
        wallet_name = pos.get("wallet_name", "Unknown")
        msg = (
            f"Travel Percent Liquid ALERT: {asset_full} {position_type} (Wallet: {wallet_name}) - "
            f"Travel% = {current_val:.2f}%, Level = {alert_level}"
        )
        self.logger.info(f"Triggering travel percent alert: {msg}")
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
            self._update_alert_state(pos, "Normal", evaluated_value=profit_val)
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
            self._update_alert_state(pos, "Normal", evaluated_value=profit_val)
            return ""
        elif profit_val < med_thresh:
            current_level = "Low"
        elif profit_val < high_thresh:
            current_level = "Medium"
        else:
            current_level = "High"

        self._update_alert_state(pos, current_level, evaluated_value=profit_val)

        profit_key = f"profit-{asset_full}-{position_type}-{position_id}"
        now = current_time()
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
            self.logger.error("%s %s (ID: %s): Error converting liquidation distance.", asset_full, position_type, position_id)
            return ""

        hardcoded_swing_thresholds = {"BTC": 6.24, "ETH": 8.0, "SOL": 13.0}
        swing_threshold = hardcoded_swing_thresholds.get(asset, 0)
        self.logger.debug(
            f"[Swing Alert Debug] {asset_full} {position_type} (ID: {position_id}): "
            f"Actual Value = {current_value:.2f} vs Hardcoded Swing Threshold = {swing_threshold:.2f}"
        )

        if current_value >= swing_threshold:
            if not swing_config.get("notifications", {}).get("call", True):
                self.logger.debug("Swing alert call notification disabled in config.")
                return ""
            self._update_alert_state(pos, "Triggered", evaluated_value=current_value)

            key = f"swing-{asset_full}-{position_type}-{position_id}"
            now = current_time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                return (
                    f"Average Daily Swing ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                    f"Actual Value = {current_value:.2f} exceeds Hardcoded Swing Threshold of {swing_threshold:.2f}"
                )
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
            self.logger.error("%s %s (ID: %s): Error converting liquidation distance.", asset_full, position_type, position_id)
            return ""

        # Hard-coded for demonstration
        blast_threshold = 11.2

        self.logger.debug(
            f"[Blast Alert Debug] {asset_full} {position_type} (ID: {position_id}): "
            f"Actual Value = {current_value:.2f} vs Blast Threshold = {blast_threshold:.2f}"
        )

        if current_value >= blast_threshold:
            if not blast_config.get("notifications", {}).get("call", True):
                self.logger.debug("Blast alert call notification disabled in config.")
                return ""
            self._update_alert_state(pos, "Triggered", evaluated_value=current_value)

            key = f"blast-{asset_full}-{position_type}-{position_id}"
            now = current_time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                return (
                    f"One Day Blast Radius ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                    f"Actual Value = {current_value:.2f} exceeds Blast Threshold of {blast_threshold:.2f}"
                )
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
        """
        Evaluate the price-threshold alerts for each of BTC, ETH, SOL, updating
        their states as necessary. Return any triggered messages for logging.
        """
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

            price_alert_logger.debug(f"{asset}: Condition = {condition}, Trigger Value = {trigger_val:.2f}, Current Price = {current_price:.2f}")

            # Evaluate the condition
            if (condition == "ABOVE" and current_price >= trigger_val) or (condition == "BELOW" and current_price <= trigger_val):
                price_alert_logger.debug(f"Alert condition met for {asset}, processing trigger")

                # Update the matching alert in DB to "Triggered"
                alerts = self.data_locker.get_alerts()
                for alert in alerts:
                    if alert.get("alert_type") == "PriceThreshold" and alert.get("asset_type", "").upper() == asset:
                        self._update_alert_state(alert, "Triggered", evaluated_value=current_price)
                        break

                msg = self.handle_price_alert_trigger_config(asset, current_price, trigger_val, condition)
                if msg:
                    messages.append(msg)
                    result_message = f"Alert triggered: {msg}"
                    price_alert_logger.debug(result_message)
                else:
                    result_message = "Alert suppressed due to cooldown"
                    price_alert_logger.debug(result_message)
            else:
                result_message = (
                    f"Alert condition not met: current_price {current_price:.2f} vs trigger {trigger_val:.2f}"
                )
                price_alert_logger.debug(result_message)

            self.debug_price_alert_details(asset, asset_config, current_price, trigger_val, condition, price_info, result_message)

        price_alert_logger.debug(f"Exiting check_price_alerts with {len(messages)} triggered alerts")
        return messages

    def handle_price_alert_trigger_config(self, asset: str, current_price: float, trigger_val: float, condition: str) -> str:
        asset_full = self.ASSET_FULL_NAMES.get(asset, asset)
        key = f"price-alert-config-{asset}"
        now = current_time()
        last_time = self.last_triggered.get(key, 0)
        if now - last_time < self.cooldown:
            self.logger.info(f"{asset_full}: Price alert suppressed due to cooldown")
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
        """
        Actually triggers Twilio phone call if not in refractory period.
        If we are in refractory period, logs a suppression. Otherwise calls trigger_twilio_flow.
        """
        now = current_time()
        last_call_time = self.last_call_triggered.get(key, 0)
        if now - last_call_time < self.call_refractory_period:
            self.logger.info("Call alert '%s' suppressed.", key)
            u_logger.log_operation(
                operation_type="Alert Silenced",
                primary_text=f"Alert Silenced: {key}",
                source="AlertManager",
                file="alert_manager.py",
                extra_data={"log_line": inspect.currentframe().f_back.f_lineno}
            )
            return

        if not all([
            self.twilio_config.get("account_sid"),
            self.twilio_config.get("auth_token"),
            self.twilio_config.get("flow_sid"),
            self.twilio_config.get("to_phone"),
            self.twilio_config.get("from_phone")
        ]):
            self.logger.error("Twilio configuration is incomplete. Skipping call notification.")
            u_logger.log_operation(
                operation_type="Notification Failed",
                primary_text=f"Incomplete Twilio config for {key}",
                source="System",
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
            self.logger.error("Error sending call for '%s': %s", key, e, exc_info=True)

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
