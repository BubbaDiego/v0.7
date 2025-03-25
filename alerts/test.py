import unittest
import os
from uuid import uuid4
from datetime import datetime
from pprint import pprint
import logging

# --- Fake Enums and Models ---
class AlertType:
    PRICE_THRESHOLD = type("Enum", (), {"value": "PriceThreshold"})
    TRAVEL_PERCENT_LIQUID = type("Enum", (), {"value": "TravelPercentLiquid"})
    PROFIT = type("Enum", (), {"value": "Profit"})
    HEAT_INDEX = type("Enum", (), {"value": "HeatIndex"})

class AlertClass:
    MARKET = type("Enum", (), {"value": "Market"})
    POSITION = type("Enum", (), {"value": "Position"})

class NotificationType:
    ACTION = type("Enum", (), {"value": "Action"})

class Status:
    ACTIVE = type("Enum", (), {"value": "active"})

# Fake Alert model (we only use its properties in to_dict())
class Alert:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def to_dict(self):
        return self.__dict__.copy()

# --- Fake DataLocker ---
class FakeDataLocker:
    def __init__(self):
        self.created_alerts = []
        self._positions = []  # List to simulate positions
        self._conn = FakeConn()  # Fake connection

    def create_alert(self, alert_dict):
        # For testing, simply append and return True.
        self.created_alerts.append(alert_dict)
        return True

    def get_alerts(self):
        # For testing, return an empty list (or we can return self.created_alerts copy)
        return self.created_alerts.copy()

    def delete_alert(self, alert_id: str):
        # For testing, simulate deletion by removing matching alert from created_alerts
        before = len(self.created_alerts)
        self.created_alerts = [a for a in self.created_alerts if a.get("id") != alert_id]
        return len(self.created_alerts) < before

    def update_alert_status(self, alert_id: str, status):
        # For testing, update status in created_alerts if found.
        updated = False
        for a in self.created_alerts:
            if a.get("id") == alert_id:
                a["status"] = status
                updated = True
        return updated

    def read_positions(self):
        # Return our fake positions list.
        return self._positions.copy()

    @property
    def conn(self):
        return self._conn

# Fake connection and cursor to support our tests
class FakeCursor:
    def __init__(self, data=None):
        self.data = data or []
        self.rowcount = 0
    def execute(self, query, params=()):
        # We'll simulate deletion: if query starts with DELETE, return rowcount as number of items in self.data.
        if query.strip().upper().startswith("DELETE"):
            self.rowcount = len(self.data)
            self.data = []  # clear data
    def fetchall(self):
        return self.data
    def fetchone(self):
        return [len(self.data)]
    def close(self):
        pass

class FakeConn:
    def __init__(self):
        self._cursor = FakeCursor()
    def cursor(self):
        return FakeCursor(self._cursor.data)
    def commit(self):
        pass

# --- Fake JsonManager ---
class FakeJsonManager:
    def load(self, path, json_type):
        return {
            "default_notification_type": "Email",
            "alert_ranges": {
                "price_alerts": {
                    "BTC": {"enabled": True, "condition": "ABOVE", "trigger_value": 50000, "notifications": {"call": True}},
                    "ETH": {"enabled": True, "condition": "ABOVE", "trigger_value": 4000, "notifications": {"call": False}},
                    "SOL": {"enabled": True, "condition": "ABOVE", "trigger_value": 150, "notifications": {"call": True}},
                },
                "profit_ranges": {"enabled": True, "low": 50, "medium": 100, "high": 200, "condition": "ABOVE", "notifications": {"call": True}},
                "heat_index_alerts": {"enabled": True, "trigger_value": 10, "condition": "ABOVE", "notifications": {"call": False}}
            }
        }

# --- Fake Alert Object for Testing ---
class FakeAlert:
    def __init__(self, data):
        self.data = data
    def to_dict(self):
        return self.data.copy()

# --- AlertController (Updated Version) ---
class AlertController:
    def __init__(self, db_path: str = None):
        self.u_logger = logging.getLogger("FakeUnifiedLogger")
        self.u_logger.setLevel(logging.DEBUG)
        if db_path:
            self.data_locker = FakeDataLocker()
        else:
            self.data_locker = FakeDataLocker()
        self.json_manager = FakeJsonManager()

    def create_alert(self, alert_obj) -> bool:
        try:
            alert_dict = alert_obj.to_dict()
            if not alert_dict.get("asset_type"):
                alert_dict["asset_type"] = "BTC"
            if not alert_dict.get("state"):
                alert_dict["state"] = "Normal"
            if "evaluated_value" not in alert_dict:
                alert_dict["evaluated_value"] = 0.0
            if not alert_dict.get("alert_class"):
                if alert_dict.get("alert_type") == AlertType.PRICE_THRESHOLD.value:
                    alert_dict["alert_class"] = AlertClass.MARKET.value
                else:
                    alert_dict["alert_class"] = AlertClass.POSITION.value
            if not alert_dict.get("notification_type"):
                alert_limits = self.json_manager.load("", JsonType.ALERT_LIMITS)
                alert_dict["notification_type"] = alert_limits.get("default_notification_type", "Undefined")
            if not alert_dict.get("status"):
                alert_dict["status"] = Status.ACTIVE.value
            return self.data_locker.create_alert(alert_dict)
        except Exception as e:
            return False

    def delete_alert(self, alert_id: str) -> bool:
        try:
            self.data_locker.delete_alert(alert_id)
            return True
        except Exception as e:
            return False

    def update_alert(self, alert_id: str, updated_fields: dict) -> bool:
        try:
            if "status" in updated_fields:
                self.data_locker.update_alert_status(alert_id, updated_fields["status"])
            return True
        except Exception as e:
            return False

    def get_all_alerts(self):
        try:
            return self.data_locker.get_alerts()
        except Exception as e:
            return []

    def initialize_alert_data(self, alert_data: dict = None) -> dict:
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
            "position_reference_id": None,
            "evaluated_value": 0.0
        }
        if alert_data:
            defaults.update(alert_data)
        return defaults

# --- Test Cases ---
class TestAlertCreation(unittest.TestCase):
    def setUp(self):
        self.controller = AlertController()
        self.fake_dl = self.controller.data_locker

    def test_default_asset_type(self):
        data = {"alert_type": AlertType.PRICE_THRESHOLD.value}
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["asset_type"], "BTC")

    def test_default_state(self):
        data = {"alert_type": AlertType.PRICE_THRESHOLD.value}
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["state"], "Normal")

    def test_default_evaluated_value(self):
        data = {"alert_type": AlertType.PRICE_THRESHOLD.value}
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["evaluated_value"], 0.0)

    def test_infer_alert_class_for_price_threshold(self):
        data = {"alert_type": AlertType.PRICE_THRESHOLD.value}
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["alert_class"], AlertClass.MARKET.value)

    def test_infer_alert_class_for_non_price(self):
        data = {"alert_type": "Profit"}
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["alert_class"], AlertClass.POSITION.value)

    def test_default_notification_type(self):
        data = {"alert_type": AlertType.PRICE_THRESHOLD.value}
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["notification_type"], "Email")

    def test_default_status(self):
        data = {"alert_type": AlertType.PRICE_THRESHOLD.value}
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["status"], Status.ACTIVE.value)

    def test_no_override_when_fields_present(self):
        data = {
            "alert_type": AlertType.PRICE_THRESHOLD.value,
            "asset_type": "ETH",
            "state": "Custom",
            "evaluated_value": 123.45,
            "alert_class": "CustomClass",
            "notification_type": "SMS",
            "status": "inactive"
        }
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["asset_type"], "ETH")
        self.assertEqual(created["state"], "Custom")
        self.assertEqual(created["evaluated_value"], 123.45)
        self.assertEqual(created["alert_class"], "CustomClass")
        self.assertEqual(created["notification_type"], "SMS")
        self.assertEqual(created["status"], "inactive")

    def test_partial_data_defaults(self):
        data = {"alert_type": "Profit", "trigger_value": 100}
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["asset_type"], "BTC")
        self.assertEqual(created["state"], "Normal")
        self.assertEqual(created["evaluated_value"], 0.0)

    def test_invalid_data_types(self):
        data = {"alert_type": AlertType.PRICE_THRESHOLD.value, "trigger_value": "not_a_number"}
        alert = FakeAlert(data)
        self.controller.create_alert(alert)
        created = self.fake_dl.created_alerts[-1]
        self.assertEqual(created["trigger_value"], "not_a_number")

    def test_multiple_alert_creations(self):
        data1 = {"alert_type": AlertType.PRICE_THRESHOLD.value}
        data2 = {"alert_type": "Profit"}
        alert1 = FakeAlert(data1)
        alert2 = FakeAlert(data2)
        self.controller.create_alert(alert1)
        self.controller.create_alert(alert2)
        self.assertGreaterEqual(len(self.fake_dl.created_alerts), 2)

    def test_alert_creation_returns_true(self):
        data = {"alert_type": AlertType.PRICE_THRESHOLD.value}
        alert = FakeAlert(data)
        result = self.controller.create_alert(alert)
        self.assertTrue(result)

    def test_alert_creation_failure(self):
        original_create = self.controller.data_locker.create_alert
        self.controller.data_locker.create_alert = lambda x: (_ for _ in ()).throw(Exception("Forced failure"))
        data = {"alert_type": AlertType.PRICE_THRESHOLD.value}
        alert = FakeAlert(data)
        result = self.controller.create_alert(alert)
        self.assertFalse(result)
        self.controller.data_locker.create_alert = original_create

    def test_initialize_alert_data_defaults(self):
        defaults = self.controller.initialize_alert_data()
        self.assertEqual(defaults["state"], "Normal")
        self.assertEqual(defaults["status"], Status.ACTIVE.value)
        self.assertEqual(defaults["evaluated_value"], 0.0)

    def test_initialize_alert_data_override(self):
        override = {"asset_type": "SOL", "state": "Custom", "trigger_value": 200}
        data = self.controller.initialize_alert_data(override)
        self.assertEqual(data["asset_type"], "SOL")
        self.assertEqual(data["state"], "Custom")
        self.assertEqual(data["trigger_value"], 200)

    def test_create_price_alerts(self):
        created = self.controller.create_price_alerts()
        self.assertEqual(len(created), 3)

    def test_create_price_alerts_disabled(self):
        original_load = self.controller.json_manager.load
        def fake_load(path, json_type):
            config = original_load(path, json_type)
            config["alert_ranges"]["price_alerts"]["ETH"]["enabled"] = False
            return config
        self.controller.json_manager.load = fake_load
        created = self.controller.create_price_alerts()
        self.assertEqual(len(created), 2)
        self.controller.json_manager.load = original_load

    def test_create_travel_percent_alerts(self):
        fake_positions = [
            {"id": "pos1", "asset_type": "BTC", "travel_percent": -5.0},
            {"id": "pos2", "asset_type": "ETH", "travel_percent": -3.0}
        ]
        # Inject fake positions
        self.controller.data_locker._positions = fake_positions
        created = self.controller.create_travel_percent_alerts()
        self.assertEqual(len(created), 1)

    def test_create_profit_alerts(self):
        fake_positions = [
            {"id": "pos1", "asset_type": "BTC", "profit": 150.0},
            {"id": "pos2", "asset_type": "ETH", "profit": 20.0}
        ]
        self.controller.data_locker._positions = fake_positions
        created = self.controller.create_profit_alerts()
        self.assertEqual(len(created), 1)

    def test_create_heat_index_alerts(self):
        fake_positions = [
            {"id": "pos1", "asset_type": "BTC"},
            {"id": "pos2", "asset_type": "ETH"}
        ]
        self.controller.data_locker._positions = fake_positions
        created = self.controller.create_heat_index_alerts()
        self.assertEqual(len(created), 2)

if __name__ == '__main__':
    import HtmlTestRunner
    unittest.main(testRunner=HtmlTestRunner.HTMLTestRunner(output='reports'), verbosity=2)
