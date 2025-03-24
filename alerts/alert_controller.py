from data.data_locker import DataLocker
from utils.json_manager import JsonManager, JsonType
from data.models import AlertType, AlertClass, NotificationType, Status
from uuid import uuid4
from data.models import Alert, AlertType, AlertClass, NotificationType, Status
from typing import Optional
import logging
from utils.unified_logger import UnifiedLogger

class AlertController:
    def __init__(self, db_path: str = None):
        self.u_logger = UnifiedLogger()
        if db_path:
            self.data_locker = DataLocker.get_instance(db_path)
        else:
            self.data_locker = DataLocker.get_instance()

    def create_alert(self, alert_obj) -> bool:
        try:
            alert_dict = alert_obj.to_dict()
            # Set default values if needed
            if not alert_dict.get("asset_type"):
                alert_dict["asset_type"] = "BTC"
            if not alert_dict.get("state"):
                alert_dict["state"] = "Normal"
            if "evaluated_value" not in alert_dict:
                alert_dict["evaluated_value"] = 0.0
            return self.data_locker.create_alert(alert_dict)
        except Exception as e:
            UnifiedLogger().log_operation(operation_type="Alert Creation Failed", primary_text=f"Error creating alert: {e}", source="AlertController", file="alert_controller.py")


            return False

    def delete_alert(self, alert_id: str) -> bool:
        try:
            logging.debug(f"Attempting to delete alert with id: {alert_id}")
            self.data_locker.delete_alert(alert_id)
            logging.debug(f"Successfully deleted alert with id: {alert_id}")
            return True
        except Exception as e:
            logging.error(f"Error deleting alert {alert_id}: {e}", exc_info=True)
            return False

    def update_alert(self, alert_id: str, updated_fields: dict) -> bool:
        try:
            if "status" in updated_fields:
                self.data_locker.update_alert_status(alert_id, updated_fields["status"])
            return True
        except Exception as e:
            print(f"Error updating alert: {e}")
            return False

    def get_all_alerts(self):
        try:
            return self.data_locker.get_alerts()
        except Exception as e:
            print(f"Error retrieving alerts: {e}")
            return []

    def initialize_alert_data(self, alert_data: dict = None) -> dict:
        """
        Initializes alert data with all necessary fields.
        Any fields provided in alert_data will override the defaults.
        This ensures that a new alert has a complete set of data before storing in the database.
        """
        defaults = {
            "id": None,
            "alert_type": None,
            "alert_class": None,
            "asset_type": None,
            "trigger_value": None,
            "condition": None,
            "notification_type": None,
            "state": "Normal",
            "last_triggered": None,
            "status": Status.ACTIVE.value,
            "frequency": 1,
            "counter": 0,
            "liquidation_distance": 0.0,
            "target_travel_percent": 0.0,
            "liquidation_price": 0.0,
            "notes": "",
            "position_reference_id": None
        }
        if alert_data:
            defaults.update(alert_data)
        return defaults

    def create_price_alerts(self):
        """
        Creates price alerts (for BTC, ETH, and SOL) using settings from alert_limits.json.
        Price alerts are of type PRICE_THRESHOLD and class MARKET.
        Ensures only one alert exists per asset per direction (ABOVE or BELOW).
        """
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        price_alerts_config = alert_limits.get("alert_ranges", {}).get("price_alerts", {})

        created_alerts = []
        assets = ["BTC", "ETH", "SOL"]

        # Dummy alert class for price alerts
        class DummyAlert:
            def __init__(self, alert_type, alert_class, asset_type, trigger_value, condition, notification_type,
                         state="Normal", position_reference_id=None, status="Active"):
                self.id = None
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

        # Retrieve current alerts to check for duplicates.
        existing_alerts = self.get_all_alerts()

        for asset in assets:
            config = price_alerts_config.get(asset, {})
            if config.get("enabled", False):
                condition = config.get("condition", "ABOVE").upper()
                trigger_value = float(config.get("trigger_value", 0.0))
                notifications = config.get("notifications", {})
                notification_type = "Call" if notifications.get("call", False) else "Email"

                # Check if an alert already exists for this asset and condition.
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
                    print(
                        f"Created price alert for {asset}: condition {condition}, trigger {trigger_value}, notification {notification_type}.")
                else:
                    print(f"Failed to create price alert for {asset}.")
            else:
                print(f"Price alert for {asset} is not enabled in configuration.")
        return created_alerts



    def _update_alert_state(self, pos: dict, new_state: str, evaluated_value: Optional[float] = None):
        # Use alert_reference_id if available; otherwise use the position's own id.
        alert_id = pos.get("alert_reference_id") or pos.get("id")
        if not alert_id:
            self.logger.warning("No alert identifier found for updating state; update skipped.")
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
                self.logger.warning(
                    f"[_update_alert_state] No alert record found for id '{alert_id}'. Creating new alert record.")
                # Create a new alert record for this position:
                new_alert = Alert(
                    id=str(uuid4()),
                    alert_type=AlertType.TRAVEL_PERCENT_LIQUID.value,
                    # or adjust based on the alert type you are evaluating
                    alert_class=AlertClass.POSITION.value,
                    trigger_value=pos.get("travel_percent", 0.0),  # use the appropriate field
                    notification_type=NotificationType.ACTION.value,  # adjust as needed
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
                created = self.alert_controller.create_alert(new_alert)
                if created:
                    self.logger.info(f"[_update_alert_state] Created new alert record for position {pos.get('id')}")
                    # Update the position record with the new alert id if needed:
                    pos["alert_reference_id"] = new_alert.id
                else:
                    self.logger.error(
                        f"[_update_alert_state] Failed to create new alert record for position {pos.get('id')}")
            else:
                self.logger.info(
                    f"Successfully updated alert '{alert_id}' to state '{new_state}' with evaluated value '{evaluated_value}'.")
        except Exception as e:
            self.logger.error(f"Error updating alert state for id '{alert_id}': {e}", exc_info=True)

    def create_travel_percent_alerts(self):
        # In this method, we iterate through positions and create a travel alert for positions lacking one.
        created_alerts = []
        positions = self.data_locker.conn.execute("SELECT * FROM positions").fetchall()
        for pos in positions:
            pos_dict = dict(pos)
            if not pos_dict.get("alert_reference_id"):
                asset = pos_dict.get("asset_type", "BTC")
                try:
                    trigger_value = float(-4.0)  # example threshold for travel percent
                except Exception:
                    trigger_value = -4.0
                condition = "BELOW"
                notification_type = "Call"  # or "Email", based on your configuration
                position_id = pos_dict.get("id")
                # Create a dummy alert object (you could also create a proper Alert class)
                alert_obj = type("DummyAlert", (), {})()  # a simple object
                alert_obj.id = str(uuid4())
                alert_obj.alert_type = AlertType.TRAVEL_PERCENT_LIQUID.value
                alert_obj.alert_class = AlertClass.POSITION.value
                alert_obj.asset_type = asset
                alert_obj.trigger_value = trigger_value
                alert_obj.condition = condition
                alert_obj.notification_type = notification_type
                alert_obj.state = "Normal"
                alert_obj.last_triggered = None
                alert_obj.status = Status.ACTIVE.value
                alert_obj.frequency = 1
                alert_obj.counter = 0
                alert_obj.liquidation_distance = 0.0
                alert_obj.target_travel_percent = 0.0
                alert_obj.liquidation_price = 0.0
                alert_obj.notes = ""
                alert_obj.position_reference_id = position_id
                alert_obj.evaluated_value = 0.0

                # Provide a simple to_dict() method
                alert_obj.to_dict = lambda: {
                    "id": alert_obj.id,
                    "alert_type": alert_obj.alert_type,
                    "alert_class": alert_obj.alert_class,
                    "asset_type": alert_obj.asset_type,
                    "trigger_value": alert_obj.trigger_value,
                    "condition": alert_obj.condition,
                    "notification_type": alert_obj.notification_type,
                    "state": alert_obj.state,
                    "last_triggered": alert_obj.last_triggered,
                    "status": alert_obj.status,
                    "frequency": alert_obj.frequency,
                    "counter": alert_obj.counter,
                    "liquidation_distance": alert_obj.liquidation_distance,
                    "target_travel_percent": alert_obj.target_travel_percent,
                    "liquidation_price": alert_obj.liquidation_price,
                    "notes": alert_obj.notes,
                    "position_reference_id": alert_obj.position_reference_id,
                    "evaluated_value": alert_obj.evaluated_value
                }

                if self.create_alert(alert_obj):
                    created_alerts.append(alert_obj.to_dict())
                    self.logger.info(f"Created travel percent alert for position {position_id} ({asset}).")
                    # Now update the position record with the alert id:
                    conn = self.data_locker.get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (alert_obj.id, position_id))
                    conn.commit()
                else:
                    self.logger.error(f"Failed to create travel percent alert for position {position_id}.")
        return created_alerts

    def create_all_alerts(self):
        alerts_created = []
        travel_alerts = self.create_travel_percent_alerts()
        alerts_created.extend(travel_alerts)
        # Add additional alert creation methods here (e.g., profit alerts, price alerts, etc.)
        return alerts_created

    def create_profit_alerts(self):
        """
        Iterates through positions and creates a profit alert for each.
        Profit alerts are of type PROFIT and class POSITION.
        """
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        profit_config = alert_limits.get("alert_ranges", {}).get("profit_ranges", {})

        if not profit_config.get("enabled", False):
            print("Profit alerts are not enabled in configuration.")
            return []

        created_alerts = []
        data_locker = self.data_locker
        positions = data_locker.read_positions()

        class DummyAlert:
            def __init__(self, alert_type, alert_class, asset_type, trigger_value, condition, notification_type,
                         position_reference_id, state="Normal", status="Active"):
                self.id = None
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

            # Read threshold values from the config
            try:
                low_thresh = float(profit_config.get("low", 46.23))
                med_thresh = float(profit_config.get("medium", 101.3))
                high_thresh = float(profit_config.get("high", 202.0))
            except Exception:
                continue

            # Determine alert level and computed trigger value
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
                print(
                    f"Created profit alert for position {position_id} ({asset}): level {current_level}, computed trigger {computed_trigger}, notification {notification_type}.")
            else:
                print(f"Failed to create profit alert for position {position_id}.")
        return created_alerts

    def create_heat_index_alerts(self):
        """
        Iterates through positions and creates a heat index alert for each.
        Heat index alerts are of type HEAT_INDEX and class POSITION.
        """
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        heat_config = alert_limits.get("alert_ranges", {}).get("heat_index_alerts", {})

        if not heat_config.get("enabled", False):
            print("Heat index alerts are not enabled in configuration.")
            return []

        created_alerts = []
        data_locker = self.data_locker
        positions = data_locker.read_positions()

        class DummyAlert:
            def __init__(self, alert_type, alert_class, asset_type, trigger_value, condition, notification_type, position_reference_id, state="Normal", status="Active"):
                self.id = None
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

    def populate_current_value_for_alert(self, alert: dict) -> float:
        """
        Populates the 'evaluated_value' field in an alert.
        For price alerts, it uses the current market price of the asset.
        For liquid travel percent alerts, it uses the position's 'current_travel_percent'.
        For profit alerts, it uses the position's profit (PNL).
        Returns the evaluated value.
        """
        evaluated_value = 0.0
        alert_type = alert.get("alert_type")

        # For price alerts
        if alert_type == AlertType.PRICE_THRESHOLD.value:
            asset = alert.get("asset_type", "BTC")
            price_record = self.data_locker.get_latest_price(asset)
            if price_record:
                try:
                    evaluated_value = float(price_record.get("current_price", 0.0))
                except Exception:
                    evaluated_value = 0.0
            else:
                evaluated_value = 0.0

        # For liquid travel percent alerts
        elif alert_type == AlertType.TRAVEL_PERCENT_LIQUID.value:
            pos_id = alert.get("position_reference_id") or alert.get("id")
            positions = self.data_locker.read_positions()
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                try:
                    evaluated_value = float(position.get("current_travel_percent", 0.0))
                except Exception:
                    evaluated_value = 0.0
            else:
                evaluated_value = 0.0

        # For profit alerts
        elif alert_type == AlertType.PROFIT.value:
            pos_id = alert.get("position_reference_id") or alert.get("id")
            positions = self.data_locker.read_positions()
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                try:
                    evaluated_value = float(position.get("profit", 0.0))
                except Exception:
                    evaluated_value = 0.0
            else:
                evaluated_value = 0.0

        # Log the populated value.
        self.u_logger.log_operation(
            operation_type="Populate Evaluated Value",
            primary_text=f"Alert {alert.get('id')} populated with evaluated_value {evaluated_value}",
            source="AlertController",
            file="alert_controller.py"
        )
        return evaluated_value

    def create_all_alerts(self):

        print("DEBUG: create_all_alerts method called")
        # or using the unified logger:
        self.u_logger.log_operation(
            operation_type="Create Alerts",
            primary_text="create_all_alerts method called",
            source="AlertController",
            file="alert_controller.py"
        )

        """
        Calls create_price_alerts(), create_travel_percent_alerts(), create_profit_alerts(), and create_heat_index_alerts()
        and returns the combined results.
        """
        price_alerts = self.create_price_alerts()
        travel_alerts = self.create_travel_percent_alerts()
        profit_alerts = self.create_profit_alerts()
        heat_alerts = self.create_heat_index_alerts()
        return price_alerts + travel_alerts + profit_alerts + heat_alerts

    def delete_all_alerts(self):
        """
        Deletes all alerts in the database.
        """
        alerts = self.get_all_alerts()
        count = 0
        for alert in alerts:
            if self.delete_alert(alert["id"]):
                count += 1
        print(f"Deleted {count} alerts.")
        return count
