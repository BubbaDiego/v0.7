import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("ConfigLoader")


def deep_merge_dicts(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge `overrides` into `base`. For keys present in both:
      - If both values are dicts, merge them recursively.
      - Otherwise, the value from `overrides` takes precedence.
    """
    merged = dict(base)
    for key, val in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = deep_merge_dicts(merged[key], val)
        else:
            merged[key] = val
    return merged


def ensure_overrides_table(db_conn) -> None:
    """
    Ensures the 'config_overrides' table exists in the database.
    """
    try:
        db_conn.execute("""
            CREATE TABLE IF NOT EXISTS config_overrides (
                id INTEGER PRIMARY KEY,
                overrides TEXT
            )
        """)
        db_conn.execute("""
            INSERT OR IGNORE INTO config_overrides (id, overrides)
            VALUES (1, '{}')
        """)
        db_conn.commit()
    except Exception as e:
        logger.error(f"Error ensuring config_overrides table: {e}")


def load_overrides_from_db(db_conn) -> Dict[str, Any]:
    """
    Loads configuration overrides from the database.
    """
    try:
        ensure_overrides_table(db_conn)
        row = db_conn.execute("SELECT overrides FROM config_overrides WHERE id=1").fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return {}
    except Exception as e:
        logger.error(f"Could not load overrides from DB: {e}")
        return {}


def load_json_config(json_path: str) -> Dict[str, Any]:
    """
    Reads JSON from the file at `json_path` and returns it as a dictionary.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"JSON config file '{json_path}' not found. Returning empty dict.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from '{json_path}': {e}")
        return {}


def load_config():
    config_path = CONFIG_PATH  # Ensure this points to your sonic_config.json
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        current_app.logger.error("Error loading config: %s", e)
        # Return a default config to prevent template errors
        return {
            "system_config": {
                "db_path": "./v0.6/mother_brain.db",
                "log_file": "./v0.6/price_monitor.log"
            },
            "theme_config": {
                "selected_profile": "profile1",
                "profiles": {
                    "profile1": {
                        "primary": {"color": "#581845", "image": None},
                        "secondary": {"color": "#FFC300", "image": None},
                        "text": {"color": "#FFFFFF"},
                        "title_bar": {"color": "#FF5733", "image": None},
                        "side_bar": {"color": "#C70039", "image": None},
                        "wallpaper": {"color": "#900C3F", "image": None}
                    }
                }
            }
        }



def save_config(config: Dict[str, Any], json_path: str = "sonic_config.json") -> None:
    """
    Saves the configuration dictionary to the JSON file at `json_path`.
    """
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        logger.debug(f"Configuration saved to: {json_path}")
    except Exception as e:
        logger.error(f"Error saving configuration to '{json_path}': {e}")


def update_config(new_config: Dict[str, Any], json_path: str = "sonic_config.json", db_conn: Optional[Any] = None) -> Dict[str, Any]:
    """
    Updates the configuration by:
      1) Loading the current configuration (including any DB overrides if provided).
      2) Merging in the new configuration values (with new values overriding existing ones).
      3) Saving the merged configuration back to the JSON file.
      4) Returning the updated configuration dictionary.

    Parameters:
      - new_config: A dictionary of configuration updates.
      - json_path: Path to the JSON config file.
      - db_conn: Optional database connection (if you want to merge in DB overrides).

    Returns:
      The updated configuration dictionary.
    """
    current_config = load_config(json_path, db_conn)
    updated_config = deep_merge_dicts(current_config, new_config)
    save_config(updated_config, json_path)
    logger.debug(f"Configuration updated and saved to: {json_path}")
    return updated_config
