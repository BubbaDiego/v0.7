#!/usr/bin/env python3
import os
import sqlite3

def rebuild_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # --- Step 1: Ensure the 'alerts' table exists ---
    print("Checking if 'alerts' table exists...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'")
    result = cursor.fetchone()
    if result is None:
        print("'alerts' table does not exist. Creating 'alerts' table...")
        cursor.execute("""
            CREATE TABLE alerts (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                alert_type TEXT,
                alert_class TEXT,
                asset_type TEXT,
                trigger_value REAL DEFAULT 0,
                condition TEXT,
                notification_type TEXT,
                level TEXT,
                last_triggered TEXT,
                status TEXT,
                frequency INTEGER,
                counter INTEGER,
                liquidation_distance REAL,
                travel_percent REAL,
                liquidation_price REAL,
                notes TEXT,
                description TEXT,
                position_reference_id TEXT,
                evaluated_value REAL
            );
        """)
        conn.commit()
    else:
        print("'alerts' table exists.")

    # --- Step 2: Check for the 'trigger_value' column in 'alerts' table ---
    print("Checking for 'trigger_value' column in 'alerts' table...")
    cursor.execute("PRAGMA table_info(alerts)")
    columns = [row[1] for row in cursor.fetchall()]
    if "trigger_value" not in columns:
        print("Column 'trigger_value' not found in 'alerts'. Adding it now...")
        cursor.execute("ALTER TABLE alerts ADD COLUMN trigger_value REAL DEFAULT 0")
        conn.commit()
    else:
        print("Column 'trigger_value' already exists in 'alerts'.")

    # --- Step 3: Drop all other tables (excluding SQLite internal tables and 'alerts') ---
    print("Dropping all tables except 'alerts' and SQLite internals...")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
          AND name NOT LIKE 'sqlite_%'
          AND name != 'alerts'
    """)
    tables = cursor.fetchall()
    for (table_name,) in tables:
        print(f"Dropping table: {table_name}")
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    conn.commit()

    # --- Step 4: Rebuild the other tables ---
    # Adjust the following CREATE TABLE statements to match your actual schema.
    print("Rebuilding dropped tables...")

    create_tables_sql = {
        "prices": """
            CREATE TABLE prices (
                id TEXT PRIMARY KEY,
                asset_type TEXT,
                current_price REAL,
                previous_price REAL,
                created_at TEXT
            );
        """,
        "positions": """
            CREATE TABLE positions (
                id TEXT PRIMARY KEY,
                asset_type TEXT,
                entry_price REAL,
                liquidation_price REAL,
                travel_percent REAL,
                alert_reference_id TEXT,
                created_at TEXT
            );
        """,
        "alert_ledger": """
            CREATE TABLE alert_ledger (
                id TEXT PRIMARY KEY,
                alert_id TEXT,
                updated_by TEXT,
                reason TEXT,
                old_value TEXT,
                new_value TEXT,
                updated_at TEXT
            );
        """,
        "system_vars": """
            CREATE TABLE system_vars (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """,
        "brokers": """
            CREATE TABLE brokers (
                id TEXT PRIMARY KEY,
                name TEXT,
                config TEXT
            );
        """,
        "wallets": """
            CREATE TABLE wallets (
                id TEXT PRIMARY KEY,
                address TEXT,
                balance REAL,
                asset_type TEXT
            );
        """,
        "portfolio_entries": """
            CREATE TABLE portfolio_entries (
                id TEXT PRIMARY KEY,
                asset_type TEXT,
                amount REAL,
                created_at TEXT
            );
        """,
        "positions_totals_history": """
            CREATE TABLE positions_totals_history (
                id TEXT PRIMARY KEY,
                total_positions REAL,
                snapshot_date TEXT
            );
        """
    }

    for table_name, create_sql in create_tables_sql.items():
        print(f"Creating table: {table_name}")
        cursor.execute(create_sql)

    conn.commit()
    conn.close()
    print("Database rebuild complete.")

if __name__ == "__main__":
    # Use the DB_PATH environment variable if set, or default to 'alerts.db'
    db_path = os.getenv("DB_PATH", "alerts.db")
    rebuild_database(db_path)
