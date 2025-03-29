#!/usr/bin/env python
import sqlite3
from uuid import uuid4
from datetime import datetime
from data.data_locker import DataLocker
from alerts.alert_controller import AlertController, DummyPositionAlert
from config.config_constants import DB_PATH


def create_test_alert():
    """
    Create a dummy position alert for testing.
    """
    # Parameters for the dummy alert:
    # - Alert type: "TravelPercentAlert"
    # - Asset type: "BTC"
    # - Trigger value: -4.0
    # - Condition: "BELOW"
    # - Notification type: "Call"
    # - Position reference ID: "test-position-id"
    return DummyPositionAlert("TravelPercentAlert", "BTC", -4.0, "BELOW", "Call", "test-position-id")


def query_alert_ledger():
    """
    Query the alert_ledger table and return all ledger entries.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alert_ledger")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]


def main():
    # Instantiate the AlertController.
    ac = AlertController()
    # Create a test alert using our DummyPositionAlert.
    test_alert = create_test_alert()
    print("Creating alert via AlertController...")
    result = ac.create_alert(test_alert)
    print("Alert creation result:", result)

    # Query the ledger to see if the initial creation log entry was written.
    ledger_entries = query_alert_ledger()
    print("Ledger entries:")
    for entry in ledger_entries:
        print(entry)


if __name__ == "__main__":
    main()
