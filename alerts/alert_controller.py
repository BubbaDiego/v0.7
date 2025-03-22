from data.data_locker import DataLocker
from utils.json_manager import JsonManager, JsonType
from data.models import AlertType, AlertClass, NotificationType, Status

class AlertController:
    def __init__(self, db_path: str = None):
        if db_path:
            self.data_locker = DataLocker.get_instance(db_path)
        else:
            self.data_locker = DataLocker.get_instance()

    def create_alert(self, alert_obj) -> bool:
        """
        Insert an alert into the DB, including asset_type and state.
        """
        try:
            # Convert alert_obj to dict
            alert_dict = alert_obj.to_dict()

            # If asset_type was missing, default to something:
            if not alert_dict.get("asset_type"):
                alert_dict["asset_type"] = "BTC"

            # If state was missing, default to "Normal"
            if not alert_dict.get("state"):
                alert_dict["state"] = "Normal"

            self.data_locker.create_alert(alert_dict)
            return True
        except Exception as e:
            print(f"Error creating alert: {e}")
            return False

    def delete_alert(self, alert_id: str) -> bool:
        try:
            self.data_locker.delete_alert(alert_id)
            return True
        except Exception as e:
            print(f"Error deleting alert: {e}")
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
        """
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        price_alerts_config = alert_limits.get("alert_ranges", {}).get("price_alerts", {})

        created_alerts = []
        assets = ["BTC", "ETH", "SOL"]

        # Dummy alert class for price alerts
        class DummyAlert:
            def __init__(self, alert_type, alert_class, asset_type, trigger_value, condition, notification_type, state="Normal", position_reference_id=None, status="Active"):
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

        for asset in assets:
            config = price_alerts_config.get(asset, {})
            if config.get("enabled", False):
                condition = config.get("condition", "ABOVE")
                trigger_value = float(config.get("trigger_value", 0.0))
                notifications = config.get("notifications", {})
                notification_type = "Call" if notifications.get("call", False) else "Email"
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

    def create_travel_percent_alerts(self):
        """
        Iterates through active positions and creates a corresponding travel percent alert
        for each. Travel percent alerts are of type TRAVEL_PERCENT_LIQUID and class POSITION.
        """
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        travel_config = alert_limits.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})

        if not travel_config.get("enabled", False):
            print("Travel percent alerts are not enabled in configuration.")
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
            if not pos.get("alert_reference_id"):
                asset = pos.get("asset_type", "BTC")
                trigger_value = float(travel_config.get("low", 0.0))
                condition = "BELOW"
                notifications = travel_config.get("low_notifications", {})
                notification_type = "Call" if notifications.get("call", False) else "Email"
                position_id = pos.get("id")
                dummy_alert = DummyAlert(
                    alert_type=AlertType.TRAVEL_PERCENT_LIQUID.value,
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
                    print(f"Created travel percent alert for position {position_id} ({asset}): condition {condition}, trigger {trigger_value}, notification {notification_type}.")
                    try:
                        conn = data_locker.get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (dummy_alert.id, position_id))
                        conn.commit()
                        print(f"Updated position {position_id} with alert_reference_id {dummy_alert.id}.")
                    except Exception as e:
                        print(f"Error updating position {position_id} with alert reference: {e}")
                else:
                    print(f"Failed to create travel percent alert for position {position_id}.")
        return created_alerts

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

    def create_all_alerts(self):
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
