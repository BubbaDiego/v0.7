#!/usr/bin/env python
"""
dashboard_bp.py
Description:
    Flask blueprint for all dashboard-specific routes and API endpoints.
    This includes:
      - The index route.
      - The main dashboard view.
      - Theme options.
      - API endpoints for chart data (size_composition, value_composition, collateral_composition, size_balance).
      - Backend support for persisting strategy performance card data.
Usage:
    Import and register this blueprint in your main application.
"""

import json
import logging
import sqlite3
import pytz
from datetime import datetime, timedelta
import os

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from config.config_constants import DB_PATH, CONFIG_PATH, BASE_DIR, THEME_CONFIG_PATH
from data.data_locker import DataLocker
from positions.position_service import PositionService
from utils.calc_services import CalcServices
from utils.unified_logger import UnifiedLogger


# Import UnifiedLogViewer to handle both operational and alert logs.
from utils.unified_log_viewer import UnifiedLogViewer

logger = logging.getLogger("DashboardBlueprint")
logger.setLevel(logging.CRITICAL)

dashboard_bp = Blueprint("dashboard", __name__, template_folder="templates")


def get_strategy_performance():
    dl = DataLocker.get_instance()
    portfolio_history = dl.get_portfolio_history() or []
    if portfolio_history:
        start_entry = portfolio_history[0]
        current_entry = portfolio_history[-1]
        try:
            start_value = float(start_entry.get("total_value", 0))
        except Exception:
            start_value = 0
        try:
            current_value = float(current_entry.get("total_value", 0))
        except Exception:
            current_value = 0
        description = "Strategy performance since reset"
        start_date = start_entry.get("snapshot_time", "N/A")
        diff = current_value - start_value
        percent_change = (diff / start_value * 100) if start_value != 0 else 0
        return {
            "description": description,
            "start_date": start_date,
            "start_value": start_value,
            "current_value": current_value,
            "diff": diff,
            "percent_change": percent_change
        }
    else:
        return {
            "description": "No performance data available",
            "start_date": "N/A",
            "start_value": 0,
            "current_value": 0,
            "diff": 0,
            "percent_change": 0
        }


# Helper: Convert ISO timestamp to PST formatted string.
def _convert_iso_to_pst(iso_str):
    if not iso_str or iso_str == "N/A":
        return "N/A"
    try:
        dt_obj = datetime.fromisoformat(iso_str)
        pst = pytz.timezone("US/Pacific")
        if dt_obj.tzinfo is None:
            dt_obj = pst.localize(dt_obj)
        dt_pst = dt_obj.astimezone(pst)
        return dt_pst.strftime("%m/%d/%Y %I:%M:%S %p %Z")
    except Exception as e:
        logger.error(f"Error converting timestamp: {e}")
        return "N/A"


# Helper: Compute Size Composition.
def compute_size_composition():
    positions = PositionService.get_all_positions(DB_PATH) or []
    long_total = sum(float(p.get("size", 0)) for p in positions if p.get("position_type", "").upper() == "LONG")
    short_total = sum(float(p.get("size", 0)) for p in positions if p.get("position_type", "").upper() == "SHORT")
    total = long_total + short_total
    if total > 0:
        series = [round(long_total / total * 100), round(short_total / total * 100)]
    else:
        series = [0, 0]
    return series


# Helper: Compute Value Composition.
def compute_value_composition():
    positions = PositionService.get_all_positions(DB_PATH) or []
    long_total = 0.0
    short_total = 0.0
    for p in positions:
        try:
            entry_price = float(p.get("entry_price", 0))
            current_price = float(p.get("current_price", 0))
            collateral = float(p.get("collateral", 0))
            size = float(p.get("size", 0))
            if entry_price > 0:
                token_count = size / entry_price
                if p.get("position_type", "").upper() == "LONG":
                    pnl = (current_price - entry_price) * token_count
                else:
                    pnl = (entry_price - current_price) * token_count
            else:
                pnl = 0.0
            value = collateral + pnl
        except Exception as calc_err:
            logger.error(f"Error calculating value for position {p.get('id', 'unknown')}: {calc_err}", exc_info=True)
            value = 0.0
        if p.get("position_type", "").upper() == "LONG":
            long_total += value
        elif p.get("position_type", "").upper() == "SHORT":
            short_total += value
    total = long_total + short_total
    if total > 0:
        series = [round(long_total / total * 100), round(short_total / total * 100)]
    else:
        series = [0, 0]
    return series


# Helper: Compute Collateral Composition.
def compute_collateral_composition():
    positions = PositionService.get_all_positions(DB_PATH) or []
    long_total = sum(float(p.get("collateral", 0)) for p in positions if p.get("position_type", "").upper() == "LONG")
    short_total = sum(float(p.get("collateral", 0)) for p in positions if p.get("position_type", "").upper() == "SHORT")
    total = long_total + short_total
    if total > 0:
        series = [round(long_total / total * 100), round(short_total / total * 100)]
    else:
        series = [0, 0]
    return series


@dashboard_bp.route("/dashboard")
def dashboard():
    try:
        all_positions = PositionService.get_all_positions(DB_PATH) or []
        positions = all_positions
        liquidation_positions = all_positions
        top_positions = sorted(all_positions, key=lambda pos: float(pos.get("current_travel_percent", 0)), reverse=True)
        bottom_positions = sorted(all_positions, key=lambda pos: float(pos.get("current_travel_percent", 0)))[:3]

        totals = {
            "total_collateral": sum(float(pos.get("collateral", 0)) for pos in positions),
            "total_value": sum(float(pos.get("value", 0)) for pos in positions),
            "total_size": sum(float(pos.get("size", 0)) for pos in positions)
        }
        if positions:
            totals["avg_leverage"] = sum(float(pos.get("leverage", 0)) for pos in positions) / len(positions)
            totals["avg_travel_percent"] = sum(float(pos.get("current_travel_percent", 0)) for pos in positions) / len(positions)
        else:
            totals["avg_leverage"] = 0
            totals["avg_travel_percent"] = 0

        dl = DataLocker.get_instance()
        portfolio_history = dl.get_portfolio_history() or []
        portfolio_value_num = portfolio_history[-1].get("total_value", 0) if portfolio_history else 0
        portfolio_change = 0
        if portfolio_history:
            cutoff = datetime.now() - timedelta(hours=24)
            filtered_history = [
                entry for entry in portfolio_history
                if entry.get("snapshot_time") and datetime.fromisoformat(entry.get("snapshot_time")) >= cutoff
            ]
            first_val = filtered_history[0].get("total_value", 0) if filtered_history else portfolio_history[0].get("total_value", 0)
            if first_val:
                portfolio_change = ((portfolio_history[-1].get("total_value", 0) - first_val) / first_val) * 100

        formatted_portfolio_value = "{:,.2f}".format(portfolio_value_num)
        formatted_portfolio_change = "{:,.1f}".format(portfolio_change)

        btc_data = dl.get_latest_price("BTC") or {}
        eth_data = dl.get_latest_price("ETH") or {}
        sol_data = dl.get_latest_price("SOL") or {}
        sp500_data = dl.get_latest_price("SP500") or {}

        formatted_btc_price = "{:,.2f}".format(float(btc_data.get("current_price", 0)))
        formatted_eth_price = "{:,.2f}".format(float(eth_data.get("current_price", 0)))
        formatted_sol_price = "{:,.2f}".format(float(sol_data.get("current_price", 0)))
        formatted_sp500_value = "{:,.2f}".format(float(sp500_data.get("current_price", 0)))

        strategy_performance = get_strategy_performance()

        update_times = dl.get_last_update_times() or {}
        raw_last_update = update_times.get("last_update_time_positions")
        last_update_positions_source = update_times.get("last_update_positions_source", "N/A")
        if raw_last_update:
            converted_last_update = _convert_iso_to_pst(raw_last_update)
            if converted_last_update != "N/A":
                try:
                    dt_obj = datetime.strptime(converted_last_update, "%m/%d/%Y %I:%M:%S %p %Z")
                    last_update_time_only = dt_obj.strftime("%I:%M %p %Z").lstrip("0")
                    last_update_date_only = f"{dt_obj.month}/{dt_obj.day}/{dt_obj.strftime('%y')}"
                except Exception as ex:
                    last_update_time_only = "N/A"
                    last_update_date_only = "N/A"
            else:
                last_update_time_only = "N/A"
                last_update_date_only = "N/A"
        else:
            last_update_time_only = "N/A"
            last_update_date_only = "N/A"

        # Read log files using UnifiedLogViewer for both operational and alert logs.
        operations_log_file = os.path.join(str(BASE_DIR), "operations_log.txt")
        alert_log_file = os.path.join(str(BASE_DIR), "alert_monitor_log.txt")
        ops_viewer = UnifiedLogViewer([operations_log_file])
        system_feed_entries = ops_viewer.get_all_display_strings()
        alert_viewer = UnifiedLogViewer([alert_log_file])
        alert_entries = alert_viewer.get_all_display_strings()

        # Load the theme configuration freshly from file
        with open(THEME_CONFIG_PATH, "r", encoding="utf-8") as f:
            theme_config = json.load(f)
        logger.debug(f"Loaded theme config: {theme_config}")

        return render_template(
            "dashboard.html",
            theme=theme_config,  # Pass the theme config here!
            top_positions=top_positions,
            bottom_positions=bottom_positions,
            liquidation_positions=liquidation_positions,
            portfolio_data=portfolio_history,
            portfolio_value=formatted_portfolio_value,
            portfolio_change=formatted_portfolio_change,
            btc_price=formatted_btc_price,
            eth_price=formatted_eth_price,
            sol_price=formatted_sol_price,
            sp500_value=formatted_sp500_value,
            positions=positions,
            totals=totals,
            last_update_time_only=last_update_time_only,
            last_update_date_only=last_update_date_only,
            last_update_positions_source=last_update_positions_source,
            system_feed_entries=system_feed_entries,
            alert_entries=alert_entries,
            strategy_performance=strategy_performance
        )
    except Exception as e:
        logger.exception("Error rendering dashboard:")
        return render_template(
            "dashboard.html",
            theme={},  # Ensure theme is at least an empty dict to avoid template errors
            top_positions=[],
            bottom_positions=[],
            liquidation_positions=[],
            portfolio_data=[],
            portfolio_value="0.00",
            portfolio_change="0.0",
            btc_price="0.00",
            eth_price="0.00",
            sol_price="0.00",
            sp500_value="0.00",
            positions=[],
            totals={},
            last_update_time_only="N/A",
            last_update_date_only="N/A",
            last_update_positions_source="N/A",
            system_feed_entries='<div class="alert alert-secondary p-1 mb-1" role="alert">No feed data available</div>',
            alert_entries='<div class="alert alert-secondary p-1 mb-1" role="alert">No alert data available</div>'
        )


@dashboard_bp.route("/dash_performance")
def dash_performance():
    portfolio_data = DataLocker.get_instance().get_portfolio_history() or []
    return render_template("dash_performance.html", portfolio_data=portfolio_data)


# -------------------------------
# API Endpoints for Chart Data
# -------------------------------
@dashboard_bp.route("/api/size_composition")
def api_size_composition():
    try:
        series = compute_size_composition()
        return jsonify({"series": series})
    except Exception as e:
        logger.error(f"Error in api_size_composition: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/value_composition")
def api_value_composition():
    try:
        series = compute_value_composition()
        return jsonify({"series": series})
    except Exception as e:
        logger.error(f"Error in api_value_composition: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/size_balance")
def api_size_balance():
    try:
        positions = PositionService.get_all_positions(DB_PATH) or []
        groups = {}
        for pos in positions:
            wallet = pos.get("wallet", "ObiVault")
            asset = pos.get("asset_type", "BTC").upper()
            if asset not in ["BTC", "ETH", "SOL"]:
                continue
            if wallet not in ["ObiVault", "R2Vault"]:
                wallet = "ObiVault"
            key = (wallet, asset)
            if key not in groups:
                groups[key] = {"long": 0, "short": 0}
            try:
                size = float(pos.get("size", 0))
            except Exception:
                size = 0
            position_type = pos.get("position_type", "").upper()
            if position_type == "LONG":
                groups[key]["long"] += size
            elif position_type == "SHORT":
                groups[key]["short"] += size

        groups_list = []
        for (wallet, asset), values in groups.items():
            total = values["long"] + values["short"]
            if total > 0:
                groups_list.append({
                    "wallet": wallet,
                    "asset": asset,
                    "long": values["long"],
                    "short": values["short"],
                    "total": total
                })

        return jsonify({"groups": groups_list})
    except Exception as e:
        logger.error(f"Error in api_size_balance: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/collateral_composition")
def api_collateral_composition():
    try:
        series = compute_collateral_composition()
        return jsonify({"series": series})
    except Exception as e:
        logger.error(f"Error in api_collateral_composition: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/save_theme", methods=["POST"], endpoint="save_theme_route")
def save_theme_route():
    try:
        data = request.get_json() or {}
        # read the existing config
        with open(THEME_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        # only update selected_profile
        if 'selected_profile' in data:
            config['selected_profile'] = data['selected_profile']

        # now save the updated config
        with open(THEME_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        return jsonify({"success": True})
    except Exception as e:
        current_app.logger.error("Error saving theme: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/theme_setup", methods=["GET"])
def theme_setup():
    try:
        with open(THEME_CONFIG_PATH, "r", encoding="utf-8") as f:
            theme_config = json.load(f)
        return render_template("theme_config.html", theme=theme_config)
    except Exception as e:
        logger.error("Error loading theme configuration in theme_setup", exc_info=True)
        return render_template("theme_config.html", theme={})



@dashboard_bp.route("/theme_config", methods=["GET"])
def theme_config_page():
    try:
        from utils.json_manager import JsonManager, JsonType
        json_manager = JsonManager(logger=logger)
        theme_config = json_manager.load(THEME_CONFIG_PATH, json_type=JsonType.THEME_CONFIG)
        return render_template("theme_config.html", theme=theme_config)
    except Exception as e:
        logger.error("Error loading theme configuration", exc_info=True)
        return render_template("theme_config.html", theme={})



# -------------------------------
# NEW: Route for Updating Strategy Performance Data Persistence
# -------------------------------
@dashboard_bp.route("/update_performance_data", methods=["POST"])
def update_performance_data():
    """
    Expects JSON payload with:
      - strategy_start_value (float)
      - strategy_description (string)
    Persists these values in the system_vars table.
    """
    try:
        data = request.get_json() or {}
        start_value = float(data.get("strategy_start_value", 0))
        description = data.get("strategy_description", "")
        dl = DataLocker.get_instance()
        dl.set_strategy_performance_data(start_value, description)
        return jsonify({"success": True, "message": "Performance data updated."})
    except Exception as e:
        logger.exception("Error updating performance data:")
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/api/asset_percent_changes")
def api_asset_percent_changes():
    try:
        hours = int(request.args.get("hours", 24))
        factor = 24 / hours
        asset_changes = {
            "BTC": 2.34 * factor,
            "ETH": -1.23 * factor,
            "SOL": 0.56 * factor,
            "SP500": -4.23 * factor
        }
        return jsonify(asset_changes)
    except Exception as e:
        logger.error(f"Error in api_asset_percent_changes: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
