#!/usr/bin/env python
import sqlite3
from uuid import uuid4
from datetime import datetime
import os
from config.config_constants import DB_PATH


def ensure_travel_percent_column():
    """Ensure that the alerts table has the 'travel_percent' column."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(alerts)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "travel_percent" not in columns:
        print("Column 'travel_percent' not found in alerts table. Adding it...")
        cursor.execute("ALTER TABLE alerts ADD COLUMN travel_percent REAL DEFAULT 0.0")
        conn.commit()
    else:
        print("Column 'travel_percent' already exists.")
    cursor.close()
    conn.close()


def insert_test_alert():
    """Insert a test alert record into the alerts table."""
    # Ensure schema is up-to-date
    ensure_travel_percent_column()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    test_alert = {
        "id": str(uuid4()),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "alert_type": "TravelPercentAlert",
        "alert_class": "Position",
        "asset_type": "BTC",
        "trigger_value": -4.0,
        "condition": "BELOW",
        "notification_type": "Call",
        "state": "Normal",
        "last_triggered": None,
        "status": "Active",
        "frequency": 1,
        "counter": 0,
        "liquidation_distance": 0.0,
        "travel_percent": 0.0,  # Using travel_percent as desired
        "liquidation_price": 0.0,
        "notes": "Test alert for travel percent",
        "description": "Test alert inserted via script",
        "position_reference_id": "test-position-id",
        "evaluated_value": 0.0
    }

    sql = """
    INSERT INTO alerts (
        id, created_at, alert_type, alert_class, asset_type, trigger_value, condition, 
        notification_type, state, last_triggered, status, frequency, counter, 
        liquidation_distance, travel_percent, liquidation_price, notes, description, 
        position_reference_id, evaluated_value
    ) VALUES (
        :id, :created_at, :alert_type, :alert_class, :asset_type, :trigger_value, :condition, 
        :notification_type, :state, :last_triggered, :status, :frequency, :counter, 
        :liquidation_distance, :travel_percent, :liquidation_price, :notes, :description, 
        :position_reference_id, :evaluated_value
    )
    """

    try:
        cursor.execute(sql, test_alert)
        conn.commit()
        print("Test alert inserted successfully.")
    except Exception as e:
        print(f"Error inserting test alert: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    insert_test_alert()
