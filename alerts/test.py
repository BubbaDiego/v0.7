#!/usr/bin/env python3
"""
Test Alert Default Initialization
"""

from alerts.alert_controller import AlertController

def test_defaults():
    # Instantiate AlertController
    ac = AlertController()
    # Simulate an alert with minimal data (simulate a to_dict() that returns an empty dict)
    dummy_alert_data = {}
    initialized = ac.initialize_alert_data(dummy_alert_data)
    print("Initialized Alert Data:")
    for key, value in initialized.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    test_defaults()
