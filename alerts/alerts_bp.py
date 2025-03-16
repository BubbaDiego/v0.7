import os
import json
import logging
from flask import Blueprint, request, jsonify, render_template, current_app
from config.config_constants import BASE_DIR, ALERT_LIMITS_PATH
from pathlib import Path
from utils.operations_manager import OperationsLogger
from utils.json_manager import JsonManager, JsonType

# Create the blueprint with URL prefix '/alerts'
alerts_bp = Blueprint('alerts_bp', __name__, url_prefix='/alerts')

logger = logging.getLogger("AlertManagerLogger")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# Deep merge function
def deep_merge(source: dict, updates: dict) -> dict:
    for key, value in updates.items():
        if key in source and isinstance(source[key], dict) and isinstance(value, dict):
            logger.debug("Deep merging key: %s", key)
            source[key] = deep_merge(source[key], value)
        else:
            logger.debug("Updating key: %s with value: %s", key, value)
            source[key] = value
    return source

def convert_types_in_dict(d):
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
    updated = {}
    for full_key, value in form.items():
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
    metrics = [
        "heat_index_ranges", "collateral_ranges", "value_ranges",
        "size_ranges", "leverage_ranges", "liquidation_distance_ranges",
        "travel_percent_liquid_ranges", "travel_percent_profit_ranges", "profit_ranges"
    ]
    html = "<table border='1' style='border-collapse: collapse; width:100%;'>"
    html += "<tr><th>Metric</th><th>Enabled</th><th>Low</th><th>Medium</th><th>High</th></tr>"
    # Reload alert limits from the file using the current JsonManager instance
    json_manager = current_app.json_manager
    alert_data = json_manager.load("alert_limits.json", json_type=JsonType.ALERT_LIMITS)
    for m in metrics:
        data = alert_data.get("alert_ranges", {}).get(m, {})
        enabled = data.get("enabled", False)
        low = data.get("low", "")
        medium = data.get("medium", "")
        high = data.get("high", "")
        html += f"<tr><td>{m}</td><td>{enabled}</td><td>{low}</td><td>{medium}</td><td>{high}</td></tr>"
    html += "</table>"
    return html

# New route for the Alarm Viewer (default mode)
@alerts_bp.route('/viewer', methods=['GET'], endpoint="alarm_viewer")
def alarm_viewer():
    from data.data_locker import DataLocker
    data_locker = DataLocker.get_instance()
    json_manager = current_app.json_manager

    # Load the alert config from alert_limits.json
    config_data = json_manager.load("alert_limits.json", json_type=JsonType.ALERT_LIMITS)
    travel_cfg = config_data["alert_ranges"]["travel_percent_liquid_ranges"]  # e.g. {enabled, low, medium, high, ...}
    profit_cfg = config_data["alert_ranges"]["profit_ranges"]                # e.g. {enabled, low, medium, high, ...}

    # For price alerts, if you want to show real triggers:
    price_alerts = config_data["alert_ranges"].get("price_alerts", {})

    # Fetch positions from DB
    positions = data_locker.read_positions()

    for pos in positions:
        asset = pos.get("asset_type", "").upper()

        # Example logic for deciding card color
        if asset == "BTC":
            pos["alert_status"] = "green"
        elif asset == "ETH":
            pos["alert_status"] = "yellow"
        elif asset == "SOL":
            pos["alert_status"] = "red"
        else:
            pos["alert_status"] = "unknown"

        # Attach the real threshold values from your config
        # so the template can display them:
        pos["travel_low"] = travel_cfg.get("low")
        pos["travel_medium"] = travel_cfg.get("medium")
        pos["travel_high"] = travel_cfg.get("high")

        pos["profit_low"] = profit_cfg.get("low")
        pos["profit_medium"] = profit_cfg.get("medium")
        pos["profit_high"] = profit_cfg.get("high")

        # If you store current_travel_percent, profit, etc. in the DB, you can do:
        #   pos["current_travel_percent"] = ...
        #   pos["profit"] = ...
        # If you want price triggers, you could do something like:
        #   asset_alert_cfg = price_alerts.get(asset, {})
        #   pos["price_condition"] = asset_alert_cfg.get("condition", "???")
        #   pos["price_trigger"] = asset_alert_cfg.get("trigger_value", "???")

        # For demonstration, let's also assume we have a 'current_price' from DB
        # If get_latest_price(...) returns a dict with e.g. "current_price"
        latest_price = data_locker.get_latest_price(asset)
        pos["current_price"] = latest_price["current_price"] if latest_price else 0.0

    theme_config = current_app.config.get('theme', {})
    return render_template("alert_viewer.html", theme=theme_config, positions=positions)


@alerts_bp.route('/config', methods=['GET'], endpoint="alert_config_page")
def config_page():
    try:
        json_manager = current_app.json_manager
        # Load alert limits using the JsonType enum from our module
        config_data = json_manager.load("alert_limits.json", json_type=JsonType.ALERT_LIMITS)
    except Exception as e:
        op_logger = OperationsLogger(log_filename=os.path.join(os.getcwd(), "operations_log.txt"))
        op_logger.log("Alert Configuration Failed", source="System",
                      operation_type="Alert Configuration Failed",
                      file_name=str(ALERT_LIMITS_PATH))
        logger.error("Error loading alert limits: %s", str(e))
        return render_template("alert_limits.html", error_message="Error loading alert configuration."), 500

    alert_config = config_data.get("alert_ranges", {})
    price_alerts = alert_config.get("price_alerts", {})
    theme_config = config_data.get("theme_config", {})  # If theme config is stored here

    return render_template("alert_limits.html", alert_ranges=alert_config, price_alerts=price_alerts, theme=theme_config)

@alerts_bp.route('/update_config', methods=['POST'], endpoint="update_alert_config")
def update_alert_config_route():
    op_logger = OperationsLogger(log_filename=os.path.join(os.getcwd(), "operations_log.txt"))
    try:
        flat_form = request.form.to_dict(flat=False)
        logger.debug("POST Data Received:\n%s", json.dumps(flat_form, indent=2))
        nested_update = parse_nested_form(flat_form)
        logger.debug("Parsed Nested Form Data (raw):\n%s", json.dumps(nested_update, indent=2))
        nested_update = convert_types_in_dict(nested_update)
        logger.debug("Parsed Nested Form Data (converted):\n%s", json.dumps(nested_update, indent=2))
        json_manager = current_app.json_manager
        current_config = json_manager.load("alert_limits.json", json_type=JsonType.ALERT_LIMITS)
        merged_config = deep_merge(current_config, nested_update)
        json_manager.save("alert_limits.json", merged_config, json_type=JsonType.ALERT_LIMITS)
        updated_config = json_manager.load("alert_limits.json", json_type=JsonType.ALERT_LIMITS)
        formatted_table = format_alert_config_table(updated_config.get("alert_ranges", {}))
        logger.debug("New Config Loaded After Update:\n%s", json.dumps(updated_config, indent=2))
        return jsonify({"success": True, "formatted_table": formatted_table})
    except Exception as e:
        logger.error("Error updating alert config: %s", str(e))
        op_logger.log("Alert Configuration Failed", source="System",
                      operation_type="Alert Config Failed", file_name=str(ALERT_LIMITS_PATH))
        return jsonify({"success": False, "error": str(e)}), 500

# For testing this blueprint independently
if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(alerts_bp)
    # Attach a JsonManager instance to the app
    app.json_manager = JsonManager()
    app.run(debug=True, port=5001)
