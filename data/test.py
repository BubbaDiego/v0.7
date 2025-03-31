import unittest
import os
import logging
from alerts.alert_enrichment import update_trigger_value  # from alert_enrichment.py

# Define a fake DataLocker that simulates DB behavior.
class FakeDataLocker:
    def __init__(self):
        self.alerts = {}
        # We'll simulate a DB connection as self for simplicity.
        self.conn = self

    def get_alerts(self):
        return list(self.alerts.values())

    def update_alert_conditions(self, alert_id, update_fields):
        if alert_id in self.alerts:
            # Update the alert with new fields.
            self.alerts[alert_id].update(update_fields)
            return 1  # simulate one row updated
        return 0

    def get_alert(self, alert_id):
        return self.alerts.get(alert_id)

    def read_positions(self):
        # For our tests, positions are not needed.
        return []

    def add_alert(self, alert):
        # Store a copy of the alert dictionary keyed by its id.
        self.alerts[alert["id"]] = alert.copy()

# Default configuration for travel percent alerts.
DEFAULT_CONFIG = {
    "alert_ranges": {
        "travel_percent_liquid_ranges": {
            "low": -25.0,
            "medium": -50.0,
            "high": -75.0,
            "enabled": True
        }
    }
}

# Setup a simple logger.
logger = logging.getLogger("TestLogger")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# Our tests for update_trigger_value function.
class TestUpdateTriggerValue(unittest.TestCase):
    def setUp(self):
        # Initialize fake data locker and add several travel percent alerts.
        self.data_locker = FakeDataLocker()
        # Create alerts with type "TravelPercent" (normalized value expected from enrichment)
        self.alerts = [
            {"id": "a1", "alert_type": "TravelPercent", "level": "Normal", "trigger_value": -10.0},
            {"id": "a2", "alert_type": "TravelPercent", "level": "Low", "trigger_value": -10.0},
            {"id": "a3", "alert_type": "TravelPercent", "level": "Medium", "trigger_value": -10.0},
            {"id": "a4", "alert_type": "TravelPercent", "level": "High", "trigger_value": -10.0},
        ]
        for alert in self.alerts:
            self.data_locker.add_alert(alert)

    def test_normal_level_update(self):
        # For level "Normal", trigger should update to low_threshold (-25.0)
        update_trigger_value(self.data_locker, DEFAULT_CONFIG, logger, report_path="report_normal.html")
        alert = self.data_locker.get_alert("a1")
        self.assertEqual(float(alert["trigger_value"]), -25.0)

    def test_low_level_update(self):
        # For level "Low", trigger should update to medium_threshold (-50.0)
        update_trigger_value(self.data_locker, DEFAULT_CONFIG, logger, report_path="report_low.html")
        alert = self.data_locker.get_alert("a2")
        self.assertEqual(float(alert["trigger_value"]), -50.0)

    def test_medium_level_update(self):
        # For level "Medium", trigger should update to high_threshold (-75.0)
        update_trigger_value(self.data_locker, DEFAULT_CONFIG, logger, report_path="report_medium.html")
        alert = self.data_locker.get_alert("a3")
        self.assertEqual(float(alert["trigger_value"]), -75.0)

    def test_high_level_update(self):
        # For level "High", trigger should also update to high_threshold (-75.0)
        update_trigger_value(self.data_locker, DEFAULT_CONFIG, logger, report_path="report_high.html")
        alert = self.data_locker.get_alert("a4")
        self.assertEqual(float(alert["trigger_value"]), -75.0)

    def test_updated_count(self):
        # Ensure update_trigger_value returns the correct count of updated alerts.
        updated_count = update_trigger_value(self.data_locker, DEFAULT_CONFIG, logger, report_path="report_count.html")
        # All four alerts should be updated because initial trigger (-10.0) is different from expected.
        self.assertEqual(updated_count, 4)

if __name__ == '__main__':
    # Use HTMLTestRunner to generate an HTML report.
    import HtmlTestRunner
    report_dir = os.path.join(os.getcwd(), "reports")
    os.makedirs(report_dir, exist_ok=True)
    runner = HtmlTestRunner.HTMLTestRunner(
        output=report_dir,
        report_title="Trigger Value Update Test Report",
        descriptions="Automated tests verifying that the trigger value is correctly updated for travel percent alerts."
    )
    unittest.main(testRunner=runner, verbosity=2)
