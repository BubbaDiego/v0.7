import logging
from utils.json_manager import JsonManager, JsonType
from data.models import AlertType  # Import the model for consistent alert type values


def normalize_alert_type(alert: dict) -> dict:
    if "alert_type" not in alert or not alert["alert_type"]:
        raise ValueError("Alert missing alert_type.")

    # Remove spaces and underscores and convert to upper case for normalization.
    normalized = alert["alert_type"].upper().replace(" ", "").replace("_", "")

    # Map various input variants to the model's standardized values.
    if normalized in ["TRAVELPERCENTALERT", "TRAVELPERCENTLIQUID"]:
        normalized = AlertType.TRAVEL_PERCENT_LIQUID.value  # "TravelPercent"
    elif normalized == "PRICETHRESHOLD":
        normalized = AlertType.PRICE_THRESHOLD.value         # "PriceThreshold"
    elif normalized == "PROFITALERT":
        normalized = AlertType.PROFIT.value                    # "Profit"
    elif normalized == "HEATINDEXALERT":
        normalized = AlertType.HEAT_INDEX.value                # "HeatIndex"
    else:
        # For any other alert type, assume it's already standardized.
        # You may choose to add additional normalization here if needed.
        normalized = alert["alert_type"]

    alert["alert_type"] = normalized
    return alert


def populate_evaluated_value_for_alert(alert: dict, data_locker, logger: logging.Logger) -> float:
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


def enrich_alert_data(alert: dict, data_locker, logger: 'logging.Logger') -> dict:
    logger.debug("Starting enrich_alert_data with alert: %s", alert)
    try:
        # Normalize alert type using our new function.
        alert = normalize_alert_type(alert)
    except ValueError as e:
        logger.error("Error normalizing alert type: %s", e)
        return alert

    # Set alert class based on normalized type.
    if alert["alert_type"] in [AlertType.TRAVEL_PERCENT_LIQUID.value, AlertType.PROFIT.value, AlertType.HEAT_INDEX.value]:
        alert["alert_class"] = "Position"
        if not alert.get("position_reference_id"):
            logger.error("Position alert missing position_reference_id.")
    elif alert["alert_type"] == AlertType.PRICE_THRESHOLD.value:
        alert["alert_class"] = "Market"
    else:
        logger.error("Unrecognized alert type: %s", alert["alert_type"])

    # Load alert limits configuration.
    jm = JsonManager()
    alert_limits = jm.load("", JsonType.ALERT_LIMITS)
    logger.debug("Loaded alert_limits: %s", alert_limits)

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
            if float(alert.get("trigger_value", 0.0)) == 0.0:
                alert["trigger_value"] = float(config.get("low", -4.0))
            alert["condition"] = "BELOW"
        if not alert.get("notification_type"):
            alert["notification_type"] = "Email"
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

    # For position alerts, enrich with additional position data.
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
    alert["evaluated_value"] = populate_evaluated_value_for_alert(alert, data_locker, logger)
    logger.debug("After populating evaluated value: %s", alert)

    valid_states = ["Normal", "Low", "Medium", "High", "Triggered", "Liquidated"]
    current_state = alert.get("state", "Normal")
    current_state_normalized = current_state.capitalize()
    logger.debug("Current state before validation: '%s' (normalized to '%s')", current_state, current_state_normalized)
    if current_state_normalized not in valid_states:
        logger.warning("State '%s' is invalid. Defaulting to 'Normal'.", current_state_normalized)
        current_state_normalized = "Normal"
    else:
        logger.debug("State '%s' is valid.", current_state_normalized)

    update_fields = {
        "liquidation_distance": alert.get("liquidation_distance", 0.0),
        "liquidation_price": alert.get("liquidation_price", 0.0),
        "travel_percent": alert.get("travel_percent", 0.0),
        "evaluated_value": alert.get("evaluated_value", 0.0),
        "notification_type": alert.get("notification_type"),
        "trigger_value": alert.get("trigger_value"),
        "condition": alert.get("condition"),
        "state": current_state_normalized
    }
    logger.debug("Final update_fields to persist: %s", update_fields)

    try:
        num_updated = data_locker.update_alert_conditions(alert["id"], update_fields)
        logger.info("Persisted enriched alert %s to database, rows updated: %s", alert["id"], num_updated)
    except Exception as e:
        logger.error("Error persisting enriched alert %s: %s", alert["id"], e, exc_info=True)
    return alert
