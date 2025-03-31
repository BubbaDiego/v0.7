#!/usr/bin/env python3
import sqlite3
import json
import os
from config.config_constants import DB_PATH

def create_wallets_table(conn):
    # Create the wallets table if it doesn't exist.
    create_table_query = """
    CREATE TABLE IF NOT EXISTS wallets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        public_address TEXT,
        private_address TEXT,
        image_path TEXT,
        balance REAL
    );
    """
    conn.execute(create_table_query)
    conn.commit()

def insert_wallets(conn, wallets):
    cursor = conn.cursor()
    insert_query = """
    INSERT INTO wallets (name, public_address, private_address, image_path, balance)
    VALUES (?, ?, ?, ?, ?);
    """
    for wallet in wallets:
        name = wallet.get("name", "")
        public_address = wallet.get("public_address", "")
        private_address = wallet.get("private_address", "")
        image_path = wallet.get("image_path", "")
        balance = wallet.get("balance", 0)
        cursor.execute(insert_query, (name, public_address, private_address, image_path, balance))
    conn.commit()

def main():
    try:
        # Connect to the SQLite database using the DB_PATH from config_constants.py
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        
        # Create the wallets table if it doesn't exist
        create_wallets_table(conn)
        
        # Assume wallets_backup.json is in the same directory as this script
        json_path = os.path.join(os.path.dirname(__file__), "wallets_backup.json")
        with open(json_path, "r", encoding="utf-8") as f:
            wallets = json.load(f)
        
        # Insert the wallets into the DB
        insert_wallets(conn, wallets)
        print("Successfully injected wallets into the database.")
    except Exception as e:
        print(f"Error injecting wallets: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
