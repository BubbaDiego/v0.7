#!/usr/bin/env python3
"""
fix_alert_manager.py

This script fixes two issues reported in the logs:
1. Adds the missing 'evaluated_value' column to the 'alerts' table in the database.
2. Fixes any calls to the time module—replacing instances of "time(" with "time.time(" in alert_manager.py.

Usage: 
  python fix_alert_manager.py
"""

import os
import re
import sqlite3
import logging
from config.config_constants import DB_PATH  # Ensure your PYTHONPATH is set so this can be imported

# Setup a basic logger for this script.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_alert_manager")

# --- Part 1: Fix the Database Schema ---
def add_evaluated_value_column(db_path):
    logger.info("Checking if 'evaluated_value' column exists in alerts table...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(alerts)")
    cols = [row["name"] for row in cursor.fetchall()]
    if "evaluated_value" not in cols:
        logger.info("'evaluated_value' column not found. Adding column...")
        try:
            cursor.execute("ALTER TABLE alerts ADD COLUMN evaluated_value REAL")
            conn.commit()
            logger.info("Column 'evaluated_value' added successfully.")
        except sqlite3.Error as e:
            logger.error("Failed to add 'evaluated_value' column: %s", e)
    else:
        logger.info("'evaluated_value' column already exists.")
    conn.close()

# --- Part 2: Fix time() calls in alert_manager.py ---
def fix_time_calls(file_path):
    logger.info("Fixing time() calls in %s...", file_path)
    if not os.path.exists(file_path):
        logger.error("File %s does not exist.", file_path)
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Use a regex that replaces 'time(' with 'time.time(' unless already preceded by 'time.'
    # The negative lookbehind (?<!time\.) ensures we don't modify already-correct calls.
    new_content = re.sub(r'(?<!time\.)\btime\(', 'time.time(', content)

    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        logger.info("Updated %s with fixed time() calls.", file_path)
    else:
        logger.info("No changes made to %s (all time() calls appear to be correct).", file_path)

if __name__ == "__main__":
    # Fix the database schema
    db_path = str(DB_PATH)  # Convert to string if DB_PATH is a Path object.
    add_evaluated_value_column(db_path)

    # Fix the time() calls in alert_manager.py.
    # Adjust the file path if necessary.
    alert_manager_file = os.path.join(os.getcwd(), "alert_manager.py")
    fix_time_calls(alert_manager_file)

    logger.info("All fixes applied.")
