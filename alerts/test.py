#!/usr/bin/env python3
"""
Migration Script for the Alerts Table

This script checks if the 'description' and 'created_at' columns exist in the alerts table.
If they are missing, it adds them with the appropriate datatype.

WARNING: This script will only add columns and will not modify existing data.
"""

import sqlite3
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from config.config_constants import DB_PATH
except ImportError:
    logging.error("Cannot import DB_PATH from config.config_constants. Please check your configuration.")
    sys.exit(1)


def add_missing_columns_to_alerts(db_path):
    logging.info("Connecting to database: %s", db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get the current columns in the alerts table.
    cursor.execute("PRAGMA table_info(alerts)")
    columns = [row[1] for row in cursor.fetchall()]
    logging.info("Existing columns in alerts: %s", columns)

    # Define the missing columns with their definitions.
    missing_columns = {
        "description": "TEXT",
        "created_at": "DATETIME"
    }

    for col, definition in missing_columns.items():
        if col not in columns:
            try:
                logging.info("Adding column '%s' with definition '%s' to alerts table...", col, definition)
                cursor.execute(f"ALTER TABLE alerts ADD COLUMN {col} {definition}")
                conn.commit()
                logging.info("Column '%s' added successfully.", col)
            except Exception as e:
                logging.error("Error adding column '%s': %s", col, e, exc_info=True)
        else:
            logging.info("Column '%s' already exists.", col)

    conn.close()


if __name__ == "__main__":
    add_missing_columns_to_alerts(DB_PATH)
