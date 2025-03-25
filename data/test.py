import sqlite3
from config.config_constants import DB_PATH  # Adjust the path as needed

def create_alerts_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Drop the table if it already exists
        cursor.execute("DROP TABLE IF EXISTS alerts;")
        # Create the alerts table with all required columns
        cursor.execute("""
            CREATE TABLE alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id TEXT,
                alert_type TEXT NOT NULL,
                alert_class TEXT,
                notification_type TEXT,
                status TEXT,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            );
        """)
        conn.commit()
        print("Alerts table created successfully with all columns.")
    except Exception as e:
        print(f"Error creating alerts table: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_alerts_table()
