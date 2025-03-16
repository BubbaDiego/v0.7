# sonic_labs_bp.py

from flask import Blueprint, render_template, jsonify, current_app, request
import json
from positions.position_service import PositionService
from config.config_constants import DB_PATH, THEME_CONFIG_PATH
from utils.json_manager import JsonType

sonic_labs_bp = Blueprint("sonic_labs", __name__, template_folder="templates")

@sonic_labs_bp.route("/hedge_calculator", methods=["GET"])
def hedge_calculator():
    try:
        positions = PositionService.get_all_positions(DB_PATH)
        long_positions = [p for p in positions if p.get("position_type", "").upper() == "LONG"]
        short_positions = [p for p in positions if p.get("position_type", "").upper() == "SHORT"]

        with open(THEME_CONFIG_PATH, "r", encoding="utf-8") as f:
            theme_config = json.load(f)

        # Use the JsonManager instance from the app
        json_manager = current_app.json_manager
        modifiers = json_manager.load("sonic_sauce.json", json_type=JsonType.SONIC_SAUCE)

        return render_template("hedge_calculator.html",
                               theme=theme_config,
                               long_positions=long_positions,
                               short_positions=short_positions,
                               modifiers=modifiers)
    except Exception as e:
        current_app.logger.error(f"Error rendering Hedge Calculator: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@sonic_labs_bp.route("/sonic_sauce", methods=["GET"])
def get_sonic_sauce():
    try:
        json_manager = current_app.json_manager
        modifiers = json_manager.load("sonic_sauce.json", json_type=JsonType.SONIC_SAUCE)
        return jsonify(modifiers), 200
    except Exception as e:
        current_app.logger.error(f"Error loading sonic sauce: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@sonic_labs_bp.route("/sonic_sauce", methods=["POST"])
def update_sonic_sauce():
    try:
        data = request.get_json()
        json_manager = current_app.json_manager
        json_manager.save("sonic_sauce.json", data, json_type=JsonType.SONIC_SAUCE)
        return jsonify({"success": True}), 200
    except Exception as e:
        current_app.logger.error(f"Error saving sonic sauce: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
