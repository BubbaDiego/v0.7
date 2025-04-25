#!/usr/bin/env python3
import os
import time
from data.data_locker import DataLocker

# Path to the SQLite DB file on PythonAnywhere
DB_PATH = "/home/BubbaDiego/v0.7/data/mother_brain.db"


def main():
    timestamp = time.strftime("%Y%m%d%H%M%S")
    backup_path = f"{DB_PATH}.corrupt.{timestamp}"

    # Step 1: Backup corrupt DB if it exists
    if os.path.exists(DB_PATH):
        print(f"⚠️ Corrupted DB detected. Renaming original to: {backup_path}")
        os.rename(DB_PATH, backup_path)
    else:
        print("ℹ️ No existing DB file found; starting fresh.")

    # Step 2: Reinitialize DB schema via DataLocker
    print("🛠 Initializing new database schema...")
    # This will create the file and run any schema-creation logic in DataLocker
    dl = DataLocker.get_instance(DB_PATH)
    # Force initialization if necessary
    try:
        dl._init_sqlite_if_needed()
    except AttributeError:
        # If private method is named differently or auto-initialized, ignore
        pass

    print(f"✅ New database initialized at: {DB_PATH}")


if __name__ == "__main__":
    main()
