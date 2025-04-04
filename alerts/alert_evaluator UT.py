import unittest
from alerts.alert_evaluator import AlertEvaluator


# Dummy DataLocker for testing purposes
class DummyDataLocker:
    def __init__(self):
        self.positions = [
            {
                "id": "pos1",
                "pnl_after_fees_usd": 25,  # This should trigger profit alert (threshold: 20)
                "travel_percent": -35,  # This should trigger travel alert (threshold: -30)
                "current_heat_index": 45  # This should trigger heat index alert (threshold: 40)
            },
            {
                "id": "pos2",
                "pnl_after_fees_usd": 15,  # Does not trigger profit alert
                "travel_percent": -20,  # Does not trigger travel alert
                "current_heat_index": 30  # Does not trigger heat index alert
            }
        ]

    def read_positions(self):
        return self.positions


class TestGlobalAlerts(unittest.TestCase):
    def test_evaluate_global_alerts(self):
        # Define a test config with global_alert_config enabled
        config = {
            "global_alert_config": {
                "enabled": True,
                "data_fields": {
                    "price": True,
                    "profit": True,
                    "travel_percent": True,
                    "heat_index": True
                },
                "thresholds": {
                    "price": {
                        "BTC": 70000,
                        "ETH": 1500,
                        "SOL": 120
                    },
                    "profit": 20.0,
                    "travel_percent": -30.0,
                    "heat_index": 40.0
                }
            },
            # Include any other required config items here, if necessary.
        }

        # Create a dummy data locker and evaluator instance
        dummy_data_locker = DummyDataLocker()
        evaluator = AlertEvaluator(config, dummy_data_locker)

        # Simulate market data for testing price alerts
        market_data = {
            "BTC": 72000,  # Should trigger (72000 >= 70000)
            "ETH": 1400,  # Should NOT trigger (1400 < 1500)
            "SOL": 130  # Should trigger (130 >= 120)
        }

        # Get the positions from our dummy data locker
        positions = dummy_data_locker.read_positions()

        # Evaluate global alerts
        alerts = evaluator.evaluate_global_alerts(positions, market_data)

        # Expected results based on our dummy data:
        expected_alerts = {
            "price": "BTC price 72000 >= 70000; SOL price 130 >= 120",
            "profit": "Pos pos1 profit 25.0 >= 20.0",
            "travel_percent": "Pos pos1 travel percent -35.0 <= -30.0",
            "heat_index": "Pos pos1 heat index 45.0 >= 40.0"
        }

        self.assertEqual(alerts, expected_alerts)


if __name__ == '__main__':
    unittest.main()
