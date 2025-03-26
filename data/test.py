#!/usr/bin/env python3
"""
Add 'description' column to the alerts table if it doesn't exist.
WARNING: This script will only add the column and won't modify existing data.
"""

import sqlite3
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from config.config_constants import DB_PATH
except ImportError:
    logging.error("Cannot import DB_PATH from config.config_constants. Please ensure the file exists.")
    sys.exit(1)


def add_description_column(db_path):
    logging.info("Connecting to database: %s", db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get current columns in alerts table.
    cursor.execute("PRAGMA table_info(alerts)")
    columns = [row[1] for row in cursor.fetchall()]
    logging.info("Existing columns in alerts: %s", columns)

    # If description column is missing, add it.
    if "description" not in columns:
        try:
            logging.info("Adding 'description' column to alerts table...")
            cursor.execute("ALTER TABLE alerts ADD COLUMN description TEXT")
            conn.commit()
            logging.info("'description' column added successfully.")
        except Exception as e:
            logging.error("Error adding 'description' column: %s", e, exc_info=True)
    else:
        logging.info("'description' column already exists.")

    conn.close()


if __name__ == "__main__":
    add_description_column(DB_PATH)
