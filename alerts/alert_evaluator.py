import logging
import time
from config.unified_config_manager import UnifiedConfigManager
from config.config_constants import CONFIG_PATH
from utils.unified_logger import UnifiedLogger
from alerts.alert_enrichment import enrich_alert_data
from data.models import Alert, AlertType, AlertClass, NotificationType, Status
from uuid import uuid4

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
        self.logger = logging.getLogger("AlertEvaluatorLogger")

    def _debug_log(self, message: str):
        """Helper method to print messages to console and write to a debug log file."""
        print(message)
        try:
            with open("alert_evaluator_debug.log", "a") as f:
                f.write(message + "\n")
        except Exception as e:
            print(f"Error writing to debug log file: {e}")

    # -------------------------
    # Subordinate Evaluation Methods
    # -------------------------
    def evaluate_travel_alert(self, pos: dict):
        """
        Evaluate the travel percent alert based on configuration thresholds.
        Returns a tuple (level, evaluated_value) or None if evaluation cannot be done.
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
            current_val = float(pos.get("travel_percent", 0.0))
        except Exception as e:
            u_logger.log_operation(
                operation_type="Alert Evaluation Error",
                primary_text=f"Error parsing travel percent: {e}",
                source="AlertEvaluator",
                file="alert_evaluator.py"
            )
            return None

        before_log = (f"[Travel Alert] BEFORE: travel_percent = {current_val}, "
                      f"thresholds -> low: {low_threshold}, medium: {medium_threshold}, high: {high_threshold}")
        print("\033[94m" + before_log + "\033[0m")
        u_logger.log_operation(
            operation_type="Alert Evaluation",
            primary_text=before_log,
            source="AlertEvaluator",
            file="alert_evaluator.py"
        )

        # Determine level based on thresholds
        if current_val >= 0:
            level = "Normal"
            color = "\033[0m"
        elif current_val <= high_threshold:
            level = "High"
            color = "\033[91m"
        elif current_val <= medium_threshold:
            level = "Medium"
            color = "\033[93m"
        elif current_val <= low_threshold:
            level = "Low"
            color = "\033[92m"
        else:
            level = "Normal"
            color = "\033[0m"

        after_log = f"[Travel Alert] AFTER: Evaluated level = '{level}' for travel_percent = {current_val}"
        print(color + after_log + "\033[0m")
        u_logger.log_operation(
            operation_type="Alert Evaluation",
            primary_text=after_log,
            source="AlertEvaluator",
            file="alert_evaluator.py"
        )

        return level, current_val

    def evaluate_profit_alert(self, pos: dict) -> str:
        """
        Evaluate profit alert for a position.
        Returns a message if triggered, else an empty string.
        """
        asset_code = pos.get("asset_type", "???").upper()
        asset_full = asset_code
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        try:
            profit_val = float(pos.get("profit", 0.0))
        except Exception:
            return ""
        self._debug_log(f"[Profit Alert] Initial profit value: {profit_val} for position {position_id}")

        if profit_val <= 0:
            self._debug_log(f"[Profit Alert] Profit value <= 0. Setting level to Normal for position {position_id}")
            self._update_alert_level(pos, "Normal", evaluated_value=profit_val)
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

        self._debug_log(
            f"[Profit Alert] profit: {profit_val}, thresholds -> low: {low_thresh}, medium: {med_thresh}, high: {high_thresh}")

        if profit_val < low_thresh:
            self._debug_log(
                f"[Profit Alert] Profit {profit_val} is below low threshold {low_thresh}. Setting level to Normal.")
            self._update_alert_level(pos, "Normal", evaluated_value=profit_val)
            return ""
        elif profit_val < med_thresh:
            current_level = "Low"
        elif profit_val < high_thresh:
            current_level = "Medium"
        else:
            current_level = "High"

        self._debug_log(f"[Profit Alert] Evaluated level: {current_level} for profit value: {profit_val}")
        self._update_alert_level(pos, current_level, evaluated_value=profit_val)
        profit_key = f"profit-{asset_full}-{position_type}-{position_id}"
        now = time.time()
        last_time = self.last_triggered.get(profit_key, 0)
        if now - last_time < self.cooldown:
            self.suppressed_count += 1
            self._debug_log(f"[Profit Alert] Alert for {position_id} suppressed due to cooldown.")
            return ""
        self.last_triggered[profit_key] = now
        msg = f"Profit ALERT: {asset_full} {position_type} profit of {profit_val:.2f} (Level: {current_level})"
        self._debug_log(f"[Profit Alert] Final message: {msg}")
        return msg

    def evaluate_swing_alert(self, pos: dict) -> str:
        """
        Evaluate swing alert for a position.
        Returns a message if triggered, else an empty string.
        """
        swing_config = self.config.get("alert_ranges", {}).get("swing_alerts",
                                                               {"enabled": True, "notifications": {"call": True}})
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
        self._debug_log(
            f"[Swing Alert] liquidation_distance: {current_value}, threshold for {asset}: {swing_threshold}")
        if current_value >= swing_threshold:
            self._debug_log(
                f"[Swing Alert] Condition met. Updating alert level to 'High' for position {position_id} with value {current_value}")
            self._update_alert_level(pos, "High", evaluated_value=current_value)
            key = f"swing-{asset_full}-{position_type}-{position_id}"
            now = time.time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                msg = (f"Average Daily Swing ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                       f"Actual Value = {current_value:.2f} exceeds threshold {swing_threshold:.2f}")
                self._debug_log(f"[Swing Alert] Final message: {msg}")
                return msg
        return ""

    def evaluate_blast_alert(self, pos: dict) -> str:
        """
        Evaluate blast alert for a position.
        Returns a message if triggered, else an empty string.
        """
        blast_config = self.config.get("alert_ranges", {}).get("blast_alerts",
                                                               {"enabled": True, "notifications": {"call": True}})
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
        self._debug_log(f"[Blast Alert] liquidation_distance: {current_value}, blast threshold: {blast_threshold}")
        if current_value >= blast_threshold:
            self._debug_log(
                f"[Blast Alert] Condition met. Updating alert level to 'High' for position {position_id} with value {current_value}")
            self._update_alert_level(pos, "High", evaluated_value=current_value)
            key = f"blast-{asset_full}-{position_type}-{position_id}"
            now = time.time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                msg = (f"One Day Blast Radius ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                       f"Actual Value = {current_value:.2f} exceeds threshold {blast_threshold:.2f}")
                self._debug_log(f"[Blast Alert] Final message: {msg}")
                return msg
        return ""

    def evaluate_heat_index_alert(self, pos: dict) -> str:
        """
        Evaluate heat index alert for a position.
        Returns a message if triggered, else an empty string.
        """
        print(f"[DEBUG] evaluate_heat_index_alert: Evaluating position with id: {pos.get('id')}")
        try:
            current_heat = float(pos.get("current_heat_index", 0.0))
            print(f"[DEBUG] evaluate_heat_index_alert: current_heat = {current_heat}")
        except Exception as e:
            self._debug_log(f"[Heat Alert] Error parsing heat index: {e}")
            return ""
        try:
            trigger_value = float(pos.get("heat_index_trigger", 12.0))
            print(f"[DEBUG] evaluate_heat_index_alert: trigger_value = {trigger_value}")
        except Exception:
            trigger_value = 12.0
            print(f"[DEBUG] evaluate_heat_index_alert: Using default trigger_value = {trigger_value}")

        self._debug_log(f"[Heat Alert] current_heat = {current_heat}, trigger_value = {trigger_value}")

        if current_heat <= trigger_value:
            print(
                "[DEBUG] evaluate_heat_index_alert: current_heat is below or equal to trigger, setting level to Normal.")
            self._update_alert_level(pos, "Normal", evaluated_value=current_heat,
                                     custom_alert_type=AlertType.HEAT_INDEX.value)
            return ""
        if current_heat < trigger_value * 1.5:
            current_level = "Low"
        elif current_heat < trigger_value * 2:
            current_level = "Medium"
        else:
            current_level = "High"

        print(f"[DEBUG] evaluate_heat_index_alert: Determined alert level as {current_level}")
        self._update_alert_level(pos, current_level, evaluated_value=current_heat,
                                 custom_alert_type=AlertType.HEAT_INDEX.value)
        msg = (f"Heat Index ALERT: Position {pos.get('id')} heat index {current_heat:.2f} "
               f"exceeds trigger {trigger_value} (Level: {current_level})")
        self._debug_log(f"[Heat Alert] {msg}")
        print(f"[DEBUG] evaluate_heat_index_alert: {msg}")
        return msg

    def enrich_alert(self, alert: dict) -> dict:
        """
        Enrich the alert by delegating to the shared enrichment routine.
        """
        enriched_alert = enrich_alert_data(alert, self.data_locker, self.logger)
        return enriched_alert



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
                self._debug_log(f"[Market Alert] {asset}: current price: {price}, trigger value: {trigger_val}, condition: {condition}")
                if (condition == "ABOVE" and price >= trigger_val) or (condition == "BELOW" and price <= trigger_val):
                    msg = f"Market ALERT: {asset} price {price} meets condition {condition} {trigger_val}"
                    alerts.append(msg)
                    u_logger.log_operation(
                        operation_type="Market Alert Triggered",
                        primary_text=msg,
                        source="AlertEvaluator",
                        file="alert_evaluator.py"
                    )
                    self._debug_log(f"[Market Alert] Triggered message: {msg}")
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
        Evaluate position-related alerts by checking travel, profit, swing, blast, and heat index alerts.
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
            heat_msg = self.evaluate_heat_index_alert(pos)
            if heat_msg:
                alerts.append(heat_msg)
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
            threshold = system_config.get("heartbeat_threshold", 300)
            if current_time_val - heartbeat > threshold:
                msg = "System ALERT: Heartbeat threshold exceeded"
                alerts.append(msg)
                u_logger.log_operation(
                    operation_type="System Alert Triggered",
                    primary_text=msg,
                    source="AlertEvaluator",
                    file="alert_evaluator.py"
                )
                self._debug_log(f"[System Alert] {msg}")
        return alerts

    def evaluate_heat_index_alert(self, pos: dict) -> str:
        """
        Evaluate heat index alert for a position.
        Returns a message if triggered, else an empty string.
        """
        print(f"[DEBUG] evaluate_heat_index_alert: Evaluating position with id: {pos.get('id')}")
        try:
            current_heat = float(pos.get("current_heat_index", 0.0))
            print(f"[DEBUG] evaluate_heat_index_alert: current_heat = {current_heat}")
        except Exception as e:
            self._debug_log(f"[Heat Alert] Error parsing heat index: {e}")
            return ""
        try:
            trigger_value = float(pos.get("heat_index_trigger", 12.0))
            print(f"[DEBUG] evaluate_heat_index_alert: trigger_value = {trigger_value}")
        except Exception:
            trigger_value = 12.0
            print(f"[DEBUG] evaluate_heat_index_alert: Using default trigger_value = {trigger_value}")

        self._debug_log(f"[Heat Alert] current_heat = {current_heat}, trigger_value = {trigger_value}")

        if current_heat <= trigger_value:
            print("[DEBUG] evaluate_heat_index_alert: current_heat is below or equal to trigger, setting state to Normal.")
            self._update_alert_level(pos, "Normal", evaluated_value=current_heat, custom_alert_type=AlertType.HEAT_INDEX.value)
            return ""
        if current_heat < trigger_value * 1.5:
            current_level = "Low"
        elif current_heat < trigger_value * 2:
            current_level = "Medium"
        else:
            current_level = "High"

        print(f"[DEBUG] evaluate_heat_index_alert: Determined alert level as {current_level}")
        self._update_alert_level(pos, current_level, evaluated_value=current_heat, custom_alert_type=AlertType.HEAT_INDEX.value)
        msg = (f"Heat Index ALERT: Position {pos.get('id')} heat index {current_heat:.2f} "
               f"exceeds trigger {trigger_value} (Level: {current_level})")
        self._debug_log(f"[Heat Alert] {msg}")
        print(f"[DEBUG] evaluate_heat_index_alert: {msg}")
        return msg

    def _update_alert_level(self, pos: dict, new_level: str, evaluated_value: float = None,
                            custom_alert_type: str = None):
        alert_id = pos.get("alert_reference_id")
        if not alert_id:
            u_logger.log_operation(
                operation_type="Alert Update Skipped",
                primary_text="No alert_reference_id found for position. Creating new alert record.",
                source="AlertEvaluator",
                file="alert_evaluator.py"
            )
            print("[DEBUG] _update_alert_level: No alert_reference_id found. Creating new alert record.")
            new_alert_type = custom_alert_type if custom_alert_type is not None else AlertType.TRAVEL_PERCENT_LIQUID.value
            if new_alert_type == AlertType.HEAT_INDEX.value:
                new_trigger = pos.get("heat_index_trigger", 12.0)
            else:
                new_trigger = pos.get("travel_percent", 0.0)
            new_alert = Alert(
                id=str(uuid4()),
                alert_type=new_alert_type,
                alert_class=AlertClass.POSITION.value,
                trigger_value=new_trigger,
                notification_type=NotificationType.ACTION.value,
                last_triggered=None,
                status=Status.ACTIVE.value,
                frequency=1,
                counter=0,
                liquidation_distance=pos.get("liquidation_distance", 0.0),
                travel_percent=pos.get("travel_percent", 0.0),
                liquidation_price=pos.get("liquidation_price", 0.0),
                notes="Auto-created alert record",
                position_reference_id=pos.get("id"),
                level=new_level,
                evaluated_value=evaluated_value or 0.0
            )
            created = self.create_alert(new_alert)
            if created:
                pos["alert_reference_id"] = new_alert.id
                conn = self.data_locker.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (new_alert.id, pos.get("id")))
                conn.commit()
                alert_id = new_alert.id
                u_logger.log_operation(
                    operation_type="Alert Creation",
                    primary_text=f"Created new alert record for position {pos.get('id')} with alert id {new_alert.id}",
                    source="AlertEvaluator",
                    file="alert_evaluator.py"
                )
                print(
                    f"[DEBUG] _update_alert_level: Created new alert with id {new_alert.id} and updated position record.")
            else:
                u_logger.log_operation(
                    operation_type="Alert Creation Failed",
                    primary_text=f"Failed to create new alert record for position {pos.get('id')}",
                    source="AlertEvaluator",
                    file="alert_evaluator.py"
                )
                print("[DEBUG] _update_alert_level: Failed to create new alert record.")
                return

        update_fields = {"level": new_level}
        if evaluated_value is not None:
            update_fields["evaluated_value"] = evaluated_value

        if pos.get("alert_reference_id") and pos.get("id"):
            update_fields["position_reference_id"] = pos.get("id")

        # --- Updated: Set the trigger_value to the next threshold for travel percent alerts ---
        if custom_alert_type is None or custom_alert_type == AlertType.TRAVEL_PERCENT_LIQUID.value:
            tp_config = self.config.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
            try:
                low_threshold = float(tp_config.get("low", -25.0))
                medium_threshold = float(tp_config.get("medium", -50.0))
                high_threshold = float(tp_config.get("high", -75.0))
            except Exception as e:
                low_threshold, medium_threshold, high_threshold = -25.0, -50.0, -75.0
            if new_level == "Normal":
                next_trigger = low_threshold
            elif new_level == "Low":
                next_trigger = medium_threshold
            elif new_level == "Medium":
                next_trigger = high_threshold
            elif new_level == "High":
                next_trigger = high_threshold
            else:
                next_trigger = update_fields.get("trigger_value", 0.0)
            update_fields["trigger_value"] = next_trigger
        # --- End updated block ---

        print(f"[DEBUG] _update_alert_level: Updating alert '{alert_id}' with fields: {update_fields}")
        u_logger.log_operation(
            operation_type="Alert Level Update",
            primary_text=f"Updating alert '{alert_id}' with {update_fields}",
            source="AlertEvaluator",
            file="alert_evaluator.py"
        )
        try:
            num_updated = self.data_locker.update_alert_conditions(alert_id, update_fields)
            print(f"[DEBUG] _update_alert_level: Number of rows updated: {num_updated}")
            if num_updated == 0:
                u_logger.log_operation(
                    operation_type="Alert Update",
                    primary_text=f"No alert record found for id '{alert_id}' even after creation.",
                    source="AlertEvaluator",
                    file="alert_evaluator.py"
                )
                print(f"[DEBUG] _update_alert_level: No alert record found for id '{alert_id}'.")
            else:
                u_logger.log_operation(
                    operation_type="Alert Level Updated",
                    primary_text=f"Updated alert '{alert_id}' to level '{new_level}' with evaluated value '{evaluated_value}'.",
                    source="AlertEvaluator",
                    file="alert_evaluator.py"
                )
                print(f"[DEBUG] _update_alert_level: Successfully updated alert '{alert_id}' to level '{new_level}'.")
        except Exception as e:
            u_logger.log_operation(
                operation_type="Alert Update Error",
                primary_text=f"Error updating alert level for id '{alert_id}': {e}",
                source="AlertEvaluator",
                file="alert_evaluator.py"
            )
            print(f"[DEBUG] _update_alert_level: Exception while updating alert '{alert_id}': {e}")


def create_alert(self, alert_obj) -> bool:
    """
    Delegate alert creation to the data locker.
    Converts the alert object to a dictionary if necessary.
    This patch ensures that DataLocker.data_locker is set.
    """
    try:
        # Patch DataLocker: if it doesn't have 'data_locker', assign it to itself.
        if not hasattr(self.data_locker, "data_locker"):
            self.data_locker.data_locker = self.data_locker
        if not hasattr(self.data_locker, "initialize_alert_data"):
            self.data_locker.initialize_alert_data = lambda x: x
        if isinstance(alert_obj, dict):
            return self.data_locker.create_alert(alert_obj)
        elif hasattr(alert_obj, "to_dict"):
            return self.data_locker.create_alert(alert_obj.to_dict())
        else:
            # Fallback: convert using the object's __dict__
            return self.data_locker.create_alert(alert_obj.__dict__)
    except Exception as e:
        self._debug_log(f"[DEBUG] create_alert: Error creating alert: {e}")
        return False

