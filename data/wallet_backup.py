#!/usr/bin/env python3
"""
reset_db.py

This script performs the following steps:
  1. Connects to the database and backs up wallet entries to a JSON file.
  2. Deletes (wipes) the current database file.
  3. Reinitializes the database (which recreates all tables).
  4. Reads the backup file and reinserts the wallet entries into the new database.

Usage:
    python reset_db.py
"""

import os
import sys
import json
from data.data_locker import DataLocker
from config.config_constants import DB_PATH

BACKUP_FILENAME = "wallets_backup.json"


def backup_wallets():
    print("Backing up wallet entries from the database...")
    dl = DataLocker.get_instance()
    wallets = dl.read_wallets()
    with open(BACKUP_FILENAME, "w", encoding="utf-8") as f:
        json.dump(wallets, f, indent=2)
    print(f"Wallet backup saved to {BACKUP_FILENAME}.")
    return wallets


def wipe_database():
    print("Wiping out the database...")
    # Close the connection if it is open.
    dl = DataLocker.get_instance()
    dl.close()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Deleted database file: {DB_PATH}")
    else:
        print("Database file not found; nothing to delete.")


def rebuild_database_and_restore_wallets(wallets):
    print("Rebuilding the database...")
    # Force a new instance by resetting the singleton.
    DataLocker._instance = None
    dl = DataLocker.get_instance()  # This will reinitialize the DB and create tables.
    print("Database reinitialized.")
    print("Restoring wallet entries...")
    # Reinsert each wallet into the new database.
    for wallet in wallets:
        try:
            dl.create_wallet(wallet)
            print(f"Restored wallet: {wallet.get('name', 'Unnamed')}")
        except Exception as e:
            print(f"Error restoring wallet {wallet.get('name', 'Unnamed')}: {e}")
    print("Wallet restoration complete.")


def main():
    print("=== DB Reset and Wallet Restoration Script ===")
    # Step 1: Backup wallets.
    wallets = backup_wallets()
    # Confirm from the user.
    confirm = input("WARNING: This will wipe out the entire database. Type 'yes' to proceed: ")
    if confirm.lower() != "yes":
        print("Aborting reset process.")
        sys.exit(0)
    # Step 2: Wipe database.
    wipe_database()
    # Step 3: Rebuild database and restore wallets.
    rebuild_database_and_restore_wallets(wallets)
    print("Database reset and wallet restoration complete.")


if __name__ == "__main__":
    main()
