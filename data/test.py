#!/usr/bin/env python3
import sqlite3
import os


def find_duplicate_alerts(db_path):
    """
    Connects to the SQLite database at db_path, queries the alerts table for duplicate alerts,
    and prints out details about any duplicate entries found.

    Duplicate alerts are defined here as rows with the same position_reference_id and alert_type.
    """
    try:
        conn = sqlite3.connect(db_path)
        # Enable accessing columns by name
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
        SELECT 
            position_reference_id, 
            alert_type, 
            COUNT(*) as count, 
            GROUP_CONCAT(id) as alert_ids
        FROM alerts
        GROUP BY position_reference_id, alert_type
        HAVING COUNT(*) > 1;
        """

        cursor.execute(query)
        duplicates = cursor.fetchall()

        if duplicates:
            print("Duplicate alerts found:")
            for row in duplicates:
                pos_id = row["position_reference_id"] or "None"
                print(f"  Position Reference ID: {pos_id}")
                print(f"  Alert Type: {row['alert_type']}")
                print(f"  Count: {row['count']}")
                print(f"  Alert IDs: {row['alert_ids']}")
                print("-" * 40)
        else:
            print("No duplicate alerts found.")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    # Set the default database path.
    # Update this path as needed.
    default_db_path = "c:/v0.7/data/mother_brain.db"  # <-- Change this to the actual DB file path

    print("Using database file:", default_db_path)
    if not os.path.exists(default_db_path):
        print(f"Database file '{default_db_path}' not found. Please update the default_db_path variable in the script.")
    else:
        find_duplicate_alerts(default_db_path)
