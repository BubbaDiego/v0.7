#!/usr/bin/env python
"""
update_schema.py

This self-contained script connects to your SQLite database and ensures that
the required tables are created with the correct schema, including the 'position_type'
column in the alerts table.

Usage:
    python update_schema.py [database_file]

If [database_file] is not provided, it defaults to a platform-appropriate path.
For Windows, it will default to using the "data/mother_brain.db" file in the current directory.
"""

import sqlite3
import sys
import os
import platform

def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    exists = cursor.fetchone() is not None
    cursor.close()
    return exists

def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = [row["name"] for row in cursor.fetchall()]
    cursor.close()
    return cols

def create_system_vars_table(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute(""" 
        CREATE TABLE IF NOT EXISTS system_vars (
            id INTEGER PRIMARY KEY,
            last_update_time_positions DATETIME,
            last_update_positions_source TEXT,
            last_update_time_prices DATETIME,
            last_update_prices_source TEXT,
            last_update_time_jupiter DATETIME
        )
    """)
    conn.commit()
    cursor.close()
    print("Created 'system_vars' table.")

def create_alerts_table(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            created_at DATETIME,
            alert_type TEXT,
            alert_class TEXT,
            asset_type TEXT,
            trigger_value REAL,
            condition TEXT,
            notification_type TEXT,
            level TEXT,
            last_triggered DATETIME,
            status TEXT,
            frequency INTEGER,
            counter INTEGER,
            liquidation_distance REAL,
            travel_percent REAL,
            liquidation_price REAL,
            notes TEXT,
            description TEXT,
            position_reference_id TEXT,
            evaluated_value REAL,
            position_type TEXT
        )
    """)
    conn.commit()
    cursor.close()
    print("Created or verified 'alerts' table with 'position_type' column.")

def update_alerts_table(conn: sqlite3.Connection):
    cols = get_table_columns(conn, "alerts")
    if "position_type" not in cols:
        print("Column 'position_type' not found in 'alerts' table. Altering table to add column.")
        try:
            cursor = conn.cursor()
            cursor.execute("ALTER TABLE alerts ADD COLUMN position_type TEXT")
            conn.commit()
            cursor.close()
            print("Column 'position_type' added successfully.")
        except Exception as e:
            print(f"Error adding 'position_type' column: {e}")
    else:
        print("Column 'position_type' exists in 'alerts' table.")

def create_positions_table(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            asset_type TEXT,
            position_type TEXT,
            entry_price REAL,
            liquidation_price REAL,
            travel_percent REAL,
            value REAL,
            collateral REAL,
            size REAL,
            leverage REAL,
            wallet_name TEXT,
            last_updated DATETIME,
            alert_reference_id TEXT,
            hedge_buddy_id TEXT,
            current_price REAL,
            liquidation_distance REAL,
            heat_index REAL,
            current_heat_index REAL,
            pnl_after_fees_usd REAL
        )
    """)
    conn.commit()
    cursor.close()
    print("Created 'positions' table with 'position_type' column.")

def create_brokers_table(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brokers (
            id TEXT PRIMARY KEY,
            name TEXT,
            api_key TEXT,
            secret TEXT,
            created_at DATETIME
        )
    """)
    conn.commit()
    cursor.close()
    print("Created 'brokers' table.")

def create_wallets_table(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id TEXT PRIMARY KEY,
            name TEXT,
            balance REAL,
            created_at DATETIME
        )
    """)
    conn.commit()
    cursor.close()
    print("Created 'wallets' table.")

def run_schema_update(db_path):
    print(f"Connecting to database at: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)
    conn.row_factory = sqlite3.Row  # Enable accessing columns by name

    # Create or update tables
    create_system_vars_table(conn)

    if not table_exists(conn, "alerts"):
        print("Table 'alerts' does not exist. Creating table...")
        create_alerts_table(conn)
    else:
        print("Table 'alerts' exists. Verifying required columns...")
        update_alerts_table(conn)

    if not table_exists(conn, "positions"):
        print("Table 'positions' does not exist. Creating table...")
        create_positions_table(conn)
    else:
        print("Table 'positions' exists.")

    if not table_exists(conn, "brokers"):
        print("Table 'brokers' does not exist. Creating table...")
        create_brokers_table(conn)
    else:
        print("Table 'brokers' exists.")

    if not table_exists(conn, "wallets"):
        print("Table 'wallets' does not exist. Creating table...")
        create_wallets_table(conn)
    else:
        print("Table 'wallets' exists.")

    conn.close()
    print("Database schema update completed successfully.")

if __name__ == "__main__":
    # Detect operating system and set default database path accordingly.
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # If running on Windows, use a Windows-style path.
        if os.name == "nt":
            # Assume the script is run from C:\v0.7, then the database is in the data folder.
            default_path = os.path.join(os.getcwd(), "data", "mother_brain.db")
        else:
            default_path = "/data/mother_brain.db"
        db_path = default_path
    print(f"Using database path: {db_path}")
    run_schema_update(db_path)
