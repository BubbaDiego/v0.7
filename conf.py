import unittest
from unittest.mock import MagicMock, patch
import time
from alerts.alert_evaluator import AlertEvaluator

class TestAlertEvaluator(unittest.TestCase):
    def setUp(self):
        # Update the configuration to include all necessary alert ranges.
        self.config = {
            "alert_cooldown_seconds": 900,
            "alert_ranges": {
                "travel_percent_liquid_ranges": {
                    "enabled": True,
                    "low": -4.0,
                    "medium": -7.0,
                    "high": -10.0
                },
                "profit_ranges": {
                    "enabled": True,
                    "low": 50.0,
                    "medium": 100.0,
                    "high": 150.0,
                    "condition": "ABOVE",
                    "notifications": {"call": False}
                },
                "swing_alerts": {
                    "enabled": True,
                    "notifications": {"call": True}
                },
                "price_alerts": {
                    "BTC": {
                        "enabled": True,
                        "condition": "ABOVE",
                        "trigger_value": 40000
                    }
                },
                "system_alerts": {
                    "heartbeat_enabled": True,
                    # Set last_heartbeat far enough in the past to trigger alert
                    "last_heartbeat": time.time() - 400,
                    "heartbeat_threshold": 300
                }
            }
        }
        # Create a dummy data_locker stub.
        self.data_locker = MagicMock()
        # Initialize evaluator with the updated configuration.
        self.evaluator = AlertEvaluator(self.config, self.data_locker)
        # Clear last_triggered so that cooldown does not interfere.
        self.evaluator.last_triggered = {}

    # 1. Test travel alert: normal case
    def test_evaluate_travel_alert_normal(self):
        pos = {"current_travel_percent": 5.0}
        state, value = self.evaluator.evaluate_travel_alert(pos)
        self.assertEqual(state, "Normal")
        self.assertEqual(value, 5.0)

    # 2. Test travel alert: medium level triggered
    def test_evaluate_travel_alert_medium(self):
        pos = {"current_travel_percent": -8.0}
        state, value = self.evaluator.evaluate_travel_alert(pos)
        self.assertEqual(state, "Medium")
        self.assertEqual(value, -8.0)

    # 3. Test profit alert update is called and message returned for profit=150.0 (edge: should be "High")
    def test_update_alert_state_called_in_profit_alert(self):
        pos = {
            "id": "alert123",
            "asset_type": "BTC",
            "profit": 150.0,
            "position_type": "long"
        }
        self.evaluator._update_alert_state = MagicMock()
        msg = self.evaluator.evaluate_profit_alert(pos)
        # Expect a non-empty message because profit is 150.0 (equal or above high threshold)
        self.assertNotEqual(msg, "")
        self.evaluator._update_alert_state.assert_called()

    # 4. Test profit alert: negative profit should return empty and update state to "Normal"
    def test_evaluate_profit_alert_negative_profit(self):
        pos = {
            "id": "alertNeg",
            "asset_type": "BTC",
            "profit": -20.0,
            "position_type": "short"
        }
        self.evaluator._update_alert_state = MagicMock()
        msg = self.evaluator.evaluate_profit_alert(pos)
        self.assertEqual(msg, "")
        self.evaluator._update_alert_state.assert_called_with(pos, "Normal", evaluated_value=-20.0)

    # 5. Test profit alert: profit between low and medium thresholds (e.g., 75 -> Low level)
    def test_evaluate_profit_alert_low_level(self):
        pos = {
            "id": "alertLow",
            "asset_type": "BTC",
            "profit": 75.0,
            "position_type": "long"
        }
        self.evaluator._update_alert_state = MagicMock()
        msg = self.evaluator.evaluate_profit_alert(pos)
        # Expect a "Low" level message
        self.assertIn("Low", msg)
        self.evaluator._update_alert_state.assert_called_with(pos, "Low", evaluated_value=75.0)

    # 6. Test profit alert: profit between medium and high thresholds (e.g., 120 -> Medium level)
    def test_evaluate_profit_alert_medium_level(self):
        pos = {
            "id": "alertMed",
            "asset_type": "BTC",
            "profit": 120.0,
            "position_type": "long"
        }
        self.evaluator._update_alert_state = MagicMock()
        msg = self.evaluator.evaluate_profit_alert(pos)
        self.assertIn("Medium", msg)
        self.evaluator._update_alert_state.assert_called_with(pos, "Medium", evaluated_value=120.0)

    # 7. Test profit alert: profit above high threshold (e.g., 200 -> High level)
    def test_evaluate_profit_alert_high_level(self):
        pos = {
            "id": "alertHigh",
            "asset_type": "BTC",
            "profit": 200.0,
            "position_type": "long"
        }
        self.evaluator._update_alert_state = MagicMock()
        msg = self.evaluator.evaluate_profit_alert(pos)
        self.assertIn("High", msg)
        self.evaluator._update_alert_state.assert_called_with(pos, "High", evaluated_value=200.0)

    # 8. Test market alerts: price alert for BTC meets condition
    def test_evaluate_price_alerts(self):
        market_data = {"BTC": 45000}
        msgs = self.evaluator.evaluate_price_alerts(market_data)
        self.assertGreater(len(msgs), 0)
        # Check that the message contains expected substrings.
        self.assertIn("Market ALERT", msgs[0])
        self.assertIn("BTC", msgs[0])

    # 9. Test system alerts: heartbeat threshold exceeded
    def test_evaluate_system_alerts(self):
        msgs = self.evaluator.evaluate_system_alerts()
        self.assertGreater(len(msgs), 0)
        self.assertIn("System ALERT: Heartbeat threshold exceeded", msgs[0])

    # 10. Test swing alert: for BTC with liquidation_distance triggering swing alert
    def test_evaluate_swing_alert_triggered(self):
        # For BTC, the hardcoded swing threshold is 6.24.
        pos = {
            "id": "swingTest",
            "asset_type": "BTC",
            "liquidation_distance": 7.0,
            "position_type": "long"
        }
        self.evaluator._update_alert_state = MagicMock()
        msg = self.evaluator.evaluate_swing_alert(pos)
        self.assertNotEqual(msg, "")
        self.assertIn("Average Daily Swing ALERT", msg)
        self.evaluator._update_alert_state.assert_called_with(pos, "Triggered", evaluated_value=7.0)

if __name__ == '__main__':
    unittest.main()
