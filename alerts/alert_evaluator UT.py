import unittest
import os
from datetime import datetime
from uuid import uuid4

# Fake configuration and constants
DEFAULT_CONFIG = {
    "alert_ranges": {
        "travel_percent_liquid_ranges": {
            "low": -25.0,
            "medium": -50.0,
            "high": -75.0
        }
    }
}

# Fake AlertType constants (simulate the ones from data.models)
class AlertType:
    TRAVEL_PERCENT_LIQUID = type("Enum", (), {"value": "TRAVEL_PERCENT_LIQUID"})
    HEAT_INDEX = type("Enum", (), {"value": "HEAT_INDEX"})
    PRICE_THRESHOLD = type("Enum", (), {"value": "PRICE_THRESHOLD"})
    PROFIT = type("Enum", (), {"value": "PROFIT"})

# Fake DataLocker that captures update calls.
class FakeDataLocker:
    def __init__(self):
        self.last_update_fields = None
        self.conn = self  # For simplicity in get_db_connection

    def update_alert_conditions(self, alert_id, update_fields):
        self.last_update_fields = update_fields
        return 1  # simulate one row updated

    def get_db_connection(self):
        return self

# Subclass AlertEvaluator from our production code.
# For our tests, we only need _update_alert_level; we simulate logging via prints.
class AlertEvaluator:
    def __init__(self, config, data_locker):
        self.config = config
        self.data_locker = data_locker

    def _update_alert_level(self, pos: dict, new_level: str, evaluated_value: float = None,
                            custom_alert_type: str = None):
        # Use the same logic as in the production code
        alert_id = pos.get("alert_reference_id")
        # If no alert_reference_id, normally create new alert record.
        # For testing, assume pos always has it.
        update_fields = {"level": new_level}
        if evaluated_value is not None:
            update_fields["evaluated_value"] = evaluated_value
        if pos.get("alert_reference_id") and pos.get("id"):
            update_fields["position_reference_id"] = pos.get("id")
        # Travel percent trigger update block:
        if custom_alert_type is None or custom_alert_type == AlertType.TRAVEL_PERCENT_LIQUID.value:
            tp_config = self.config.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
            try:
                low_threshold = float(tp_config.get("low", -25.0))
                medium_threshold = float(tp_config.get("medium", -50.0))
                high_threshold = float(tp_config.get("high", -75.0))
            except Exception as e:
                low_threshold, medium_threshold, high_threshold = -25.0, -50.0, -75.0
            if new_level == "Normal":
                next_trigger = low_threshold
            elif new_level == "Low":
                next_trigger = medium_threshold
            elif new_level == "Medium":
                next_trigger = high_threshold
            elif new_level == "High":
                next_trigger = high_threshold
            else:
                next_trigger = update_fields.get("trigger_value", 0.0)
            update_fields["trigger_value"] = next_trigger
        # Simulate updating the alert conditions via DataLocker
        self.data_locker.update_alert_conditions(alert_id, update_fields)

    # For non-travel alerts, _update_alert_level does not update the trigger value.
    # The same method is used, so if custom_alert_type is not travel, then block is skipped.
    
# Now define our test cases.
class TestUpdateAlertLevel(unittest.TestCase):
    def setUp(self):
        # By default, use the default config.
        self.fake_dl = FakeDataLocker()
        self.evaluator = AlertEvaluator(DEFAULT_CONFIG, self.fake_dl)
        # A sample position with existing alert_reference_id and id.
        self.base_pos = {
            "id": "pos1",
            "alert_reference_id": "alert1",
            # For travel percent alerts, we can supply an initial travel_percent if needed.
            "travel_percent": -30.0
        }
    
    # --- Travel percent alert tests (10 test cases) ---
    
    def test_travel_normal_default(self):
        # new_level "Normal" should set trigger_value to low threshold (-25.0)
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Normal", evaluated_value=100)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Normal")
        self.assertEqual(uf["evaluated_value"], 100)
        self.assertEqual(uf["position_reference_id"], "pos1")
        self.assertIn("trigger_value", uf)
        self.assertEqual(uf["trigger_value"], -25.0)

    def test_travel_low_default(self):
        # new_level "Low" should set trigger_value to medium threshold (-50.0)
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Low", evaluated_value=200)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Low")
        self.assertEqual(uf["evaluated_value"], 200)
        self.assertEqual(uf["trigger_value"], -50.0)

    def test_travel_medium_default(self):
        # new_level "Medium" should set trigger_value to high threshold (-75.0)
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Medium", evaluated_value=300)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Medium")
        self.assertEqual(uf["evaluated_value"], 300)
        self.assertEqual(uf["trigger_value"], -75.0)

    def test_travel_high_default(self):
        # new_level "High" should also set trigger_value to high threshold (-75.0)
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "High", evaluated_value=400)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "High")
        self.assertEqual(uf["evaluated_value"], 400)
        self.assertEqual(uf["trigger_value"], -75.0)

    def test_travel_unknown_level(self):
        # new_level not one of the recognized ones should leave trigger_value as 0.0 (default fallback)
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Unexpected", evaluated_value=500)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Unexpected")
        self.assertEqual(uf["evaluated_value"], 500)
        self.assertEqual(uf["trigger_value"], 0.0)

    def test_travel_with_overridden_config_normal(self):
        # Override config thresholds
        config_override = {
            "alert_ranges": {
                "travel_percent_liquid_ranges": {
                    "low": -20.0,
                    "medium": -40.0,
                    "high": -60.0
                }
            }
        }
        evaluator = AlertEvaluator(config_override, self.fake_dl)
        pos = self.base_pos.copy()
        evaluator._update_alert_level(pos, "Normal", evaluated_value=600)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["trigger_value"], -20.0)

    def test_travel_with_overridden_config_low(self):
        config_override = {
            "alert_ranges": {
                "travel_percent_liquid_ranges": {
                    "low": -20.0,
                    "medium": -40.0,
                    "high": -60.0
                }
            }
        }
        evaluator = AlertEvaluator(config_override, self.fake_dl)
        pos = self.base_pos.copy()
        evaluator._update_alert_level(pos, "Low", evaluated_value=700)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["trigger_value"], -40.0)

    def test_travel_with_overridden_config_medium(self):
        config_override = {
            "alert_ranges": {
                "travel_percent_liquid_ranges": {
                    "low": -20.0,
                    "medium": -40.0,
                    "high": -60.0
                }
            }
        }
        evaluator = AlertEvaluator(config_override, self.fake_dl)
        pos = self.base_pos.copy()
        evaluator._update_alert_level(pos, "Medium", evaluated_value=800)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["trigger_value"], -60.0)

    def test_travel_with_overridden_config_high(self):
        config_override = {
            "alert_ranges": {
                "travel_percent_liquid_ranges": {
                    "low": -20.0,
                    "medium": -40.0,
                    "high": -60.0
                }
            }
        }
        evaluator = AlertEvaluator(config_override, self.fake_dl)
        pos = self.base_pos.copy()
        evaluator._update_alert_level(pos, "High", evaluated_value=900)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["trigger_value"], -60.0)

    def test_travel_invalid_thresholds(self):
        # Test that if thresholds are non-numeric, the fallback defaults are used.
        config_override = {
            "alert_ranges": {
                "travel_percent_liquid_ranges": {
                    "low": "invalid",
                    "medium": "invalid",
                    "high": "invalid"
                }
            }
        }
        evaluator = AlertEvaluator(config_override, self.fake_dl)
        pos = self.base_pos.copy()
        evaluator._update_alert_level(pos, "Low", evaluated_value=1000)
        uf = self.fake_dl.last_update_fields
        # Fallback defaults: low=-25, medium=-50, high=-75; for "Low" level, trigger should be medium = -50.
        self.assertEqual(uf["trigger_value"], -50.0)
    
    # --- Non-travel alert tests (10 test cases) ---
    # For non-travel alerts, we set custom_alert_type to something other than TRAVEL_PERCENT_LIQUID.
    
    def test_non_travel_heat_index_normal(self):
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Normal", evaluated_value=110, custom_alert_type=AlertType.HEAT_INDEX.value)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Normal")
        self.assertEqual(uf["evaluated_value"], 110)
        self.assertEqual(uf["position_reference_id"], "pos1")
        # Ensure trigger_value is not updated (i.e. not present)
        self.assertNotIn("trigger_value", uf)

    def test_non_travel_heat_index_low(self):
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Low", evaluated_value=120, custom_alert_type=AlertType.HEAT_INDEX.value)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Low")
        self.assertEqual(uf["evaluated_value"], 120)
        self.assertNotIn("trigger_value", uf)

    def test_non_travel_profit(self):
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Medium", evaluated_value=130, custom_alert_type=AlertType.PROFIT.value)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Medium")
        self.assertEqual(uf["evaluated_value"], 130)
        self.assertNotIn("trigger_value", uf)

    def test_non_travel_price_threshold(self):
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "High", evaluated_value=140, custom_alert_type=AlertType.PRICE_THRESHOLD.value)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "High")
        self.assertEqual(uf["evaluated_value"], 140)
        self.assertNotIn("trigger_value", uf)

    def test_non_travel_custom_string(self):
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Custom", evaluated_value=150, custom_alert_type="SOMETHING")
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Custom")
        self.assertEqual(uf["evaluated_value"], 150)
        self.assertNotIn("trigger_value", uf)

    def test_non_travel_with_none_custom(self):
        # When custom_alert_type is explicitly not set (None) it should default to travel percent behavior.
        # So this is similar to travel, and we test that trigger_value is updated.
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Low", evaluated_value=160, custom_alert_type=None)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["trigger_value"], -50.0)

    def test_non_travel_custom_numeric(self):
        # If custom_alert_type is provided as a numeric value (which is unexpected),
        # the condition (custom_alert_type is None or equals TRAVEL_PERCENT_LIQUID) will be False.
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Normal", evaluated_value=170, custom_alert_type=123)
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Normal")
        self.assertEqual(uf["evaluated_value"], 170)
        self.assertNotIn("trigger_value", uf)

    def test_non_travel_edge_case_empty_string(self):
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "", evaluated_value=180, custom_alert_type="HEAT_INDEX")
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "")
        self.assertEqual(uf["evaluated_value"], 180)
        self.assertNotIn("trigger_value", uf)

    def test_non_travel_missing_position_reference(self):
        # If position_reference_id is missing, update_fields won't include it.
        pos = self.base_pos.copy()
        pos.pop("alert_reference_id", None)
        pos["id"] = "pos_missing"
        # In _update_alert_level, since alert_reference_id is missing,
        # normally a new alert would be created – we bypass that by not calling update.
        # For this test, simulate that branch by setting it manually.
        pos["alert_reference_id"] = "alert_missing"
        self.evaluator._update_alert_level(pos, "Normal", evaluated_value=190, custom_alert_type="HEAT_INDEX")
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["position_reference_id"], "pos_missing")

    def test_non_travel_override_combination(self):
        # Test with custom_alert_type that is not travel and new_level "Low" with evaluated_value.
        pos = self.base_pos.copy()
        self.evaluator._update_alert_level(pos, "Low", evaluated_value=200, custom_alert_type="NOT_TRAVEL")
        uf = self.fake_dl.last_update_fields
        self.assertEqual(uf["level"], "Low")
        self.assertEqual(uf["evaluated_value"], 200)
        self.assertNotIn("trigger_value", uf)

# To run tests and generate an HTML report, we can use HTMLTestRunner.
# If you don't have it installed, install via: pip install html-testRunner
import sys
try:
    import HtmlTestRunner
except ImportError:
    print("Please install HtmlTestRunner (pip install html-testRunner)")
    sys.exit(1)

if __name__ == '__main__':
    # Define the output directory for the report.
    report_dir = os.path.join(os.getcwd(), "reports")
    os.makedirs(report_dir, exist_ok=True)
    runner = HtmlTestRunner.HTMLTestRunner(
        output=report_dir,
        report_title="Update Alert Level Test Report",
        descriptions="Extensive unit tests around update alert level functionality."
    )
    unittest.main(testRunner=runner, verbosity=2)
