#!/usr/bin/env python3
"""
Clear the Cyclone Database Completely Except for the Wallets Table

This script drops the following tables if they exist:
  - system_vars
  - prices
  - positions
  - alerts
  - brokers
  - portfolio_entries
  - positions_totals_history

Then, it recreates these tables with a fresh schema. The wallets table is preserved.
The alerts table will include the columns:
  - id (TEXT PRIMARY KEY)
  - created_at (DATETIME)
  - alert_type (TEXT)
  - asset_type (TEXT)
  - trigger_value (REAL)
  - condition (TEXT)
  - notification_type (TEXT)
  - state (TEXT)
  - last_triggered (DATETIME)
  - status (TEXT)
  - frequency (INTEGER)
  - counter (INTEGER)
  - liquidation_distance (REAL)
  - target_travel_percent (REAL)
  - liquidation_price (REAL)
  - notes (TEXT)
  - description (TEXT)
  - position_reference_id (TEXT)
  - evaluated_value (REAL)

WARNING: This will remove all data in the dropped tables.
"""

import sqlite3
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from config.config_constants import DB_PATH
except ImportError:
    logging.error("Unable to import DB_PATH from config.config_constants. Please check your configuration.")
    sys.exit(1)

def drop_tables(conn, tables):
    cursor = conn.cursor()
    for table in tables:
        logging.info(f"Dropping table if exists: {table}")
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()

def create_tables(conn):
    cursor = conn.cursor()

    # Create system_vars table
    cursor.execute("""
        CREATE TABLE system_vars (
            id INTEGER PRIMARY KEY,
            last_update_time_positions DATETIME,
            last_update_positions_source TEXT,
            last_update_time_prices DATETIME,
            last_update_prices_source TEXT,
            last_update_time_jupiter DATETIME,
            last_update_jupiter_source TEXT,
            total_brokerage_balance REAL DEFAULT 0.0,
            total_wallet_balance REAL DEFAULT 0.0,
            total_balance REAL DEFAULT 0.0,
            strategy_start_value REAL DEFAULT 0.0,
            strategy_description TEXT DEFAULT ''
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO system_vars (id) VALUES (1)
    """)

    # Create prices table
    cursor.execute("""
        CREATE TABLE prices (
            id TEXT PRIMARY KEY,
            asset_type TEXT,
            current_price REAL,
            previous_price REAL,
            last_update_time DATETIME,
            previous_update_time DATETIME,
            source TEXT
        )
    """)

    # Create positions table
    cursor.execute("""
        CREATE TABLE positions (
            id TEXT PRIMARY KEY,
            asset_type TEXT,
            position_type TEXT,
            entry_price REAL,
            liquidation_price REAL,
            current_travel_percent REAL,
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

    # Create alerts table with created_at and description columns
    cursor.execute("""
        CREATE TABLE alerts (
            id TEXT PRIMARY KEY,
            created_at DATETIME,
            alert_type TEXT,
            asset_type TEXT,
            trigger_value REAL,
            condition TEXT,
            notification_type TEXT,
            state TEXT,
            last_triggered DATETIME,
            status TEXT,
            frequency INTEGER,
            counter INTEGER,
            liquidation_distance REAL,
            target_travel_percent REAL,
            liquidation_price REAL,
            notes TEXT,
            description TEXT,
            position_reference_id TEXT,
            evaluated_value REAL
        )
    """)

    # Create brokers table
    cursor.execute("""
        CREATE TABLE brokers (
            name TEXT PRIMARY KEY,
            image_path TEXT,
            web_address TEXT,
            total_holding REAL DEFAULT 0.0
        )
    """)

    # Do not drop wallets table (preserve existing wallets)

    # Create portfolio_entries table
    cursor.execute("""
        CREATE TABLE portfolio_entries (
            id TEXT PRIMARY KEY,
            snapshot_time DATETIME,
            total_value REAL NOT NULL
        )
    """)

    # Create positions_totals_history table
    cursor.execute("""
        CREATE TABLE positions_totals_history (
            id TEXT PRIMARY KEY,
            snapshot_time DATETIME,
            total_size REAL,
            total_value REAL,
            total_collateral REAL,
            avg_leverage REAL,
            avg_travel_percent REAL,
            avg_heat_index REAL
        )
    """)
    conn.commit()
    logging.info("All tables recreated successfully (wallets table preserved).")

def main():
    logging.info("Starting database clearance (except wallets table)...")
    conn = sqlite3.connect(DB_PATH)
    try:
        # List of tables to drop and recreate (wallets table is preserved)
        tables_to_clear = [
            "system_vars", "prices", "positions", "alerts", "brokers",
            "portfolio_entries", "positions_totals_history"
        ]
        drop_tables(conn, tables_to_clear)
        create_tables(conn)
        logging.info("Database cleared and recreated successfully.")
    except Exception as e:
        logging.error("Error clearing database: %s", e, exc_info=True)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
