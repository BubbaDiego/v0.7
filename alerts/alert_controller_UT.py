import unittest
import sqlite3
import asyncio
import logging
import re
from uuid import UUID
from datetime import datetime

# Patch the underlying DataLocker so that both modules use our dummy instance.
import data.data_locker
from alert_controller import AlertController, DummyPositionAlert
from cyclone import Cyclone  # Make sure cyclone.py is accessible (e.g., in your package or same folder)

# --- Dummy DataLocker for Testing ---
class DummyDataLocker:
    def __init__(self, db_path=None):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # Added alert_class column after alert_type
        cursor.execute("""
            CREATE TABLE alerts (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                alert_type TEXT,
                alert_class TEXT,
                asset_type TEXT,
                trigger_value REAL,
                condition TEXT,
                notification_type TEXT,
                state TEXT,
                last_triggered TEXT,
                status TEXT,
                frequency INTEGER,
                counter INTEGER,
                liquidation_distance REAL,
                target_travel_percent REAL,
                liquidation_price REAL,
                notes TEXT,
                description TEXT,
                position_reference_id TEXT,
                evaluated_value REAL
            )
        """)
        self.conn.commit()

    def delete_alert(self, alert_id: str):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
        self.conn.commit()

    def update_alert_status(self, alert_id: str, status: str):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE alerts SET status=? WHERE id=?", (status, alert_id))
        self.conn.commit()

    def update_alert_conditions(self, alert_id: str, update_fields: dict):
        cursor = self.conn.cursor()
        set_clause = ", ".join(f"{k}=?" for k in update_fields.keys())
        values = list(update_fields.values()) + [alert_id]
        cursor.execute(f"UPDATE alerts SET {set_clause} WHERE id=?", values)
        self.conn.commit()
        return cursor.rowcount

    def get_alerts(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM alerts")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_db_connection(self):
        return self.conn

# Use a shared dummy database for all components.
def get_shared_dummy_db(db_path=None):
    return DummyDataLocker(db_path)

# Patch DataLocker.get_instance in the underlying module so that both AlertController and Cyclone use the same DB.
data.data_locker.DataLocker.get_instance = get_shared_dummy_db

# Disable logging for clean test output.
logging.disable(logging.CRITICAL)

class TestPositionAlerts(unittest.TestCase):

    def setUp(self):
        # Create a new DummyDataLocker instance and patch DataLocker.get_instance to return it.
        self.dummy_db = DummyDataLocker(":memory:")
        data.data_locker.DataLocker.get_instance = lambda db_path=None: self.dummy_db

        # Instantiate AlertController and Cyclone.
        self.controller = AlertController(db_path=":memory:")
        self.controller.logger = logging.getLogger("TestPositionAlerts")
        self.cyclone = Cyclone(poll_interval=1)

    def get_latest_alert(self):
        alerts = self.controller.data_locker.get_alerts()
        return alerts[-1] if alerts else None

    def test_1_dummy_position_alert_defaults(self):
        # Verify that DummyPositionAlert gets proper default values.
        dp_alert = DummyPositionAlert(
            alert_type="TravelPercentAlert",
            asset_type="SOL",
            trigger_value=5.0,
            condition="BELOW",
            notification_type="Call",
            position_reference_id="pos1"
        )
        result = self.controller.create_alert(dp_alert)
        self.assertTrue(result, "create_alert should return True")
        alert = self.get_latest_alert()
        self.assertEqual(alert["alert_class"], "Position", "Default alert_class should be 'Position'")
        self.assertEqual(alert["status"], "Active", "Default status should be 'Active'")
        self.assertEqual(alert["frequency"], 1, "Default frequency should be 1")
        self.assertEqual(alert["counter"], 0, "Default counter should be 0")
        self.assertEqual(alert["liquidation_distance"], 0.0, "Default liquidation_distance should be 0.0")
        self.assertEqual(alert["target_travel_percent"], 0.0, "Default target_travel_percent should be 0.0")
        self.assertEqual(alert["liquidation_price"], 0.0, "Default liquidation_price should be 0.0")
        self.assertEqual(alert["evaluated_value"], 0.0, "Default evaluated_value should be 0.0")
        self.assertEqual(alert["asset_type"], "SOL", "Asset type should be preserved as 'SOL'")
        self.assertTrue(alert["id"], "Alert id should not be empty")
        self.assertTrue(alert["created_at"], "created_at should not be empty")

    def test_2_empty_fields_default(self):
        # Test that empty or None fields get replaced by defaults.
        dp_alert = DummyPositionAlert(
            alert_type="TravelPercentAlert",
            asset_type="",           # should default to "BTC"
            trigger_value=10.0,
            condition=None,          # should default to "ABOVE"
            notification_type="",    # should default to "Email"
            position_reference_id="pos2"
        )
        self.controller.create_alert(dp_alert)
        alert = self.get_latest_alert()
        self.assertEqual(alert["asset_type"], "BTC", "Empty asset_type should default to 'BTC'")
        self.assertEqual(alert["condition"], "ABOVE", "None condition should default to 'ABOVE'")
        self.assertEqual(alert["notification_type"], "Email", "Empty notification_type should default to 'Email'")

    def test_3_preserve_valid_values(self):
        # Verify that valid non-empty values remain unchanged.
        dp_alert = DummyPositionAlert(
            alert_type="TravelPercentAlert",
            asset_type="ETH",
            trigger_value=20.0,
            condition="BELOW",
            notification_type="Call",
            position_reference_id="pos3"
        )
        self.controller.create_alert(dp_alert)
        alert = self.get_latest_alert()
        self.assertEqual(alert["asset_type"], "ETH", "Asset type should be 'ETH'")
        self.assertEqual(alert["condition"], "BELOW", "Condition should be 'BELOW'")
        self.assertEqual(alert["notification_type"], "Call", "Notification type should be 'Call'")

    def test_4_create_alert_with_dict_input(self):
        # Test that create_alert accepts a dictionary input and applies defaults.
        alert_dict = {
            "alert_type": "TravelPercentAlert",
            "asset_type": "",       # empty -> default to "BTC"
            "trigger_value": 15.0,
            "condition": "",        # empty -> default to "ABOVE"
            "notification_type": None,  # None -> default to "Email"
            "state": "",
            "notes": "",
            "description": "",
            "position_reference_id": ""
        }
        result = self.controller.create_alert(alert_dict)
        self.assertTrue(result, "create_alert should return True when passed a dict")
        alert = self.get_latest_alert()
        self.assertEqual(alert["asset_type"], "BTC", "Empty asset_type in dict should default to 'BTC'")
        self.assertEqual(alert["condition"], "ABOVE", "Empty condition in dict should default to 'ABOVE'")
        self.assertEqual(alert["notification_type"], "Email", "None notification_type should default to 'Email'")

    def test_5_notes_field_format(self):
        # Test that the notes field is correctly formatted.
        dp_alert = DummyPositionAlert(
            alert_type="TravelPercentAlert",
            asset_type="BTC",
            trigger_value=7.0,
            condition="ABOVE",
            notification_type="Email",
            position_reference_id="pos4"
        )
        self.controller.create_alert(dp_alert)
        alert = self.get_latest_alert()
        expected_notes = "Position TravelPercentAlert alert created by Cyclone"
        self.assertEqual(alert["notes"], expected_notes, "Notes field should match expected format")

    def test_6_cyclone_run_create_position_alerts_integration(self):
        # Integration test: Cyclone's run_create_position_alerts should create 3 alerts.
        async def run_test():
            await self.cyclone.run_create_position_alerts()
        asyncio.run(run_test())
        alerts = self.dummy_db.get_alerts()  # Use the shared dummy DB instance.
        self.assertEqual(len(alerts), 3, "Cyclone.run_create_position_alerts should insert 3 alerts")
        expected_types = {"TravelPercentAlert", "ProfitAlert", "HeatIndexAlert"}
        types = {alert["alert_type"] for alert in alerts}
        self.assertEqual(types, expected_types, "Alert types should match expected position alerts")
        for alert in alerts:
            self.assertTrue(alert.get("created_at"), "created_at should be set for each alert")

    def test_7_cyclone_and_alert_controller_integration(self):
        # Integration test: Create a position alert via AlertController and verify it in the shared DB.
        dp_alert = DummyPositionAlert(
            alert_type="TravelPercentAlert",
            asset_type="LTC",
            trigger_value=12.0,
            condition="BELOW",
            notification_type="Call",
            position_reference_id="pos5"
        )
        self.controller.create_alert(dp_alert)
        alerts = self.dummy_db.get_alerts()
        self.assertTrue(any(alert["position_reference_id"] == "pos5" for alert in alerts),
                        "The created alert should be retrievable via the shared database integration")

    def test_8_valid_uuid_generation(self):
        # Test that the alert id generated is a valid UUID.
        dp_alert = DummyPositionAlert(
            alert_type="TravelPercentAlert",
            asset_type="XRP",
            trigger_value=3.0,
            condition="ABOVE",
            notification_type="Email",
            position_reference_id="pos6"
        )
        self.controller.create_alert(dp_alert)
        alert = self.get_latest_alert()
        try:
            UUID(alert["id"], version=4)
        except ValueError:
            self.fail("Alert id is not a valid UUID")

    def test_9_created_at_format(self):
        # Test that created_at follows the format YYYY-MM-DD HH:MM:SS.
        dp_alert = DummyPositionAlert(
            alert_type="TravelPercentAlert",
            asset_type="ADA",
            trigger_value=8.0,
            condition="ABOVE",
            notification_type="Call",
            position_reference_id="pos7"
        )
        self.controller.create_alert(dp_alert)
        alert = self.get_latest_alert()
        pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        self.assertRegex(alert["created_at"], pattern, "created_at should match the datetime format YYYY-MM-DD HH:MM:SS")

    def test_10_create_alert_returns_true(self):
        # Test that create_alert returns True upon successful creation.
        dp_alert = DummyPositionAlert(
            alert_type="TravelPercentAlert",
            asset_type="DOGE",
            trigger_value=2.0,
            condition="BELOW",
            notification_type="Email",
            position_reference_id="pos8"
        )
        result = self.controller.create_alert(dp_alert)
        self.assertTrue(result, "create_alert should return True upon successful creation")

if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(TestPositionAlerts))
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total - failures - errors
    print("\nDetailed Test Report:")
    print(f"Total tests run: {total}")
    print(f"Passed: {passed}")
    print(f"Failures: {failures}")
    print(f"Errors: {errors}")
