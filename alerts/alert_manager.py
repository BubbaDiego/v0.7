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
from alerts.alert_evaluator import AlertEvaluator

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
        # Instantiate AlertEvaluator and delegate detailed evaluations to it.
        from alerts.alert_evaluator import AlertEvaluator
        self.alert_evaluator = AlertEvaluator(self.config, self.data_locker)

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
        Uses alert_reference_id if present, else pos["id"].
        """
        alert_id = pos.get("alert_reference_id") or pos.get("id")
        if not alert_id:
            self.logger.warning("[_update_alert_state] No alert identifier found; update skipped.")
            return

        update_fields = {"state": new_state}
        if evaluated_value is not None:
            update_fields["evaluated_value"] = evaluated_value

        if pos.get("alert_reference_id") and pos.get("id"):
            update_fields["position_reference_id"] = pos.get("id")

        self.logger.debug(f"[_update_alert_state] Attempting to update alert '{alert_id}' with fields: {update_fields}")
        try:
            num_updated = self.data_locker.update_alert_conditions(alert_id, update_fields)
            if num_updated == 0:
                self.logger.warning(f"[_update_alert_state] No alert record found for id '{alert_id}'.")
            else:
                self.logger.info(
                    f"Successfully updated alert '{alert_id}' to state '{new_state}' with evaluated value '{evaluated_value}'."
                )
        except Exception as e:
            self.logger.error(f"Error updating alert state for id '{alert_id}': {e}", exc_info=True)

    def reevaluate_alerts(self):
        """
        Reevaluate all alert conditions by delegating evaluation to AlertEvaluator.
        This replaces the previous calls to check_profit, check_travel_percent_liquid, etc.
        """
        positions = self.data_locker.read_positions()
        # Delegate evaluation to AlertEvaluator:
        evaluation_results = self.alert_evaluator.evaluate_alerts(positions=positions)
        # Optionally, you can log the aggregated results here.
        self.logger.debug(f"Reevaluation completed. Position Alerts: {evaluation_results.get('position')}, "
                          f"Market Alerts: {evaluation_results.get('market')}, "
                          f"System Alerts: {evaluation_results.get('system')}")

    def check_alerts(self, source: Optional[str] = None):
        """
        Called typically by the 'Refresh' route or background loop.
        Reevaluate conditions, retrieve updated alerts from DB,
        and trigger notifications if needed.
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

        self.reevaluate_alerts()

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

    def update_alerts_evaluated_value(self):
        """
        Updates the evaluated_value for each alert based on its alert type.

        - For Price* alerts, sets evaluated_value to the latest asset price.
        - For TravelPercent* alerts, sets evaluated_value to the position's current travel percent.
        - For Profit* alerts, sets evaluated_value to the position's pnl_after_fees_usd.
        - For HeatIndex* alerts, sets evaluated_value to the position's current_heat_index.
        """
        alerts = self.data_locker.get_alerts()
        positions = self.data_locker.read_positions()
        # Build lookup using the position id from positions
        pos_lookup = {pos.get("id"): pos for pos in positions}

        for alert in alerts:
            evaluated_val = None
            alert_type = alert.get("alert_type", "")

            if alert_type.startswith("Price"):
                asset_type = alert.get("asset_type", "BTC")
                price_data = self.data_locker.get_latest_price(asset_type)
                if price_data and "current_price" in price_data:
                    try:
                        evaluated_val = float(price_data["current_price"])
                    except Exception as e:
                        self.logger.error(f"Error converting latest price for asset {asset_type}: {e}", exc_info=True)

            elif alert_type.startswith("TravelPercent"):
                # Check both 'position_reference_id' and 'position_id'
                pos_id = alert.get("position_reference_id") or alert.get("position_id")
                if pos_id and pos_id in pos_lookup:
                    try:
                        evaluated_val = float(pos_lookup[pos_id].get("current_travel_percent", 0))
                    except Exception as e:
                        self.logger.error(f"Error retrieving travel percent for position {pos_id}: {e}", exc_info=True)

            elif alert_type.startswith("Profit"):
                pos_id = alert.get("position_reference_id") or alert.get("position_id")
                if pos_id and pos_id in pos_lookup:
                    try:
                        evaluated_val = float(pos_lookup[pos_id].get("pnl_after_fees_usd", 0))
                    except Exception as e:
                        self.logger.error(f"Error retrieving pnl for position {pos_id}: {e}", exc_info=True)

            elif alert_type.startswith("HeatIndex"):
                pos_id = alert.get("position_reference_id") or alert.get("position_id")
                if pos_id and pos_id in pos_lookup:
                    try:
                        evaluated_val = float(pos_lookup[pos_id].get("current_heat_index", 0))
                    except Exception as e:
                        self.logger.error(f"Error retrieving heat index for position {pos_id}: {e}", exc_info=True)

            if evaluated_val is not None:
                alert_id = alert.get("id")
                try:
                    self.data_locker.update_alert_conditions(alert_id, {"evaluated_value": evaluated_val})
                    self.logger.info(f"Updated alert {alert_id} evaluated_value to {evaluated_val}")
                except Exception as update_ex:
                    self.logger.error(f"Failed to update evaluated_value for alert {alert_id}: {update_ex}",
                                      exc_info=True)

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

    def send_call(self, body: str, key: str):
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
        Background loop if run as a main script.
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
