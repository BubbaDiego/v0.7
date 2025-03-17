
Sonic Alert Subsystem Specification
Version: 1.0
Date: 2025-03-17

Table of Contents
Overview
Architecture
Module Descriptions
Alert Manager
Alerts Blueprint
Heartbeat & Monitoring
Calculation Services
JSON Manager
Detailed Design: Direct Alert Classes and Methods
Configuration and Dependencies
Error Handling, Logging & Notifications
Integration Points & Future Enhancements
Overview
The Sonic subsystem is built to monitor positions, calculate key risk and performance metrics, and trigger alerts when conditions are met. It aggregates data from a database, evaluates thresholds defined in JSON configuration files, and uses external services (e.g., Twilio) for notifications. A web interface via Flask also allows viewing and updating alert configurations.

Architecture
The subsystem comprises several tightly integrated modules:

Alert Manager: The core engine that periodically polls data, checks multiple alert conditions, and manages notifications.
Alerts Blueprint: A Flask-based web interface for viewing alerts and managing alert configurations.
Heartbeat & Monitoring: Scripts (like the watchdog den_mother and sonic_monitor) that ensure the system’s continuous operation and update a heartbeat file.
Calculation Services: A collection of functions for computing risk indices, profit classifications, travel percentages, and other position metrics.
JSON Manager: Manages loading and saving various configuration files (alert limits, themes, etc.).
Module Descriptions
Alert Manager
File: alert_manager.py

Purpose:
Central component responsible for:

Polling positions from the database.
Evaluating alert conditions (profit, travel percent liquid, swing, blast, and price alerts).
Triggering notifications via Twilio and logging alert events.
Key Attributes:

db_path: SQLite DB path.
poll_interval: Interval (seconds) between alert checks.
config: System configuration (thresholds, notification settings).
twilio_config: Contains Twilio credentials and phone numbers.
cooldown & call_refractory_period: Time controls to avoid duplicate alerts.
Tracking dictionaries: last_triggered, last_profit, last_call_triggered.
Key Methods:

__init__(...): Initializes dependencies, loads configuration, and sets internal state.
reload_config(): Refreshes the configuration from file/DB.
run(): Main loop that continuously calls check_alerts().
check_alerts(source: Optional[str]): Aggregates alerts from different checks and triggers notifications.
Direct Alert Methods:
check_profit(pos: dict) -> str: Checks profit against configured thresholds.
check_travel_percent_liquid(pos: dict) -> str: Monitors travel percent thresholds (liquid alerts).
check_swing_alert(pos: dict) -> str: Evaluates swing-based alerts using hardcoded thresholds.
check_blast_alert(pos: dict) -> str: Evaluates blast conditions.
check_price_alerts() -> List[str]: Iterates over assets (BTC, ETH, SOL) to trigger price alerts.
handle_price_alert_trigger_config(asset: str, current_price: float, trigger_val: float, condition: str) -> str: Applies cooldown and logging for price alerts.
send_call(body: str, key: str): Sends out a notification call via Twilio after verifying the refractory period.
Utility Methods:
load_json_config(json_path: str) -> dict and save_config(config: dict, json_path: str): For managing configuration files.
debug_price_alert_details(...): Logs detailed HTML debug info for price alerts.
External Function:

trigger_twilio_flow(custom_message: str, twilio_config: dict) -> str:
Triggers a Twilio Studio Flow to send a call notification, ensuring all required Twilio parameters are present.
Alerts Blueprint
File: alerts_bp.py

Purpose:
Provides a Flask blueprint to handle web endpoints for:
Viewing active alerts (alarm viewer).
Displaying and updating alert configuration.
Key Components:
Endpoints:
/alerts/viewer: Renders an HTML page with current position alerts.
/alerts/config: Displays the alert configuration page for adjustments.
/alerts/update_config: Accepts POST requests to update configuration using a nested form parser.
Utility Functions:
deep_merge(source: dict, updates: dict) -> dict: Recursively merges dictionaries.
convert_types_in_dict(d): Converts string form values to their proper types.
parse_nested_form(form: dict) -> dict: Transforms flat form data into nested JSON structures.
format_alert_config_table(alert_ranges: dict) -> str: Generates an HTML table for configuration display.
Heartbeat & Monitoring
Files: den_mother.py and sonic_monitor.py

Den Mother (den_mother.py):

Purpose:
Acts as a watchdog that reads a heartbeat file. If the heartbeat timestamp is stale (beyond a set threshold), it triggers notifications (using Twilio) to alert about a potential system failure.
Key Function:
check_heartbeat(): Parses the heartbeat file, compares the timestamp against the current time, and triggers alerts if the heartbeat is too old.
Sonic Monitor (sonic_monitor.py):

Purpose:
Runs continuously to:
Call an update endpoint to refresh positions.
Write the current UTC timestamp to the heartbeat file.
Log each loop iteration and update.
Key Function:
main(): Executes the monitoring loop, calling call_update_jupiter() and write_heartbeat() periodically.
Calculation Services
File: calc_services.py

Purpose:
Provides all aggregator and analytics functions for positions:

Calculating composite risk indices.
Determining travel percent (both with and without profit anchors).
Computing profit alert classes.
Calculating liquidation distance, heat index, and leverage.
Prepares position data for display with additional metrics (e.g., color coding based on thresholds).
Key Methods:

calculate_composite_risk_index(position: dict) -> Optional[float]
calculate_travel_percent(position_type: str, entry_price: float, current_price: float, liquidation_price: float) -> float
get_profit_alert_class(profit, low_thresh, med_thresh, high_thresh): Static method to assign an alert class.
aggregator_positions(positions: List[dict], db_path: str) -> List[dict]: Updates and persists calculated metrics.
calculate_liquid_distance(current_price: float, liquidation_price: float) -> float
calculate_heat_index(position: dict) -> Optional[float]
prepare_positions_for_display(positions: List[dict]) -> List[dict]
Additional helper methods for slider values and color coding.
JSON Manager
File: json_manager.py

Purpose:
Handles reading and writing of JSON configuration files, ensuring that configuration for alert limits, themes, and other settings is managed consistently.

Key Components:

JsonType (Enum):
Defines types like ALERT_LIMITS, THEME_CONFIG, SONIC_SAUCE, etc., which map to file paths.
JsonManager Class:
load(file_path: str, json_type: JsonType = None): Loads a JSON file and performs optional verification.
save(file_path: str, data, json_type: JsonType = None): Saves the JSON data back to the file with logging of the operation.
Detailed Design: Direct Alert Classes and Methods
The core alert functionality is encapsulated in the AlertManager class. Below is an in‑depth look at its direct alert methods:

trigger_twilio_flow(custom_message: str, twilio_config: dict) -> str
Functionality:
Initiates a Twilio Studio Flow call using the provided message and configuration. Ensures that all Twilio parameters (account SID, auth token, flow SID, to/from phone numbers) are available.
Output: Returns the Twilio execution SID.
check_profit(pos: dict) -> str
Functionality:
Converts the profit value from the position to a float.
Compares it against thresholds defined in the configuration (low, medium, high).
Uses internal tracking (e.g., last_profit, last_triggered) to manage cooldowns.
Output: Returns a formatted alert string if the profit condition is met, otherwise returns an empty string.
check_travel_percent_liquid(pos: dict) -> str
Functionality:
Validates and converts the travel percentage.
Compares the value against negative thresholds configured in alert_ranges.
Determines the alert level (Low, Medium, High) and checks if the corresponding notifications (call, SMS, email) are enabled.
Suppresses the alert if within the cooldown period.
Output: Returns a detailed alert message or an empty string if no alert is triggered.
check_swing_alert(pos: dict) -> str and check_blast_alert(pos: dict) -> str
Functionality:
Evaluates whether the current position’s swing or blast metrics exceed hardcoded or configured thresholds.
Checks for cooldown conditions and whether notifications are enabled.
Output: Returns an alert message when triggered.
check_price_alerts() -> List[str]
Functionality:
Iterates over a list of assets (e.g., BTC, ETH, SOL).
Retrieves asset-specific configuration and the latest price data.
Compares current price against the trigger value based on conditions (e.g., ABOVE or BELOW).
Delegates to handle_price_alert_trigger_config if conditions are met.
Output: Returns a list of alert messages.
handle_price_alert_trigger_config(asset: str, current_price: float, trigger_val: float, condition: str) -> str
Functionality:
Checks the cooldown period to prevent duplicate price alerts.
Logs the alert (including caller line number) and prepares a formatted alert message.
Output: Returns the alert message or an empty string if suppressed.
send_call(body: str, key: str)
Functionality:
Checks the time elapsed since the last call notification using the call_refractory_period.
If the period has passed, triggers the Twilio call notification via trigger_twilio_flow.
Logs the operation and updates the internal tracking to enforce the refractory period.
Configuration and Dependencies
Configuration Files:

alert_limits.json: Defines thresholds for various alerts and notification settings.
sonic_config.json: Contains global settings including Twilio configuration and system controls.
Additional files (e.g., theme config) are managed via the JSON Manager.
External Dependencies:

Twilio: Used for sending call notifications.
Flask: Provides the web interface through the Alerts Blueprint.
SQLite3: Stores position and alert data.
Standard Python Libraries: Such as logging, JSON, datetime, etc.
Error Handling, Logging & Notifications
Unified Logging:
All modules utilize a unified logger to capture debug, operation, and error messages.
Error Handling:
Robust try/except blocks are present in configuration loading, alert checking, and notification sending to prevent subsystem crashes.
Cooldown & Refractory Mechanisms:
These mechanisms suppress duplicate alerts within specified time windows.
Notification Failures:
Any issues with triggering notifications (e.g., Twilio errors) are logged for further investigation.
Integration Points & Future Enhancements
Integration Points:

Data Locker: Interface for retrieving positions and latest price data.
Web Frontend: Provided by the Alerts Blueprint to view and update alert configurations.
External APIs: Twilio integration for real-time alert notifications.
Database: SQLite serves as the persistent storage for positions and state tracking.
Future Enhancements:

Introduce granular alert configurations per asset.
Modularize calculation logic further.
Expand web interface analytics with historical trends.
Implement comprehensive unit testing for each module.
Enhance retry logic for external API calls.





