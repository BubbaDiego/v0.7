#!/usr/bin/env python3
"""
rebuild_db.py

This script will drop all tables in the SQLite database except for the
'wallets' table, and then rebuild the remaining tables using new definitions.
Be sure to back up your data before running this script!
"""

import sqlite3
from config.config_constants import DB_PATH
import os

def get_existing_tables(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    return tables

def drop_tables(conn, tables_to_keep):
    existing_tables = get_existing_tables(conn)
    cursor = conn.cursor()
    for table in existing_tables:
        if table not in tables_to_keep:
            print(f"Dropping table: {table}")
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()

def create_tables(conn):
    cursor = conn.cursor()
    
    # Create system_vars table with additional columns (including theme_mode)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_vars (
            id INTEGER PRIMARY KEY,
            last_update_time_positions DATETIME,
            last_update_positions_source TEXT,
            last_update_time_prices DATETIME,
            last_update_prices_source TEXT,
            last_update_time_jupiter DATETIME,
            theme_mode TEXT DEFAULT 'light',
            total_brokerage_balance REAL DEFAULT 0.0,
            total_wallet_balance REAL DEFAULT 0.0,
            total_balance REAL DEFAULT 0.0,
            strategy_start_value REAL DEFAULT 0.0,
            strategy_description TEXT DEFAULT ''
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO system_vars (
            id,
            last_update_time_positions,
            last_update_positions_source,
            last_update_time_prices,
            last_update_prices_source,
            last_update_time_jupiter,
            theme_mode,
            total_brokerage_balance,
            total_wallet_balance,
            total_balance,
            strategy_start_value,
            strategy_description
        )
        VALUES (1, NULL, NULL, NULL, NULL, NULL, 'light', 0.0, 0.0, 0.0, 0.0, '')
    """)

    # Create prices table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
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

    # Create alerts table
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
            evaluated_value REAL
        )
    """)

    # Create alert_ledger table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_ledger (
            id TEXT PRIMARY KEY,
            alert_id TEXT,
            modified_by TEXT,
            reason TEXT,
            before_value TEXT,
            after_value TEXT,
            timestamp DATETIME
        )
    """)

    # Create brokers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brokers (
            name TEXT PRIMARY KEY,
            image_path TEXT,
            web_address TEXT,
            total_holding REAL DEFAULT 0.0
        )
    """)

    # Create portfolio_entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_entries (
            id TEXT PRIMARY KEY,
            snapshot_time DATETIME,
            total_value REAL NOT NULL
        )
    """)

    # Create positions_totals_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions_totals_history (
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
    print("New tables created.")

def main():
    # Connect to the database
    conn = sqlite3.connect(str(DB_PATH))
    # We want to keep the "wallets" table
    tables_to_keep = ["wallets"]
    drop_tables(conn, tables_to_keep)
    create_tables(conn)
    conn.close()
    print("Database rebuild complete.")

if __name__ == '__main__':
    main()
