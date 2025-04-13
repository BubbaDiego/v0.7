import unittest
import sqlite3
from datetime import datetime
from data.data_locker import DataLocker
from alerts.alert_controller import AlertController
from data.models import AlertType
import os

class TestPositionAlertCreation(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite database.
        self.db_path = ":memory:"
        # Instantiate DataLocker with in-memory DB
        self.data_locker = DataLocker(self.db_path)
        # Force table creation by initializing database.
        self.data_locker._initialize_database()

        # Insert a test position that has no alert_reference_id.
        self.test_position = {
            "id": "testpos1",
            "asset_type": "BTC",
            "position_type": "SHORT",
            "entry_price": 50000.0,
            "liquidation_price": 45000.0,
            "travel_percent": 0.0,
            "alert_reference_id": "",   # Explicitly empty
            "pnl_after_fees_usd": 1000.0,
            "current_heat_index": 0.0,
            "current_price": 51000.0,
            "last_updated": datetime.now().isoformat()
        }
        cursor = self.data_locker.conn.cursor()
        cursor.execute("""
            INSERT INTO positions 
            (id, asset_type, position_type, entry_price, liquidation_price, travel_percent,
             alert_reference_id, pnl_after_fees_usd, current_heat_index, current_price, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.test_position["id"],
            self.test_position["asset_type"],
            self.test_position["position_type"],
            self.test_position["entry_price"],
            self.test_position["liquidation_price"],
            self.test_position["travel_percent"],
            self.test_position["alert_reference_id"],
            self.test_position["pnl_after_fees_usd"],
            self.test_position["current_heat_index"],
            self.test_position["current_price"],
            self.test_position["last_updated"]
        ))
        self.data_locker.conn.commit()

        # Create a dummy configuration that enables travel alerts.
        self.config = {
            "alert_ranges": {
                "travel_percent_liquid_ranges": {
                    "enabled": True,
                    "low": -25.0,
                    "medium": -50.0,
                    "high": -75.0
                },
                "profit_ranges": {
                    "enabled": True,
                    "low": 50.0,
                    "medium": 100.0,
                    "high": 150.0
                },
                "heat_index_ranges": {
                    "enabled": True,
                    "low": 10.0,
                    "medium": 20.0,
                    "high": 30.0,
                    "condition": "ABOVE"
                },
                "price_alerts": {}
            },
            "alert_cooldown_seconds": 900,
            "call_refractory_period": 3600,
            "snooze_countdown": 300
        }

        # Instantiate AlertController and override its DataLocker with our in-memory instance.
        self.alert_controller = AlertController(db_path=self.db_path)
        self.alert_controller.data_locker = self.data_locker

    def tearDown(self):
        self.data_locker.conn.close()

    def test_create_position_alerts(self):
        # Invoke the creation of position alerts.
        created_alerts = self.alert_controller.create_position_alerts()
        # Check that at least one alert was created.
        self.assertIsInstance(created_alerts, list)
        self.assertGreater(len(created_alerts), 0, "No position alerts were created.")

        # Check that the created alert has the correct position_type ("SHORT")
        # Fetch alert record from the database.
        cursor = self.data_locker.conn.cursor()
        cursor.execute("SELECT * FROM alerts WHERE position_reference_id=?", (self.test_position["id"],))
        alert_row = cursor.fetchone()
        cursor.close()

        self.assertIsNotNone(alert_row, "Alert record not found in database for test position.")
        self.assertEqual(alert_row["position_type"], "SHORT", "position_type not correctly propagated to alert.")

        # Also check that the position record now has a non-empty alert_reference_id.
        cursor = self.data_locker.conn.cursor()
        cursor.execute("SELECT alert_reference_id FROM positions WHERE id=?", (self.test_position["id"],))
        pos_row = cursor.fetchone()
        cursor.close()
        self.assertTrue(pos_row and pos_row["alert_reference_id"].strip() != "",
                        "Position alert_reference_id not updated.")

if __name__ == "__main__":
    unittest.main()
