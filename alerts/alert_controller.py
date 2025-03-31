from data.data_locker import DataLocker
from utils.json_manager import JsonManager, JsonType
from uuid import uuid4
from data.models import Alert, AlertType, AlertClass, NotificationType, Status
from typing import Optional
import logging
import sqlite3
from utils.unified_logger import UnifiedLogger
from utils.update_ledger import log_alert_update
from alerts.alert_enrichment import enrich_alert_data

from uuid import uuid4
from data.models import Status  # Ensure Status is imported

# Global DummyPositionAlert definition to be used across all position alert creation methods.
class DummyPositionAlert:
    def __init__(self, alert_type, asset_type, trigger_value, condition, notification_type, position_reference_id):
        self.id = str(uuid4())
        self.alert_type = alert_type  # e.g., using model values like "PriceThreshold", "TravelPercent", "Profit", "HeatIndex"
        self.alert_class = "Position"  # default for position alerts; might be updated later
        self.asset_type = asset_type   # e.g., "SOL"
        self.trigger_value = trigger_value  # e.g., a numeric threshold
        self.condition = condition          # e.g., "BELOW" or "ABOVE"
        # Replace state with level:
        self.level = "Normal"
        self.last_triggered = None
        self.status = Status.ACTIVE.value  # e.g., "Active"
        self.frequency = 1
        self.counter = 0
        self.liquidation_distance = 0.0
        self.travel_percent = 0.0
        self.liquidation_price = 0.0
        self.notes = f"Position {alert_type} alert created by Cyclone"
        self.position_reference_id = position_reference_id
        self.evaluated_value = 0.0

    def to_dict(self):
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "alert_class": self.alert_class,
            "asset_type": self.asset_type,
            "trigger_value": self.trigger_value,
            "condition": self.condition,
            "notification_type": self.notification_type,
            # Use key "level" instead of "state"
            "level": self.level,
            "last_triggered": self.last_triggered,
            "status": self.status,
            "frequency": self.frequency,
            "counter": self.counter,
            "liquidation_distance": self.liquidation_distance,
            "travel_percent": self.travel_percent,
            "liquidation_price": self.liquidation_price,
            "notes": self.notes,
            "description": f"Position {self.alert_type} alert created by Cyclone",
            "position_reference_id": self.position_reference_id,
            "evaluated_value": self.evaluated_value
        }

class AlertController:
    def __init__(self, db_path: str = None):
        self.u_logger = UnifiedLogger()
        self.logger = logging.getLogger(__name__)  # Standard logger for debug and exceptions
        if db_path:
            self.data_locker = DataLocker.get_instance(db_path)
        else:
            self.data_locker = DataLocker.get_instance()
        self.json_manager = JsonManager()

    def create_alert(self, alert_obj) -> bool:
        try:
            print("[DEBUG] Starting create_alert process.")
            self.logger.debug("[DEBUG] Starting create_alert process.")

            # Convert alert object to dictionary if needed.
            if not isinstance(alert_obj, dict):
                alert_dict = alert_obj.to_dict()
                print("[DEBUG] Converted alert object to dict.")
                self.logger.debug("Converted alert object to dict.")
            else:
                alert_dict = alert_obj
                print("[DEBUG] Alert object is already a dict.")
                self.logger.debug("Alert object is already a dict.")

            print(f"[DEBUG] Alert before processing: {alert_dict}")
            self.logger.debug(f"Alert before processing: {alert_dict}")

            # Set alert_class based on alert type.
            if alert_dict["alert_type"] == AlertType.PRICE_THRESHOLD.value:
                alert_dict["alert_class"] = AlertClass.MARKET.value
            else:
                alert_dict["alert_class"] = AlertClass.POSITION.value
            print(f"[DEBUG] Set alert_class to: {alert_dict['alert_class']}")
            self.logger.debug(f"Set alert_class to: {alert_dict['alert_class']}")

            # Initialize alert defaults.
            alert_dict = self.initialize_alert_data(alert_dict)
            print(f"[DEBUG] Alert after initializing defaults: {alert_dict}")
            self.logger.debug(f"Alert after initializing defaults: {alert_dict}")

            print(f"[DEBUG] Final alert_dict to insert: {alert_dict}")
            self.logger.debug(f"Final alert_dict to insert: {alert_dict}")

            # Insert alert into the database.
            cursor = self.data_locker.conn.cursor()
            sql = """
                INSERT INTO alerts (
                    id,
                    created_at,
                    alert_type,
                    alert_class,
                    asset_type,
                    trigger_value,
                    condition,
                    notification_type,
                    level,
                    last_triggered,
                    status,
                    frequency,
                    counter,
                    liquidation_distance,
                    travel_percent,
                    liquidation_price,
                    notes,
                    description,
                    position_reference_id,
                    evaluated_value
                ) VALUES (
                    :id,
                    :created_at,
                    :alert_type,
                    :alert_class,
                    :asset_type,
                    :trigger_value,
                    :condition,
                    :notification_type,
                    :level,
                    :last_triggered,
                    :status,
                    :frequency,
                    :counter,
                    :liquidation_distance,
                    :travel_percent,
                    :liquidation_price,
                    :notes,
                    :description,
                    :position_reference_id,
                    :evaluated_value
                )
            """
            print(f"[DEBUG] Executing SQL: {sql}")
            self.logger.debug(f"Executing SQL for alert creation: {sql}")
            cursor.execute(sql, alert_dict)
            self.data_locker.conn.commit()
            print(f"[DEBUG] Alert inserted successfully with ID: {alert_dict['id']}")
            self.logger.debug(f"Alert inserted successfully with ID: {alert_dict['id']}")

            # Log initial creation to the ledger.
            # This logs an entry with empty before value and "Created" as the after value.
            from utils.update_ledger import log_alert_update
            log_alert_update(self.data_locker, alert_dict['id'], 'system', 'Initial creation', '', 'Created')
            self.logger.debug("Initial creation logged to ledger.")

            enriched_alert = self.enrich_alert(alert_dict)
            print(f"[DEBUG] Alert after enrichment: {enriched_alert}")
            self.logger.debug(f"Alert after enrichment: {enriched_alert}")

            return True
        except sqlite3.IntegrityError as ie:
            self.logger.error("CREATE ALERT: IntegrityError creating alert: %s", ie, exc_info=True)
            print(f"[ERROR] IntegrityError creating alert: {ie}")
            return False
        except Exception as ex:
            self.logger.exception("CREATE ALERT: Unexpected error in create_alert: %s", ex)
            print(f"[ERROR] Unexpected error in create_alert: {ex}")
            raise

    def create_position_alerts(self):
        """
        Create position alerts for each position that doesn't have an alert_reference_id.
        Returns a list of created alert dictionaries.
        """
        self.logger.debug("Starting create_position_alerts method.")
        created_alerts = []
        positions = self.data_locker.read_positions()
        self.logger.debug(f"Retrieved {len(positions)} positions from the database.")

        for pos in positions:
            pos_id = pos.get("id")
            if not pos.get("alert_reference_id"):
                self.logger.debug(f"Position {pos_id} has no alert_reference_id. Creating alert...")
                asset = pos.get("asset_type", "BTC")
                self.logger.debug(f"Position {pos_id}: asset type = {asset}")
                try:
                    trigger_value = float(-4.0)
                    self.logger.debug(f"Using trigger_value {trigger_value} for position {pos_id}.")
                except Exception as e:
                    self.logger.error(f"Error converting trigger_value for position {pos_id}: {e}")
                    trigger_value = -4.0
                condition = "BELOW"
                notification_type = "Call"
                self.logger.debug(
                    f"Position {pos_id}: condition set to {condition} and notification_type set to {notification_type}.")

                alert_obj = DummyPositionAlert(AlertType.TRAVEL_PERCENT_LIQUID.value, asset, trigger_value, condition,
                                               notification_type, pos_id)
                self.logger.debug(f"Created DummyPositionAlert for position {pos_id}: {alert_obj.to_dict()}")

                if self.create_alert(alert_obj):
                    self.logger.debug(f"Alert created successfully for position {pos_id}.")
                    created_alerts.append(alert_obj.to_dict())
                    try:
                        conn = self.data_locker.get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (alert_obj.id, pos_id))
                        conn.commit()
                        self.logger.debug(f"Updated position {pos_id} with alert_reference_id {alert_obj.id}.")
                    except Exception as e:
                        self.logger.error(f"Error updating position {pos_id} with alert_reference_id: {e}")
                else:
                    self.logger.error(f"Failed to create alert for position {pos_id}.")
            else:
                self.logger.debug(
                    f"Position {pos_id} already has alert_reference_id: {pos.get('alert_reference_id')}. Skipping alert creation.")

        self.logger.debug(f"create_position_alerts completed. Created {len(created_alerts)} alerts.")
        return created_alerts

    def enrich_alert(self, alert: dict) -> dict:
        """
        Enrich the alert by delegating to the shared enrichment routine.
        """
        enriched_alert = enrich_alert_data(alert, self.data_locker, self.logger)
        return enriched_alert

    def populate_evaluated_value_for_alert(self, alert: dict) -> float:
        self.logger.debug("Entering populate_evaluated_value_for_alert with alert: %s", alert)
        evaluated_value = 0.0
        alert_type = alert.get("alert_type")
        self.logger.debug("Alert type: %s", alert_type)

        if alert_type == "PRICE_THRESHOLD":
            asset = alert.get("asset_type", "BTC")
            self.logger.debug("Processing PRICE_THRESHOLD for asset: %s", asset)
            price_record = self.data_locker.get_latest_price(asset)
            if price_record and "current_price" in price_record:
                try:
                    evaluated_value = float(price_record["current_price"])
                    self.logger.debug("Parsed current_price: %f", evaluated_value)
                except Exception as e:
                    self.logger.error("Error parsing current_price from price_record: %s", e, exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.error("No price record found for asset: %s", asset)
                evaluated_value = 0.0

        elif alert_type == "TRAVEL_PERCENT_LIQUID":
            pos_id = alert.get("position_reference_id") or alert.get("id")
            positions = {p.get("id"): p for p in self.data_locker.read_positions()}
            if pos_id and pos_id in positions:
                try:
                    evaluated_value = float(positions[pos_id].get("travel_percent", 0))
                except Exception as e:
                    self.logger.error("Error retrieving travel percent for position %s: %s", pos_id, e, exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.error("No matching position found for id: %s", pos_id)
                evaluated_value = 0.0

        elif alert_type == "PROFIT":
            pos_id = alert.get("position_reference_id") or alert.get("id")
            positions = {p.get("id"): p for p in self.data_locker.read_positions()}
            if pos_id and pos_id in positions:
                try:
                    evaluated_value = float(positions[pos_id].get("pnl_after_fees_usd", 0))
                except Exception as e:
                    self.logger.error("Error retrieving pnl for position %s: %s", pos_id, e, exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.error("No matching position found for id: %s", pos_id)
                evaluated_value = 0.0

        elif alert_type == "HEAT_INDEX":
            pos_id = alert.get("position_reference_id") or alert.get("id")
            positions = {p.get("id"): p for p in self.data_locker.read_positions()}
            if pos_id and pos_id in positions:
                try:
                    evaluated_value = float(positions[pos_id].get("current_heat_index", 0))
                except Exception as e:
                    self.logger.error("Error retrieving current_heat_index for position %s: %s", pos_id, e,
                                      exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.error("No matching position found for id: %s", pos_id)
                evaluated_value = 0.0

        else:
            self.logger.debug("Alert type %s not recognized; defaulting evaluated_value to 0.0", alert_type)
            evaluated_value = 0.0

        self.logger.debug("Exiting populate_evaluated_value_for_alert with evaluated_value: %f", evaluated_value)
        return evaluated_value

    def get_all_alerts(self):
        try:
            return self.data_locker.get_alerts()
        except Exception as e:
            print(f"Error retrieving alerts: {e}")
            return []

    def initialize_alert_data(self, alert_data: dict = None) -> dict:
        from data.models import Status
        from uuid import uuid4
        from datetime import datetime

        defaults = {
            "id": str(uuid4()),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "alert_type": "",
            "alert_class": "",
            "asset_type": "BTC",
            "trigger_value": 0.0,
            "condition": "ABOVE",
            "notification_type": "Email",
            # Replace default key "state" with "level"
            "level": "Normal",
            "last_triggered": None,
            "status": Status.ACTIVE.value,
            "frequency": 1,
            "counter": 0,
            "liquidation_distance": 0.0,
            "travel_percent": 0.0,
            "liquidation_price": 0.0,
            "notes": "",
            "description": "",
            "position_reference_id": None,
            "evaluated_value": 0.0
        }
        if alert_data is None:
            alert_data = {}

        for key, default_val in defaults.items():
            if key not in alert_data or alert_data.get(key) is None:
                alert_data[key] = default_val
            elif key == "position_reference_id":
                value = alert_data.get(key)
                if isinstance(value, str) and value.strip() == "":
                    self.logger.error("initialize_alert_data: position_reference_id is empty for a position alert")
        return alert_data

    def create_price_alerts(self):
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        price_alerts_config = alert_limits.get("alert_ranges", {}).get("price_alerts", {})

        created_alerts = []
        assets = ["BTC", "ETH", "SOL"]

        class DummyAlert:
            def __init__(self, alert_type, alert_class, asset_type, trigger_value, condition, notification_type,
                         level="Normal", position_reference_id=None, status="Active"):
                self.id = str(uuid4())
                self.alert_type = alert_type
                self.alert_class = alert_class
                self.asset_type = asset_type
                self.trigger_value = trigger_value
                self.condition = condition
                self.notification_type = notification_type
                # Use 'level' consistently
                self.level = level
                self.last_triggered = None
                self.status = status
                self.frequency = 1
                self.counter = 0
                self.liquidation_distance = 0.0
                self.travel_percent = 0.0
                self.liquidation_price = 0.0
                self.notes = ""
                self.position_reference_id = position_reference_id

            def to_dict(self):
                return {
                    "id": self.id,
                    "alert_type": self.alert_type,
                    "alert_class": self.alert_class,
                    "asset_type": self.asset_type,
                    "trigger_value": self.trigger_value,
                    "condition": self.condition,
                    "notification_type": self.notification_type,
                    "level": self.level,  # key is now "level"
                    "last_triggered": self.last_triggered,
                    "status": self.status,
                    "frequency": self.frequency,
                    "counter": self.counter,
                    "liquidation_distance": self.liquidation_distance,
                    "travel_percent": self.travel_percent,
                    "liquidation_price": self.liquidation_price,
                    "notes": self.notes,
                    "position_reference_id": self.position_reference_id
                }

        existing_alerts = self.get_all_alerts()

        for asset in assets:
            config = price_alerts_config.get(asset, {})
            if config.get("enabled", False):
                condition = config.get("condition", "ABOVE").upper()
                trigger_value = float(config.get("trigger_value", 0.0))
                notifications = config.get("notifications", {})
                notification_type = "Call" if notifications.get("call", False) else "Email"

                alert_exists = any(
                    alert.get("alert_type") == AlertType.PRICE_THRESHOLD.value and
                    alert.get("asset_type") == asset and
                    alert.get("condition", "").upper() == condition
                    for alert in existing_alerts
                )
                if alert_exists:
                    print(f"Price alert for {asset} with condition {condition} already exists; skipping creation.")
                    continue

                dummy_alert = DummyAlert(
                    alert_type=AlertType.PRICE_THRESHOLD.value,
                    alert_class=AlertClass.MARKET.value,
                    asset_type=asset,
                    trigger_value=trigger_value,
                    condition=condition,
                    notification_type=notification_type,
                    state="Normal",
                    status=Status.ACTIVE.value
                )
                if self.create_alert(dummy_alert):
                    created_alerts.append(dummy_alert.to_dict())
                    print(f"Created price alert for {asset}: condition {condition}, trigger {trigger_value}, notification {notification_type}.")
                else:
                    print(f"Failed to create price alert for {asset}.")
            else:
                print(f"Price alert for {asset} is not enabled in configuration.")
        return created_alerts

    def _update_alert_level(self, pos: dict, new_level: str, evaluated_value: Optional[float] = None,
                            updated_by: str = "system", reason: str = "Automatic update"):
        """
        Updates the alert's level for a given position.
        If no alert_reference_id exists in the position, creates a new alert record with the specified level.

        :param pos: Dictionary containing position data (must include position id).
        :param new_level: The new alert level to set (e.g., "Normal", "Low", "Medium", "High").
        :param evaluated_value: The evaluated value from the alert evaluation.
        :param updated_by: Identifier for who/what is making the update.
        :param reason: Reason for the update (for logging purposes).
        """
        alert_id = pos.get("alert_reference_id")
        if not alert_id:
            UnifiedLogger().log_operation(
                operation_type="Alert Level Update",
                primary_text="No alert_reference_id found for updating level. Creating new alert record.",
                source="AlertController",
                file="alert_controller.py"
            )
            print("[DEBUG] _update_alert_level: No alert_reference_id found. Creating new alert record.")
            # Default to a travel percent alert type if no custom type is provided.
            new_trigger = pos.get("travel_percent", 0.0)
            new_alert = DummyPositionAlert(
                AlertType.TRAVEL_PERCENT_LIQUID.value,
                pos.get("asset_type", "BTC"),
                new_trigger,
                "BELOW",
                "Call",
                pos.get("id")
            )
            if self.create_alert(new_alert):
                pos["alert_reference_id"] = new_alert.id
                conn = self.data_locker.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (new_alert.id, pos.get("id")))
                conn.commit()
                alert_id = new_alert.id
                UnifiedLogger().log_operation(
                    operation_type="Alert Creation",
                    primary_text=f"Created new alert record for position {pos.get('id')} with alert id {new_alert.id}",
                    source="AlertController",
                    file="alert_controller.py"
                )
                print(
                    f"[DEBUG] _update_alert_level: Created new alert with id {new_alert.id} and updated position record.")
            else:
                UnifiedLogger().log_operation(
                    operation_type="Alert Creation Failed",
                    primary_text=f"Failed to create new alert record for position {pos.get('id')}",
                    source="AlertController",
                    file="alert_controller.py"
                )
                print("[DEBUG] _update_alert_level: Failed to create new alert record.")
                return

        old_level = pos.get("level", "Normal")
        update_fields = {"level": new_level}
        if evaluated_value is not None:
            update_fields["evaluated_value"] = evaluated_value

        if pos.get("alert_reference_id") and pos.get("id"):
            update_fields["position_reference_id"] = pos.get("id")

        print(f"[DEBUG] _update_alert_level: Updating alert '{alert_id}' with fields: {update_fields}")
        UnifiedLogger().log_operation(
            operation_type="Alert Level Update",
            primary_text=f"Updating alert '{alert_id}' with {update_fields}",
            source="AlertController",
            file="alert_controller.py"
        )
        try:
            num_updated = self.data_locker.update_alert_conditions(alert_id, update_fields)
            if num_updated == 0:
                UnifiedLogger().log_operation(
                    operation_type="Alert Level Update",
                    primary_text=f"No alert record found for id '{alert_id}', creating new alert record.",
                    source="AlertController",
                    file="alert_controller.py"
                )
                print(f"[DEBUG] _update_alert_level: No alert record found for id '{alert_id}'.")
            else:
                UnifiedLogger().log_operation(
                    operation_type="Alert Level Updated",
                    primary_text=f"Updated alert '{alert_id}' to level '{new_level}' with evaluated value '{evaluated_value}'.",
                    source="AlertController",
                    file="alert_controller.py"
                )
                from utils.update_ledger import log_alert_update
                log_alert_update(self.data_locker, alert_id, updated_by, reason, old_level, new_level)
                print(f"[DEBUG] _update_alert_level: Successfully updated alert '{alert_id}' to level '{new_level}'.")
        except Exception as e:
            UnifiedLogger().log_operation(
                operation_type="Alert Level Update Error",
                primary_text=f"Error updating alert level for id '{alert_id}': {e}",
                source="AlertController",
                file="alert_controller.py"
            )
            print(f"[DEBUG] _update_alert_level: Exception while updating alert '{alert_id}': {e}")

    def create_travel_percent_alerts(self):
        created_alerts = []
        positions = self.data_locker.read_positions()  # Consistent data retrieval
        self.logger.debug(f"Retrieved {len(positions)} positions for travel percent alert creation.")

        for pos in positions:
            pos_id = pos.get("id")
            # Only create an alert if one isn't already linked
            if not pos.get("alert_reference_id"):
                asset = pos.get("asset_type", "BTC")
                # Set trigger_value to 0.0 so that enrichment will pick up and assign the real config threshold (e.g., -25.0)
                trigger_value = 0.0
                condition = "BELOW"
                notification_type = "Call"
                self.logger.debug(
                    f"Creating travel percent alert for position {pos_id} with trigger_value {trigger_value}.")

                alert_obj = DummyPositionAlert(
                    AlertType.TRAVEL_PERCENT_LIQUID.value,
                    asset,
                    trigger_value,
                    condition,
                    notification_type,
                    pos_id
                )

                if self.create_alert(alert_obj):
                    created_alerts.append(alert_obj.to_dict())
                    UnifiedLogger().log_operation(
                        operation_type="Create Travel Percent Alert",
                        primary_text=f"Created travel percent alert for position {pos_id} ({asset}).",
                        source="AlertController",
                        file="alert_controller.py"
                    )
                    try:
                        conn = self.data_locker.get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (alert_obj.id, pos_id))
                        conn.commit()
                        self.logger.debug(f"Updated position {pos_id} with alert_reference_id {alert_obj.id}.")
                    except Exception as e:
                        self.logger.error(f"Error updating position {pos_id} with alert_reference_id: {e}")
                        UnifiedLogger().log_operation(
                            operation_type="Update Position Alert ID Failed",
                            primary_text=f"Failed to update position {pos_id} with alert_reference_id: {e}",
                            source="AlertController",
                            file="alert_controller.py"
                        )
                else:
                    self.logger.error(f"Failed to create travel percent alert for position {pos_id}.")
                    UnifiedLogger().log_operation(
                        operation_type="Create Travel Percent Alert Failed",
                        primary_text=f"Failed to create travel percent alert for position {pos_id}.",
                        source="AlertController",
                        file="alert_controller.py"
                    )
            else:
                self.logger.debug(f"Position {pos_id} already has an alert_reference_id; skipping alert creation.")

        self.logger.debug(f"create_travel_percent_alerts completed. Created {len(created_alerts)} alerts.")
        return created_alerts

    def create_profit_alerts(self):
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        profit_config = alert_limits.get("alert_ranges", {}).get("profit_ranges", {})
        if not profit_config.get("enabled", False):
            print("Profit alerts are not enabled in configuration.")
            return []
        created_alerts = []
        positions = self.data_locker.read_positions()
        for pos in positions:
            asset = pos.get("asset_type", "BTC")
            try:
                profit_val = float(pos.get("pnl_after_fees_usd", 0.0))
            except Exception:
                continue
            if profit_val <= 0:
                self._update_alert_state(pos, "Normal")
                continue
            try:
                low_thresh = float(profit_config.get("low", 46.23))
                med_thresh = float(profit_config.get("medium", 101.3))
                high_thresh = float(profit_config.get("high", 202.0))
            except Exception:
                continue
            if profit_val < low_thresh:
                self._update_alert_state(pos, "Normal")
                continue
            elif profit_val < med_thresh:
                current_level = "Low"
                computed_trigger = low_thresh
            elif profit_val < high_thresh:
                current_level = "Medium"
                computed_trigger = med_thresh
            else:
                current_level = "High"
                computed_trigger = high_thresh
            condition = profit_config.get("condition", "ABOVE")
            notifications = profit_config.get("notifications", {})
            notification_type = "Call" if notifications.get("call", False) else "Email"
            position_id = pos.get("id")
            alert_obj = DummyPositionAlert(
                AlertType.PROFIT.value,
                AlertClass.POSITION.value,
                asset,
                computed_trigger,
                condition,
                notification_type,
                position_id
            )
            # Set level instead of state.
            alert_obj.level = current_level
            if self.create_alert(alert_obj):
                created_alerts.append(alert_obj.to_dict())
                print(f"Created profit alert for position {position_id} ({asset}): level {current_level}, computed trigger {computed_trigger}, notification {notification_type}.")
            else:
                print(f"Failed to create profit alert for position {position_id}.")
        return created_alerts

    def refresh_position_alerts(self) -> int:
        updated_count = 0
        try:
            alerts = self.get_all_alerts()
            positions = self.data_locker.read_positions()
            for alert in alerts:
                print(f"[Early Debug] Processing alert ID: {alert.get('id')} | Class: {alert.get('alert_class')} | Position Ref ID: {alert.get('position_reference_id')}")
                self.logger.debug(f"[Early Debug] Processing alert ID: {alert.get('id')} | Class: {alert.get('alert_class')} | Position Ref ID: {alert.get('position_reference_id')}")

                if alert.get("alert_class") == "Position" and alert.get("position_reference_id"):
                    pos_id = alert["position_reference_id"]
                    position = next((p for p in positions if p.get("id") == pos_id), None)
                    if not position:
                        print(f"[Refresh] No position found for id {pos_id}.")
                        self.logger.error(f"No position found for id {pos_id} during periodic alert refresh.")
                        continue

                    print(f"[Before Update] Alert {alert['id']} original values: {alert}")
                    self.logger.debug(f"[Before Update] Alert {alert['id']} original values: {alert}")

                    enriched_alert = self.enrich_alert(alert.copy())
                    evaluated_val = self.populate_evaluated_value_for_alert(enriched_alert)
                    enriched_alert["evaluated_value"] = evaluated_val

                    update_fields = {
                        "liquidation_distance": enriched_alert.get("liquidation_distance") or 0.0,
                        "liquidation_price": enriched_alert.get("liquidation_price") or 0.0,
                        "travel_percent": enriched_alert.get("travel_percent") or 0.0,
                        "evaluated_value": enriched_alert.get("evaluated_value") or 0.0
                    }
                    print(f"[Update Data] Alert {enriched_alert['id']} will be updated with: {update_fields}")
                    self.logger.debug(f"[Update Data] Alert {enriched_alert['id']} will be updated with: {update_fields}")

                    rows_updated = self.data_locker.update_alert_conditions(enriched_alert["id"], update_fields)
                    print(f"[Update Result] Rows updated for alert {enriched_alert['id']}: {rows_updated}")
                    self.logger.debug(f"Rows updated for alert {enriched_alert['id']}: {rows_updated}")

                    cursor = self.data_locker.conn.cursor()
                    cursor.execute("SELECT liquidation_distance, liquidation_price, travel_percent, evaluated_value FROM alerts WHERE id=?", (enriched_alert["id"],))
                    row = cursor.fetchone()
                    if row:
                        confirmed_values = {
                            "liquidation_distance": row["liquidation_distance"] or 0.0,
                            "liquidation_price": row["liquidation_price"] or 0.0,
                            "travel_percent": row["travel_percent"] or 0.0,
                            "evaluated_value": row["evaluated_value"] or 0.0
                        }
                        print(f"[After Update] Alert {enriched_alert['id']} confirmed values: {confirmed_values}")
                        self.logger.info(f"[After Update] Alert {enriched_alert['id']} confirmed values: {confirmed_values}")

                        diff_liq_dist = abs(confirmed_values["liquidation_distance"] - update_fields["liquidation_distance"])
                        diff_liq_price = abs(confirmed_values["liquidation_price"] - update_fields["liquidation_price"])
                        diff_travel = abs(confirmed_values["travel_percent"] - update_fields["travel_percent"])
                        diff_eval_value = abs(confirmed_values["evaluated_value"] - update_fields["evaluated_value"])

                        print(f"[Differences] Alert {enriched_alert['id']} differences:")
                        print(f"  liquidation_distance diff: {diff_liq_dist}")
                        print(f"  liquidation_price diff:    {diff_liq_price}")
                        print(f"  travel_percent diff:         {diff_travel}")
                        print(f"  evaluated_value diff:        {diff_eval_value}")
                        self.logger.debug(f"Alert {enriched_alert['id']} differences -> liquidation_distance: {diff_liq_dist}, liquidation_price: {diff_liq_price}, travel_percent: {diff_travel}, evaluated_value: {diff_eval_value}")

                        tolerance = 1e-6
                        if (diff_liq_dist < tolerance and diff_liq_price < tolerance and diff_travel < tolerance and diff_eval_value < tolerance):
                            updated_count += 1
                            print(f"[Confirmation] Alert {enriched_alert['id']} update confirmed.")
                            self.logger.info(f"Alert {enriched_alert['id']} update confirmed.")
                        else:
                            print(f"[Mismatch] Alert {enriched_alert['id']} update mismatch.")
                            print(f"  Intended update: {update_fields}")
                            print(f"  Confirmed in DB: {confirmed_values}")
                            self.logger.error(f"Alert {enriched_alert['id']} update mismatch. Intended: {update_fields} | Confirmed: {confirmed_values}")
                    else:
                        print(f"[Error] Could not retrieve alert {enriched_alert['id']} after update.")
                        self.logger.error(f"Could not retrieve alert {enriched_alert['id']} after update.")
        except Exception as e:
            print(f"[Exception] Exception during refresh_position_alerts: {e}")
            self.logger.exception(f"Exception during refresh_position_alerts: {e}")
        print(f"[Final] Periodic alert enrichment: Updated and confirmed {updated_count} position alert(s).")
        self.logger.info(f"Periodic alert enrichment: Updated and confirmed {updated_count} position alert(s).")
        return updated_count

    def refresh_all_alerts(self) -> int:
        """
        Refreshes all alerts. Currently, only position alerts are refreshed.
        Future implementations may refresh market and system alerts.
        Returns the total count of alerts updated and confirmed.
        """
        total_updated = self.refresh_position_alerts()
        self.logger.info(f"refresh_all_alerts: Refreshed and confirmed {total_updated} alert(s).")
        return total_updated

    def refresh_all_alerts(self) -> int:
        """
        Refreshes all alerts. Currently, only position alerts are refreshed.
        Future implementations may refresh market and system alerts.
        Returns the total count of alerts updated and confirmed.
        """
        total_updated = self.refresh_position_alerts()
        self.logger.info(f"refresh_all_alerts: Refreshed and confirmed {total_updated} alert(s).")
        return total_updated

    def create_heat_index_alerts(self):
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        heat_config = alert_limits.get("alert_ranges", {}).get("heat_index_alerts", {})
        if not heat_config.get("enabled", False):
            print("Heat index alerts are not enabled in configuration.")
            return []
        created_alerts = []
        positions = self.data_locker.read_positions()
        for pos in positions:
            asset = pos.get("asset_type", "BTC")
            trigger_value = float(heat_config.get("trigger_value", 0.0))
            condition = heat_config.get("condition", "ABOVE")
            notifications = heat_config.get("notifications", {})
            notification_type = "Call" if notifications.get("call", False) else "Email"
            position_id = pos.get("id")
            alert_obj = DummyPositionAlert(AlertType.HEAT_INDEX.value, AlertClass.POSITION.value, asset, trigger_value, condition, notification_type, position_id)
            if self.create_alert(alert_obj):
                created_alerts.append(alert_obj.to_dict())
                print(f"Created heat index alert for position {position_id} ({asset}): condition {condition}, trigger {trigger_value}, notification {notification_type}.")
            else:
                print(f"Failed to create heat index alert for position {position_id}.")
        return created_alerts

    def get_RID_OF_ME_zopulate_evaluated_value_for_alert(self, alert: dict) -> float:
        self.logger.debug("Entering populate_evaluated_value_for_alert with alert: %s", alert)
        print(f"[populate_evaluated_value] Received alert: {alert}")
        evaluated_value = 0.0
        alert_type = alert.get("alert_type")
        self.logger.debug("Alert type: %s", alert_type)
        print(f"[populate_evaluated_value] Alert type: {alert_type}")

        if alert_type == AlertType.PRICE_THRESHOLD.value:
            asset = alert.get("asset_type", "BTC")
            self.logger.debug("Processing PRICE_THRESHOLD for asset: %s", asset)
            print(f"[populate_evaluated_value] Processing PRICE_THRESHOLD for asset: {asset}")
            price_record = self.data_locker.get_latest_price(asset)
            if price_record:
                self.logger.debug("Found price record: %s", price_record)
                print(f"[populate_evaluated_value] Found price record: {price_record}")
                try:
                    evaluated_value = float(price_record.get("current_price", 0.0))
                    self.logger.debug("Parsed current_price: %f", evaluated_value)
                    print(f"[populate_evaluated_value] Parsed current_price: {evaluated_value}")
                except Exception as e:
                    self.logger.error("Error parsing current_price from price_record: %s", e, exc_info=True)
                    print(f"[populate_evaluated_value] Error parsing current_price: {e}")
                    evaluated_value = 0.0
            else:
                self.logger.debug("No price record found for asset: %s", asset)
                print(f"[populate_evaluated_value] No price record found for asset: {asset}")
                evaluated_value = 0.0

        elif alert_type == AlertType.TRAVEL_PERCENT_LIQUID.value:
            pos_id = alert.get("position_reference_id") or alert.get("id")
            self.logger.debug("Processing TRAVEL_PERCENT for position id: %s", pos_id)
            print(f"[populate_evaluated_value] Processing TRAVEL_PERCENT for position id: {pos_id}")
            positions = self.data_locker.read_positions()
            self.logger.debug("Retrieved positions: %s", positions)
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                self.logger.debug("Found matching position: %s", position)
                print(f"[populate_evaluated_value] Found matching position: {position}")
                try:
                    evaluated_value = float(position.get("travel_percent", 0.0))
                    self.logger.debug("Parsed travel_percent: %f", evaluated_value)
                    print(f"[populate_evaluated_value] Parsed travel_percent: {evaluated_value}")
                except Exception as e:
                    self.logger.error("Error parsing travel_percent: %s", e, exc_info=True)
                    print(f"[populate_evaluated_value] Error parsing travel_percent: {e}")
                    evaluated_value = 0.0
            else:
                self.logger.debug("No matching position found for id: %s", pos_id)
                print(f"[populate_evaluated_value] No matching position found for id: {pos_id}")
                evaluated_value = 0.0

        elif alert_type == AlertType.PROFIT.value:
            pos_id = alert.get("position_reference_id") or alert.get("id")
            self.logger.debug("Processing PROFIT for position id: %s", pos_id)
            print(f"[populate_evaluated_value] Processing PROFIT for position id: {pos_id}")
            positions = self.data_locker.read_positions()
            self.logger.debug("Retrieved positions: %s", positions)
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                self.logger.debug("Found matching position: %s", position)
                print(f"[populate_evaluated_value] Found matching position: {position}")
                try:
                    evaluated_value = float(position.get("pnl_after_fees_usd", 0.0))
                    self.logger.debug("Parsed pnl_after_fees_usd: %f", evaluated_value)
                    print(f"[populate_evaluated_value] Parsed pnl_after_fees_usd: {evaluated_value}")
                except Exception as e:
                    self.logger.error("Error parsing pnl_after_fees_usd: %s", e, exc_info=True)
                    print(f"[populate_evaluated_value] Error parsing pnl_after_fees_usd: {e}")
                    evaluated_value = 0.0
            else:
                self.logger.debug("No matching position found for id: %s", pos_id)
                print(f"[populate_evaluated_value] No matching position found for id: {pos_id}")
                evaluated_value = 0.0

        elif alert_type == AlertType.HEAT_INDEX.value:
            pos_id = alert.get("position_reference_id") or alert.get("id")
            self.logger.debug("Processing HEAT_INDEX for position id: %s", pos_id)
            print(f"[populate_evaluated_value] Processing HEAT_INDEX for position id: {pos_id}")
            positions = self.data_locker.read_positions()
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                self.logger.debug("Found matching position for HEAT_INDEX: %s", position)
                print(f"[populate_evaluated_value] Found matching position: {position}")
                try:
                    evaluated_value = float(position.get("current_heat_index", 0.0))
                    self.logger.debug("Parsed current_heat_index: %f", evaluated_value)
                    print(f"[populate_evaluated_value] Parsed current_heat_index: {evaluated_value}")
                except Exception as e:
                    self.logger.error("Error parsing current_heat_index: %s", e, exc_info=True)
                    print(f"[populate_evaluated_value] Error parsing current_heat_index: {e}")
                    evaluated_value = 0.0
            else:
                self.logger.debug("No matching position found for id: %s", pos_id)
                print(f"[populate_evaluated_value] No matching position found for id: {pos_id}")
                evaluated_value = 0.0

        else:
            self.logger.debug("Alert type %s not recognized; defaulting evaluated_value to 0.0", alert_type)
            print(f"[populate_evaluated_value] Alert type {alert_type} not recognized; defaulting evaluated_value to 0.0")
            evaluated_value = 0.0

        self.logger.debug("Exiting populate_evaluated_value_for_alert with evaluated_value: %f", evaluated_value)
        print(f"[populate_evaluated_value] Exiting with evaluated_value: {evaluated_value}")
        return evaluated_value

    def get_all_alerts(self):
        try:
            return self.data_locker.get_alerts()
        except Exception as e:
            print(f"Error retrieving alerts: {e}")
            return []

    def create_all_alerts(self):
        print("DEBUG: create_all_alerts method called")
        self.u_logger.log_operation(
            operation_type="Create Alerts",
            primary_text="create_all_alerts method called",
            source="AlertController",
            file="alert_controller.py"
        )
        price_alerts = self.create_price_alerts()
        travel_alerts = self.create_travel_percent_alerts()
        profit_alerts = self.create_profit_alerts()
        heat_alerts = self.create_heat_index_alerts()
        return price_alerts + travel_alerts + profit_alerts + heat_alerts

    def delete_all_alerts(self):
        alerts = self.get_all_alerts()
        count = 0
        for alert in alerts:
            if self.delete_alert(alert["id"]):
                count += 1
        print(f"Deleted {count} alerts.")
        return count
