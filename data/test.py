#!/usr/bin/env python
import sqlite3
import os

# Update this path to point to your SQLite database file.
DB_PATH = "c:/v0.7/data/mother_brain.db"


def backup_wallets(conn):
    """Backup all rows from the wallets table."""
    cursor = conn.cursor()
    cursor.execute("SELECT name, public_address, private_address, image_path, balance FROM wallets")
    wallets = cursor.fetchall()
    cursor.close()
    return wallets

def drop_old_tables(conn):
    """Drop all tables except the wallets table."""
    # List of tables to drop (all except wallets)
    tables_to_drop = [
        "system_vars",
        "prices",
        "positions",
        "alerts",
        "alert_ledger",
        "brokers",
        "portfolio_entries",
        "positions_totals_history"
    ]
    cursor = conn.cursor()
    for table in tables_to_drop:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"Dropped table {table}")
    conn.commit()
    cursor.close()

def create_new_tables(conn):
    """Create new tables with the updated schemas."""
    cursor = conn.cursor()

    # system_vars table
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
    print("Created table system_vars")

    # prices table
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
    print("Created table prices")

    # positions table
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
    print("Created table positions")

    # alerts table with new 'level' column instead of 'state'
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
    print("Created table alerts")

    # alert_ledger table
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
    print("Created table alert_ledger")

    # brokers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS brokers (
        name TEXT PRIMARY KEY,
        image_path TEXT,
        web_address TEXT,
        total_holding REAL DEFAULT 0.0
    )
    """)
    print("Created table brokers")

    # wallets table: ensure it exists (we keep its data)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wallets (
        name TEXT PRIMARY KEY,
        public_address TEXT,
        private_address TEXT,
        image_path TEXT,
        balance REAL DEFAULT 0.0
    )
    """)
    print("Ensured table wallets exists")

    # portfolio_entries table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_entries (
        id TEXT PRIMARY KEY,
        snapshot_time DATETIME,
        total_value REAL NOT NULL
    )
    """)
    print("Created table portfolio_entries")

    # positions_totals_history table
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
    print("Created table positions_totals_history")

    conn.commit()
    cursor.close()

def restore_wallets(conn, wallets):
    """Reinsert wallets backup if the wallets table is empty."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM wallets")
    count = cursor.fetchone()[0]
    if count == 0 and wallets:
        for wallet in wallets:
            # wallet is a sqlite3.Row; convert to tuple matching (name, public_address, private_address, image_path, balance)
            cursor.execute("""
            INSERT INTO wallets (name, public_address, private_address, image_path, balance)
            VALUES (?, ?, ?, ?, ?)
            """, (wallet["name"], wallet["public_address"], wallet["private_address"], wallet["image_path"], wallet["balance"]))
        conn.commit()
        print(f"Restored {len(wallets)} wallet record(s)")
    else:
        print("Wallets table already has data; no need to restore backup")
    cursor.close()

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database file {DB_PATH} does not exist.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("Backing up wallets data...")
    wallets_backup = backup_wallets(conn)
    print(f"Backed up {len(wallets_backup)} wallet record(s)")

    print("Dropping old tables (except wallets)...")
    drop_old_tables(conn)

    print("Creating new tables with updated schemas...")
    create_new_tables(conn)

    print("Restoring wallets data if needed...")
    restore_wallets(conn, wallets_backup)

    conn.close()
    print("Database migration complete.")

if __name__ == "__main__":
    main()
