import os
import sys
import json
import logging
from flask import Blueprint, request, jsonify, render_template, current_app
from config.config_constants import BASE_DIR, ALERT_LIMITS_PATH
from pathlib import Path
from utils.operations_manager import OperationsLogger
from utils.json_manager import JsonManager, JsonType
from sonic_labs.hedge_manager import HedgeManager
from time import time

# Ensure the current directory is in sys.path so we can import alert_manager.py
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Create the blueprint with URL prefix '/alerts'
alerts_bp = Blueprint('alerts_bp', __name__, url_prefix='/alerts', template_folder='.')

logger = logging.getLogger("AlertManagerLogger")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

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


@alerts_bp.route('/create_all_alerts', methods=['POST'], endpoint="create_all_alerts")
def create_all_alerts():
    from alert_manager import manager  # <--- import the global manager
    print("DEBUG: create_all_alerts route was called!")  # or use logger.debug

    # Now call the manager's create_all_alerts, which internally calls the controller
    created_alerts = manager.create_all_alerts()

    return jsonify({"success": True, "created_alerts": created_alerts})

@alerts_bp.route('/delete_all_alerts', methods=['POST'], endpoint="delete_all_alerts")
def delete_all_alerts():
    from alert_controller import AlertController
    controller = AlertController()
    deleted_count = controller.delete_all_alerts()
    return jsonify({"success": True, "deleted_count": deleted_count})

# NEW: Refresh alerts route
@alerts_bp.route('/refresh_alerts', methods=['POST'], endpoint="refresh_alerts")
def refresh_alerts():
    from alert_manager import manager
    try:
        # Call check_alerts to evaluate and update alerts; source "manual refresh" is passed
        manager.check_alerts(source="manual refresh")
        return jsonify({"success": True, "message": "Alerts refreshed."})
    except Exception as e:
        logger.error("Error refreshing alerts: %s", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

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
    try:
        from alert_manager import manager
    except ModuleNotFoundError as e:
        logger.error("Error importing alert_manager: %s", e)
        return "Server configuration error.", 500

    data_locker = DataLocker.get_instance()
    json_manager = current_app.json_manager

    config_data = json_manager.load("alert_limits.json", json_type=JsonType.ALERT_LIMITS)
    cooldown_seconds = float(config_data.get("alert_cooldown_seconds", 900))
    call_refractory_seconds = float(config_data.get("call_refractory_period", 1800))

    travel_cfg = config_data["alert_ranges"]["travel_percent_liquid_ranges"]
    profit_cfg = config_data["alert_ranges"]["profit_ranges"]
    price_alerts = config_data["alert_ranges"].get("price_alerts", {})

    positions = data_locker.read_positions()
    now = time()

    for pos in positions:
        asset = pos.get("asset_type", "").upper()
        position_type = pos.get("position_type", "").capitalize() or "Unknown"
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        asset_full = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana"}.get(asset, asset)

        if asset == "BTC":
            pos["alert_status"] = "green"
        elif asset == "ETH":
            pos["alert_status"] = "yellow"
        elif asset == "SOL":
            pos["alert_status"] = "red"
        else:
            pos["alert_status"] = "unknown"

        pos["travel_low"] = travel_cfg.get("low")
        pos["travel_medium"] = travel_cfg.get("medium")
        pos["travel_high"] = travel_cfg.get("high")
        pos["profit_low"] = profit_cfg.get("low")
        pos["profit_medium"] = profit_cfg.get("medium")
        pos["profit_high"] = profit_cfg.get("high")

        alert_types = []
        details = {}

        try:
            current_travel = float(pos.get("current_travel_percent", 0))
        except:
            current_travel = 0
        if current_travel < 0:
            low_val = float(travel_cfg.get("low", -50))
            medium_val = float(travel_cfg.get("medium", -60))
            high_val = float(travel_cfg.get("high", -75))
            if current_travel <= high_val:
                level = "High"
            elif current_travel <= medium_val:
                level = "Medium"
            elif current_travel <= low_val:
                level = "Low"
            else:
                level = None
            if level:
                alert_types.append("Travel")
                key = f"{asset_full}-{position_type}-{position_id}-travel-{level}"
                last_trigger = manager.last_triggered.get(key, 0)
                remaining = max(0, cooldown_seconds - (now - last_trigger))
                details["Travel Alert"] = f"Remaining cooldown: {remaining:.0f} sec (Level: {level})"
        try:
            profit_val = float(pos.get("profit", 0))
        except:
            profit_val = 0
        if profit_val > 0:
            alert_types.append("Profit")
            key = f"profit-{asset_full}-{position_type}-{position_id}"
            last_trigger = manager.last_triggered.get(key, 0)
            remaining = max(0, cooldown_seconds - (now - last_trigger))
            details["Profit Alert"] = f"Remaining cooldown: {remaining:.0f} sec"

        pos["alert_type"] = ", ".join(alert_types) if alert_types else "None"
        pos["alert_details"] = details

        latest_price = data_locker.get_latest_price(asset)
        pos["current_price"] = latest_price["current_price"] if latest_price else 0.0

        last_call = manager.last_call_triggered.get("all_alerts", 0)
        pos["call_refractory_remaining"] = max(0, call_refractory_seconds - (now - last_call))
        pos["configured_cooldown"] = cooldown_seconds
        pos["configured_call_refractory"] = call_refractory_seconds

    theme_config = current_app.config.get('theme', {})
    return render_template("alert_matrix.html",
                           theme=theme_config,
                           positions=positions)

@alerts_bp.route('/config', methods=['GET'], endpoint="alert_config_page")
def config_page():
    try:
        json_manager = current_app.json_manager
        config_data = json_manager.load("alert_limits.json", json_type=JsonType.ALERT_LIMITS)
        config_data = convert_types_in_dict(config_data)
    except Exception as e:
        op_logger = OperationsLogger(log_filename=os.path.join(os.getcwd(), "operations_log.txt"))
        op_logger.log("Alert Configuration Failed", source="System",
                      operation_type="Alert Configuration Failed",
                      file_name=str(ALERT_LIMITS_PATH))
        logger.error("Error loading alert limits: %s", str(e))
        return render_template("alert_limits.html", error_message="Error loading alert configuration."), 500

    alert_config = config_data.get("alert_ranges", {})
    price_alerts = alert_config.get("price_alerts", {})
    theme_config = config_data.get("theme_config", {})

    alert_cooldown_seconds = config_data.get("alert_cooldown_seconds", 900)
    call_refractory_period = config_data.get("call_refractory_period", 3600)

    return render_template("alert_limits.html",
                           alert_ranges=alert_config,
                           price_alerts=price_alerts,
                           theme=theme_config,
                           alert_cooldown_seconds=alert_cooldown_seconds,
                           call_refractory_period=call_refractory_period)

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
        merged_config = json_manager.deep_merge(current_config, nested_update)

        if "alert_cooldown_seconds" in merged_config and (merged_config["alert_cooldown_seconds"] == "" or merged_config["alert_cooldown_seconds"] is None):
            merged_config["alert_cooldown_seconds"] = 900
        if "call_refractory_period" in merged_config and (merged_config["call_refractory_period"] == "" or merged_config["call_refractory_period"] is None):
            merged_config["call_refractory_period"] = 1800

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


@alerts_bp.route('/matrix', methods=['GET'], endpoint="alert_matrix")
def alert_matrix():
    from data.data_locker import DataLocker
    from alerts.alert_controller import AlertController
    from sonic_labs.hedge_manager import HedgeManager  # Import HedgeManager to retrieve hedges

    # Set up theme configuration if not already set
    theme_config = current_app.config.get('theme')
    if not theme_config:
        theme_config = {
            "border_color": "#ccc",
            "card_header_color": "#007bff",
            "card_header_text_color": "#fff",
            "profiles": {},
            "selected_profile": ""
        }
        current_app.config['theme'] = theme_config

    # Retrieve alerts and positions
    data_locker = DataLocker.get_instance()
    alerts = data_locker.get_alerts()
    positions = data_locker.read_positions()

    # Update alerts with missing position_reference_id using positions data
    for alert in alerts:
        if not alert.get("position_reference_id"):
            for pos in positions:
                if pos.get("alert_reference_id") == alert.get("id"):
                    alert["position_reference_id"] = pos.get("id")
                    break

    # Retrieve hedges using HedgeManager
    hedge_manager = HedgeManager(positions)
    hedges = hedge_manager.get_hedges()

    # Load alert configuration ranges
    json_manager = current_app.json_manager
    alert_config = json_manager.load("alert_limits.json", json_type=JsonType.ALERT_LIMITS)
    alert_ranges = alert_config.get("alert_ranges", {})

    # Pass alerts, alert_ranges, and hedges to the template
    return render_template("alert_matrix.html",
                           theme=theme_config,
                           alerts=alerts,
                           alert_ranges=alert_ranges,
                           hedges=hedges)


if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(alerts_bp)
    app.json_manager = JsonManager()
    app.run(debug=True, port=5001)
