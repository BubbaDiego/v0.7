import logging
import time
from config.unified_config_manager import UnifiedConfigManager
from config.config_constants import CONFIG_PATH
from utils.unified_logger import UnifiedLogger
from alerts.alert_enrichment import enrich_alert_data

u_logger = UnifiedLogger()

class AlertEvaluator:
    def __init__(self, config, data_locker):
        """
        :param config: The loaded configuration (e.g. from alert_limits.json)
        :param data_locker: Instance of DataLocker for DB operations.
        """
        self.config = config
        self.data_locker = data_locker
        # For cooldown management (in seconds)
        self.cooldown = self.config.get("alert_cooldown_seconds", 900)
        self.last_triggered = {}
        self.suppressed_count = 0

    # -------------------------
    # Subordinate Evaluation Methods
    # -------------------------
    def evaluate_travel_alert(self, pos: dict):
        """
        Evaluate the travel percent alert based on configuration thresholds.
        Returns a tuple (state, evaluated_value) or None if evaluation cannot be done.
        """
        tp_config = self.config.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
        if not tp_config.get("enabled", False):
            return None
        try:
            low_threshold = float(tp_config.get("low", -4.0))
            medium_threshold = float(tp_config.get("medium", -7.0))
            high_threshold = float(tp_config.get("high", -10.0))
        except Exception as e:
            u_logger.log_operation(
                operation_type="Alert Evaluation Error",
                primary_text=f"Error parsing travel thresholds: {e}",
                source="AlertEvaluator",
                file="alert_evaluator.py"
            )
            return None
        try:
            current_val = float(pos.get("current_travel_percent", 0.0))
        except Exception as e:
            u_logger.log_operation(
                operation_type="Alert Evaluation Error",
                primary_text=f"Error parsing travel percent: {e}",
                source="AlertEvaluator",
                file="alert_evaluator.py"
            )
            return None

        if current_val >= 0:
            state = "Normal"

        elif current_val <= high_threshold:
            state = "High"
            print("🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
        elif current_val <= medium_threshold:
            state = "Medium"
            print("🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡")
        elif current_val <= low_threshold:
            state = "Low"
            print(" 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢")
        else:
            state = "Normal"
        return state, current_val

    def enrich_alert(self, alert: dict) -> dict:
        """
        Enrich the alert by delegating to the shared enrichment routine.
        """
        enriched_alert = enrich_alert_data(alert, self.data_locker, self.logger)
        return enriched_alert

    def evaluate_profit_alert(self, pos: dict) -> str:
        """
        Evaluate profit alert for a position.
        Returns a message if triggered, else an empty string.
        """
        asset_code = pos.get("asset_type", "???").upper()
        asset_full = asset_code  # Alternatively, you could map this to full names.
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
        now = time.time()
        last_time = self.last_triggered.get(profit_key, 0)
        if now - last_time < self.cooldown:
            self.suppressed_count += 1
            return ""
        self.last_triggered[profit_key] = now
        msg = f"Profit ALERT: {asset_full} {position_type} profit of {profit_val:.2f} (Level: {current_level})"
        return msg

    def evaluate_swing_alert(self, pos: dict) -> str:
        """
        Evaluate swing alert for a position.
        Returns a message if triggered, else an empty string.
        """
        swing_config = self.config.get("alert_ranges", {}).get("swing_alerts", {"enabled": True, "notifications": {"call": True}})
        if not swing_config.get("enabled", True):
            return ""
        asset = pos.get("asset_type", "???").upper()
        asset_full = asset
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        try:
            current_value = float(pos.get("liquidation_distance", 0.0))
        except Exception:
            return ""
        hardcoded_swing_thresholds = {"BTC": 6.24, "ETH": 8.0, "SOL": 13.0}
        swing_threshold = hardcoded_swing_thresholds.get(asset, 0)
        if current_value >= swing_threshold:
            self._update_alert_state(pos, "Triggered", evaluated_value=current_value)
            key = f"swing-{asset_full}-{position_type}-{position_id}"
            now = time.time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                return (f"Average Daily Swing ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                        f"Actual Value = {current_value:.2f} exceeds threshold {swing_threshold:.2f}")
        return ""

    def evaluate_blast_alert(self, pos: dict) -> str:
        """
        Evaluate blast alert for a position.
        Returns a message if triggered, else an empty string.
        """
        blast_config = self.config.get("alert_ranges", {}).get("blast_alerts", {"enabled": True, "notifications": {"call": True}})
        if not blast_config.get("enabled", True):
            return ""
        asset = pos.get("asset_type", "???").upper()
        asset_full = asset
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        try:
            current_value = float(pos.get("liquidation_distance", 0.0))
        except Exception:
            return ""
        blast_threshold = 11.2  # Hard-coded for demonstration
        if current_value >= blast_threshold:
            self._update_alert_state(pos, "Triggered", evaluated_value=current_value)
            key = f"blast-{asset_full}-{position_type}-{position_id}"
            now = time.time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                return (f"One Day Blast Radius ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                        f"Actual Value = {current_value:.2f} exceeds threshold {blast_threshold:.2f}")
        return ""

    def evaluate_price_alerts(self, market_data: dict) -> list:
        """
        Evaluate market (price-threshold) alerts.
        :param market_data: Dictionary of asset prices, e.g., {"BTC": 45000, "ETH": 3000}.
        :return: List of triggered market alert messages.
        """
        alerts = []
        price_config = self.config.get("alert_ranges", {}).get("price_alerts", {})
        for asset, price in market_data.items():
            asset_conf = price_config.get(asset, {})
            if asset_conf.get("enabled", False):
                condition = asset_conf.get("condition", "ABOVE").upper()
                try:
                    trigger_val = float(asset_conf.get("trigger_value", 0.0))
                except Exception as e:
                    u_logger.log_operation(
                        operation_type="Market Alert Evaluation Error",
                        primary_text=f"Error parsing trigger value for {asset}: {e}",
                        source="AlertEvaluator",
                        file="alert_evaluator.py"
                    )
                    continue
                if (condition == "ABOVE" and price >= trigger_val) or (condition == "BELOW" and price <= trigger_val):
                    msg = f"Market ALERT: {asset} price {price} meets condition {condition} {trigger_val}"
                    alerts.append(msg)
                    u_logger.log_operation(
                        operation_type="Market Alert Triggered",
                        primary_text=msg,
                        source="AlertEvaluator",
                        file="alert_evaluator.py"
                    )
        return alerts

    # -------------------------
    # Major Evaluation Methods
    # -------------------------
    def evaluate_alerts(self, positions: list = None, market_data: dict = None) -> dict:
        """
        Master evaluation method that aggregates market, position, and system alerts.
        :param positions: List of position dictionaries.
        :param market_data: Dictionary containing market data.
        :return: Dictionary with keys 'market', 'position', and 'system' and their respective alert messages.
        """
        return {
            "market": self.evaluate_market_alerts(market_data) if market_data is not None else [],
            "position": self.evaluate_position_alerts(positions) if positions is not None else [],
            "system": self.evaluate_system_alerts()
        }

    def evaluate_market_alerts(self, market_data: dict) -> list:
        """
        Evaluate market-related alerts.
        :param market_data: Dictionary of asset prices.
        :return: List of triggered market alert messages.
        """
        return self.evaluate_price_alerts(market_data)

    def evaluate_position_alerts(self, positions: list) -> list:
        """
        Evaluate position-related alerts by checking travel, profit, swing, and blast alerts.
        :param positions: List of position dictionaries.
        :return: List of triggered position alert messages.
        """
        alerts = []
        for pos in positions:
            travel_result = self.evaluate_travel_alert(pos)
            if travel_result is not None:
                state, evaluated_value = travel_result
                if state != "Normal":
                    alerts.append(f"Position ALERT (Travel): {pos.get('id')} travel percent {evaluated_value} => {state}")
            profit_msg = self.evaluate_profit_alert(pos)
            if profit_msg:
                alerts.append(profit_msg)
            swing_msg = self.evaluate_swing_alert(pos)
            if swing_msg:
                alerts.append(swing_msg)
            blast_msg = self.evaluate_blast_alert(pos)
            if blast_msg:
                alerts.append(blast_msg)
        return alerts

    def evaluate_system_alerts(self) -> list:
        """
        Evaluate system-level alerts, such as heartbeat checks.
        :return: List of triggered system alert messages.
        """
        alerts = []
        system_config = self.config.get("system_alerts", {})
        if system_config.get("heartbeat_enabled", False):
            heartbeat = system_config.get("last_heartbeat", 0)
            current_time_val = time.time()
            threshold = system_config.get("heartbeat_threshold", 300)  # seconds
            if current_time_val - heartbeat > threshold:
                msg = "System ALERT: Heartbeat threshold exceeded"
                alerts.append(msg)
                u_logger.log_operation(
                    operation_type="System Alert Triggered",
                    primary_text=msg,
                    source="AlertEvaluator",
                    file="alert_evaluator.py"
                )
        # Additional system checks can be added here.
        return alerts

    # -------------------------
    # Helper Method
    # -------------------------
    def _update_alert_state(self, pos: dict, new_state: str, evaluated_value: float = None):
        """
        Helper method to update the alert record in the DB.
        """
        alert_id = pos.get("alert_reference_id") or pos.get("id")
        if not alert_id:
            u_logger.log_operation(
                operation_type="Update Alert State",
                primary_text="No alert identifier found; update skipped",
                source="AlertEvaluator",
                file="alert_evaluator.py"
            )
            return
        update_fields = {"state": new_state}
        if evaluated_value is not None:
            update_fields["evaluated_value"] = evaluated_value
        try:
            self.data_locker.update_alert_conditions(alert_id, update_fields)
            u_logger.log_operation(
                operation_type="Alert Updated",
                primary_text=f"Alert {alert_id} updated to state '{new_state}' with value {evaluated_value}",
                source="AlertEvaluator",
                file="alert_evaluator.py"
            )
        except Exception as e:
            u_logger.log_operation(
                operation_type="Alert Update Failed",
                primary_text=f"Failed to update alert {alert_id}: {e}",
                source="AlertEvaluator",
                file="alert_evaluator.py"
            )
