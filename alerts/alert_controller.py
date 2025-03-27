from data.data_locker import DataLocker
from utils.json_manager import JsonManager, JsonType
from uuid import uuid4
from data.models import Alert, AlertType, AlertClass, NotificationType, Status
from typing import Optional
import logging
import sqlite3
from utils.unified_logger import UnifiedLogger

from uuid import uuid4
from data.models import Status  # Ensure Status is imported

class DummyPositionAlert:
    def __init__(self, alert_type, asset_type, trigger_value, condition, notification_type, position_reference_id):
        self.id = str(uuid4())
        self.alert_type = alert_type                     # e.g., "TravelPercentAlert", "ProfitAlert", "HeatIndexAlert"
        self.alert_class = "Position"                    # default for position alerts
        self.asset_type = asset_type                     # e.g., "SOL"
        self.trigger_value = trigger_value               # e.g., a numeric threshold
        self.condition = condition                       # e.g., "BELOW" or "ABOVE"
        self.notification_type = notification_type       # e.g., "Call" or "Email"
        self.state = "Normal"
        self.last_triggered = None
        self.status = Status.ACTIVE.value                # e.g., "Active"
        self.frequency = 1
        self.counter = 0
        self.liquidation_distance = 0.0
        self.target_travel_percent = 0.0
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
            "state": self.state,
            "last_triggered": self.last_triggered,
            "status": self.status,
            "frequency": self.frequency,
            "counter": self.counter,
            "liquidation_distance": self.liquidation_distance,
            "target_travel_percent": self.target_travel_percent,
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

            # Print alert before normalization.
            print(f"[DEBUG] Alert before normalization: {alert_dict}")
            self.logger.debug(f"Alert before normalization: {alert_dict}")

            # Normalize alert_type.
            if alert_dict.get("alert_type"):
                normalized_type = alert_dict["alert_type"].upper().replace(" ", "").replace("_", "")
                print(f"[DEBUG] Normalized alert_type: {normalized_type}")
                self.logger.debug(f"Normalized alert_type: {normalized_type}")
                if normalized_type == "PRICETHRESHOLD":
                    normalized_type = "PRICE_THRESHOLD"
                alert_dict["alert_type"] = normalized_type

                # Set alert_class based on alert_type.
                if normalized_type == "PRICE_THRESHOLD":
                    alert_dict["alert_class"] = "Market"
                else:
                    alert_dict["alert_class"] = "Position"
                print(f"[DEBUG] Set alert_class to: {alert_dict['alert_class']}")
                self.logger.debug(f"Set alert_class to: {alert_dict['alert_class']}")
            else:
                self.logger.error("Alert missing alert_type.")
                print("[ERROR] Alert missing alert_type.")
                return False

            # Initialize alert defaults.
            alert_dict = self.initialize_alert_data(alert_dict)
            print(f"[DEBUG] Alert after initializing defaults: {alert_dict}")
            self.logger.debug(f"Alert after initializing defaults: {alert_dict}")

            # Log the complete alert dictionary before insertion.
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
                    state,
                    last_triggered,
                    status,
                    frequency,
                    counter,
                    liquidation_distance,
                    target_travel_percent,
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
                    :state,
                    :last_triggered,
                    :status,
                    :frequency,
                    :counter,
                    :liquidation_distance,
                    :target_travel_percent,
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

            # Optionally, enrich alert after creation.
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

    def delete_alert(self, alert_id: str) -> bool:
        try:
            self.logger.debug(f"Attempting to delete alert with id: {alert_id}")
            self.data_locker.delete_alert(alert_id)
            self.logger.debug(f"Successfully deleted alert with id: {alert_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting alert {alert_id}: {e}", exc_info=True)
            return False

    def enrich_alert(self, alert: dict) -> dict:
        print("Before enrichment:", alert)

        # 1. Normalize the alert type.
        if alert.get("alert_type"):
            normalized_type = alert["alert_type"].upper().replace(" ", "").replace("_", "")
            if normalized_type == "PRICETHRESHOLD":
                normalized_type = "PRICE_THRESHOLD"
            elif normalized_type in ["TRAVELPERCENTALERT", "TRAVELPERCENTLIQUID"]:
                normalized_type = "TRAVEL_PERCENT_ALERT"
            elif normalized_type == "PROFITALERT":
                normalized_type = "PROFIT"
            elif normalized_type == "HEATINDEXALERT":
                normalized_type = "HEAT_INDEX_ALERT"
            alert["alert_type"] = normalized_type
        else:
            self.logger.error("Alert missing alert_type.")
            print("Error: Alert missing alert_type.")
            return alert

        # 2. Set Alert Class and assert position_reference_id for position alerts.
        if alert["alert_type"] in ["TRAVEL_PERCENT_ALERT", "PROFIT", "HEAT_INDEX_ALERT"]:
            alert["alert_class"] = "Position"
            if not alert.get("position_reference_id"):
                self.logger.error("Position alert missing position_reference_id.")
                print("Error: Position alert missing position_reference_id.")
        elif alert["alert_type"] == "PRICE_THRESHOLD":
            alert["alert_class"] = "Market"
        else:
            self.logger.error(f"Unrecognized alert_type: {alert['alert_type']}")
            print(f"Error: Unrecognized alert_type: {alert['alert_type']}")

        # 3. Load alert limits configuration.
        jm = self.json_manager
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)

        # 4. Enrich based on alert type.
        if alert["alert_type"] == "PRICE_THRESHOLD":
            asset = alert.get("asset_type", "BTC")
            asset_config = alert_limits.get("alert_ranges", {}).get("price_alerts", {}).get(asset, {})
            if asset_config:
                notifications = asset_config.get("notifications", {})
                alert["notification_type"] = "Call" if notifications.get("call", False) else "Email"
                if alert.get("trigger_value", 0.0) == 0.0:
                    alert["trigger_value"] = float(asset_config.get("trigger_value", 0.0))
                alert["condition"] = asset_config.get("condition", alert["condition"])
            else:
                self.logger.error(f"No configuration found for price alert asset {asset}.")
                print(f"Error: No configuration found for price alert asset {asset}.")
                alert["notification_type"] = "Email"
        elif alert["alert_type"] == "TRAVEL_PERCENT_ALERT":
            config = alert_limits.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
            if config.get("enabled", False):
                if alert.get("trigger_value", 0.0) == 0.0:
                    alert["trigger_value"] = float(config.get("low", -4.0))
                alert["condition"] = "BELOW"
            if not alert.get("notification_type"):
                alert["notification_type"] = "Email"
        elif alert["alert_type"] == "PROFIT":
            config = alert_limits.get("alert_ranges", {}).get("profit_ranges", {})
            if config.get("enabled", False):
                if alert.get("trigger_value", 0.0) == 0.0:
                    alert["trigger_value"] = float(config.get("low", 22.0))
                alert["condition"] = config.get("condition", "ABOVE")
            if not alert.get("notification_type"):
                alert["notification_type"] = "Email"
        elif alert["alert_type"] == "HEAT_INDEX_ALERT":
            config = alert_limits.get("alert_ranges", {}).get("heat_index_ranges", {})
            if config.get("enabled", False):
                if alert.get("trigger_value", 0.0) == 0.0:
                    alert["trigger_value"] = float(config.get("low", 12.0))
                alert["condition"] = config.get("condition", "ABOVE")
            if not alert.get("notification_type"):
                alert["notification_type"] = "Email"
        else:
            if not alert.get("notification_type"):
                alert["notification_type"] = "Email"

        # 4.5. For position alerts, update additional fields from the associated position.
        if alert.get("alert_class") == "Position":
            pos_id = alert.get("position_reference_id")
            if pos_id:
                positions = self.data_locker.read_positions()
                self.logger.debug("Enriching position alert: retrieved positions: %s", positions)
                position = next((p for p in positions if p.get("id") == pos_id), None)
                if position:
                    alert["liquidation_distance"] = position.get("liquidation_distance", 0.0)
                    alert["liquidation_price"] = position.get("liquidation_price", 0.0)
                    alert["target_travel_percent"] = position.get("target_travel_percent", 0.0)
                    self.logger.debug("Enriched position alert %s with liquidation_distance: %s, liquidation_price: %s, target_travel_percent: %s",
                                        alert["id"], alert["liquidation_distance"], alert["liquidation_price"], alert["target_travel_percent"])
                else:
                    self.logger.error("No position found for id %s during alert enrichment.", pos_id)
                    print(f"Error: No position found for id {pos_id} during alert enrichment.")
            else:
                self.logger.error("Position alert missing position_reference_id during enrichment.")
                print("Error: Position alert missing position_reference_id during enrichment.")

        # 5. Force state to "Normal".
        alert["state"] = "Normal"

        # 6. Populate evaluated value.
        alert["evaluated_value"] = self.populate_evaluated_value_for_alert(alert)

        print("After enrichment:", alert)
        return alert

    def populate_evaluated_value_for_alert(self, alert: dict) -> float:
        self.logger.debug("Entering populate_evaluated_value_for_alert with alert: %s", alert)
        evaluated_value = 0.0
        alert_type = alert.get("alert_type")
        self.logger.debug("Alert type: %s", alert_type)

        if alert_type == AlertType.PRICE_THRESHOLD.value:
            asset = alert.get("asset_type", "BTC")
            self.logger.debug("Processing PRICE_THRESHOLD for asset: %s", asset)
            price_record = self.data_locker.get_latest_price(asset)
            if price_record:
                self.logger.debug("Found price record: %s", price_record)
                try:
                    evaluated_value = float(price_record.get("current_price", 0.0))
                    self.logger.debug("Parsed current_price: %f", evaluated_value)
                except Exception as e:
                    self.logger.error("Error parsing current_price from price_record: %s", e, exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.debug("No price record found for asset: %s", asset)
                evaluated_value = 0.0

        elif alert_type == AlertType.TRAVEL_PERCENT_LIQUID.value:
            pos_id = alert.get("position_reference_id") or alert.get("id")
            self.logger.debug("Processing TRAVEL_PERCENT_LIQUID for position id: %s", pos_id)
            positions = self.data_locker.read_positions()
            self.logger.debug("Retrieved positions: %s", positions)
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                self.logger.debug("Found matching position: %s", position)
                try:
                    evaluated_value = float(position.get("current_travel_percent", 0.0))
                    self.logger.debug("Parsed current_travel_percent: %f", evaluated_value)
                except Exception as e:
                    self.logger.error("Error parsing current_travel_percent: %s", e, exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.debug("No matching position found for id: %s", pos_id)
                evaluated_value = 0.0

        elif alert_type == AlertType.PROFIT.value:
            pos_id = alert.get("position_reference_id") or alert.get("id")
            self.logger.debug("Processing PROFIT for position id: %s", pos_id)
            positions = self.data_locker.read_positions()
            self.logger.debug("Retrieved positions: %s", positions)
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                self.logger.debug("Found matching position: %s", position)
                try:
                    evaluated_value = float(position.get("profit", 0.0))
                    self.logger.debug("Parsed profit: %f", evaluated_value)
                except Exception as e:
                    self.logger.error("Error parsing profit: %s", e, exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.debug("No matching position found for id: %s", pos_id)
                evaluated_value = 0.0

        else:
            self.logger.debug("Alert type %s not recognized for evaluation; defaulting evaluated_value to 0.0", alert_type)
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
            "state": "Normal",
            "last_triggered": None,
            "status": Status.ACTIVE.value,
            "frequency": 1,
            "counter": 0,
            "liquidation_distance": 0.0,
            "target_travel_percent": 0.0,
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
                         state="Normal", position_reference_id=None, status="Active"):
                self.id = str(uuid4())
                self.alert_type = alert_type
                self.alert_class = alert_class
                self.asset_type = asset_type
                self.trigger_value = trigger_value
                self.condition = condition
                self.notification_type = notification_type
                self.state = state
                self.last_triggered = None
                self.status = status
                self.frequency = 1
                self.counter = 0
                self.liquidation_distance = 0.0
                self.target_travel_percent = 0.0
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
                    "state": self.state,
                    "last_triggered": self.last_triggered,
                    "status": self.status,
                    "frequency": self.frequency,
                    "counter": self.counter,
                    "liquidation_distance": self.liquidation_distance,
                    "target_travel_percent": self.target_travel_percent,
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

    def _update_alert_state(self, pos: dict, new_state: str, evaluated_value: Optional[float] = None):
        alert_id = pos.get("alert_reference_id") or pos.get("id")
        if not alert_id:
            UnifiedLogger().log_operation(
                operation_type="Alert Update Skipped",
                primary_text="No alert identifier found for updating state.",
                source="AlertController",
                file="alert_controller.py"
            )
            return

        update_fields = {"state": new_state}
        if evaluated_value is not None:
            update_fields["evaluated_value"] = evaluated_value

        if pos.get("alert_reference_id") and pos.get("id"):
            update_fields["position_reference_id"] = pos.get("id")

        UnifiedLogger().log_operation(
            operation_type="Alert State Update",
            primary_text=f"Updating alert '{alert_id}' with {update_fields}",
            source="AlertController",
            file="alert_controller.py"
        )
        try:
            num_updated = self.data_locker.update_alert_conditions(alert_id, update_fields)
            if num_updated == 0:
                UnifiedLogger().log_operation(
                    operation_type="Alert Update",
                    primary_text=f"No alert record found for id '{alert_id}', creating new alert record.",
                    source="AlertController",
                    file="alert_controller.py"
                )
                new_alert = Alert(
                    id=str(uuid4()),
                    alert_type=AlertType.TRAVEL_PERCENT_LIQUID.value,
                    alert_class=AlertClass.POSITION.value,
                    trigger_value=pos.get("travel_percent", 0.0),
                    notification_type=NotificationType.ACTION.value,
                    last_triggered=None,
                    status=Status.ACTIVE.value,
                    frequency=1,
                    counter=0,
                    liquidation_distance=pos.get("liquidation_distance", 0.0),
                    target_travel_percent=pos.get("travel_percent", 0.0),
                    liquidation_price=pos.get("liquidation_price", 0.0),
                    notes="Auto-created alert record",
                    position_reference_id=pos.get("id"),
                    state=new_state,
                    evaluated_value=evaluated_value or 0.0
                )
                created = self.create_alert(new_alert)
                if created:
                    UnifiedLogger().log_operation(
                        operation_type="Alert Creation",
                        primary_text=f"Created new alert record for position {pos.get('id')}",
                        source="AlertController",
                        file="alert_controller.py"
                    )
                    pos["alert_reference_id"] = new_alert.id
                else:
                    UnifiedLogger().log_operation(
                        operation_type="Alert Creation Failed",
                        primary_text=f"Failed to create new alert record for position {pos.get('id')}",
                        source="AlertController",
                        file="alert_controller.py"
                    )
            else:
                UnifiedLogger().log_operation(
                    operation_type="Alert State Updated",
                    primary_text=f"Updated alert '{alert_id}' to state '{new_state}' with evaluated value '{evaluated_value}'.",
                    source="AlertController",
                    file="alert_controller.py"
                )
        except Exception as e:
            UnifiedLogger().log_operation(
                operation_type="Alert Update Error",
                primary_text=f"Error updating alert state for id '{alert_id}': {e}",
                source="AlertController",
                file="alert_controller.py"
            )

    def create_travel_percent_alerts(self):
        created_alerts = []
        cursor = self.data_locker.conn.cursor()
        positions = cursor.execute("SELECT * FROM positions").fetchall()
        cursor.close()
        for pos in positions:
            pos_dict = dict(pos)
            if not pos_dict.get("alert_reference_id"):
                asset = pos_dict.get("asset_type", "BTC")
                try:
                    trigger_value = float(-4.0)
                except Exception:
                    trigger_value = -4.0
                condition = "BELOW"
                notification_type = "Call"
                position_id = pos_dict.get("id")
                class DummyAlert:
                    def __init__(self):
                        self.id = str(uuid4())
                        self.alert_type = "TravelPercentAlert"  # Or use AlertType.TRAVEL_PERCENT_LIQUID.value
                        self.alert_class = "Position"
                        self.asset_type = asset
                        self.trigger_value = trigger_value
                        self.condition = condition
                        self.notification_type = notification_type
                        self.state = "Normal"
                        self.last_triggered = None
                        self.status = "Active"
                        self.frequency = 1
                        self.counter = 0
                        self.liquidation_distance = 0.0
                        self.target_travel_percent = 0.0
                        self.liquidation_price = 0.0
                        self.notes = "Auto-created alert record"
                        self.position_reference_id = position_id
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
                            "state": self.state,
                            "last_triggered": self.last_triggered,
                            "status": self.status,
                            "frequency": self.frequency,
                            "counter": self.counter,
                            "liquidation_distance": self.liquidation_distance,
                            "target_travel_percent": self.target_travel_percent,
                            "liquidation_price": self.liquidation_price,
                            "notes": self.notes,
                            "position_reference_id": self.position_reference_id,
                            "evaluated_value": self.evaluated_value
                        }
                alert_obj = DummyAlert()
                if self.create_alert(alert_obj):
                    created_alerts.append(alert_obj.to_dict())
                    UnifiedLogger().log_operation(
                        operation_type="Create Travel Percent Alert",
                        primary_text=f"Created travel percent alert for position {position_id} ({asset}).",
                        source="AlertController",
                        file="alert_controller.py"
                    )
                    conn = self.data_locker.get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (alert_obj.id, position_id))
                    conn.commit()
                else:
                    UnifiedLogger().log_operation(
                        operation_type="Create Travel Percent Alert Failed",
                        primary_text=f"Failed to create travel percent alert for position {position_id}.",
                        source="AlertController",
                        file="alert_controller.py"
                    )
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
        class DummyAlert:
            def __init__(self, alert_type, alert_class, asset_type, trigger_value, condition, notification_type,
                         position_reference_id, state="Normal", status="Active"):
                self.id = str(uuid4())
                self.alert_type = alert_type
                self.alert_class = alert_class
                self.asset_type = asset_type
                self.trigger_value = trigger_value
                self.condition = condition
                self.notification_type = notification_type
                self.state = state
                self.last_triggered = None
                self.status = status
                self.frequency = 1
                self.counter = 0
                self.liquidation_distance = 0.0
                self.target_travel_percent = 0.0
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
                    "state": self.state,
                    "last_triggered": self.last_triggered,
                    "status": self.status,
                    "frequency": self.frequency,
                    "counter": self.counter,
                    "liquidation_distance": self.liquidation_distance,
                    "target_travel_percent": self.target_travel_percent,
                    "liquidation_price": self.liquidation_price,
                    "notes": self.notes,
                    "position_reference_id": self.position_reference_id
                }
        for pos in positions:
            asset = pos.get("asset_type", "BTC")
            try:
                profit_val = float(pos.get("profit", 0.0))
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
            dummy_alert = DummyAlert(
                alert_type=AlertType.PROFIT.value,
                alert_class=AlertClass.POSITION.value,
                asset_type=asset,
                trigger_value=computed_trigger,
                condition=condition,
                notification_type=notification_type,
                position_reference_id=position_id,
                state=current_level,
                status=Status.ACTIVE.value
            )
            if self.create_alert(dummy_alert):
                created_alerts.append(dummy_alert.to_dict())
                print(f"Created profit alert for position {position_id} ({asset}): level {current_level}, computed trigger {computed_trigger}, notification {notification_type}.")
            else:
                print(f"Failed to create profit alert for position {position_id}.")
        return created_alerts

    #print("↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️↩️")

    def refresh_position_alerts(self) -> int:
        """
        Periodically refreshes position alerts by pulling the latest position data.
        For each alert with alert_class "Position" and a valid position_reference_id,
        it re-enriches the alert, updates the record in the database, and confirms the write.
        Returns the count of alerts updated and confirmed.
        """
        updated_count = 0
        try:
            alerts = self.get_all_alerts()
            positions = self.data_locker.read_positions()
            for alert in alerts:
                # Early debug: print alert id, class, and position reference.
                print(
                    f"[Early Debug] Processing alert ID: {alert.get('id')} | Class: {alert.get('alert_class')} | Position Ref ID: {alert.get('position_reference_id')}")
                self.logger.debug(
                    f"[Early Debug] Processing alert ID: {alert.get('id')} | Class: {alert.get('alert_class')} | Position Ref ID: {alert.get('position_reference_id')}")

                if alert.get("alert_class") == "Position" and alert.get("position_reference_id"):
                    pos_id = alert["position_reference_id"]
                    # Find the corresponding position.
                    position = next((p for p in positions if p.get("id") == pos_id), None)
                    if not position:
                        print(f"[Refresh] No position found for id {pos_id}.")
                        self.logger.error(f"No position found for id {pos_id} during periodic alert refresh.")
                        continue

                    # Log original alert data.
                    print(f"[Before Update] Alert {alert['id']} original values: {alert}")
                    self.logger.debug(f"[Before Update] Alert {alert['id']} original values: {alert}")

                    # Enrich a copy of the alert.
                    enriched_alert = self.enrich_alert(alert.copy())
                    update_fields = {
                        "liquidation_distance": enriched_alert.get("liquidation_distance", 0.0),
                        "liquidation_price": enriched_alert.get("liquidation_price", 0.0),
                        "target_travel_percent": enriched_alert.get("target_travel_percent", 0.0),
                        "evaluated_value": enriched_alert.get("evaluated_value", 0.0)
                    }
                    print(f"[Update Data] Alert {enriched_alert['id']} will be updated with: {update_fields}")
                    self.logger.debug(
                        f"[Update Data] Alert {enriched_alert['id']} will be updated with: {update_fields}")

                    # Execute update.
                    rows_updated = self.data_locker.update_alert_conditions(enriched_alert["id"], update_fields)
                    print(f"[Update Result] Rows updated for alert {enriched_alert['id']}: {rows_updated}")
                    self.logger.debug(f"Rows updated for alert {enriched_alert['id']}: {rows_updated}")

                    # Query the alert to confirm the update.
                    cursor = self.data_locker.conn.cursor()
                    cursor.execute(
                        "SELECT liquidation_distance, liquidation_price, target_travel_percent, evaluated_value FROM alerts WHERE id=?",
                        (enriched_alert["id"],)
                    )
                    row = cursor.fetchone()
                    if row:
                        confirmed_values = {
                            "liquidation_distance": row["liquidation_distance"],
                            "liquidation_price": row["liquidation_price"],
                            "target_travel_percent": row["target_travel_percent"],
                            "evaluated_value": row["evaluated_value"]
                        }
                        print(f"[After Update] Alert {enriched_alert['id']} confirmed values: {confirmed_values}")
                        self.logger.info(
                            f"[After Update] Alert {enriched_alert['id']} confirmed values: {confirmed_values}")

                        # Compute differences.
                        diff_liq_dist = abs(
                            confirmed_values["liquidation_distance"] - update_fields["liquidation_distance"])
                        diff_liq_price = abs(confirmed_values["liquidation_price"] - update_fields["liquidation_price"])
                        diff_target_travel = abs(
                            confirmed_values["target_travel_percent"] - update_fields["target_travel_percent"])
                        diff_eval_value = abs(confirmed_values["evaluated_value"] - update_fields["evaluated_value"])

                        print(f"[Differences] Alert {enriched_alert['id']} differences:")
                        print(f"  liquidation_distance diff: {diff_liq_dist}")
                        print(f"  liquidation_price diff:    {diff_liq_price}")
                        print(f"  target_travel_percent diff:{diff_target_travel}")
                        print(f"  evaluated_value diff:      {diff_eval_value}")
                        self.logger.debug(
                            f"Alert {enriched_alert['id']} differences -> liquidation_distance: {diff_liq_dist}, "
                            f"liquidation_price: {diff_liq_price}, target_travel_percent: {diff_target_travel}, "
                            f"evaluated_value: {diff_eval_value}")

                        tolerance = 1e-6
                        if (diff_liq_dist < tolerance and diff_liq_price < tolerance and
                                diff_target_travel < tolerance and diff_eval_value < tolerance):
                            updated_count += 1
                            print(f"[Confirmation] Alert {enriched_alert['id']} update confirmed.")
                            self.logger.info(f"Alert {enriched_alert['id']} update confirmed.")
                        else:
                            print(f"[Mismatch] Alert {enriched_alert['id']} update mismatch.")
                            print(f"  Intended update: {update_fields}")
                            print(f"  Confirmed in DB: {confirmed_values}")
                            self.logger.error(
                                f"Alert {enriched_alert['id']} update mismatch. Intended: {update_fields} | Confirmed: {confirmed_values}")
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
        class DummyAlert:
            def __init__(self, alert_type, alert_class, asset_type, trigger_value, condition, notification_type, position_reference_id, state="Normal", status="Active"):
                self.id = str(uuid4())
                self.alert_type = alert_type
                self.alert_class = alert_class
                self.asset_type = asset_type
                self.trigger_value = trigger_value
                self.condition = condition
                self.notification_type = notification_type
                self.state = state
                self.last_triggered = None
                self.status = status
                self.frequency = 1
                self.counter = 0
                self.liquidation_distance = 0.0
                self.target_travel_percent = 0.0
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
                    "state": self.state,
                    "last_triggered": self.last_triggered,
                    "status": self.status,
                    "frequency": self.frequency,
                    "counter": self.counter,
                    "liquidation_distance": self.liquidation_distance,
                    "target_travel_percent": self.target_travel_percent,
                    "liquidation_price": self.liquidation_price,
                    "notes": self.notes,
                    "position_reference_id": self.position_reference_id
                }
        for pos in positions:
            asset = pos.get("asset_type", "BTC")
            trigger_value = float(heat_config.get("trigger_value", 0.0))
            condition = heat_config.get("condition", "ABOVE")
            notifications = heat_config.get("notifications", {})
            notification_type = "Call" if notifications.get("call", False) else "Email"
            position_id = pos.get("id")
            dummy_alert = DummyAlert(
                alert_type=AlertType.HEAT_INDEX.value,
                alert_class=AlertClass.POSITION.value,
                asset_type=asset,
                trigger_value=trigger_value,
                condition=condition,
                notification_type=notification_type,
                position_reference_id=position_id,
                state="Normal",
                status=Status.ACTIVE.value
            )
            if self.create_alert(dummy_alert):
                created_alerts.append(dummy_alert.to_dict())
                print(f"Created heat index alert for position {position_id} ({asset}): condition {condition}, trigger {trigger_value}, notification {notification_type}.")
            else:
                print(f"Failed to create heat index alert for position {position_id}.")
        return created_alerts

    def populate_evaluated_value_for_alert(self, alert: dict) -> float:
        self.logger.debug("Entering populate_evaluated_value_for_alert with alert: %s", alert)
        evaluated_value = 0.0
        alert_type = alert.get("alert_type")
        self.logger.debug("Alert type: %s", alert_type)

        if alert_type == AlertType.PRICE_THRESHOLD.value:
            asset = alert.get("asset_type", "BTC")
            self.logger.debug("Processing PRICE_THRESHOLD for asset: %s", asset)
            price_record = self.data_locker.get_latest_price(asset)
            if price_record:
                self.logger.debug("Found price record: %s", price_record)
                try:
                    evaluated_value = float(price_record.get("current_price", 0.0))
                    self.logger.debug("Parsed current_price: %f", evaluated_value)
                except Exception as e:
                    self.logger.error("Error parsing current_price from price_record: %s", e, exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.debug("No price record found for asset: %s", asset)
                evaluated_value = 0.0

        elif alert_type == AlertType.TRAVEL_PERCENT_LIQUID.value:
            pos_id = alert.get("position_reference_id") or alert.get("id")
            self.logger.debug("Processing TRAVEL_PERCENT_LIQUID for position id: %s", pos_id)
            positions = self.data_locker.read_positions()
            self.logger.debug("Retrieved positions: %s", positions)
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                self.logger.debug("Found matching position: %s", position)
                try:
                    evaluated_value = float(position.get("current_travel_percent", 0.0))
                    self.logger.debug("Parsed current_travel_percent: %f", evaluated_value)
                except Exception as e:
                    self.logger.error("Error parsing current_travel_percent: %s", e, exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.debug("No matching position found for id: %s", pos_id)
                evaluated_value = 0.0

        elif alert_type == AlertType.PROFIT.value:
            pos_id = alert.get("position_reference_id") or alert.get("id")
            self.logger.debug("Processing PROFIT for position id: %s", pos_id)
            positions = self.data_locker.read_positions()
            self.logger.debug("Retrieved positions: %s", positions)
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                self.logger.debug("Found matching position: %s", position)
                try:
                    evaluated_value = float(position.get("profit", 0.0))
                    self.logger.debug("Parsed profit: %f", evaluated_value)
                except Exception as e:
                    self.logger.error("Error parsing profit: %s", e, exc_info=True)
                    evaluated_value = 0.0
            else:
                self.logger.debug("No matching position found for id: %s", pos_id)
                evaluated_value = 0.0

        else:
            self.logger.debug("Alert type %s not recognized for evaluation; defaulting evaluated_value to 0.0", alert_type)
            evaluated_value = 0.0

        self.logger.debug("Exiting populate_evaluated_value_for_alert with evaluated_value: %f", evaluated_value)
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




