#!/usr/bin/env python
import time
from uuid import uuid4
from alert_controller import AlertController

# Define a dummy alert class that mimics the expected interface.
class DummyAlert:
    def __init__(self, alert_type="TestAlert", asset_type="BTC", trigger_value=100.0, condition="ABOVE",
                 notification_type="Email", status="Active", frequency=1, counter=0, liquidation_distance=0.0,
                 target_travel_percent=0.0, liquidation_price=0.0, notes="Test note", position_reference_id=None):
        # Let DataLocker assign an ID if not provided.
        self.id = None  
        self.alert_type = alert_type
        self.asset_type = asset_type
        self.trigger_value = trigger_value
        self.condition = condition
        self.notification_type = notification_type
        self.last_triggered = None
        self.status = status
        self.frequency = frequency
        self.counter = counter
        self.liquidation_distance = liquidation_distance
        self.target_travel_percent = target_travel_percent
        self.liquidation_price = liquidation_price
        self.notes = notes
        self.position_reference_id = position_reference_id

    def to_dict(self):
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "asset_type": self.asset_type,
            "trigger_value": self.trigger_value,
            "condition": self.condition,
            "notification_type": self.notification_type,
            "last_triggered": self.last_triggered,
            "status": self.status,
            "frequency": self.frequency,
            "counter": self.counter,
            "liquidation_distance": self.liquidation_distance,
            "target_travel_percent": self.target_travel_percent,
            "liquidation_price": self.liquidation_price,
            "notes": self.notes,
            "position_reference_id": self.position_reference_id
        }

def test_alert_controller():
    # Instantiate the controller
    controller = AlertController()

    # ---- Create Alert ----
    print("=== Creating Dummy Alert ===")
    dummy_alert = DummyAlert(alert_type="PriceThreshold", trigger_value=200.0, status="Active")
    if controller.create_alert(dummy_alert):
        print("Alert created successfully.")
    else:
        print("Failed to create alert.")

    # Wait a moment to ensure the alert is committed
    time.sleep(1)
    alerts = controller.data_locker.get_alerts()
    print("\n=== Alerts After Creation ===")
    if alerts:
        for alert in alerts:
            print(alert)
    else:
        print("No alerts found.")

    # ---- Update Alert ----
    if alerts:
        alert_id = alerts[0]["id"]
        print(f"\n=== Updating Alert (ID: {alert_id}) ===")
        if controller.update_alert(alert_id, {"status": "Inactive"}):
            print("Alert updated successfully.")
        else:
            print("Failed to update alert.")

        # Verify update
        alerts_after_update = controller.data_locker.get_alerts()
        print("\n=== Alerts After Update ===")
        for alert in alerts_after_update:
            print(alert)
    else:
        print("No alerts available to update.")

    # ---- Delete Alert ----
    if alerts:
        alert_id = alerts[0]["id"]
        print(f"\n=== Deleting Alert (ID: {alert_id}) ===")
        if controller.delete_alert(alert_id):
            print("Alert deleted successfully.")
        else:
            print("Failed to delete alert.")

        # Verify deletion
        alerts_after_deletion = controller.data_locker.get_alerts()
        print("\n=== Alerts After Deletion ===")
        if alerts_after_deletion:
            for alert in alerts_after_deletion:
                print(alert)
        else:
            print("No alerts found; deletion successful.")
    else:
        print("No alerts available to delete.")

if __name__ == "__main__":
    test_alert_controller()
