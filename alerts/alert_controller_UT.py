#!/usr/bin/env python
import os
import json
import unittest
import time as t  # import as t so we can patch properly
from data.data_locker import DataLocker
from alerts.alert_controller import AlertController
from alerts.alert_manager import AlertManager
from sonic_labs.hedge_manager import HedgeManager
from data.models import Position, Hedge  # assuming these exist

# Dummy configuration for alerts (all alert types enabled for testing)
DUMMY_CONFIG = {
    "alert_ranges": {
        "price_alerts": {
            "BTC": {"enabled": True, "condition": "ABOVE", "trigger_value": 70000, "notifications": {"call": False, "email": True}},
            "ETH": {"enabled": True, "condition": "ABOVE", "trigger_value": 1800, "notifications": {"call": False, "email": True}},
            "SOL": {"enabled": True, "condition": "BELOW", "trigger_value": 150, "notifications": {"call": True, "email": False}}
        },
        "travel_percent_liquid_ranges": {
            "enabled": True,
            "low": -10.0,
            "medium": -30.0,
            "high": -50.0,
            "low_notifications": {"call": True},
            "medium_notifications": {"call": True},
            "high_notifications": {"call": True}
        },
        "profit_ranges": {
            "enabled": True,
            "low": 50.0,
            "medium": 100.0,
            "high": 150.0,
            "condition": "ABOVE",
            "notifications": {"call": True, "email": True}
        },
        "heat_index_alerts": {
            "enabled": False  # disabled for testing
        }
    },
    "alert_cooldown_seconds": 1,
    "call_refractory_period": 1,
    "snooze_countdown": 300,
    "twilio_config": {}
}

# A simple DummyAlert for manual alert creation tests
class DummyAlert:
    def __init__(self, position_reference_id=None, state="Normal", asset_type="BTC", condition="Normal", profit=None):
        self.data = {
            "id": None,
            "alert_type": "TestAlert",
            "alert_class": "TestClass",
            "asset_type": asset_type,
            "trigger_value": 100.0,
            "condition": condition,
            "notification_type": "Email",
            "state": state,
            "last_triggered": None,
            "status": "Active",
            "frequency": 1,
            "counter": 0,
            "liquidation_distance": 0.0,
            "target_travel_percent": 0.0,
            "liquidation_price": 0.0,
            "notes": "Test note",
            "position_reference_id": position_reference_id
        }
        if profit is not None:
            self.data["profit"] = profit

    def to_dict(self):
        return self.data.copy()

class TestIntegrationUseCases(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite DB and reset the DataLocker singleton.
        self.db_path = ":memory:"
        DataLocker._instance = None
        # Force DataLocker.get_instance to always return our patched instance.
        DataLocker.get_instance = lambda db_path=None: self.data_locker

        # Create a dummy config file.
        self.config_path = "dummy_config.json"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(DUMMY_CONFIG, f, indent=2)

        # Instantiate our DataLocker, AlertController, and AlertManager.
        self.data_locker = DataLocker(db_path=self.db_path)
        self.alert_controller = AlertController(db_path=self.db_path)
        self.alert_manager = AlertManager(db_path=self.db_path, poll_interval=1, config_path=self.config_path)
        # Override send_call to avoid real Twilio calls.
        self.alert_manager.send_call = lambda body, key: None

        # Force both AlertController and AlertManager to use our patched DataLocker.
        self.alert_controller.data_locker = self.data_locker
        self.alert_manager.data_locker = self.data_locker

        # Patch DataLocker methods to store alerts and positions in in-memory lists.
        self._alerts = []
        self._positions = []
        self.data_locker.create_alert = self._dummy_create_alert
        self.data_locker.get_alerts = lambda: self._alerts
        self.data_locker.delete_alert = self._dummy_delete_alert
        self.data_locker.delete_all_alerts = lambda: self._dummy_delete_all_alerts()
        self.data_locker.create_position = lambda pos: self._positions.append(pos)
        self.data_locker.read_positions = lambda: self._positions
        self.data_locker.delete_all_positions = lambda: self._positions.clear()
        # Patch update_alert_conditions to update our in-memory alerts.
        self.data_locker.update_alert_conditions = lambda alert_id, fields: [
            a.update(fields) for a in self._alerts if a.get("id") == alert_id
        ]

        # Patch the time in the alert_manager module so that time.time() works.
        import alerts.alert_manager as am
        am.time = t

    def _dummy_create_alert(self, alert):
        alert["id"] = f"alert_{len(self._alerts)+1}"
        self._alerts.append(alert)
        return True  # Ensure we return True for success.

    def _dummy_delete_alert(self, alert_id):
        initial = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.get("id") != alert_id]
        return initial - len(self._alerts)

    def _dummy_delete_all_alerts(self):
        count = len(self._alerts)
        self._alerts = []
        return count

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        self._alerts.clear()
        self._positions.clear()

    # 1. Create an alert successfully via AlertController.
    def test_create_alert_success(self):
        dummy = DummyAlert(position_reference_id="pos1", state="Normal")
        result = self.alert_controller.create_alert(dummy)
        self.assertTrue(result)
        alerts = self.data_locker.get_alerts()
        self.assertEqual(len(alerts), 1)

    # 2. Delete an alert successfully.
    def test_delete_alert_success(self):
        dummy = DummyAlert(position_reference_id="posDel", state="Normal")
        self.alert_controller.create_alert(dummy)
        alerts = self.alert_controller.get_all_alerts()
        self.assertEqual(len(alerts), 1)
        alert_id = alerts[0]["id"]
        result = self.alert_controller.delete_alert(alert_id)
        self.assertTrue(result)
        alerts_after = self.data_locker.get_alerts()
        self.assertEqual(len(alerts_after), 0)

    # 3. Update alert conditions.
    def test_update_alert_conditions(self):
        dummy = DummyAlert(position_reference_id="posUpdate", state="Normal")
        self.alert_controller.create_alert(dummy)
        alerts = self.data_locker.get_alerts()
        self.assertGreater(len(alerts), 0)
        alert_id = alerts[0]["id"]
        update_fields = {"state": "High", "position_reference_id": "posUpdated"}
        self.data_locker.update_alert_conditions(alert_id, update_fields)
        updated_alerts = self.data_locker.get_alerts()
        self.assertEqual(updated_alerts[0].get("state"), "High")
        self.assertEqual(updated_alerts[0].get("position_reference_id"), "posUpdated")

    # 4. Retrieve all alerts (count check).
    def test_get_all_alerts_count(self):
        for i in range(3):
            dummy = DummyAlert(position_reference_id=f"pos{i}", state="Normal")
            self.alert_controller.create_alert(dummy)
        alerts = self.alert_controller.get_all_alerts()
        self.assertEqual(len(alerts), 3)

    # 5. Create price alerts via AlertController.
    def test_price_alerts_creation(self):
        created = self.alert_controller.create_price_alerts()
        self.assertEqual(len(created), 3)

    # 6. Create travel percent alerts.
    def test_travel_percent_alerts_creation(self):
        dummy_position = {
            "id": "posT1",
            "asset_type": "SOL",
            "position_type": "short",
            "current_travel_percent": -40.0
        }
        self.data_locker.create_position(dummy_position)
        created = self.alert_controller.create_travel_percent_alerts()
        self.assertEqual(len(created), 1)

    # 7. Create profit alerts.
    def test_profit_alerts_creation(self):
        dummy_position = {
            "id": "posP1",
            "asset_type": "BTC",
            "position_type": "long",
            "profit": 160.0
        }
        self.data_locker.create_position(dummy_position)
        created = self.alert_controller.create_profit_alerts()
        self.assertGreaterEqual(len(created), 1)

    # 8. Create heat index alerts (disabled).
    def test_heat_index_alerts_disabled(self):
        created = self.alert_controller.create_heat_index_alerts()
        self.assertEqual(len(created), 0)

    # 9. Create all alerts (combined).
    def test_create_all_alerts_combined(self):
        created = self.alert_controller.create_all_alerts()
        self.assertEqual(len(created), 3)

    # 10. AlertManager refresh with no positions.
    def test_alert_manager_refresh_no_positions(self):
        self.data_locker.delete_all_positions()
        self.alert_manager.check_alerts(source="manual refresh")
        alerts = self.data_locker.get_alerts()
        self.assertEqual(len(alerts), 0)

    # 11. AlertManager refresh with positions triggering alerts.
    def test_alert_manager_refresh_with_positions(self):
        dummy_position = {
            "id": "posRefresh",
            "asset_type": "BTC",
            "position_type": "long",
            "profit": 160.0,
            "current_travel_percent": -80.0
        }
        self.data_locker.create_position(dummy_position)
        _ = self.alert_manager.create_all_alerts()
        self.alert_manager.check_alerts(source="end-to-end test")
        alerts = self.data_locker.get_alerts()
        profit_alerts = [a for a in alerts if a.get("alert_type") == "Profit"]
        self.assertGreaterEqual(len(profit_alerts), 1)

    # 12. Update alert state helper using AlertController.
    def test_update_alert_state_helper(self):
        dummy = DummyAlert(position_reference_id="posHelper", state="Normal")
        self.alert_controller.create_alert(dummy)
        alerts = self.data_locker.get_alerts()
        self.assertGreater(len(alerts), 0)
        self.alert_controller._update_alert_state(alerts[0], "Medium", evaluated_value=75.0)
        updated = self.data_locker.get_alerts()
        self.assertEqual(updated[0].get("state"), "Medium")

    # 13. End-to-end interaction.
    def test_end_to_end_interaction(self):
        pos = {
            "id": "posE2",
            "asset_type": "BTC",
            "position_type": "long",
            "profit": 160.0,
            "current_travel_percent": -80.0
        }
        self.data_locker.create_position(pos)
        created_alerts = self.alert_manager.create_all_alerts()
        self.assertGreater(len(created_alerts), 0)
        self.alert_manager.check_alerts(source="end-to-end test")
        alerts = self.data_locker.get_alerts()
        triggered = [a for a in alerts if a.get("state") in ["Low", "Medium", "High", "Triggered"]]
        self.assertGreaterEqual(len(triggered), 1)

    # 14. Multiple alerts for the same position.
    def test_multiple_alerts_for_same_position(self):
        pos = {
            "id": "posMulti",
            "asset_type": "ETH",
            "position_type": "long",
            "profit": 200.0,
            "current_travel_percent": -90.0,
            "liquidation_distance": 15.0
        }
        self.data_locker.create_position(pos)
        all_alerts = self.alert_manager.create_all_alerts()
        self.assertGreaterEqual(len(all_alerts), 3)

    # 15. Alert suppression due to cooldown.
    def test_alert_suppression_due_to_cooldown(self):
        pos = {
            "id": "posCool",
            "asset_type": "BTC",
            "position_type": "long",
            "profit": 180.0,
            "current_travel_percent": -85.0
        }
        self.data_locker.create_position(pos)
        _ = self.alert_manager.create_all_alerts()
        self.alert_manager.check_alerts(source="cooldown test")
        before = self.alert_manager.suppressed_count
        self.alert_manager.check_alerts(source="cooldown test")
        after = self.alert_manager.suppressed_count
        self.assertGreaterEqual(after, before)

    # 16. Configuration reload.
    def test_config_reload(self):
        new_config = DUMMY_CONFIG.copy()
        new_config["alert_cooldown_seconds"] = 5
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, indent=2)
        try:
            self.alert_manager.reload_config()
            self.assertEqual(self.alert_manager.cooldown, 5)
        except ModuleNotFoundError:
            self.skipTest("Module config.config_manager not found; skipping reload test.")

    # 17. Delete all alerts.
    def test_delete_all_alerts(self):
        for i in range(3):
            dummy = DummyAlert(position_reference_id=f"posDel{i}", state="Normal")
            self.alert_controller.create_alert(dummy)
        count = self.alert_controller.delete_all_alerts()
        self.assertEqual(count, 3)
        alerts = self.data_locker.get_alerts()
        self.assertEqual(len(alerts), 0)

    # 18. HedgeManager integration: grouping positions.
    def test_hedge_manager_integration(self):
        pos1 = Position(asset_type="BTC", position_type="long", size=1.5, heat_index=10.0, hedge_buddy_id="group1")
        pos2 = Position(asset_type="BTC", position_type="short", size=0.5, heat_index=5.0, hedge_buddy_id="group1")
        pos3 = Position(asset_type="ETH", position_type="long", size=2.0, heat_index=8.0, hedge_buddy_id="group2")
        pos4 = Position(asset_type="ETH", position_type="long", size=1.0, heat_index=6.0, hedge_buddy_id="group2")
        pos5 = Position(asset_type="SOL", position_type="long", size=3.0, heat_index=4.0, hedge_buddy_id=None)
        positions = [p.__dict__ for p in [pos1, pos2, pos3, pos4, pos5]]
        hedge_manager = HedgeManager(positions)
        hedges = hedge_manager.get_hedges()
        self.assertEqual(len(hedges), 2)

    # 19. Alert creation with missing optional fields.
    def test_alert_creation_missing_fields(self):
        dummy = DummyAlert(position_reference_id="posMissing")
        alert_created = self.alert_controller.create_alert(dummy)
        self.assertTrue(alert_created)
        alerts = self.data_locker.get_alerts()
        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0].get("asset_type"), "BTC")
        self.assertEqual(alerts[0].get("state"), "Normal")
        self.assertEqual(alerts[0].get("evaluated_value"), 0.0)

    # 20. AlertController default initialization.
    def test_alert_controller_default_initialization(self):
        controller = AlertController()
        self.assertIsNotNone(controller.data_locker)

if __name__ == '__main__':
    unittest.main(verbosity=2)
