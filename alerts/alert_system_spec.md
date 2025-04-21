Alert Module/Subsystem Specification
This document provides a comprehensive specification for the Alert Module/Subsystem. It outlines the architecture, components, data flow, external integrations, and configuration options.

1. Overview
The Alert Module/Subsystem is designed to monitor various conditions related to market data and trading positions, evaluate alert conditions based on configurable thresholds, and trigger notifications via multiple channels (e.g., email, SMS, Twilio calls). It provides both backend processing (alert creation, enrichment, evaluation, and management) and a web-based UI for configuration and visualization.

2. Architecture
The subsystem is composed of several interrelated components:

Data Persistence Layer: Managed by the DataLocker, which handles all SQLite database interactions.

Business Logic Components:

Alert Controller: Creates, updates, and initializes alert records.

Alert Enrichment: Normalizes and enriches alert data with configuration and external data.

Alert Evaluator: Evaluates alert conditions (e.g., travel percent, profit, heat index) against predefined thresholds and cooldown periods.

Alert Manager: Orchestrates the entire alert lifecycle (creation, evaluation, notification, and timer management).

Web/API Layer:

Alerts Blueprint: A Flask blueprint exposing REST endpoints and UI routes for alert operations.

UI Templates: HTML views for configuring alert limits and visualizing the alert matrix.

Data Models: Defined in the models module to standardize asset types, alert types, status, levels, and notifications.

3. Components
3.1 Data Models
The module uses a set of standardized models and enumerations to maintain consistency across alerts and positions. Key models include:

AssetType, SourceType, Status, AlertLevel, AlertType, AlertClass, NotificationType
Defined in models.py to standardize values across the system. For example, Alert types include PriceThreshold, TravelPercent (used for travel percent liquidation), Profit, and HeatIndex ​
.

Price, Alert, Position, Hedge
These classes encapsulate the properties of pricing data, alert configurations, trading positions, and hedge information.

3.2 Data Persistence – DataLocker
Database Interaction:
The DataLocker (in data_locker.py) initializes and maintains a SQLite database with tables for prices, positions, alerts, alert ledger, system variables, brokers, and wallets. It provides APIs for reading, inserting, updating, and deleting records ​
.

Database Schema Highlights:

Alerts Table: Contains columns like id, created_at, alert_type, alert_class, trigger_value, condition, notification_type, level, last_triggered, status, and more.

Positions Table: Stores trading position details and includes an alert_reference_id to link a position to its corresponding alert.

3.3 Alert Controller
Responsibilities:

Creating alerts (including price, travel percent, and profit alerts).

Initializing alert defaults and setting correct alert classes based on the type.

Updating alert conditions and linking alerts to trading positions.

Key Methods:

create_alert(), create_position_alerts(), create_price_alerts(), create_travel_percent_alerts(), and create_profit_alerts().

These functions also log detailed debug information and integrate with the DataLocker for persistence ​
.

3.4 Alert Enrichment
Purpose:
Functions in alert_enrichment.py normalize the alert type and enrich alert data by:

Converting various alert type formats to standardized values.

Loading additional configuration (e.g., trigger values and notification methods) from JSON configuration.

Populating the evaluated value based on the latest market or position data.

Key Functions:

normalize_alert_type()

populate_evaluated_value_for_alert()

enrich_alert_data() ​
.

3.5 Alert Evaluator
Purpose:
The Alert Evaluator (in alert_evaluator.py) is responsible for determining if alert conditions are met. It supports evaluation of:

Travel Alerts: Based on travel percent thresholds.
[alert_controller.py](alert_controller.py)
Profit Alerts: Evaluated against profit thresholds.

Swing, Blast, and Heat Index Alerts: With specific logic and cooldown handling.

Market Alerts: Based on price thresholds.

Cooldown and Suppression:
A cooldown mechanism ensures that alerts are not triggered repeatedly within a short time frame.

Key Methods:

evaluate_travel_alert(), evaluate_profit_alert(), evaluate_swing_alert(), evaluate_blast_alert(), evaluate_heat_index_alert(), and evaluate_price_alerts().

A master method evaluate_alerts() aggregates results from market, position, and system evaluations ​
.

3.6 Alert Manager
Role:
Orchestrates the overall alert lifecycle by:

Loading configuration settings (from alert_limits.json and a unified config manager).

Coordinating alert creation, re-evaluation, and notification.

Handling timers for cooldowns, call refractory periods, and snooze intervals.

Triggering notifications via Twilio and updating the alert ledger.

Key Functionalities:

check_alerts(), reevaluate_alerts(), and update_alerts_evaluated_value().

Integrates with both AlertController and AlertEvaluator.

Manages external notifications through methods like send_call() and helper functions to trigger Twilio flows ​
.

3.7 Alerts Blueprint (Flask API)
API Endpoints:

/alerts/create_all_alerts: Create all alerts in the system.

/alerts/delete_all_alerts: Remove all alerts.

/alerts/refresh_alerts: Manually trigger re-evaluation of alerts.

/alerts/config & /alerts/update_config: Serve and update the alert configuration.

/alerts/viewer: Render the Alert Matrix UI for visualizing current alerts.

UI Integration:
The blueprint integrates with HTML templates such as alert_limits.html (for configuration) and alert_matrix.html (for visualization) ​
, ​
.

3.8 UI Templates
Alert Limits Configuration (alert_limits.html):
Provides an interactive form for setting:

Price alert thresholds and conditions.

Alert timing settings (cooldown, call refractory, snooze countdown).

Notification preferences with inline selectors for call, SMS, and email.

Alert Matrix (alert_matrix.html):
Displays the current alert statuses in a card-based layout with:

Color-coded levels (Normal, Low, Medium, High).

Icons representing alert types.

Detailed information about each alert (trigger, evaluated value, status).

Both templates support dynamic theming via CSS variables ​
, ​
.

4. Configuration
JSON Configuration (alert_limits.json):

Contains system-level configurations (e.g., API keys, DB paths, logging settings).

Defines alert ranges for different metrics:

Heat Index, Travel Percent Liquid, Profit, Price Alerts (with specific thresholds for assets BTC, ETH, SOL).

Also includes timing settings (alert cooldown, call refractory period, snooze countdown) ​
.

Dynamic Update via Web UI:
The /alerts/config route in the Alerts Blueprint allows users to view and update configuration parameters.

5. Notification and External Integrations
Notification Channels:

Email & SMS: Configured via the notification_config in the JSON file.

Twilio Integration:

Managed in the Alert Manager using trigger_twilio_flow() to initiate calls or alerts.

Requires complete Twilio configuration (account SID, auth token, flow SID, phone numbers) ​
.

6. Logging and Audit Trail
Unified Logging:
Each component (AlertController, AlertEvaluator, AlertManager, DataLocker) uses a unified logger for:

Debug logging of alert operations.

Error and exception logging.

Audit logging via an alert ledger (stored in the alert_ledger table) for tracking changes in alert states.

Operation Logs:
Detailed logs are generated when alerts are created, updated, or triggered. These logs facilitate troubleshooting and historical audits.

7. Error Handling and Cooldowns
Error Handling:
Exceptions during alert creation or database operations are caught and logged. For example, SQLite integrity errors are specifically handled in create_alert().

Cooldown Mechanism:
To avoid excessive notifications, each alert type has a configurable cooldown period. The Alert Evaluator and Manager track the last triggered time and suppress new notifications if within the cooldown window.

8. Database Schema Summary
Tables:

prices: Stores current and previous asset prices.

positions: Contains trading position details, including alert references.

alerts: Records alert configurations and current state.

alert_ledger: Maintains an audit trail of changes to alerts.

system_vars, brokers, wallets, portfolio_entries, positions_totals_history: Support system-wide settings and snapshots.

DataLocker handles schema creation and migrations on initialization ​
.

9. External Dependencies
SQLite:
Used for persistent storage via DataLocker.

Twilio:
Integrated for call notifications via the Twilio API.

Flask:
Provides the web framework for REST endpoints and UI rendering.

Other Utilities:
JSON management, unified logging, and configuration management utilities ensure consistent behavior across modules.

10. Future Enhancements
Modularization:
Consider splitting the evaluation logic further to support additional alert types.

Scalability:
Evaluate migrating from SQLite to a more scalable database solution.

Real-time Integration:
Integrate with real-time data feeds and websocket notifications.

Enhanced UI:
Provide richer dashboards and interactive filtering of alerts.


11. Travel Percent Alert Evaluation Behavior
For travel percent alerts, the system leverages the existing trigger_value field to represent the next threshold that will trigger a change in the alert level. This behavior is implemented to aid debugging and provide clarity in the UI, and it may be further integrated into the evaluation logic in the future. The behavior is as follows:

Initial Alert Creation:
When a position is created with a travel percent of 0%, the alert is initialized with a "Normal" level. The trigger_value is set to the lowest configured threshold (e.g., -25.0), indicating that a drop below -25.0 will trigger an escalation.

Dynamic Evaluation:
During subsequent evaluations:

Normal Level:
If the current travel percent is above 0% or remains between 0% and -25% (e.g., -22%), the alert stays "Normal" and the trigger_value remains at -25.0.

Escalation to Low:
When the travel percent drops below -25% (e.g., -30%), the alert level escalates to "Low" and the trigger_value is updated to the next threshold (e.g., -50.0), indicating the target for further escalation.

Escalation to Medium:
If the travel percent further declines into the next bracket (e.g., -52%), the alert level becomes "Medium" and the trigger_value updates to the highest threshold (e.g., -75.0).

Highest Level:
Once the travel percent reaches or exceeds the highest configured threshold (e.g., -75% or lower), the alert level is set to "High." At this point, the trigger_value may remain at -75.0 (or be marked as final), indicating that the maximum escalation has been reached.

Reversal Scenario:
If the travel percent improves (e.g., from -52% to -48%), the alert level and trigger_value adjust accordingly to reflect the current bracket.

Purpose and Benefits:

Operational Clarity:[alert_matrix.html](alert_matrix.html)
Displaying the next threshold via the trigger_value helps operators quickly understand what change in travel percent will result in an escalation.

Debugging Aid:
With a dynamically updated trigger_value, logs and UI messages can clearly indicate the future alert condition, streamlining troubleshooting.
[alert_matrix.html](alert_matrix.html)
Potential Integration:
While the evaluator currently uses the configuration thresholds directly, the updated trigger_value can be leveraged in future enhancements to make the evaluation process even more dynamic.