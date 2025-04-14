from data.data_locker import DataLocker
from utils.json_manager import JsonManager, JsonType
from uuid import uuid4
from data.models import Alert, AlertType, AlertClass, NotificationType, Status
from typing import Optional
from datetime import datetime
import logging
import sqlite3
from utils.unified_logger import UnifiedLogger
from utils.update_ledger import log_alert_update
from alerts.alert_enrichment import enrich_alert_data

from uuid import uuid4
from data.models import Status  # Ensure Status is imported

# Global DummyPositionAlert definition to be used across all position alert creation methods.
from uuid import uuid4
from data.models import Status  # Ensure Status is imported

class DummyPositionAlert:
    def __init__(self, alert_type, asset_type, trigger_value, condition, notification_type, position_reference_id, position_type):
        self.id = str(uuid4())
        self.alert_type = alert_type  # e.g., "PriceThreshold", "TravelPercent", etc.
        self.alert_class = "Position"  # default for position alerts
        self.asset_type = asset_type   # e.g., "SOL"
        self.trigger_value = trigger_value  # a numeric threshold
        self.condition = condition  # e.g., "BELOW" or "ABOVE"
        self.level = "Normal"
        self.last_triggered = None
        self.status = Status.ACTIVE.value
        self.frequency = 1
        self.counter = 0
        self.liquidation_distance = 0.0
        self.travel_percent = 0.0
        self.liquidation_price = 0.0
        self.notes = f"Position {alert_type} alert created by Cyclone"
        self.position_reference_id = position_reference_id
        self.evaluated_value = 0.0
        self.position_type = position_type   # New field to store LONG/SHORT
        self.notification_type = notification_type  # FIX: assign the notification_type

    def to_dict(self):
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "alert_class": self.alert_class,
            "asset_type": self.asset_type,
            "trigger_value": self.trigger_value,
            "condition": self.condition,
            "notification_type": self.notification_type,  # Now available
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
            "evaluated_value": self.evaluated_value,
            "position_type": self.position_type
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

    def get_position_type(self, position_id: str) -> str:
        """
        Looks up the position from the database using its ID and returns its normalized position type.
        Defaults to 'LONG' if not found or if the position_type is blank.
        """
        try:
            positions = self.data_locker.read_positions()
            pos = next((p for p in positions if p.get("id") == position_id), None)
            if pos is None:
                self.logger.warning("Position with id %s not found. Defaulting to LONG.", position_id)
                return "LONG"
            ptype = pos.get("position_type")
            if not ptype or ptype.strip() == "":
                return "LONG"
            return ptype.upper()
        except Exception as e:
            self.logger.error("Error retrieving position type for id %s: %s", position_id, e, exc_info=True)
            return "LONG"

    def create_alert(self, alert_obj) -> bool:
        """
        Creates an alert record in the database. For market alerts (PriceThreshold), position_type is set to None.
        For other alerts, the position type is determined by calling get_position_type() using the position_reference_id.
        After insertion, the inserted alert is queried from the database to verify that position_type is stored.
        """
        try:
            self.logger.debug("[DEBUG] Starting create_alert process.")
            # Convert alert object to dictionary if needed.
            if not isinstance(alert_obj, dict):
                alert_dict = alert_obj.to_dict()
                self.logger.debug("[DEBUG] Converted alert object to dict.")
            else:
                alert_dict = alert_obj
                self.logger.debug("[DEBUG] Alert object is already a dict.")

            self.logger.debug(f"[DEBUG] Alert before processing: {alert_dict}")

            # Set alert_class based on alert type.
            if alert_dict["alert_type"] == AlertType.PRICE_THRESHOLD.value:
                alert_dict["alert_class"] = AlertClass.MARKET.value
            else:
                alert_dict["alert_class"] = AlertClass.POSITION.value
            self.logger.debug(f"[DEBUG] Set alert_class to: {alert_dict['alert_class']}")

            # Initialize alert defaults.
            alert_dict = self.initialize_alert_data(alert_dict)
            self.logger.debug(f"[DEBUG] Alert after initializing defaults: {alert_dict}")

            # Set position_type:
            if alert_dict["alert_type"] == AlertType.PRICE_THRESHOLD.value:
                # Market alerts don't need position type.
                alert_dict["position_type"] = None
            else:
                pos_ref_id = alert_dict.get("position_reference_id")
                if pos_ref_id:
                    alert_dict["position_type"] = self.get_position_type(pos_ref_id)
                else:
                    alert_dict["position_type"] = "LONG"
            self.logger.debug(f"[DEBUG] Final alert_dict to insert (including position_type): {alert_dict}")

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
                    evaluated_value,
                    position_type
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
                    :evaluated_value,
                    :position_type
                )
            """
            self.logger.debug(f"[DEBUG] Executing SQL for alert creation: {sql}")
            cursor = self.data_locker.conn.cursor()
            cursor.execute(sql, alert_dict)
            self.data_locker.conn.commit()
            self.logger.debug(f"[DEBUG] Alert inserted successfully with ID: {alert_dict['id']}")

            # Immediately verify by fetching the stored position_type from the DB.
            cursor.execute("SELECT position_type FROM alerts WHERE id = ?", (alert_dict["id"],))
            row = cursor.fetchone()
            if row is not None:
                self.logger.debug(
                    f"[DEBUG] Retrieved position_type from DB for alert {alert_dict['id']}: {row['position_type']}")
                print(f"[DEBUG] Inserted alert position_type from DB: {row['position_type']}")
            else:
                self.logger.error(f"[DEBUG] No DB record found for alert {alert_dict['id']} after insertion.")

            from utils.update_ledger import log_alert_update
            log_alert_update(self.data_locker, alert_dict['id'], 'system', 'Initial creation', '', 'Created')
            self.logger.debug("Initial creation logged to ledger.")

            enriched_alert = self.enrich_alert(alert_dict)
            self.logger.debug(f"[DEBUG] Alert after enrichment: {enriched_alert}")

            return True
        except sqlite3.IntegrityError as ie:
            self.logger.error("CREATE ALERT: IntegrityError creating alert: %s", ie, exc_info=True)
            return False
        except Exception as ex:
            self.logger.exception("CREATE ALERT: Unexpected error in create_alert: %s", ex)
            raise

    def create_all_position_alerts(self) -> list:
        """
        Iterates over each position and creates individual alerts for each enabled
        metric (travel percent, profit, and heat index) if not already mapped.
        Returns a list of created alert dictionaries.
        """
        created_alerts = []
        positions = self.data_locker.read_positions()
        # Load configuration for enabled alert types.
        alert_limits = self.json_manager.load("", JsonType.ALERT_LIMITS)

        for pos in positions:
            position_id = pos.get("id")
            # 1. Travel Percent Alert
            travel_config = alert_limits.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
            if travel_config.get("enabled", False):
                if not self.data_locker.has_alert_mapping(position_id, AlertType.TRAVEL_PERCENT_LIQUID.value):
                    travel_alert = self.create_alert_for_position(pos, AlertType.TRAVEL_PERCENT_LIQUID.value,
                                                                  0.0, "BELOW", "Call")
                    if travel_alert:
                        created_alerts.append(travel_alert)
            # 2. Profit Alert
            profit_config = alert_limits.get("alert_ranges", {}).get("profit_ranges", {})
            if profit_config.get("enabled", False):
                if not self.data_locker.has_alert_mapping(position_id, AlertType.PROFIT.value):
                    try:
                        profit_val = float(pos.get("pnl_after_fees_usd", 0.0))
                    except Exception:
                        profit_val = 0.0
                    profit_alert = self.create_alert_for_position(pos, AlertType.PROFIT.value,
                                                                  profit_val, "ABOVE", "Call")
                    if profit_alert:
                        created_alerts.append(profit_alert)
            # 3. Heat Index Alert
            heat_config = alert_limits.get("alert_ranges", {}).get("heat_index_ranges", {})
            if heat_config.get("enabled", False):
                if not self.data_locker.has_alert_mapping(position_id, AlertType.HEAT_INDEX.value):
                    try:
                        heat_val = float(pos.get("current_heat_index", 0.0))
                    except Exception:
                        heat_val = 0.0
                    heat_alert = self.create_alert_for_position(pos, AlertType.HEAT_INDEX.value,
                                                                heat_val, "ABOVE", "Call")
                    if heat_alert:
                        created_alerts.append(heat_alert)
        return created_alerts

    def create_position_alertsff(self):
        """
        Create position alerts for each position that doesn't have a valid alert_reference_id.
        Returns a list of created alert dictionaries.
        """
        print("📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈📈Starting create_position_alerts method.")
        created_alerts = []
        positions = self.data_locker.read_positions()
        self.logger.debug("Retrieved {} positions from the database.".format(len(positions)))

        for pos in positions:
            pos_id = pos.get("id")
            # Check if alert_reference_id is missing or empty.
            if not pos.get("alert_reference_id") or pos.get("alert_reference_id").strip() == "":
                asset = pos.get("asset_type", "BTC")
                # Retrieve position_type robustly:
                position_type = pos.get("position_type")
                if not position_type or (isinstance(position_type, str) and position_type.strip() == ""):
                    position_type = "LONG"
                else:
                    position_type = position_type.upper()
                self.logger.debug("Creating alert for position {} with position_type: {}".format(pos_id, position_type))

                # For testing, set trigger_value to 0.0 (which triggers enrichment later)
                try:
                    trigger_value = float(0.0)
                    self.logger.debug("Using trigger_value {} for position {}.".format(trigger_value, pos_id))
                except Exception as e:
                    self.logger.error("Error converting trigger_value for position {}: {}".format(pos_id, e))
                    trigger_value = 0.0
                condition = "BELOW"
                notification_type = "Call"

                alert_obj = DummyPositionAlert(
                    AlertType.TRAVEL_PERCENT_LIQUID.value,
                    asset,
                    trigger_value,
                    condition,
                    notification_type,
                    pos_id,
                    position_type  # New parameter passed
                )
                # Log the created alert object's dictionary (should include position_type)
                self.logger.debug("Created DummyPositionAlert for position {}: {}".format(pos_id, alert_obj.to_dict()))
                print("DEBUG: Created alert object for position {} with position_type: {}".format(pos_id,
                                                                                                  alert_obj.position_type))

                if self.create_alert(alert_obj):
                    self.logger.debug(
                        "Alert created successfully for position {}: {}".format(pos_id, alert_obj.to_dict()))
                    created_alerts.append(alert_obj.to_dict())
                    # Query DB to log inserted alert's position_type
                    try:
                        conn = self.data_locker.get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT position_type FROM alerts WHERE id=?", (alert_obj.id,))
                        row = cursor.fetchone()
                        if row:
                            self.logger.debug(
                                "DB record for alert {}: position_type={}".format(alert_obj.id, row["position_type"]))
                            print("DEBUG: DB record for alert {}: position_type={}".format(alert_obj.id,
                                                                                           row["position_type"]))
                        else:
                            self.logger.error("No alert record found in DB for alert id {}".format(alert_obj.id))
                        cursor.close()
                    except Exception as e:
                        self.logger.error("Error querying alert record for alert id {}: {}".format(alert_obj.id, e),
                                          exc_info=True)
                    # Update the position record with the alert_reference_id.
                    try:
                        conn = self.data_locker.get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (alert_obj.id, pos_id))
                        conn.commit()
                        self.logger.debug("Updated position {} with alert_reference_id {}".format(pos_id, alert_obj.id))
                        cursor.close()
                    except Exception as e:
                        self.logger.error("Error updating position {} with alert_reference_id: {}".format(pos_id, e))
                else:
                    self.logger.error("Failed to create alert for position {}.".format(pos_id))
            else:
                self.logger.debug("Position {} already has alert_reference_id: '{}'. Skipping alert creation.".format(
                    pos_id, pos.get("alert_reference_id")))
        self.logger.debug("create_position_alerts completed. Created {} alerts.".format(len(created_alerts)))
        return created_alerts

    def enrich_alert(self, alert: dict) -> dict:
        """
        Enrich the alert by delegating to the shared enrichment routine.
        Passes self as the alert_controller.

        Args:
            alert (dict): The alert dictionary to enrich.

        Returns:
            dict: The enriched alert dictionary.
        """
        from alerts.alert_enrichment import enrich_alert_data
        enriched_alert = enrich_alert_data(alert, self.data_locker, self.logger, self)
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
        """
        Sets default values for alert fields if they are not provided.
        """
        from data.models import Status
        defaults = {
            "id": str(uuid4()),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "alert_type": "",
            "alert_class": "",
            "asset_type": "BTC",
            "trigger_value": 0.0,
            "condition": "ABOVE",
            "notification_type": "Email",
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
        for key, value in defaults.items():
            if key not in alert_data or alert_data.get(key) is None:
                alert_data[key] = value
        return alert_data

    def enrich_alert(self, alert: dict) -> dict:
        """
        Enriches an alert using the shared enrichment routine.
        Passes self as the alert controller.
        """
        from alerts.alert_enrichment import enrich_alert_data
        enriched_alert = enrich_alert_data(alert, self.data_locker, self.logger, self)
        return enriched_alert

    def create_price_alerts(self):
        """
        Creates market (price threshold) alerts for assets.
        Follows the BTC model—position type is not used, so it is set to None.
        """
        created_alerts = []
        from utils.json_manager import JsonManager, JsonType
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        price_alerts_config = alert_limits.get("alert_ranges", {}).get("price_alerts", {})

        # Use case-insensitive keys for configuration.
        config_by_asset = {k.upper(): v for k, v in price_alerts_config.items()}
        for asset in ["BTC", "ETH", "SOL"]:
            config = config_by_asset.get(asset.upper())
            if config is None or not config.get("enabled", False):
                self.logger.debug("Price alert for asset %s is not enabled or missing.", asset)
                continue
            condition = config.get("condition", "ABOVE").upper()
            try:
                trigger_value = float(config.get("trigger_value", 0.0))
            except Exception as e:
                self.logger.error("Error parsing trigger value for %s: %s", asset, e)
                continue
            notification_type = "Call" if config.get("notifications", {}).get("call", False) else "Email"
            # For market alerts, ignore position_reference_id and position_type.
            alert_obj = DummyPositionAlert(
                AlertType.PRICE_THRESHOLD.value,
                asset.upper(),
                trigger_value,
                condition,
                notification_type,
                None,  # No position_reference_id
                None  # Position type is not relevant.
            )
            alert_obj.level = "Normal"
            if self.create_alert(alert_obj):
                created_alerts.append(alert_obj.to_dict())
            else:
                self.logger.error("Failed to create price alert for asset %s", asset)
        return created_alerts

    def create_alert_for_position(self, pos: dict, alert_type: str, trigger_value: float,
                                  condition: str, notification_type: str) -> dict:
        """
        Creates an alert of the specified type for the given position,
        then records the mapping to allow multiple alerts per position.
        """
        position_id = pos.get("id")
        asset = pos.get("asset_type", "BTC")
        position_type = self.get_position_type(position_id)
        alert_obj = DummyPositionAlert(
            alert_type,
            asset,
            trigger_value,
            condition,
            notification_type,
            position_id,
            position_type
        )
        if self.create_alert(alert_obj):
            # After creating the alert, add a mapping record in the new table.
            self.data_locker.add_position_alert_mapping(position_id, alert_obj.id)
            return alert_obj.to_dict()
        else:
            return None

    # In alert_controller.py

    from data.models import AlertType
    from utils.json_manager import JsonManager, JsonType
    from uuid import uuid4

    class AlertController:
        # ... existing __init__ and other methods ...

        def create_alert_for_position(self, pos: dict, alert_type: str, trigger_value: float,
                                      condition: str, notification_type: str) -> dict:
            """
            Creates an alert of the specified type for the given position,
            then records the mapping to allow multiple alerts per position.
            """
            position_id = pos.get("id")
            asset = pos.get("asset_type", "BTC")
            position_type = self.get_position_type(position_id)
            alert_obj = DummyPositionAlert(
                alert_type,
                asset,
                trigger_value,
                condition,
                notification_type,
                position_id,
                position_type
            )
            if self.create_alert(alert_obj):
                # After creating the alert, add a mapping record in the new table.
                self.data_locker.add_position_alert_mapping(position_id, alert_obj.id)
                return alert_obj.to_dict()
            else:
                return None

        def create_all_position_alerts(self) -> list:
            """
            Iterates over each position and creates individual alerts for each enabled
            metric (travel percent, profit, and heat index) if not already mapped.
            """
            created_alerts = []
            positions = self.data_locker.read_positions()
            # Load configuration for enabled alert types.
            jm = self.json_manager
            alert_limits = jm.load("", JsonType.ALERT_LIMITS)

            for pos in positions:
                position_id = pos.get("id")
                # 1. Travel Percent Alert
                travel_config = alert_limits.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
                if travel_config.get("enabled", False):
                    if not self.data_locker.has_alert_mapping(position_id, AlertType.TRAVEL_PERCENT_LIQUID.value):
                        travel_alert = self.create_alert_for_position(pos, AlertType.TRAVEL_PERCENT_LIQUID.value,
                                                                      0.0, "BELOW", "Call")
                        if travel_alert:
                            created_alerts.append(travel_alert)
                # 2. Profit Alert
                profit_config = alert_limits.get("alert_ranges", {}).get("profit_ranges", {})
                if profit_config.get("enabled", False):
                    if not self.data_locker.has_alert_mapping(position_id, AlertType.PROFIT.value):
                        try:
                            profit_val = float(pos.get("pnl_after_fees_usd", 0.0))
                        except Exception:
                            profit_val = 0.0
                        profit_alert = self.create_alert_for_position(pos, AlertType.PROFIT.value,
                                                                      profit_val, "ABOVE", "Call")
                        if profit_alert:
                            created_alerts.append(profit_alert)
                # 3. Heat Index Alert
                heat_config = alert_limits.get("alert_ranges", {}).get("heat_index_ranges", {})
                if heat_config.get("enabled", False):
                    if not self.data_locker.has_alert_mapping(position_id, AlertType.HEAT_INDEX.value):
                        try:
                            heat_val = float(pos.get("current_heat_index", 0.0))
                        except Exception:
                            heat_val = 0.0
                        heat_alert = self.create_alert_for_position(pos, AlertType.HEAT_INDEX.value,
                                                                    heat_val, "ABOVE", "Call")
                        if heat_alert:
                            created_alerts.append(heat_alert)
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
        from utils.json_manager import JsonManager, JsonType  # Ensure proper imports
        jm = JsonManager()
        alert_limits = jm.load("", JsonType.ALERT_LIMITS)
        travel_config = alert_limits.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})

        # Check if travel percent alerts are enabled
        if not travel_config.get("enabled", False):
            print("Travel percent alerts are not enabled in configuration.")
            return []

        created_alerts = []
        positions = self.data_locker.read_positions()  # Consistent data retrieval
        self.logger.debug(f"Retrieved {len(positions)} positions for travel percent alert creation.")

        for pos in positions:
            pos_id = pos.get("id")
            # Create alert if alert_reference_id is missing or empty
            if not pos.get("alert_reference_id") or pos.get("alert_reference_id").strip() == "":
                asset = pos.get("asset_type", "BTC")
                # Set trigger_value to 0.0 so that enrichment will pick up and assign the real config threshold (e.g., -25.0)
                trigger_value = 0.0
                condition = "BELOW"
                notification_type = "Call"
                # Retrieve position_type robustly:
                position_type = pos.get("position_type")
                if not position_type or (isinstance(position_type, str) and position_type.strip() == ""):
                    position_type = "LONG"
                else:
                    position_type = position_type.upper()
                self.logger.debug(
                    f"Creating travel percent alert for position {pos_id} with trigger_value {trigger_value} and position_type {position_type}.")

                alert_obj = DummyPositionAlert(
                    AlertType.TRAVEL_PERCENT_LIQUID.value,
                    asset,
                    trigger_value,
                    condition,
                    notification_type,
                    pos_id,
                    position_type  # New: propagate the position type
                )

                if self.create_alert(alert_obj):
                    created_alerts.append(alert_obj.to_dict())
                    self.logger.debug(f"Created travel percent alert for position {pos_id}: {alert_obj.to_dict()}")
                    try:
                        conn = self.data_locker.get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE positions SET alert_reference_id=? WHERE id=?", (alert_obj.id, pos_id))
                        conn.commit()
                        self.logger.debug(f"Updated position {pos_id} with alert_reference_id {alert_obj.id}.")
                    except Exception as e:
                        self.logger.error(f"Error updating position {pos_id} with alert_reference_id: {e}")
                else:
                    self.logger.error(f"Failed to create travel percent alert for position {pos_id}.")
            else:
                self.logger.debug(
                    f"Position {pos_id} already has alert_reference_id: '{pos.get('alert_reference_id')}'. Skipping alert creation.")
        self.logger.debug(f"create_travel_percent_alerts completed. Created {len(created_alerts)} alerts.")
        return created_alerts

    def create_profit_alerts(self):
        """
        Creates a profit alert for each position, regardless of whether the calculated profit is positive or negative.
        """
        created_alerts = []
        positions = self.data_locker.read_positions()
        for pos in positions:
            asset = pos.get("asset_type", "BTC")
            pos_id = pos.get("id")
            try:
                profit_val = float(pos.get("pnl_after_fees_usd", 0.0))
            except Exception as e:
                self.logger.error("Error parsing profit for position %s: %s", pos_id, e)
                profit_val = 0.0
            condition = "ABOVE"  # Use a default condition (adjustable as needed)
            notification_type = "Call"  # Default notification type
            # Retrieve position type via DB lookup
            position_type = self.get_position_type(pos_id)
            alert_obj = DummyPositionAlert(
                AlertType.PROFIT.value,
                asset,
                profit_val,  # Use profit as the trigger value
                condition,
                notification_type,
                pos_id,
                position_type
            )
            alert_obj.level = "Normal"  # Set default level; adjust if you want level logic later
            if self.create_alert(alert_obj):
                created_alerts.append(alert_obj.to_dict())
            else:
                self.logger.error("Failed to create profit alert for position %s", pos_id)
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
        """
        Creates a heat index alert for each position regardless of the current heat index value.
        """
        created_alerts = []
        positions = self.data_locker.read_positions()
        for pos in positions:
            asset = pos.get("asset_type", "BTC")
            pos_id = pos.get("id")
            try:
                current_heat = float(pos.get("current_heat_index", 0.0))
            except Exception as e:
                self.logger.error("Error parsing heat index for position %s: %s", pos_id, e)
                current_heat = 0.0
            # Use a default trigger for heat alerts (could also be pulled from config)
            trigger_value = 12.0
            condition = "ABOVE"  # Heat alert triggers when current_heat exceeds trigger_value
            notification_type = "Call"
            position_type = self.get_position_type(pos_id)
            alert_obj = DummyPositionAlert(
                AlertType.HEAT_INDEX.value,
                asset,
                trigger_value,
                condition,
                notification_type,
                pos_id,
                position_type
            )
            alert_obj.level = "Normal"  # Set default level
            if self.create_alert(alert_obj):
                created_alerts.append(alert_obj.to_dict())
            else:
                self.logger.error("Failed to create heat alert for position %s", pos_id)
        return created_alerts

    def create_all_alerts(self):
        print("✨✨✨✨✨✨✨✨                ✨✨✨✨✨✨✨✨✨✨✨✨✨")
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
