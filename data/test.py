#!/usr/bin/env python
import sqlite3
import os
import sys

# Replace this with your actual DB_PATH or import it from your config_constants if available.
DB_PATH = "mother_brain.db"


def add_column_if_not_exists(conn, table_name, column_name, column_definition):
    """
    Checks if the specified column exists in the table.
    If not, adds the column using an ALTER TABLE statement.
    """
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]  # row[1] is the column name.
    if column_name in columns:
        print(f"Column '{column_name}' already exists in table '{table_name}'.")
    else:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        print(f"Adding column: {sql}")
        cursor.execute(sql)
        conn.commit()
        print(f"Column '{column_name}' added to table '{table_name}'.")


def main():
    if not os.path.exists(DB_PATH):
        print(f"Database file '{DB_PATH}' not found.")
        sys.exit(1)
    try:
        conn = sqlite3.connect(DB_PATH)
        print("Connected to the database.")

        # Add missing columns.
        add_column_if_not_exists(conn, "alerts", "alert_class", "TEXT")
        add_column_if_not_exists(conn, "alerts", "description", "TEXT")

        conn.close()
        print("Done. Database connection closed.")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
