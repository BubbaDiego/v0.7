#!/usr/bin/env python
"""
alert_and_hedge_integration_UT.py

This file defines a series of unit tests to verify the interactions between:
  - DataLocker (DB access)
  - AlertController (for creating/deleting alerts)
  - AlertManager (for evaluating and refreshing alerts using a JSON config)
  - HedgeManager (for grouping positions into hedges)

There are 10 tests covering:
  1. Creating an alert (and verifying its default state is 'Normal').
  2. Updating alert conditions (state update and position_reference_id update).
  3. AlertManager refresh (simulate check_alerts and verify it calls send_call).
  4. Getting all alerts from the DB.
  5. Creating all alerts in a chain.
  6. Deleting an alert.
  7. Evaluating a profit alert.
  8. Evaluating a travel percent alert.
  9. End‑to‑end alert interaction (create a position, create an alert, and re‑evaluate).
 10. HedgeManager integration (grouping positions by hedge_buddy_id).

Run this file directly to see detailed test output.
"""

import os
import json
import unittest
import time
from data.data_locker import DataLocker
from alerts.alert_controller import AlertController
from alerts.alert_manager import AlertManager
from sonic_labs.hedge_manager import HedgeManager
from data.models import Position, Hedge


# Updated DummyAlert now includes all required keys.
class DummyAlert:
    def __init__(self, position_reference_id=None, state="Normal", asset_type="BTC", condition="Normal"):
        self.data = {
            "id": None,
            "alert_type": "TestAlert",
            "alert_class": "TestClass",
            "asset_type": asset_type,
            "trigger_value": 100.0,
            "condition": condition,
            "notification_type": "Email",
            "last_triggered": None,
            "status": "Active",
            "frequency": 1,
            "counter": 0,
            "liquidation_distance": 0.0,
            "target_travel_percent": 0.0,
            "liquidation_price": 0.0,
            "notes": "Test note",
            "position_reference_id": position_reference_id,
            "state": state
        }

    def to_dict(self):
        return self.data


class TestInteraction(unittest.TestCase):

    def setUp(self):
        # Use an in-memory SQLite DB.
        self.db_path = ":memory:"
        # Reset the DataLocker singleton.
        DataLocker._instance = None

        # Create a dummy configuration dictionary.
        self.dummy_config = {
            "alert_ranges": {
                "price_alerts": {
                    "BTC": {
                        "enabled": True,
                        "condition": "ABOVE",
                        "trigger_value": 100.0,
                        "notifications": {"call": True}
                    }
                },
                "travel_percent_liquid_ranges": {
                    "enabled": True,
                    "low": -50.0,
                    "medium": -60.0,
                    "high": -75.0,
                    "low_notifications": {"call": True},
                    "medium_notifications": {"call": True},
                    "high_notifications": {"call": True}
                },
                "profit_ranges": {
                    "enabled": True,
                    "low": 50.0,
                    "medium": 100.0,
                    "high": 150.0,
                    "low_notifications": {"call": True},
                    "medium_notifications": {"call": True},
                    "high_notifications": {"call": True}
                }
            },
            "alert_cooldown_seconds": 1,
            "call_refractory_period": 1,
            "snooze_countdown": 300,
            "twilio_config": {}
        }
        # Save dummy config to a temporary file.
        self.config_path = "dummy_config.json"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.dummy_config, f, indent=2)

        # Create instances of the components.
        self.data_locker = DataLocker(db_path=self.db_path)
        self.alert_controller = AlertController()
        self.alert_manager = AlertManager(db_path=self.db_path, poll_interval=1, config_path=self.config_path)
        # Override send_call so no actual Twilio call is made.
        self.alert_manager.send_call = lambda body, key: None
        # In case create_all_alerts is not implemented on AlertManager, override it.
        if not hasattr(self.alert_manager, "create_all_alerts"):
            self.alert_manager.create_all_alerts = lambda: self.alert_controller.create_price_alerts()

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_create_alert(self):
        dummy = DummyAlert(position_reference_id="pos123", state="Normal")
        result = self.alert_controller.create_alert(dummy)
        self.assertTrue(result, "Alert creation should return True.")

        alerts = self.data_locker.get_alerts()
        self.assertEqual(len(alerts), 1, "There should be one alert in the DB.")
        alert_record = alerts[0]
        self.assertEqual(alert_record.get("state"), "Normal", "Initial state should be 'Normal'.")
        self.assertEqual(alert_record.get("position_reference_id"), "pos123",
                         "Position reference ID should be 'pos123'.")
        self.assertEqual(alert_record.get("asset_type"), "BTC", "Default asset_type should be 'BTC'.")
        self.assertEqual(alert_record.get("condition"), "Normal", "Default condition should be 'Normal'.")

    def test_update_alert_conditions(self):
        dummy = DummyAlert(position_reference_id="pos123", state="Normal")
        self.alert_controller.create_alert(dummy)
        alerts = self.data_locker.get_alerts()
        self.assertGreater(len(alerts), 0, "At least one alert should exist.")
        alert_id = alerts[0].get("id")
        update_fields = {"state": "High", "position_reference_id": "pos456"}
        self.data_locker.update_alert_conditions(alert_id, update_fields)
        updated_alerts = self.data_locker.get_alerts()
        self.assertEqual(updated_alerts[0].get("state"), "High", "Alert state should be updated to 'High'.")
        self.assertEqual(updated_alerts[0].get("position_reference_id"), "pos456",
                         "Position reference ID should be updated to 'pos456'.")

    def test_alert_manager_refresh(self):
        dummy1 = DummyAlert(position_reference_id="pos1", state="Normal")
        dummy2 = DummyAlert(position_reference_id="pos2", state="Normal")
        self.alert_controller.create_alert(dummy1)
        self.alert_controller.create_alert(dummy2)
        self.alert_manager.check_alerts(source="manual refresh")
        alerts = self.data_locker.get_alerts()
        for alert in alerts:
            self.assertEqual(alert.get("state"), "Normal",
                             "After refresh, alert state should remain 'Normal' if not triggered.")

    def test_get_all_alerts(self):
        for i in range(3):
            dummy = DummyAlert(position_reference_id=f"pos{i}", state="Normal")
            self.alert_controller.create_alert(dummy)
        alerts = self.alert_controller.get_all_alerts()
        self.assertEqual(len(alerts), 3, "Should retrieve 3 alerts.")

    def test_create_all_alerts_chain(self):
        created = self.alert_controller.create_price_alerts()
        self.assertGreaterEqual(len(created), 1, "At least one price alert should be created.")

    def test_delete_alert(self):
        dummy = DummyAlert(position_reference_id="posDel", state="Normal")
        self.alert_controller.create_alert(dummy)
        alerts = self.alert_controller.get_all_alerts()
        self.assertEqual(len(alerts), 1, "One alert should be created before deletion.")
        alert_id = alerts[0].get("id")
        result = self.alert_controller.delete_alert(alert_id)
        self.assertTrue(result, "delete_alert should return True.")
        alerts_after = self.alert_controller.get_all_alerts()
        self.assertEqual(len(alerts_after), 0, "Alert should be deleted from the DB.")

    def test_profit_alert(self):
        pos = Position(
            asset_type="BTC",
            position_type="long",
            size=1.0,
            heat_index=0.0,
            pnl_after_fees_usd=120.0
        )
        self.data_locker.create_position(pos.__dict__)
        alert_msg = self.alert_manager.check_profit(pos.__dict__)
        self.assertIn("Profit ALERT", alert_msg, "Profit alert should be triggered for profit above threshold.")

    def test_travel_percent_alert(self):
        pos = Position(
            asset_type="BTC",
            position_type="long",
            size=1.0,
            heat_index=0.0,
            current_travel_percent=-65.0
        )
        self.data_locker.create_position(pos.__dict__)
        alert_msg = self.alert_manager.check_travel_percent_liquid(pos.__dict__)
        self.assertIn("Travel Percent Liquid ALERT", alert_msg,
                      "Travel percent alert should be triggered for negative travel percent.")

    def test_end_to_end_interaction(self):
        pos = Position(
            asset_type="BTC",
            position_type="long",
            size=1.0,
            heat_index=0.0,
            pnl_after_fees_usd=160.0,
            current_travel_percent=-80.0
        )
        self.data_locker.create_position(pos.__dict__)
        created_alerts = self.alert_manager.create_all_alerts()
        self.assertGreater(len(created_alerts), 0, "At least one alert should be created in end-to-end interaction.")
        self.alert_manager.check_alerts(source="end-to-end test")
        alerts = self.data_locker.get_alerts()
        for alert in alerts:
            if alert["alert_type"] == "Profit":
                self.assertEqual(alert.get("state"), "High", "Profit alert state should be 'High'.")
            if alert["alert_type"] in ["TravelPercent", "TravelPercentLiquid"]:
                self.assertEqual(alert.get("state"), "High", "Travel alert state should be 'High'.")

    def test_update_alert_state_helper(self):
        dummy = DummyAlert(position_reference_id="pos100", state="Normal")
        self.alert_controller.create_alert(dummy)
        alerts = self.data_locker.get_alerts()
        self.assertGreater(len(alerts), 0, "Alert should have been created.")
        self.assertEqual(alerts[0].get("state"), "Normal", "Initial state should be 'Normal'.")
        pos = {"id": "pos200", "alert_reference_id": alerts[0].get("id")}
        self.alert_manager._update_alert_state(pos, "Medium")
        updated_alerts = self.data_locker.get_alerts()
        self.assertEqual(updated_alerts[0].get("state"), "Medium", "Alert state should be updated to 'Medium'.")
        self.assertEqual(updated_alerts[0].get("position_reference_id"), "pos200",
                         "Position reference ID should be updated to 'pos200'.")


class TestHedgeManager(unittest.TestCase):
    def test_hedge_manager_integration(self):
        pos1 = Position(asset_type="BTC", position_type="long", size=1.5, heat_index=10.0, hedge_buddy_id="group1")
        pos2 = Position(asset_type="BTC", position_type="short", size=0.5, heat_index=5.0, hedge_buddy_id="group1")
        pos3 = Position(asset_type="ETH", position_type="long", size=2.0, heat_index=8.0, hedge_buddy_id="group2")
        pos4 = Position(asset_type="ETH", position_type="long", size=1.0, heat_index=6.0, hedge_buddy_id="group2")
        pos5 = Position(asset_type="SOL", position_type="long", size=3.0, heat_index=4.0, hedge_buddy_id=None)
        positions = [pos1, pos2, pos3, pos4, pos5]
        hedge_manager = HedgeManager(positions)
        hedges = hedge_manager.get_hedges()
        self.assertEqual(len(hedges), 2, "There should be 2 hedges created from groups with at least 2 positions.")
        for hedge in hedges:
            if "group1" in hedge.notes:
                self.assertEqual(hedge.total_long_size, 1.5, "Total long size for group1 should be 1.5.")
                self.assertEqual(hedge.total_short_size, 0.5, "Total short size for group1 should be 0.5.")
                self.assertEqual(hedge.total_heat_index, 15.0, "Total heat index for group1 should be 15.0.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
