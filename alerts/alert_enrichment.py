import logging
from utils.json_manager import JsonManager, JsonType
from data.models import AlertType  # Import the model for consistent alert type values

def normalize_alert_type(alert: dict) -> dict:
    """
    Normalize the alert_type field in the alert dictionary.
    This function removes spaces and underscores, converts the string to upper case,
    and then maps various input variants to the standardized alert type values
    as defined in models.py.

    Valid standardized values:
      - PriceThreshold
      - DeltaChange
      - TravelPercent
      - Time
      - Profit
      - HeatIndex

    :param alert: Dictionary containing at least the "alert_type" key.
    :return: The alert dictionary with normalized "alert_type".
    :raises ValueError: if the alert does not contain an "alert_type".
    """
    from data.models import AlertType  # Ensure we have the standardized alert types

    if "alert_type" not in alert or not alert["alert_type"]:
        raise ValueError("Alert missing alert_type.")

    normalized = alert["alert_type"].upper().replace(" ", "").replace("_", "")

    if normalized in ["TRAVELPERCENT", "TRAVELPERCENTALERT", "TRAVELPERCENTLIQUID"]:
        normalized = AlertType.TRAVEL_PERCENT_LIQUID.value  # Expected to be "TravelPercent"
    elif normalized in ["PRICETHRESHOLD", "PRICETHRESHOLDALERT"]:
        normalized = AlertType.PRICE_THRESHOLD.value  # Expected to be "PriceThreshold"
    elif normalized in ["PROFITALERT"]:
        normalized = AlertType.PROFIT.value  # Expected to be "Profit"
    elif normalized in ["HEATINDEX", "HEATINDEXALERT"]:
        normalized = AlertType.HEAT_INDEX.value  # Expected to be "HeatIndex"
    elif normalized in ["DELTACHANGE"]:
        normalized = AlertType.DELTA_CHANGE.value  # Expected to be "DeltaChange"
    elif normalized in ["TIME"]:
        normalized = AlertType.TIME.value  # Expected to be "Time"
    else:
        normalized = alert["alert_type"]

    alert["alert_type"] = normalized
    return alert


def populate_evaluated_value_for_alert(alert: dict, data_locker, logger: logging.Logger) -> float:
    logger.debug("Exiting populate_evaluated_value_for_alert with evaluated_value: %f", 0.0)
    logger.debug("Entering populate_evaluated_value_for_alert with alert: %s", alert)
    evaluated_value = 0.0
    alert_type = alert.get("alert_type")
    logger.debug("Alert type: %s", alert_type)

    if alert_type == AlertType.PRICE_THRESHOLD.value:
        asset = alert.get("asset_type", "BTC")
        logger.debug("Processing PriceThreshold for asset: %s", asset)
        price_record = data_locker.get_latest_price(asset)
        if price_record:
            try:
                evaluated_value = float(price_record.get("current_price", 0.0))
                logger.debug("Parsed current_price: %f", evaluated_value)
            except Exception as e:
                logger.error("Error parsing current_price from price_record: %s", e, exc_info=True)
                evaluated_value = 0.0
        else:
            logger.debug("No price record found for asset: %s", asset)
            evaluated_value = 0.0

    elif alert_type == AlertType.TRAVEL_PERCENT_LIQUID.value:
        pos_id = alert.get("position_reference_id") or alert.get("id")
        logger.debug("Processing TravelPercent for position id: %s", pos_id)
        positions = data_locker.read_positions()
        position = next((p for p in positions if p.get("id") == pos_id), None)
        if position:
            try:
                evaluated_value = float(position.get("travel_percent", 0.0))
                logger.debug("Parsed travel_percent: %f", evaluated_value)
            except Exception as e:
                logger.error("Error parsing travel_percent: %s", e, exc_info=True)
                evaluated_value = 0.0
        else:
            logger.debug("No matching position found for id: %s", pos_id)
            evaluated_value = 0.0

    elif alert_type == AlertType.PROFIT.value:
        pos_id = alert.get("position_reference_id") or alert.get("id")
        logger.debug("Processing Profit for position id: %s", pos_id)
        positions = data_locker.read_positions()
        position = next((p for p in positions if p.get("id") == pos_id), None)
        if position:
            try:
                evaluated_value = float(position.get("pnl_after_fees_usd", 0.0))
                logger.debug("Parsed pnl_after_fees_usd: %f", evaluated_value)
            except Exception as e:
                logger.error("Error parsing pnl_after_fees_usd: %s", e, exc_info=True)
                evaluated_value = 0.0
        else:
            logger.debug("No matching position found for id: %s", pos_id)
            evaluated_value = 0.0

    elif alert_type == AlertType.HEAT_INDEX.value:
        pos_id = alert.get("position_reference_id") or alert.get("id")
        logger.debug("Processing HeatIndex for position id: %s", pos_id)
        positions = data_locker.read_positions()
        position = next((p for p in positions if p.get("id") == pos_id), None)
        if position:
            try:
                evaluated_value = float(position.get("current_heat_index", 0.0))
                logger.debug("Parsed current_heat_index: %f", evaluated_value)
            except Exception as e:
                logger.error("Error parsing current_heat_index: %s", e, exc_info=True)
                evaluated_value = 0.0
        else:
            logger.debug("No matching position found for id: %s", pos_id)
            evaluated_value = 0.0

    else:
        logger.debug("Alert type %s not recognized; defaulting evaluated_value to 0.0", alert_type)
        evaluated_value = 0.0

    logger.debug("Exiting populate_evaluated_value_for_alert with evaluated_value: %f", evaluated_value)
    return evaluated_value


def update_trigger_value_FUCK_ME(data_locker, config, logger, report_path="trigger_update_report.html"):
    """
    Update the trigger value for all travel percent alerts based on current alert levels.
    Writes a detailed HTML report of evaluations and prints debug info to console.
    Also logs all debug messages to trigger_fuck.txt.
    Returns the count of alerts updated.
    """

    def purple_print(message: str):
        PURPLE = "\033[95m"
        RESET = "\033[0m"
        full_msg = f"{PURPLE}{message}{RESET}"
        print(full_msg)
        with open("trigger_fuck.txt", "a", encoding="utf-8") as f:
            f.write(message + "\n")

    purple_print("------------------------------------------------------------------------>")
    alerts = data_locker.get_alerts()
    updated_count = 0
    report_lines = []
    report_lines.append("<html><head><title>Trigger Update Report</title></head><body>")
    report_lines.append("<h1>Trigger Update Report</h1>")
    report_lines.append("<table border='1' style='border-collapse: collapse;'>")
    report_lines.append("<tr>"
                        "<th>Alert ID</th>"
                        "<th>Type</th>"
                        "<th>Current Level</th>"
                        "<th>Old Trigger Value</th>"
                        "<th>New Trigger Value</th>"
                        "<th>Config Low</th>"
                        "<th>Config Medium</th>"
                        "<th>Config High</th>"
                        "</tr>")
    tp_config = config.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
    try:
        low_threshold = float(tp_config.get("low", -25.0))
        medium_threshold = float(tp_config.get("medium", -50.0))
        high_threshold = float(tp_config.get("high", -75.0))
    except Exception as e:
        logger.error("Error parsing travel percent thresholds: %s", e)
        low_threshold, medium_threshold, high_threshold = -25.0, -50.0, -75.0
    for alert in alerts:
        if alert.get("alert_type") == AlertType.TRAVEL_PERCENT_LIQUID.value:
            alert_id = alert.get("id")
            old_trigger = float(alert.get("trigger_value", 0.0))
            current_level = alert.get("level", "Normal")
            if current_level == "Normal":
                new_trigger = low_threshold
            elif current_level == "Low":
                new_trigger = medium_threshold
            elif current_level in ["Medium", "High"]:
                new_trigger = high_threshold
            else:
                new_trigger = old_trigger
            purple_print(
                f"[Before Save] Alert {alert_id}: type={alert.get('alert_type')}, level={current_level}, old trigger={old_trigger}, calculated new trigger={new_trigger}")
            logger.debug(
                f"[Before Save] Alert {alert_id}: type={alert.get('alert_type')}, level={current_level}, old trigger={old_trigger}, calculated new trigger={new_trigger}")
            if new_trigger != old_trigger:
                update_fields = {"trigger_value": new_trigger}
                try:
                    num_updated = data_locker.update_alert_conditions(alert_id, update_fields)
                    logger.info("Updated alert %s: new trigger value set to %s (rows affected: %s)", alert_id,
                                new_trigger, num_updated)
                    updated_alert = data_locker.get_alert(alert_id)
                    if updated_alert:
                        purple_print(
                            f"[After Save] Alert {alert_id}: trigger_value now {updated_alert.get('trigger_value')}")
                        logger.debug("Re-read alert %s: trigger_value now %s", alert_id,
                                     updated_alert.get("trigger_value"))
                        alert["trigger_value"] = float(updated_alert.get("trigger_value", 0.0))
                    updated_count += 1
                except Exception as e:
                    logger.error("Error updating alert %s: %s", alert_id, e)
            else:
                logger.debug("Alert %s trigger value remains unchanged.", alert_id)
            report_lines.append(
                f"<tr><td>{alert_id}</td><td>{alert.get('alert_type')}</td><td>{current_level}</td>"
                f"<td>{old_trigger}</td><td>{new_trigger}</td>"
                f"<td>{low_threshold}</td><td>{medium_threshold}</td><td>{high_threshold}</td></tr>"
            )
    report_lines.append("</table>")
    report_lines.append(f"<p>Total alerts updated: {updated_count}</p>")
    report_lines.append("</body></html>")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        logger.info("Trigger update report written to %s", report_path)
    except Exception as e:
        logger.error("Error writing trigger update report: %s", e)
    return updated_count


def log_level_debug(message: str):
    try:
        with open("level_rich.txt", "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception as e:
        print(f"Error writing to level_rich.txt: {e}")


def validate_alert_level(alert: dict, logger: logging.Logger) -> str:
    valid_levels = ["Normal", "Low", "Medium", "High"]
    current_level = alert.get("level", "Normal")
    current_level_normalized = current_level.capitalize()
    debug_message = f"Current level before validation: '{current_level}' (normalized to '{current_level_normalized}')"
    logger.debug(debug_message)
    log_level_debug(debug_message)
    if current_level_normalized not in valid_levels:
        warning_message = f"Level '{current_level_normalized}' is invalid. Defaulting to 'Normal'."
        logger.warning(warning_message)
        log_level_debug(warning_message)
        current_level_normalized = "Normal"
    else:
        debug_message = f"Level '{current_level_normalized}' is valid."
        logger.debug(debug_message)
        log_level_debug(debug_message)
    return current_level_normalized


import logging
from utils.json_manager import JsonManager, JsonType
from data.models import AlertType  # Import the model for consistent alert type values
from alerts.alert_enrichment import normalize_alert_type

import logging
from utils.json_manager import JsonManager, JsonType
from data.models import AlertType
#from alerts.alert_enrichment_helper import normalize_alert_type  # if you have a helper for normalization


def enrich_alert_data(alert: dict, data_locker, logger: logging.Logger, alert_controller) -> dict:
    """
    Enriches an alert dictionary with additional computed fields.

    Args:
        alert (dict): The alert dictionary to enrich.
        data_locker: Instance managing database interactions.
        logger (logging.Logger): Logger for debugging.
        alert_controller: The AlertController instance; used to instantiate AlertEvaluator.

    Returns:
        dict: The enriched alert dictionary.
    """
    logger.debug("=== Starting enrich_alert_data ===")
    logger.debug("Initial alert: %s", alert)

    try:
        # Normalize the alert type (this function should adjust alert["alert_type"] accordingly)
        alert = normalize_alert_type(alert)
        normalized_alert_type = alert.get("alert_type")
        logger.debug("Normalized alert_type: %s", normalized_alert_type)
    except ValueError as e:
        logger.error("Error normalizing alert type: %s", e)
        return alert

    # Enforce classification based on alert type.
    if normalized_alert_type in [AlertType.TRAVEL_PERCENT_LIQUID.value,
                                 AlertType.PROFIT.value,
                                 AlertType.HEAT_INDEX.value]:
        alert["alert_class"] = "Position"
        if not alert.get("position_reference_id"):
            logger.error("Position alert missing position_reference_id.")
    elif normalized_alert_type == AlertType.PRICE_THRESHOLD.value:
        alert["alert_class"] = "Market"
    else:
        logger.error("Unrecognized alert type: %s", alert["alert_type"])

    # Load configuration (alert_limits).
    jm = JsonManager()
    alert_limits = jm.load("", JsonType.ALERT_LIMITS)
    logger.debug("Loaded alert_limits: %s", alert_limits)

    # For price alerts: adjust notification type, trigger, and condition if applicable.
    if alert["alert_type"] == AlertType.PRICE_THRESHOLD.value:
        asset = alert.get("asset_type", "BTC")
        asset_config = alert_limits.get("alert_ranges", {}).get("price_alerts", {}).get(asset, {})
        logger.debug("Asset config for %s: %s", asset, asset_config)
        if asset_config:
            notifications = asset_config.get("notifications", {})
            alert["notification_type"] = "Call" if notifications.get("call", False) else "Email"
            if float(alert.get("trigger_value", 0.0)) == 0.0:
                alert["trigger_value"] = float(asset_config.get("trigger_value", 0.0))
            alert["condition"] = asset_config.get("condition", alert.get("condition", "ABOVE"))
        else:
            logger.error("No configuration found for price alert asset %s.", asset)
            alert["notification_type"] = "Email"

    elif alert["alert_type"] == AlertType.TRAVEL_PERCENT_LIQUID.value:
        config = alert_limits.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
        logger.debug("Travel alert config: %s", config)
        if config.get("enabled", False):
            updated_alert = data_locker.get_alert(alert.get("id"))
            if updated_alert:
                alert["trigger_value"] = updated_alert.get("trigger_value")
                logger.debug("Updated trigger_value fetched from DB: %s", alert["trigger_value"])
            else:
                alert["trigger_value"] = float(config.get("low", -25.0))
                logger.debug("Fallback trigger_value from config: %s", alert["trigger_value"])
            alert["condition"] = "BELOW"
        if not alert.get("notification_type"):
            alert["notification_type"] = "Email"
        if alert.get("position_reference_id"):
            positions = data_locker.read_positions()
            logger.debug("Retrieved positions from DB: %s", positions)
            position = next((p for p in positions if p.get("id") == alert.get("position_reference_id")), None)
            if position:
                # Import AlertEvaluator locally to avoid circular import.
                from alerts.alert_evaluator import AlertEvaluator
                evaluator = AlertEvaluator(alert_limits, data_locker, alert_controller)
                logger.debug("AlertEvaluator instantiated successfully with alert_controller reference.")
                level, current_val = evaluator.evaluate_travel_alert(position)
                updated_alert = data_locker.get_alert(alert.get("id"))
                if updated_alert:
                    alert["trigger_value"] = updated_alert.get("trigger_value")
                    logger.debug("Alert trigger value updated via evaluator: %s", alert["trigger_value"])
                else:
                    alert["trigger_value"] = current_val
                    logger.debug("Alert trigger value set to evaluator's computed value: %s", alert["trigger_value"])
            else:
                logger.error("Cannot enrich trigger value: no position found for id %s",
                             alert.get("position_reference_id"))

    elif alert["alert_type"] == AlertType.PROFIT.value:
        config = alert_limits.get("alert_ranges", {}).get("profit_ranges", {})
        logger.debug("Profit alert config: %s", config)
        if config.get("enabled", False):
            if float(alert.get("trigger_value", 0.0)) == 0.0:
                alert["trigger_value"] = float(config.get("low", 22.0))
            alert["condition"] = config.get("condition", "ABOVE")
        if not alert.get("notification_type"):
            alert["notification_type"] = "Email"

    elif alert["alert_type"] == AlertType.HEAT_INDEX.value:
        config = alert_limits.get("alert_ranges", {}).get("heat_index_ranges", {})
        logger.debug("Heat index alert config: %s", config)
        if config.get("enabled", False):
            if float(alert.get("trigger_value", 0.0)) == 0.0:
                alert["trigger_value"] = float(config.get("low", 12.0))
            alert["condition"] = config.get("condition", "ABOVE")
        if not alert.get("notification_type"):
            alert["notification_type"] = "Email"
    else:
        if not alert.get("notification_type"):
            alert["notification_type"] = "Email"

    if alert.get("alert_class") == "Position":
        pos_id = alert.get("position_reference_id")
        logger.debug("For Position alert, pos_id: %s", pos_id)
        if pos_id:
            positions = data_locker.read_positions()
            logger.debug("Retrieved positions from DB: %s", positions)
            position = next((p for p in positions if p.get("id") == pos_id), None)
            if position:
                alert["liquidation_distance"] = position.get("liquidation_distance", 0.0)
                alert["liquidation_price"] = position.get("liquidation_price", 0.0)
                alert["travel_percent"] = position.get("travel_percent", 0.0)
                logger.debug("Enriched alert %s with position data: %s", alert.get("id"), position)
            else:
                logger.error("No position found for id %s during enrichment.", pos_id)
        else:
            logger.error("Position alert missing position_reference_id during enrichment.")

    # Populate evaluated_value using a helper function.
    from alerts.alert_enrichment import populate_evaluated_value_for_alert
    alert["evaluated_value"] = populate_evaluated_value_for_alert(alert, data_locker, logger)
    logger.debug("After populating evaluated value: %s", alert)

    def validate_level(level_str: str) -> str:
        valid_levels = ["Normal", "Low", "Medium", "High"]
        norm = level_str.capitalize()
        if norm not in valid_levels:
            logger.warning("Invalid level '%s'; defaulting to 'Normal'.", norm)
            return "Normal"
        return norm

    current_level_normalized = validate_level(alert.get("level", "Normal"))
    logger.debug("Final validated level: %s", current_level_normalized)
    alert["level"] = current_level_normalized

    update_fields = {
        "liquidation_distance": alert.get("liquidation_distance", 0.0),
        "liquidation_price": alert.get("liquidation_price", 0.0),
        "travel_percent": alert.get("travel_percent", 0.0),
        "evaluated_value": alert.get("evaluated_value", 0.0),
        "notification_type": alert.get("notification_type"),
        "trigger_value": alert.get("trigger_value"),
        "condition": alert.get("condition"),
        "level": current_level_normalized
    }
    logger.debug("Final update_fields to persist: %s", update_fields)

    try:
        num_updated = data_locker.update_alert_conditions(alert["id"], update_fields)
        logger.info("Exiting enrich_alert_data: Persisted enriched alert %s to database, rows updated: %s",
                    alert["id"], num_updated)
    except Exception as e:
        logger.error("Error persisting enriched alert %s: %s", alert["id"], e, exc_info=True)

    logger.debug("=== Finished enrich_alert_data ===")
    return alert

