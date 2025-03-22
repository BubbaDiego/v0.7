import unittest
from jinja2 import Environment, DictLoader
from data.data_locker import DataLocker
from alerts.alert_controller import AlertController


# DummyAlert mimics the structure expected by the DataLocker (and our alert matrix template).
class DummyAlert:
    def __init__(self, id_val, position_reference_id, state, alert_type="TestAlert", trigger_value=100.0,
                 condition="Normal", notification_type="Email", status="Active"):
        self.data = {
            "id": id_val,  # if None, DataLocker.create_alert will auto-generate one
            "alert_type": alert_type,
            "alert_class": "TestClass",
            "asset_type": "BTC",
            "trigger_value": trigger_value,
            "condition": condition,
            "notification_type": notification_type,
            "state": state,
            "last_triggered": None,
            "status": status,
            "frequency": 1,
            "counter": 0,
            "liquidation_distance": 0.0,
            "target_travel_percent": 0.0,
            "liquidation_price": 0.0,
            "notes": "Test note",
            "position_reference_id": position_reference_id
        }

    def to_dict(self):
        return self.data


class TestAlertMatrixInjection(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite DB; reset the DataLocker singleton.
        self.db_path = ":memory:"
        DataLocker._instance = None
        # Create our AlertController using the shared db_path.
        self.alert_controller = AlertController(db_path=self.db_path)

        # Inject three alerts:
        # Alert 1: Has an alert ID and a position reference ID.
        alert1 = DummyAlert("alert123", "posABC", "Normal", alert_type="PriceThreshold", trigger_value=120.0)
        # Alert 2: Does NOT have an alert ID (should be auto-generated) but has a position reference ID.
        alert2 = DummyAlert(None, "posDEF", "High", alert_type="Profit", trigger_value=150.0)
        # Alert 3: Has an alert ID but NO position reference ID.
        alert3 = DummyAlert("alert789", None, "Medium", alert_type="TravelPercentLiquid", trigger_value=0.0)

        # Insert alerts into the database.
        self.alert_controller.create_alert(alert1)
        self.alert_controller.create_alert(alert2)
        self.alert_controller.create_alert(alert3)

        # Retrieve alerts from the DB.
        self.alerts = self.alert_controller.get_all_alerts()

        # Set up a Jinja2 environment with a simplified alert matrix template.
        self.template_str = """
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Alert Matrix</title>
          <style>
            .info-box { border: 1px solid #ccc; padding: 10px; margin: 5px; border-radius: 0.5rem; }
            .no-alert { background-color: #0d6efd; color: #fff; }
            .low { background-color: #198754; color: #fff; }
            .medium { background-color: #ffc107; color: #000; }
            .high { background-color: #dc3545; color: #fff; }
            .unknown { background-color: #6c757d; color: #fff; }
            .info-box-text { display: block; margin: 2px 0; }
          </style>
        </head>
        <body>
        <div>
          {% for alert in alerts %}
            <div class="info-box 
              {% if alert.state == 'Normal' %} no-alert
              {% elif alert.state == 'Low' %} low
              {% elif alert.state == 'Medium' %} medium
              {% elif alert.state == 'High' %} high
              {% else %} unknown {% endif %}">
              <div>
                <span class="info-box-text">Type: {{ alert.alert_type }}</span>
                <span class="info-box-text">Trigger: {{ alert.trigger_value }}</span>
                <span class="info-box-text">State: {{ alert.state }}</span>
                <span class="info-box-text">Status: {{ alert.status }}</span>
                <span class="info-box-text">Alert ID: {{ alert.id if alert.id else 'N/A' }}</span>
                <span class="info-box-text">Pos Ref: {{ alert.position_reference_id if alert.position_reference_id else 'N/A' }}</span>
              </div>
            </div>
          {% endfor %}
        </div>
        </body>
        </html>
        """
        self.env = Environment(loader=DictLoader({"alert_matrix.html": self.template_str}))
        self.template = self.env.get_template("alert_matrix.html")

    def test_render_alert_matrix(self):
        rendered_html = self.template.render({"alerts": self.alerts})
        # Write the rendered HTML to a file so you can manually inspect it.
        with open("alert_matrix_injection_output.html", "w", encoding="utf-8") as f:
            f.write(rendered_html)

        # Debug print the number of alerts and their details.
        print("Number of alerts in DB:", len(self.alerts))
        for alert in self.alerts:
            print(alert)

        # Assert that each alert's ID and position reference are rendered correctly.
        for alert in self.alerts:
            if alert.get("id"):
                self.assertIn(str(alert.get("id")), rendered_html)
            else:
                self.assertIn("Alert ID: N/A", rendered_html)
            if alert.get("position_reference_id"):
                self.assertIn(str(alert.get("position_reference_id")), rendered_html)
            else:
                self.assertIn("Pos Ref: N/A", rendered_html)
        print("Rendered alert matrix with DB alerts in alert_matrix_injection_output.html.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
