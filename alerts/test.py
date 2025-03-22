#!/usr/bin/env python
import sqlite3
from config.config_constants import DB_PATH

def add_missing_columns(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Try to add the asset_type column.
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN asset_type TEXT")
        print("Added column 'asset_type' to alerts table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Column 'asset_type' already exists.")
        else:
            print("Error adding 'asset_type':", e)
            raise

    # Try to add the state column.
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN state TEXT")
        print("Added column 'state' to alerts table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Column 'state' already exists.")
        else:
            print("Error adding 'state':", e)
            raise

    conn.commit()
    conn.close()

if __name__ == "__main__":
    add_missing_columns(DB_PATH)
