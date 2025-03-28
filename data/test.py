#!/usr/bin/env python
import sqlite3
import os
from config.config_constants import DB_PATH

def wipe_and_recreate_db():
    db_path = DB_PATH
    print(f"Wiping and recreating DB at {db_path} (preserving 'wallets' table)...")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List of tables to drop (do not include "wallets")
    tables_to_drop = [
        "system_vars",
        "prices",
        "positions",
        "alerts",
        "brokers",
        "portfolio_entries",
        "positions_totals_history"
    ]
    
    for table in tables_to_drop:
        print(f"Dropping table '{table}' if it exists...")
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    
    # Recreate tables with the updated (perfect) schema

    # 1. system_vars table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_vars (
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
        INSERT OR IGNORE INTO system_vars (
            id, last_update_time_positions, last_update_positions_source,
            last_update_time_prices, last_update_prices_source, last_update_time_jupiter,
            last_update_jupiter_source, total_brokerage_balance, total_wallet_balance,
            total_balance, strategy_start_value, strategy_description
        )
        VALUES (1, NULL, NULL, NULL, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, '')
    """)

    # 2. prices table
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

    # 3. positions table (using "travel_percent" instead of "current_travel_percent")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            asset_type TEXT,
            position_type TEXT,
            entry_price REAL,
            liquidation_price REAL,
            travel_percent REAL,       -- Updated field name
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

    # 4. alerts table (using "travel_percent" instead of "target_travel_percent")
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
            state TEXT,
            last_triggered DATETIME,
            status TEXT,
            frequency INTEGER,
            counter INTEGER,
            liquidation_distance REAL,
            travel_percent REAL,       -- Updated field name
            liquidation_price REAL,
            notes TEXT,
            description TEXT,
            position_reference_id TEXT,
            evaluated_value REAL
        )
    """)

    # 5. brokers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brokers (
            name TEXT PRIMARY KEY,
            image_path TEXT,
            web_address TEXT,
            total_holding REAL DEFAULT 0.0
        )
    """)

    # 6. wallets table is preserved (do not drop)

    # 7. portfolio_entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_entries (
            id TEXT PRIMARY KEY,
            snapshot_time DATETIME,
            total_value REAL NOT NULL
        )
    """)

    # 8. positions_totals_history table
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
    conn.close()
    print("Database wiped and recreated successfully (wallets table preserved).")

if __name__ == "__main__":
    wipe_and_recreate_db()
