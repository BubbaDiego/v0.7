import os
import json
import logging
from flask import Blueprint, request, jsonify, render_template
from config.config_constants import CONFIG_PATH
from pathlib import Path

# -------------------------------
# Logger Setup
# -------------------------------
logger = logging.getLogger("AlertManagerLogger")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# -------------------------------
# Deep Merge Function
# -------------------------------
def deep_merge(source: dict, updates: dict) -> dict:
    """
    Recursively merge 'updates' into 'source'.
    """
    for key, value in updates.items():
        if key in source and isinstance(source[key], dict) and isinstance(value, dict):
            logger.debug("Deep merging key: %s", key)
            source[key] = deep_merge(source[key], value)
        else:
            logger.debug("Updating key: %s with value: %s", key, value)
            source[key] = value
    return source

# -------------------------------
# SonicConfigManager Class
# -------------------------------
class SonicConfigManager:
    def __init__(self, config_path: str, lock_path: str = "sonic_config.lock"):
        self.config_path = config_path
        self.lock_path = lock_path

    def load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            logger.error("Configuration file not found: %s", self.config_path)
            raise FileNotFoundError("Configuration file not found")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.debug("Loaded config: %s", config)
        return config

    def save_config(self, config: dict) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info("Configuration saved to %s", self.config_path)

    def update_alert_config(self, new_alerts: dict) -> None:
        config = self.load_config()
        current_alerts = config.get("alert_ranges", {})
        logger.debug("Existing alert config: %s", current_alerts)
        merged = deep_merge(current_alerts, new_alerts)
        config["alert_ranges"] = merged
        self.save_config(config)
        logger.info("Alert configuration updated successfully.")

# -------------------------------
# Blueprint Setup and Helpers
# -------------------------------
alerts_bp = Blueprint('alerts_bp', __name__, url_prefix='/alerts')

# Use the robust CONFIG_PATH from config_constants
CONFIG_PATH = str(CONFIG_PATH)
config_mgr = SonicConfigManager(CONFIG_PATH)

def convert_types_in_dict(d):
    """
    Recursively convert string values:
      - "true"/"false" into booleans,
      - Numeric strings to floats.
    """
    if isinstance(d, dict):
        new_d = {}
        for k, v in d.items():
            new_d[k] = convert_types_in_dict(v)
        return new_d
    elif isinstance(d, list):
        return [convert_types_in_dict(item) for item in d]
    elif isinstance(d, str):
        low = d.lower().strip()
        if low == "true":
            return True
        elif low == "false":
            return False
        else:
            try:
                return float(d)
            except ValueError:
                return d
    else:
        return d

def parse_nested_form(form: dict) -> dict:
    """
    Convert flat form keys (like:
       alert_ranges[profit_ranges][enabled]
    ) into a nested dictionary.
    Assumes 'form' is a dict whose values may be lists.
    It also removes the outer "alert_ranges" key if present.
    """
    updated = {}
    for full_key, value in form.items():
        # If value is a list (e.g. hidden + checkbox), take the last one.
        if isinstance(value, list):
            value = value[-1]
        full_key = full_key.strip()
        keys = []
        part = ""
        for char in full_key:
            if char == "[":
                if part:
                    keys.append(part)
                    part = ""
            elif char == "]":
                if part:
                    keys.append(part)
                    part = ""
            else:
                part += char
        if part:
            keys.append(part)
        # Remove the outer "alert_ranges" if present.
        if keys and keys[0] == "alert_ranges":
            keys = keys[1:]
        current = updated
        for i, key in enumerate(keys):
            if i == len(keys) - 1:
                if isinstance(value, str):
                    lower_val = value.lower().strip()
                    if lower_val == "true":
                        v = True
                    elif lower_val == "false":
                        v = False
                    else:
                        try:
                            v = float(value)
                        except ValueError:
                            v = value
                else:
                    v = value
                current[key] = v
            else:
                if key not in current:
                    current[key] = {}
                current = current[key]
    return updated

def format_alert_config_table(alert_ranges: dict) -> str:
    """
    Returns an HTML table string summarizing the alert ranges.
    """
    metrics = [
        "heat_index_ranges", "collateral_ranges", "value_ranges",
        "size_ranges", "leverage_ranges", "liquidation_distance_ranges",
        "travel_percent_liquid_ranges", "travel_percent_profit_ranges", "profit_ranges"
    ]
    html = "<table border='1' style='border-collapse: collapse; width:100%;'>"
    html += "<tr><th>Metric</th><th>Enabled</th><th>Low</th><th>Medium</th><th>High</th></tr>"
    for m in metrics:
        data = alert_ranges.get(m, {})
        enabled = data.get("enabled", False)
        low = data.get("low", "")
        medium = data.get("medium", "")
        high = data.get("high", "")
        html += f"<tr><td>{m}</td><td>{enabled}</td><td>{low}</td><td>{medium}</td><td>{high}</td></tr>"
    html += "</table>"
    return html

# -------------------------------
# Routes
# -------------------------------
@alerts_bp.route('/config', methods=['GET'], endpoint="alert_config_page")
def config():
    try:
        config_data = config_mgr.load_config()
        theme_config = config_data.get("theme_config", {})
        return render_template(
            "alert_manager_config.html",
            alert_ranges=config_data.get("alert_ranges", {}),
            theme=theme_config
        )
    except Exception as e:
        logger.error("Error loading config: %s", str(e))
        return "Error loading config", 500

@alerts_bp.route('/update_config', methods=['POST'], endpoint="update_alert_config")
def update_alert_config():
    logger.debug("Entered update_alert_config endpoint")
    try:
        flat_form = request.form.to_dict(flat=False)
        logger.debug("POST Data Received:\n%s", json.dumps(flat_form, indent=2))

        nested_update = parse_nested_form(flat_form)
        logger.debug("Parsed Nested Form Data (raw):\n%s", json.dumps(nested_update, indent=2))

        nested_update = convert_types_in_dict(nested_update)
        logger.debug("Parsed Nested Form Data (converted):\n%s", json.dumps(nested_update, indent=2))

        config_mgr.update_alert_config(nested_update)
        logger.debug("update_alert_config() called successfully with merged data.")

        updated_config = config_mgr.load_config()
        logger.debug("New Config Loaded After Update:\n%s", json.dumps(updated_config, indent=2))

        formatted_table = format_alert_config_table(updated_config.get("alert_ranges", {}))
        logger.debug("Formatted HTML Table for Alert Config:\n%s", formatted_table)
        return jsonify({"success": True, "formatted_table": formatted_table})
    except Exception as e:
        logger.error("Error updating alert config: %s", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

# -------------------------------
# For running this file directly (for testing)
# -------------------------------
if __name__ == "__main__":
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(alerts_bp)
    app.run(debug=True, port=5001)
