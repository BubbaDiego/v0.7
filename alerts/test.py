#!/usr/bin/env python
import sqlite3
import os
import logging
from config.config_constants import DB_PATH  # Adjust import as needed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def column_exists(conn, table_name, column_name):
    """
    Checks if a given column exists in a table.
    """
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row["name"] for row in cursor.fetchall()]
    cursor.close()
    return column_name in columns

def add_evaluated_value_column(conn):
    """
    Adds the evaluated_value column to the alerts table.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN evaluated_value REAL DEFAULT 0.0")
        conn.commit()
        logger.info("Column 'evaluated_value' added successfully to the 'alerts' table.")
    except sqlite3.OperationalError as e:
        logger.error("Error adding column 'evaluated_value': %s", e)
    finally:
        cursor.close()

def main():
    if not os.path.exists(DB_PATH):
        logger.error("Database file does not exist: %s", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # To access rows as dictionaries
    if column_exists(conn, "alerts", "evaluated_value"):
        logger.info("Column 'evaluated_value' already exists in the 'alerts' table.")
    else:
        add_evaluated_value_column(conn)
    conn.close()

if __name__ == "__main__":
    main()
