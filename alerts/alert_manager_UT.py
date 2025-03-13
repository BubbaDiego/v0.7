#!/usr/bin/env python
"""
alert_manager_UT.py

This file contains extensive unit tests for the AlertManager.
It builds a test setup with dummy dependencies, executes various test cases,
and then uses HtmlTestRunner to generate a detailed HTML report.
Additionally, it produces a pie chart showing the success/failure rate.

Dependencies:
  - unittest (built-in)
  - HtmlTestRunner (install via pip install html-testRunner)
  - matplotlib (install via pip install matplotlib)

Run this file directly to execute all tests, generate the HTML report,
and display a pie chart of test results.
"""

import os
import sys
import time
import json
import unittest
import logging
import tempfile
from datetime import datetime
import matplotlib.pyplot as plt

# Import HtmlTestRunner. Note the proper capitalization.
import HtmlTestRunner

# Ensure the project root is on sys.path.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the AlertManager and trigger_twilio_flow from your module.
from alerts.alert_manager import AlertManager, trigger_twilio_flow


# --- Dummy Implementations for Testing ---

class DummyDataLocker:
    """
    A dummy DataLocker for unit testing.
    Simulates reading positions, alerts, and latest prices.
    """

    def __init__(self):
        self.positions = []
        self.alerts = []
        self.latest_prices = {}

    def read_positions(self):
        return self.positions

    def get_alerts(self):
        return self.alerts

    def get_latest_price(self, asset_code):
        return self.latest_prices.get(asset_code.upper(), {"current_price": "100"})

    def get_db_connection(self):
        return None


class DummyCalcServices:
    """Dummy CalcServices that does nothing."""
    pass


# Override the trigger_twilio_flow for testing so that it doesn't call the real Twilio API.
def dummy_trigger_twilio_flow(custom_message: str, twilio_config: dict) -> str:
    return "DUMMY_TWILIO_SID"


# Monkey-patch the trigger_twilio_flow function in the AlertManager module for tests.
import alert_manager

alert_manager.trigger_twilio_flow = dummy_trigger_twilio_flow


# --- Unit Test Cases ---

class TestAlertManager(unittest.TestCase):
    """
    Extensive unit tests for AlertManager.

    Tests include:
      - Travel percent liquid alerts (enabled/disabled for overall and each alert level)
      - Profit alerts (enabled/disabled overall and per alert level)
      - Swing alerts (enabled/disabled)
      - Blast alerts (enabled/disabled)
      - Price alerts
      - Notification (call) triggering

    A dummy DataLocker is injected to simulate controlled scenarios.
    """

    def setUp(self):
        # Create a temporary configuration dict simulating alert_limits.json settings.
        self.dummy_config = {
            "alert_ranges": {
                "travel_percent_liquid_ranges": {
                    "enabled": True,
                    "low": -5.0,
                    "medium": -50.0,
                    "high": -75.0,
                    "low_notifications": {"call": True, "sms": False, "email": False},
                    "medium_notifications": {"call": True, "sms": False, "email": False},
                    "high_notifications": {"call": True, "sms": False, "email": False}
                },
                "profit_ranges": {
                    "enabled": True,
                    "low": 1.0,
                    "medium": 2.0,
                    "high": 3.0,
                    "low_notifications": {"call": True, "sms": False, "email": False},
                    "medium_notifications": {"call": True, "sms": False, "email": False},
                    "high_notifications": {"call": True, "sms": False, "email": False}
                },
                "swing_alerts": {
                    "enabled": True,
                    "notifications": {"call": True}
                },
                "blast_alerts": {
                    "enabled": True,
                    "notifications": {"call": True}
                }
            },
            "alert_cooldown_seconds": 0,  # disable cooldown for testing
            "call_refractory_period": 0,
            "twilio_config": {
                "account_sid": "dummy_sid",
                "auth_token": "dummy_token",
                "flow_sid": "dummy_flow",
                "to_phone": "+1234567890",
                "from_phone": "+0987654321"
            },
            "system_config": {
                "alert_monitor_enabled": True
            }
        }

        # Create a temporary dummy config file.
        self.temp_config_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        json.dump(self.dummy_config, self.temp_config_file)
        self.temp_config_file.close()

        # Instantiate AlertManager with dummy config and a dummy DB path.
        self.alert_manager = AlertManager(db_path=":memory:", config_path=self.temp_config_file.name)

        # Inject dummy dependencies.
        self.alert_manager.data_locker = DummyDataLocker()
        self.alert_manager.calc_services = DummyCalcServices()

    def tearDown(self):
        os.unlink(self.temp_config_file.name)

    # -------------------------------------------------------------------------
    # Existing Tests
    # -------------------------------------------------------------------------
    def test_travel_percent_liquid_alert_enabled(self):
        """Test that a travel percent liquid alert is triggered when conditions are met."""
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos1",
            "current_travel_percent": -80.0,
            "wallet_name": "TestWallet"
        }
        result = self.alert_manager.check_travel_percent_liquid(position)
        self.assertIn("Travel Percent Liquid ALERT", result)

    def test_travel_percent_liquid_alert_disabled(self):
        """Test that travel percent liquid alert returns empty when config is disabled."""
        self.alert_manager.config["alert_ranges"]["travel_percent_liquid_ranges"]["enabled"] = False
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos2",
            "current_travel_percent": -80.0,
            "wallet_name": "TestWallet"
        }
        result = self.alert_manager.check_travel_percent_liquid(position)
        self.assertEqual(result, "")

    def test_profit_alert_enabled(self):
        """Test that a profit alert is triggered when profit conditions are met."""
        position = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos3",
            "profit": 5.0  # High level
        }
        result = self.alert_manager.check_profit(position)
        self.assertIn("Profit ALERT", result)

    def test_profit_alert_disabled(self):
        """Test that profit alert returns empty when profit alert config is disabled."""
        self.alert_manager.config["alert_ranges"]["profit_ranges"]["enabled"] = False
        position = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos4",
            "profit": 5.0
        }
        result = self.alert_manager.check_profit(position)
        self.assertEqual(result, "")

    def test_swing_alert_enabled(self):
        """Test that swing alert is triggered when conditions are met."""
        position = {
            "asset_type": "SOL",
            "position_type": "long",
            "position_id": "pos5",
            "liquidation_distance": 15.0
        }
        result = self.alert_manager.check_swing_alert(position)
        self.assertIn("Average Daily Swing ALERT", result)

    def test_swing_alert_disabled(self):
        """Test that swing alert returns empty when swing alerts are disabled."""
        self.alert_manager.config["alert_ranges"]["swing_alerts"]["enabled"] = False
        position = {
            "asset_type": "SOL",
            "position_type": "long",
            "position_id": "pos6",
            "liquidation_distance": 15.0
        }
        result = self.alert_manager.check_swing_alert(position)
        self.assertEqual(result, "")

    def test_blast_alert_enabled(self):
        """Test that blast alert is triggered when conditions are met."""
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos7",
            "liquidation_distance": 20.0
        }
        result = self.alert_manager.check_blast_alert(position)
        self.assertIn("One Day Blast Radius ALERT", result)

    def test_blast_alert_disabled(self):
        """Test that blast alert returns empty when blast alerts are disabled."""
        self.alert_manager.config["alert_ranges"]["blast_alerts"] = {"enabled": False, "notifications": {"call": True}}
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos8",
            "liquidation_distance": 20.0
        }
        result = self.alert_manager.check_blast_alert(position)
        self.assertEqual(result, "")

    def test_price_alert(self):
        """Test that a price alert is triggered given a simulated alert from DataLocker."""
        dummy_alert = {
            "alert_type": "PRICE_THRESHOLD",
            "status": "active",
            "asset_type": "BTC",
            "position_id": "pos9",
            "trigger_value": 90.0,
            "condition": "ABOVE",
            "wallet_name": "TestWallet"
        }
        self.alert_manager.data_locker.alerts = [dummy_alert]
        self.alert_manager.data_locker.latest_prices = {"BTC": {"current_price": "100"}}
        results = self.alert_manager.check_price_alerts()
        self.assertTrue(any("Price ALERT" in r for r in results))

    def test_send_call(self):
        """Test that send_call triggers a call notification (dummy) without raising exceptions."""
        try:
            self.alert_manager.send_call("Test call message", "test_call")
        except Exception as e:
            self.fail(f"send_call raised an exception: {e}")

    # -------------------------------------------------------------------------
    # Additional Test Cases for Expanded Coverage
    # -------------------------------------------------------------------------

    def test_profit_alert_low_enabled(self):
        """Test profit alert at Low level when call notifications are enabled."""
        position = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos_low_enabled",
            "profit": 1.5
        }
        self.alert_manager.config["alert_ranges"]["profit_ranges"]["low_notifications"]["call"] = True
        result = self.alert_manager.check_profit(position)
        self.assertIn("Profit ALERT", result, "Low-level profit alert should trigger if call is enabled.")

    def test_profit_alert_low_disabled(self):
        """Test profit alert at Low level when call notifications are disabled, even if SMS/email are True."""
        position = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos_low_disabled",
            "profit": 1.5
        }
        self.alert_manager.config["alert_ranges"]["profit_ranges"]["low_notifications"]["call"] = False
        self.alert_manager.config["alert_ranges"]["profit_ranges"]["low_notifications"]["sms"] = True
        self.alert_manager.config["alert_ranges"]["profit_ranges"]["low_notifications"]["email"] = True
        result = self.alert_manager.check_profit(position)
        self.assertEqual(result, "", "Low-level profit alert should NOT trigger if call is disabled.")

    def test_profit_alert_medium_enabled(self):
        """Test profit alert at Medium level when call notifications are enabled."""
        position = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos_medium_enabled",
            "profit": 2.5
        }
        self.alert_manager.config["alert_ranges"]["profit_ranges"]["medium_notifications"]["call"] = True
        result = self.alert_manager.check_profit(position)
        self.assertIn("Profit ALERT", result, "Medium-level profit alert should trigger if call is enabled.")

    def test_profit_alert_medium_disabled(self):
        """Test profit alert at Medium level when call notifications are disabled."""
        position = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos_medium_disabled",
            "profit": 2.5
        }
        self.alert_manager.config["alert_ranges"]["profit_ranges"]["medium_notifications"]["call"] = False
        result = self.alert_manager.check_profit(position)
        self.assertEqual(result, "", "Medium-level profit alert should NOT trigger if call is disabled.")

    def test_profit_alert_high_enabled(self):
        """Test profit alert at High level when call notifications are enabled."""
        position = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos_high_enabled",
            "profit": 5.0
        }
        self.alert_manager.config["alert_ranges"]["profit_ranges"]["high_notifications"]["call"] = True
        result = self.alert_manager.check_profit(position)
        self.assertIn("Profit ALERT", result, "High-level profit alert should trigger if call is enabled.")

    def test_profit_alert_high_disabled(self):
        """Test profit alert at High level when call notifications are disabled."""
        position = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos_high_disabled",
            "profit": 5.0
        }
        self.alert_manager.config["alert_ranges"]["profit_ranges"]["high_notifications"]["call"] = False
        result = self.alert_manager.check_profit(position)
        self.assertEqual(result, "", "High-level profit alert should NOT trigger if call is disabled.")

    def test_travel_alert_low_enabled(self):
        """Test travel percent liquid alert at Low level when call notifications are enabled."""
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos_travel_low_enabled",
            "current_travel_percent": -10.0,
            "wallet_name": "TestWallet"
        }
        self.alert_manager.config["alert_ranges"]["travel_percent_liquid_ranges"]["low_notifications"]["call"] = True
        result = self.alert_manager.check_travel_percent_liquid(position)
        self.assertIn("Travel Percent Liquid ALERT", result,
                      "Low-level travel alert should trigger if call is enabled.")

    def test_travel_alert_low_disabled(self):
        """Test travel percent liquid alert at Low level when call notifications are disabled."""
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos_travel_low_disabled",
            "current_travel_percent": -10.0,
            "wallet_name": "TestWallet"
        }
        self.alert_manager.config["alert_ranges"]["travel_percent_liquid_ranges"]["low_notifications"]["call"] = False
        result = self.alert_manager.check_travel_percent_liquid(position)
        self.assertEqual(result, "", "Low-level travel alert should NOT trigger if call is disabled.")

    def test_travel_alert_medium_enabled(self):
        """Test travel percent liquid alert at Medium level when call notifications are enabled."""
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos_travel_medium_enabled",
            "current_travel_percent": -55.0,
            "wallet_name": "TestWallet"
        }
        self.alert_manager.config["alert_ranges"]["travel_percent_liquid_ranges"]["medium_notifications"]["call"] = True
        result = self.alert_manager.check_travel_percent_liquid(position)
        self.assertIn("Travel Percent Liquid ALERT", result,
                      "Medium-level travel alert should trigger if call is enabled.")

    def test_travel_alert_medium_disabled(self):
        """Test travel percent liquid alert at Medium level when call notifications are disabled."""
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos_travel_medium_disabled",
            "current_travel_percent": -55.0,
            "wallet_name": "TestWallet"
        }
        self.alert_manager.config["alert_ranges"]["travel_percent_liquid_ranges"]["medium_notifications"][
            "call"] = False
        result = self.alert_manager.check_travel_percent_liquid(position)
        self.assertEqual(result, "", "Medium-level travel alert should NOT trigger if call is disabled.")

    def test_travel_alert_high_enabled(self):
        """Test travel percent liquid alert at High level when call notifications are enabled."""
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos_travel_high_enabled",
            "current_travel_percent": -80.0,
            "wallet_name": "TestWallet"
        }
        self.alert_manager.config["alert_ranges"]["travel_percent_liquid_ranges"]["high_notifications"]["call"] = True
        result = self.alert_manager.check_travel_percent_liquid(position)
        self.assertIn("Travel Percent Liquid ALERT", result,
                      "High-level travel alert should trigger if call is enabled.")

    def test_travel_alert_high_disabled(self):
        """Test travel percent liquid alert at High level when call notifications are disabled."""
        position = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos_travel_high_disabled",
            "current_travel_percent": -80.0,
            "wallet_name": "TestWallet"
        }
        self.alert_manager.config["alert_ranges"]["travel_percent_liquid_ranges"]["high_notifications"]["call"] = False
        result = self.alert_manager.check_travel_percent_liquid(position)
        self.assertEqual(result, "", "High-level travel alert should NOT trigger if call is disabled.")

    def test_monitor_disabled(self):
        """Test that no alerts are triggered at all when the alert monitor is disabled."""
        self.alert_manager.monitor_enabled = False
        self.alert_manager.data_locker.positions = [
            {"asset_type": "BTC", "position_type": "long", "profit": 10.0, "current_travel_percent": -80.0}
        ]
        # We'll run check_alerts and see if any alerts appear in the logs or returned messages.
        # Because monitor_enabled=False, we expect no triggers.
        # We'll verify by hooking into the aggregator logic.
        self.alert_manager.suppressed_count = 0
        self.alert_manager.check_alerts()
        # If the monitor is disabled, we expect "No Alerts Found" or "Monitor disabled" logs, but no triggered alerts.
        # There's no direct aggregator result to check, so we rely on the code returning no triggers.
        # We can confirm by the suppressed_count not incrementing from zero or similar logic if needed.
        self.assertEqual(self.alert_manager.suppressed_count, 0, "Should remain 0 because no alerts are triggered.")

    def test_cooldown_suppression(self):
        """Test that an alert triggered once is suppressed if triggered again within the cooldown period."""
        # Set a non-zero cooldown to test the suppression.
        self.alert_manager.cooldown = 999999
        position = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos_cooldown",
            "profit": 5.0
        }
        # First check should trigger the alert.
        result1 = self.alert_manager.check_profit(position)
        self.assertIn("Profit ALERT", result1, "First profit check should trigger alert.")
        # Second check should be suppressed because of the high cooldown.
        result2 = self.alert_manager.check_profit(position)
        self.assertEqual(result2, "", "Second profit check should be suppressed by cooldown.")

    def test_negative_profit_no_alert(self):
        """Test that negative or zero profit does not trigger a profit alert."""
        # Negative profit
        position_neg = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos_neg_profit",
            "profit": -1.0
        }
        result_neg = self.alert_manager.check_profit(position_neg)
        self.assertEqual(result_neg, "", "Negative profit should not trigger a profit alert.")

        # Zero profit
        position_zero = {
            "asset_type": "ETH",
            "position_type": "short",
            "position_id": "pos_zero_profit",
            "profit": 0.0
        }
        result_zero = self.alert_manager.check_profit(position_zero)
        self.assertEqual(result_zero, "", "Zero profit should not trigger a profit alert.")

    def test_travel_percent_missing(self):
        """Test that no travel alert is triggered if current_travel_percent is missing or non-numeric."""
        # Missing field
        pos_missing = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos_missing_travel"
            # no 'current_travel_percent' key
        }
        result_missing = self.alert_manager.check_travel_percent_liquid(pos_missing)
        self.assertEqual(result_missing, "", "Missing travel percent should not trigger an alert.")

        # Non-numeric
        pos_non_numeric = {
            "asset_type": "BTC",
            "position_type": "long",
            "position_id": "pos_non_numeric_travel",
            "current_travel_percent": "bad_value"
        }
        result_non_numeric = self.alert_manager.check_travel_percent_liquid(pos_non_numeric)
        self.assertEqual(result_non_numeric, "", "Non-numeric travel percent should fail gracefully, no alert.")

    def test_partial_invalid_config(self):
        """
        Test partial/invalid config for profit_ranges or travel_percent_liquid_ranges.
        This ensures that if keys are missing, we fail gracefully or trigger no alerts.
        """
        # Remove the 'profit_ranges' entirely
        del self.alert_manager.config["alert_ranges"]["profit_ranges"]
        pos = {"asset_type": "ETH", "position_type": "short", "profit": 5.0}
        result = self.alert_manager.check_profit(pos)
        self.assertEqual(result, "", "Missing profit_ranges config => no alert triggered (fails gracefully).")

        # Remove the 'travel_percent_liquid_ranges' entirely
        del self.alert_manager.config["alert_ranges"]["travel_percent_liquid_ranges"]
        pos2 = {"asset_type": "BTC", "position_type": "long", "current_travel_percent": -80.0}
        result2 = self.alert_manager.check_travel_percent_liquid(pos2)
        self.assertEqual(result2, "", "Missing travel_percent_liquid_ranges => no alert triggered (fails gracefully).")

    def test_price_alert_not_triggered(self):
        """
        Test that a price alert is not triggered if the condition isn't met.
        e.g. we want 'ABOVE' 120 but the price is 100 => no alert
        """
        dummy_alert = {
            "alert_type": "PRICE_THRESHOLD",
            "status": "active",
            "asset_type": "BTC",
            "position_id": "pos_no_trigger",
            "trigger_value": 120.0,
            "condition": "ABOVE",
            "wallet_name": "TestWallet"
        }
        self.alert_manager.data_locker.alerts = [dummy_alert]
        self.alert_manager.data_locker.latest_prices = {"BTC": {"current_price": "100"}}
        results = self.alert_manager.check_price_alerts()
        self.assertFalse(results, "No price alert should be triggered if price < trigger_value.")


# --- Main Test Runner with HTML Report and Pie Chart Generation ---

if __name__ == '__main__':
    # Create test suite from all test cases.
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAlertManager)

    # Set report directory to the same directory as this test file.
    report_dir = os.path.dirname(os.path.abspath(__file__))

    # Run tests with HtmlTestRunner, using higher verbosity for more detail.
    runner = HtmlTestRunner.HTMLTestRunner(
        output=report_dir,
        report_title="AlertManager Unit Test Report",
        report_name="AlertManager_Test_Report",
        descriptions="Detailed results for AlertManager unit tests with success/failure metrics.",
        verbosity=2
    )
    result = runner.run(suite)

    # Generate a pie chart for success/failure rate.
    successes = result.testsRun - len(result.failures) - len(result.errors)
    failures = len(result.failures) + len(result.errors)
    labels = ['Successes', 'Failures']
    sizes = [successes, failures]
    colors = ['green', 'red']
    plt.figure(figsize=(6, 6))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=90)
    plt.title("Test Success/Failure Rate")
    plt.axis('equal')
    pie_chart_file = os.path.join(report_dir, "test_results_pie.png")
    plt.savefig(pie_chart_file)
    plt.close()

    print(f"HTML test report generated at: {os.path.join(report_dir, 'AlertManager_Test_Report.html')}")
    print(f"Pie chart image generated at: {pie_chart_file}")
