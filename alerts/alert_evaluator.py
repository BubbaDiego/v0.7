import logging
import time
from typing import Optional

from config.unified_config_manager import UnifiedConfigManager
from config.config_constants import CONFIG_PATH
from utils.unified_logger import UnifiedLogger
from utils.calc_services import CalcServices
from alerts.alert_enrichment import enrich_alert_data, update_trigger_value_FUCK_ME
from data.models import Alert, AlertType, AlertClass, NotificationType, Status
from uuid import uuid4

u_logger = UnifiedLogger()

class AlertEvaluator:
    def __init__(self, config, data_locker, alert_controller):
        """
        :param config: The loaded configuration.
        :param data_locker: Instance of DataLocker.
        :param alert_controller: Reference to the AlertController for alert creation.
        """
        self.config = config
        self.data_locker = data_locker
        self.alert_controller = alert_controller  # Store reference to AlertController
        self.calc_services = CalcServices()
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
    async def run_update_evaluated_value(self):
        self.logger.info("Updating Evaluated Values for Alerts...")
        try:
            await asyncio.to_thread(self.alert_evaluator.update_alerts_evaluated_value)
            self.u_logger.log_cyclone(
                operation_type="Update Evaluated Value",
                primary_text="Alert evaluated values updated successfully",
                source="Cyclone",
                file="cyclone.py"
            )
            print("Alert evaluated values updated.")
        except Exception as e:
            self.logger.error(f"Updating evaluated values failed: {e}")
            self.u_logger.log_cyclone(
                operation_type="Update Evaluated Value",
                primary_text=f"Failed: {e}",
                source="Cyclone",
                file="cyclone.py"
            )

    def evaluate_profit_alert(self, pos: dict) -> str:
        asset = pos.get("asset_type", "BTC")
        price_record = self.data_locker.get_latest_price(asset)
        if price_record and "current_price" in price_record:
            current_price = float(price_record["current_price"])
        else:
            self._debug_log(f"[Profit Alert] Error: latest price not available for asset {asset}")
            current_price = 0.0

        try:
            entry_price = float(pos.get("entry_price", 0.0))
            size = float(pos.get("size", 0.0))
        except Exception as e:
            self._debug_log(f"[Profit Alert] Error parsing price/size fields: {e}")
            return ""

        position_type = pos.get("position_type", "LONG").upper()
        if entry_price == 0:
            profit_val = 0.0
        elif position_type == "LONG":
            profit_val = (current_price - entry_price) * (size / entry_price)
        else:
            profit_val = (entry_price - current_price) * (size / entry_price)

        self._debug_log(f"[Profit Alert] Calculated profit: {profit_val} for position {pos.get('id')}")
        # Continue with threshold comparisons and updating alerts…
        return f"Profit ALERT: Position {pos.get('id')} profit {profit_val:.2f}"

    def evaluate_swing_alert(self, pos: dict) -> str:
        asset = pos.get("asset_type", "BTC")
        price_record = self.data_locker.get_latest_price(asset)
        if price_record and "current_price" in price_record:
            current_price = float(price_record["current_price"])
        else:
            self._debug_log(f"[Swing Alert] Error: latest price not available for asset {asset}")
            current_price = 0.0

        try:
            liquidation_price = float(pos.get("liquidation_price", 0.0))
        except Exception as e:
            self._debug_log(f"[Swing Alert] Error parsing liquidation_price: {e}")
            return ""

        current_value = self.calc_services.calculate_liquid_distance(current_price, liquidation_price)
        self._debug_log(f"[Swing Alert] Calculated liquidation_distance: {current_value} for asset {asset}")
        # Continue with threshold comparisons and alert updates…
        return f"Swing ALERT: Position {pos.get('id')} liquidation distance {current_value:.2f}"

    def evaluate_blast_alert(self, pos: dict) -> str:
        asset = pos.get("asset_type", "BTC")
        price_record = self.data_locker.get_latest_price(asset)
        if price_record and "current_price" in price_record:
            current_price = float(price_record["current_price"])
        else:
            self._debug_log(f"[Blast Alert] Error: latest price not available for asset {asset}")
            current_price = 0.0

        try:
            liquidation_price = float(pos.get("liquidation_price", 0.0))
        except Exception as e:
            self._debug_log(f"[Blast Alert] Error parsing liquidation_price: {e}")
            return ""

        current_value = self.calc_services.calculate_liquid_distance(current_price, liquidation_price)
        self._debug_log(f"[Blast Alert] Calculated liquidation_distance: {current_value} for asset {asset}")
        # Continue with threshold comparisons and updating the alert level…
        return f"Blast ALERT: Position {pos.get('id')} liquidation distance {current_value:.2f}"

    def evaluate_heat_index_alert(self, pos: dict) -> str:
        asset = pos.get("asset_type", "BTC")
        price_record = self.data_locker.get_latest_price(asset)
        if price_record and "current_price" in price_record:
            current_price = float(price_record["current_price"])
        else:
            self._debug_log(f"[Heat Alert] Error: latest price not available for asset {asset}")
            current_price = 0.0

        try:
            pos_updated = pos.copy()
            pos_updated["current_price"] = current_price
            current_heat = self.calc_services.calculate_composite_risk_index(pos_updated)
            if current_heat is None:
                current_heat = 0.0
        except Exception as e:
            self._debug_log(f"[Heat Alert] Error calculating composite risk index: {e}")
            return ""

        # Load explicit heat index thresholds from configuration
        from utils.json_manager import JsonManager, JsonType
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        heat_config = alert_limits.get("alert_ranges", {}).get("heat_index_ranges", {})
        low_thresh = float(heat_config.get("low", 12.0))
        medium_thresh = float(heat_config.get("medium", 33.0))
        high_thresh = float(heat_config.get("high", 66.0))

        self._debug_log(
            f"[Heat Alert] current_heat = {current_heat}, thresholds: low={low_thresh}, medium={medium_thresh}, high={high_thresh}")

        # Determine alert level based on explicit thresholds:
        if current_heat < low_thresh:
            level = "Normal"
        elif current_heat < medium_thresh:
            level = "Low"
        elif current_heat < high_thresh:
            level = "Medium"
        else:
            level = "High"

        # Determine next trigger threshold based on level:
        if level == "Normal":
            next_trigger = low_thresh
        elif level == "Low":
            next_trigger = medium_thresh
        elif level in ["Medium", "High"]:
            next_trigger = high_thresh
        else:
            next_trigger = 0.0

        self._debug_log(f"[Heat Alert] Determined level: {level}, next trigger should be: {next_trigger}")

        if level == "Normal":
            self._update_alert_level(pos, "Normal", evaluated_value=current_heat,
                                     custom_alert_type=AlertType.HEAT_INDEX.value)
            return ""
        else:
            self._update_alert_level(pos, level, evaluated_value=current_heat,
                                     custom_alert_type=AlertType.HEAT_INDEX.value)
            msg = f"Heat Index ALERT: Position {pos.get('id')} heat index {current_heat:.2f} exceeds threshold (Level: {level}). Next trigger: {next_trigger}"
            self._debug_log(f"[Heat Alert] {msg}")
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

    def evaluate_travel_alert(self, pos: dict):
        """
        Evaluate the Travel Percent for a position, determining its level based on
        absolute value thresholds. Writes detailed debug info to both console and tp_level.txt.
        Updates both the alert record (trigger_value and level) and the position record (travel_percent)
        using the DataLocker’s DB connection, updates the in-memory position dictionary, and
        reads back both the position and alert records for verification.
        """
        debug_file = "tp_level.txt"
        readback_file = "level_test.txt"

        def dbg(message: str):
            print(message)
            try:
                with open(debug_file, "a", encoding="utf-8") as f:
                    f.write(message + "\n")
            except Exception as e:
                print(f"[DEBUG ERROR] Could not write to {debug_file}: {e}")

        def dbg_readback(message: str):
            try:
                with open(readback_file, "a", encoding="utf-8") as f:
                    f.write(message + "\n")
            except Exception as e:
                print(f"[READBACK DEBUG ERROR] Could not write to {readback_file}: {e}")

        dbg("=============================================================")
        dbg(f"[Travel Alert] evaluate_travel_alert called for position ID: {pos.get('id', 'UNKNOWN')}")
        dbg(f"[Travel Alert] Position data: {pos}")

        asset = pos.get("asset_type", "BTC")
        price_record = self.data_locker.get_latest_price(asset)
        if price_record and "current_price" in price_record:
            current_price = float(price_record["current_price"])
            dbg(f"[Travel Alert] Latest price for {asset}: {current_price}")
        else:
            dbg(f"[Travel Alert] Error: no latest price available for asset {asset}. Defaulting to 0.")
            current_price = 0.0

        try:
            entry_price = float(pos.get("entry_price", 0.0))
            liquidation_price = float(pos.get("liquidation_price", 0.0))
            position_type = pos.get("position_type", "LONG").upper()
            dbg(f"[Travel Alert] entry_price={entry_price}, liquidation_price={liquidation_price}, position_type={position_type}")
        except Exception as e:
            self.u_logger.log_operation(
                operation_type="Alert Evaluation Error",
                primary_text=f"Error parsing price fields for travel alert: {e}",
                source="AlertEvaluator",
                file="alert_evaluator.py"
            )
            dbg(f"[Travel Alert] Exception reading position fields: {e}")
            return None

        # 1) Calculate travel_percent.
        travel_percent = self.calc_services.calculate_travel_percent(
            position_type, entry_price, current_price, liquidation_price
        )
        dbg(f"[Travel Alert] Computed travel_percent = {travel_percent}")
        current_val = travel_percent
        abs_val = abs(current_val)
        dbg(f"[Travel Alert] Absolute value of travel_percent = {abs_val}")

        # 2) Retrieve thresholds from config, converting them to positive values.
        tp_config = self.config.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
        try:
            low_threshold = abs(float(tp_config.get("low", -25.0)))
            medium_threshold = abs(float(tp_config.get("medium", -50.0)))
            high_threshold = abs(float(tp_config.get("high", -75.0)))
            dbg(f"[Travel Alert] Thresholds (positive) => Low={low_threshold}, Medium={medium_threshold}, High={high_threshold}")
        except Exception as e:
            dbg(f"[Travel Alert] Error parsing threshold config: {e}")
            low_threshold, medium_threshold, high_threshold = 25.0, 50.0, 75.0

        # 3) Determine alert level based on the absolute travel percent.
        if current_val >= 0:
            level = "Normal"
            dbg("[Travel Alert] current_val >= 0 => level=Normal")
        else:
            if abs_val < low_threshold:
                level = "Normal"
                dbg(f"[Travel Alert] abs_val < {low_threshold} => level=Normal")
            elif abs_val < medium_threshold:
                level = "Low"
                dbg(f"[Travel Alert] abs_val < {medium_threshold} => level=Low")
            elif abs_val < high_threshold:
                level = "Medium"
                dbg(f"[Travel Alert] abs_val < {high_threshold} => level=Medium")
            else:
                level = "High"
                dbg(f"[Travel Alert] abs_val >= {high_threshold} => level=High")

        dbg(f"[Travel Alert] Final determined level: {level}")

        # 4) Determine the next negative trigger value from the config.
        try:
            neg_low = float(tp_config.get("low", -25.0))
            neg_med = float(tp_config.get("medium", -50.0))
            neg_high = float(tp_config.get("high", -75.0))
            dbg(f"[Travel Alert] Negative thresholds => Low={neg_low}, Medium={neg_med}, High={neg_high}")
        except Exception as e:
            dbg(f"[Travel Alert] Error retrieving negative thresholds: {e}")
            neg_low, neg_med, neg_high = -25.0, -50.0, -75.0

        if level == "Normal":
            next_trigger = neg_low
        elif level == "Low":
            next_trigger = neg_med
        else:  # For Medium or High levels.
            next_trigger = neg_high

        dbg(f"[Travel Alert] Next trigger value set to {next_trigger} based on level={level}")

        # 5) Update the alert record's trigger_value and level if an alert_reference_id exists.
        alert_id = pos.get("alert_reference_id")
        if alert_id:
            update_fields = {"trigger_value": next_trigger, "level": level}
            dbg(f"[Travel Alert] Attempting to update alert {alert_id} with {update_fields}")
            try:
                self.data_locker.update_alert_conditions(alert_id, update_fields)
                dbg(f"[Travel Alert] Successfully updated alert {alert_id} with trigger_value {next_trigger} and level {level}")
            except Exception as e:
                dbg(f"[Travel Alert] Failed to update alert {alert_id}: {e}")
            # Read back alert record
            try:
                cursor = self.data_locker.conn.cursor()
                cursor.execute("SELECT level, trigger_value FROM alerts WHERE id=?", (alert_id,))
                alert_row = cursor.fetchone()
                if alert_row:
                    dbg(f"[Travel Alert] Read-back alert: level = {alert_row['level']}, trigger_value = {alert_row['trigger_value']}")
                    dbg_readback(
                        f"Alert {alert_id}: level = {alert_row['level']}, trigger_value = {alert_row['trigger_value']}")
                else:
                    dbg("[Travel Alert] Read-back: No alert record found.")
                    dbg_readback(f"Alert {alert_id}: No record found during read-back")
            except Exception as e:
                dbg(f"[Travel Alert] Exception during alert record read-back: {e}")
                dbg_readback(f"Alert {alert_id}: Exception during read-back: {e}")
        else:
            dbg("[Travel Alert] No alert_reference_id found; skipping alert record update.")

        # 6) Update the position record with the newly computed travel_percent.
        try:
            cursor = self.data_locker.conn.cursor()
            cursor.execute("UPDATE positions SET travel_percent=? WHERE id=?", (current_val, pos.get("id")))
            self.data_locker.conn.commit()
            pos["travel_percent"] = current_val
            dbg(f"[Travel Alert] Successfully updated position {pos.get('id')} travel_percent to {current_val}")
        except Exception as e:
            dbg(f"[Travel Alert] Failed to update position travel_percent: {e}")

        # 7) Read back from DB for position verification.
        try:
            cursor.execute("SELECT travel_percent FROM positions WHERE id=?", (pos.get("id"),))
            row = cursor.fetchone()
            if row:
                readback_value = row["travel_percent"]
                dbg(f"[Travel Alert] Read-back: DB travel_percent for {pos.get('id')} = {readback_value}")
                dbg_readback(f"Position {pos.get('id')}: travel_percent = {readback_value}")
            else:
                dbg("[Travel Alert] Read-back: No row found for position update.")
                dbg_readback(f"Position {pos.get('id')}: No row found during read-back")
        except Exception as e:
            dbg(f"[Travel Alert] Exception during position read-back: {e}")
            dbg_readback(f"Position {pos.get('id')}: Exception during read-back: {e}")

        dbg(f"[Travel Alert] Returning => (level={level}, travel_percent={current_val})")
        dbg("=============================================================\n")
        return level, current_val

    def update_alerts_evaluated_value(self):
        """
        Updates the evaluated_value for each alert based on its alert type.

        - For PriceThreshold alerts, sets evaluated_value to the latest asset price.
        - For TravelPercent alerts, sets evaluated_value to the position's travel percent.
        - For Profit alerts, sets evaluated_value to the position's pnl_after_fees_usd.
        - For HeatIndex alerts, sets evaluated_value to the position's current_heat_index.
        """
        alerts = self.data_locker.get_alerts()
        positions = self.data_locker.read_positions()
        pos_lookup = {pos.get("id"): pos for pos in positions}

        for alert in alerts:
            evaluated_val = 0.0
            alert_type = alert.get("alert_type", "")
            if alert_type == AlertType.PRICE_THRESHOLD.value:
                asset_type = alert.get("asset_type", "BTC")
                price_data = self.data_locker.get_latest_price(asset_type)
                if price_data and "current_price" in price_data:
                    try:
                        evaluated_val = float(price_data["current_price"])
                    except Exception as e:
                        self.logger.error(f"Error converting latest price for asset {asset_type}: {e}", exc_info=True)
            elif alert_type == AlertType.TRAVEL_PERCENT_LIQUID.value:
                pos_id = alert.get("position_reference_id") or alert.get("position_id")
                if pos_id and pos_id in pos_lookup:
                    try:
                        # Use "travel_percent" instead of "current_travel_percent"
                        evaluated_val = float(pos_lookup[pos_id].get("travel_percent", 0))
                    except Exception as e:
                        self.logger.error(f"Error retrieving travel percent for position {pos_id}: {e}", exc_info=True)
            elif alert_type == AlertType.PROFIT.value:
                pos_id = alert.get("position_reference_id") or alert.get("position_id")
                if pos_id and pos_id in pos_lookup:
                    try:
                        evaluated_val = float(pos_lookup[pos_id].get("pnl_after_fees_usd", 0))
                    except Exception as e:
                        self.logger.error(f"Error retrieving pnl for position {pos_id}: {e}", exc_info=True)
            elif alert_type == AlertType.HEAT_INDEX.value:
                pos_id = alert.get("position_reference_id") or alert.get("position_id")
                if pos_id and pos_id in pos_lookup:
                    try:
                        evaluated_val = float(pos_lookup[pos_id].get("current_heat_index", 0))
                    except Exception as e:
                        self.logger.error(f"Error retrieving heat index for position {pos_id}: {e}", exc_info=True)

            try:
                self.data_locker.update_alert_conditions(alert.get("id"), {"evaluated_value": evaluated_val})
                self.logger.info(f"Updated alert {alert.get('id')} evaluated_value to {evaluated_val}")
            except Exception as update_ex:
                self.logger.error(f"Failed to update evaluated_value for alert {alert.get('id')}: {update_ex}",
                                  exc_info=True)

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

    def evaluate_global_alerts(self, positions: list, market_data: dict) -> dict:
        """
        Evaluates global alert conditions based on the configured global thresholds.
        This method aggregates data from positions and market feeds and compares the
        values against global thresholds defined in the configuration.

        Parameters:
            positions (list): List of position dictionaries.
            market_data (dict): Dictionary of asset prices, e.g., {"BTC": 45000, "ETH": 3000}.

        Returns:
            dict: A dictionary with keys for each metric (e.g., 'price', 'profit')
                  and concatenated alert messages if thresholds are exceeded.
        """
        print("----------------------------------------------------------------------------------------")
        self.logger.debug("Starting global alert evaluation")
        global_config = self.config.get("global_alert_config", {})
        if not global_config.get("enabled", False):
            self.logger.debug("Global alerts not enabled in config")
            return {}

        thresholds = global_config.get("thresholds", {})
        data_fields = global_config.get("data_fields", {})
        alerts = {}

        # Evaluate global price alerts
        if data_fields.get("price", False):
            self.logger.debug("Evaluating global price alerts")
            price_thresholds = thresholds.get("price", {})
            price_alert_messages = []
            for asset, current_price in market_data.items():
                threshold = price_thresholds.get(asset)
                self.logger.debug(f"Asset {asset}: current price = {current_price}, threshold = {threshold}")
                if threshold is not None and current_price >= threshold:
                    msg = f"{asset} price {current_price} >= {threshold}"
                    self.logger.debug("Price alert triggered: " + msg)
                    price_alert_messages.append(msg)
            if price_alert_messages:
                alerts["price"] = "; ".join(price_alert_messages)
        else:
            self.logger.debug("Global price alerts not enabled in data_fields")

        # Evaluate global profit alerts
        if data_fields.get("profit", False):
            self.logger.debug("Evaluating global profit alerts")
            profit_threshold = thresholds.get("profit", float('inf'))
            profit_alert_messages = []
            for pos in positions:
                try:
                    profit = float(pos.get("pnl_after_fees_usd", 0))
                except Exception as e:
                    self.logger.error("Error parsing profit for position {}: {}".format(pos.get("id"), e))
                    profit = 0.0
                self.logger.debug(f"Position {pos.get('id')}: profit = {profit}, threshold = {profit_threshold}")
                if profit >= profit_threshold:
                    msg = f"Pos {pos.get('id')} profit {profit} >= {profit_threshold}"
                    self.logger.debug("Profit alert triggered: " + msg)
                    profit_alert_messages.append(msg)
            if profit_alert_messages:
                alerts["profit"] = "; ".join(profit_alert_messages)
        else:
            self.logger.debug("Global profit alerts not enabled in data_fields")

        # Evaluate global travel percent alerts
        if data_fields.get("travel_percent", False):
            self.logger.debug("Evaluating global travel percent alerts")
            travel_threshold = thresholds.get("travel_percent", 0)
            travel_alert_messages = []
            for pos in positions:
                try:
                    travel_percent = float(pos.get("travel_percent", 0))
                except Exception as e:
                    self.logger.error("Error parsing travel_percent for position {}: {}".format(pos.get("id"), e))
                    travel_percent = 0.0
                self.logger.debug(
                    f"Position {pos.get('id')}: travel_percent = {travel_percent}, threshold = {travel_threshold}")
                if travel_percent <= travel_threshold:
                    msg = f"Pos {pos.get('id')} travel percent {travel_percent} <= {travel_threshold}"
                    self.logger.debug("Travel percent alert triggered: " + msg)
                    travel_alert_messages.append(msg)
            if travel_alert_messages:
                alerts["travel_percent"] = "; ".join(travel_alert_messages)
        else:
            self.logger.debug("Global travel_percent alerts not enabled in data_fields")

        # Evaluate global heat index alerts
        if data_fields.get("heat_index", False):
            self.logger.debug("Evaluating global heat index alerts")
            heat_threshold = thresholds.get("heat_index", float('inf'))
            heat_alert_messages = []
            for pos in positions:
                try:
                    heat_index = float(pos.get("current_heat_index", 0))
                except Exception as e:
                    self.logger.error("Error parsing heat_index for position {}: {}".format(pos.get("id"), e))
                    heat_index = 0.0
                self.logger.debug(f"Position {pos.get('id')}: heat_index = {heat_index}, threshold = {heat_threshold}")
                if heat_index >= heat_threshold:
                    msg = f"Pos {pos.get('id')} heat index {heat_index} >= {heat_threshold}"
                    self.logger.debug("Heat index alert triggered: " + msg)
                    heat_alert_messages.append(msg)
            if heat_alert_messages:
                alerts["heat_index"] = "; ".join(heat_alert_messages)
        else:
            self.logger.debug("Global heat_index alerts not enabled in data_fields")

        self.logger.debug("Global alert evaluation complete with alerts: " + str(alerts))
        return alerts

    def _update_alert_level(self, pos: dict, new_level: str, evaluated_value: Optional[float] = None,
                            custom_alert_type: str = None):
        alert_id = pos.get("alert_reference_id")
        # Check if alert_reference_id is missing or empty.
        if not alert_id or (isinstance(alert_id, str) and alert_id.strip() == ""):
            self._debug_log("[AlertEvaluator] No alert_reference_id found. Creating new alert record.")
            new_alert_type = custom_alert_type if custom_alert_type is not None else AlertType.TRAVEL_PERCENT_LIQUID.value
            if new_alert_type == AlertType.HEAT_INDEX.value:
                new_trigger = pos.get("heat_index_trigger", 12.0)
            else:
                new_trigger = pos.get("travel_percent", 0.0)
            # Retrieve position_type from position; default to "LONG"
            position_type = pos.get("position_type", "LONG").upper()
            new_alert = DummyPositionAlert(
                new_alert_type,
                pos.get("asset_type", "BTC"),
                new_trigger,
                "BELOW",
                "Call",
                pos.get("id"),
                position_type
            )
            created = self.alert_controller.create_alert(new_alert)
            if created:
                pos["alert_reference_id"] = new_alert.id
                conn = self.data_locker.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (new_alert.id, pos.get("id")))
                conn.commit()
                alert_id = new_alert.id
                self._debug_log(
                    f"[AlertEvaluator] Created new alert with id {new_alert.id} for position {pos.get('id')}.")
            else:
                self._debug_log("[AlertEvaluator] Failed to create new alert record.")
                return

        old_level = pos.get("level", "Normal")
        update_fields = {"level": new_level}
        if evaluated_value is not None:
            update_fields["evaluated_value"] = evaluated_value
        if pos.get("alert_reference_id") and pos.get("id"):
            update_fields["position_reference_id"] = pos.get("id")

        self._debug_log(f"[AlertEvaluator] Updating alert '{alert_id}' with fields: {update_fields}")
        try:
            num_updated = self.data_locker.update_alert_conditions(alert_id, update_fields)
            if num_updated == 0:
                self._debug_log(f"[AlertEvaluator] No alert record found for id '{alert_id}'.")
            else:
                self._debug_log(f"[AlertEvaluator] Successfully updated alert '{alert_id}' to level '{new_level}'.")
        except Exception as e:
            self._debug_log(f"[AlertEvaluator] Exception while updating alert '{alert_id}': {e}")


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

    def evaluate_global_alerts(self, positions: list, market_data: dict) -> dict:
        """
        Evaluates global alert conditions based on the configured global thresholds.
        This method aggregates data from positions and market feeds and compares the
        values against global thresholds defined in the configuration.

        Parameters:
            positions (list): List of position dictionaries.
            market_data (dict): Dictionary of asset prices, e.g., {"BTC": 45000, "ETH": 3000}.

        Returns:
            dict: A dictionary where keys are metric names (e.g., 'price', 'profit') and
                  values are concatenated alert messages if thresholds are exceeded.
        """
        global_config = self.config.get("global_alert_config", {})
        if not global_config.get("enabled", False):
            return {}

        thresholds = global_config.get("thresholds", {})
        data_fields = global_config.get("data_fields", {})

        alerts = {}

        # Evaluate global price alerts using market data
        if data_fields.get("price", False):
            price_thresholds = thresholds.get("price", {})
            price_alert_messages = []
            for asset, current_price in market_data.items():
                threshold = price_thresholds.get(asset)
                if threshold is not None and current_price >= threshold:
                    price_alert_messages.append(f"{asset} price {current_price} >= {threshold}")
            if price_alert_messages:
                alerts["price"] = "; ".join(price_alert_messages)

        # Evaluate global profit alerts from positions
        if data_fields.get("profit", False):
            profit_threshold = thresholds.get("profit", float('inf'))
            profit_alert_messages = []
            for pos in positions:
                try:
                    profit = float(pos.get("pnl_after_fees_usd", 0))
                except Exception:
                    profit = 0.0
                if profit >= profit_threshold:
                    profit_alert_messages.append(f"Pos {pos.get('id')} profit {profit} >= {profit_threshold}")
            if profit_alert_messages:
                alerts["profit"] = "; ".join(profit_alert_messages)

        # Evaluate global travel percent alerts from positions
        if data_fields.get("travel_percent", False):
            travel_threshold = thresholds.get("travel_percent", 0)
            travel_alert_messages = []
            for pos in positions:
                try:
                    travel_percent = float(pos.get("travel_percent", 0))
                except Exception:
                    travel_percent = 0.0
                # Assuming threshold is negative (e.g., -30.0), alert if travel_percent is less than or equal to it
                if travel_percent <= travel_threshold:
                    travel_alert_messages.append(
                        f"Pos {pos.get('id')} travel percent {travel_percent} <= {travel_threshold}")
            if travel_alert_messages:
                alerts["travel_percent"] = "; ".join(travel_alert_messages)

        # Evaluate global heat index alerts from positions
        if data_fields.get("heat_index", False):
            heat_threshold = thresholds.get("heat_index", float('inf'))
            heat_alert_messages = []
            for pos in positions:
                try:
                    heat_index = float(pos.get("current_heat_index", 0))
                except Exception:
                    heat_index = 0.0
                if heat_index >= heat_threshold:
                    heat_alert_messages.append(f"Pos {pos.get('id')} heat index {heat_index} >= {heat_threshold}")
            if heat_alert_messages:
                alerts["heat_index"] = "; ".join(heat_alert_messages)

        return alerts

