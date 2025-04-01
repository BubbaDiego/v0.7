Calc Services Specification
This document provides an in-depth specification for the Calc Services module. The module is designed to perform various financial analytics and aggregation tasks for trading positions, including calculating risk metrics, leverage, travel percentages, and more. The module also includes utility functions for color coding and alert level determination based on calculated values.

​

Table of Contents
Overview

Module Functions

get_profit_alert_class

CalcServices Class

Constructor

Methods

Implementation Details

Additional Considerations

Conclusion

Overview
The Calc Services module serves as the central aggregator for performing analytical computations on trading positions. It calculates key metrics such as:

Position Value: The monetary value based on collateral and profit/loss.

Leverage: The ratio of position size to collateral.

Travel Percent: A percentage metric indicating progress from entry to profit target or liquidation.

Composite Risk Index (Heat Index): A risk assessment metric computed via a multiplicative model.

Color Coding & Alerts: Determining visual cues (colors and CSS classes) based on thresholds.

The module interfaces with a SQLite database to update and confirm the computed metrics and uses extensive logging for traceability.

Module Functions
get_profit_alert_class
A static utility function that assigns a CSS alert class based on profit and given threshold values.

Purpose:
Determine the alert level for a profit metric by comparing it with low, medium, and high thresholds.

Parameters:

profit: The profit value (numeric).

low_thresh: The low threshold (can be numeric or empty).

med_thresh: The medium threshold.

high_thresh: The high threshold.

Logic:

Returns an empty string if profit is below the low threshold.

Returns "alert-low" if profit is between the low and medium thresholds.

Returns "alert-medium" if profit is between the medium and high thresholds.

Returns "alert-high" if profit is at or above the high threshold.

Error Handling:
Each threshold is safely converted to a float; if conversion fails or is empty, it defaults to infinity.

CalcServices Class
The CalcServices class encapsulates all the analytics logic for processing positions. It updates metrics, performs database operations, and prepares data for display.

Constructor
Responsibilities:

Initializes a logger that writes DEBUG-level logs to calc_services.log.

Sets up predefined color ranges for various metrics (e.g., travel percent, heat index, collateral).

Key Attributes:

logger: Configured with a file handler and a specific log format.

color_ranges: A dictionary mapping metrics to a list of tuples defining the lower and upper bounds and the corresponding color.

Methods
update_calcs_for_cyclone(data_locker) -> (list, dict)
Purpose:
Refresh all calculation data for positions by:

Reading current positions from the database.

Updating positions via aggregation functions.

Calculating totals.

Re-reading the positions to confirm database updates.

Parameters:

data_locker: An instance that provides database read/write capabilities.

Returns:
A tuple containing:

confirmed_positions: The list of positions re-read from the DB.

totals: A dictionary of aggregated totals.

calculate_composite_risk_index(position: dict) -> Optional[float]
Purpose:
Computes the composite risk index (or heat index) for a position using a multiplicative formula.

Formula:
𝑅
=
(
1
−
NDL
)
0.45
×
(
Normalized Leverage
)
0.35
×
(
1
−
Collateral Ratio
)
0.20
×
100
R=(1−NDL) 
0.45
 ×(Normalized Leverage) 
0.35
 ×(1−Collateral Ratio) 
0.20
 ×100

NDL Calculation:

For LONG positions:
NDL
=
current_price
−
liquidation_price
entry_price
−
liquidation_price
NDL= 
entry_price−liquidation_price
current_price−liquidation_price
​
 

For SHORT positions:
NDL
=
liquidation_price
−
current_price
liquidation_price
−
entry_price
NDL= 
liquidation_price−entry_price
liquidation_price−current_price
​
 

Parameters:

position: A dictionary with keys such as entry_price, current_price, liquidation_price, collateral, size, leverage, and position_type.

Notes:

Applies a minimum risk floor (default 5) using the apply_minimum_risk_floor method.

Logs detailed calculation steps.

calculate_value(position)
Purpose:
Calculates the monetary value of a position, typically by summing collateral and profit/loss.

Logic:

Returns the size (already in USD) rounded to two decimal places.

calculate_leverage(size: float, collateral: float) -> float
Purpose:
Computes the leverage ratio by dividing position size by collateral.

Edge Cases:

Returns 0 if either size or collateral is non-positive.

calculate_travel_percent(position_type: str, entry_price: float, current_price: float, liquidation_price: float) -> float
Purpose:
Determines the travel percent which reflects how far the current price has moved relative to the entry and liquidation prices.

Logic:

For LONG positions:

If current_price is less than or equal to entry_price, the percentage is calculated between the entry price and liquidation price.

If above the entry price, it scales between the entry price and a computed profit target.

For SHORT positions:

The logic is inverted compared to LONG positions.

Logging:

Each branch logs input parameters and calculation details.

aggregator_positions(positions: List[dict], db_path: str) -> List[dict]
Purpose:
Processes a list of positions to update their metrics and writes the updates to the database.

Responsibilities:

Updates travel percent, liquidation distance, value, leverage, and heat index for each position.

Executes database update queries to store these computed values.

Confirms the updates by re-reading the updated records.

Database Interaction:

Uses a SQLite3 connection (via a DataLocker instance) to perform update and read operations.

calculate_liquid_distance(current_price: float, liquidation_price: float) -> float
Purpose:
Computes the absolute difference between the current price and the liquidation price.

Returns:
The distance rounded to two decimal places.

calculate_heat_index(position: dict) -> Optional[float]
Purpose:
Computes an example “heat index” defined as 
(
size
×
leverage
)
/
collateral
(size×leverage)/collateral.

Edge Cases:

Returns None if the collateral is zero or negative.

Logging:

Detailed logs for inputs and the computed heat index.

calculate_travel_percent_no_profit(position_type: str, entry_price: float, current_price: float, liquidation_price: float) -> float
Purpose:
Provides a version of travel percent calculation without anchoring a profit target.

Logic:

For LONG positions, computes the percent change from entry price toward liquidation.

For SHORT positions, computes the percentage change from entry price in the opposite direction.

prepare_positions_for_display(positions: List[dict]) -> List[dict]
Purpose:
Processes positions for display by:

Normalizing the data (e.g., determining position type).

Recalculating key metrics such as travel percent, value, leverage, and heat index.

Output:

Returns a list of processed positions with updated fields suitable for UI display.

calculate_totals(positions: List[dict]) -> dict
Purpose:
Aggregates totals and computes weighted averages for:

Total size, value, collateral.

Average leverage, travel percent, and heat index.

Calculation Details:

Uses weighted sums (based on position size) for averages.

Handles edge cases where no positions exist to avoid division by zero.

get_color(value: float, metric: str) -> str
Purpose:
Determines the appropriate color for a given metric value based on predefined ranges.

Logic:

Iterates over the color ranges for the metric.

Returns the color corresponding to the range in which the value falls.

Defaults to "white" if no matching range is found.

calculate_travel_percent_for_slider(position_type: str, entry_price: float, current_price: float, liquidation_price: float) -> float
Purpose:
Similar to calculate_travel_percent, but tailored for a slider UI component.

Logic:

Normalizes the travel percent such that:

For LONG positions: entry is 0, liquidation is -100, and a profit target is +100.

For SHORT positions: logic is inverted.

Note:

There appear to be duplicate definitions in the code; the intended behavior is as described.

apply_minimum_risk_floor(risk_index: float, floor: float = 5.0) -> float
Purpose:
Ensures that the computed risk index does not drop below a predefined floor (default is 5).

Logic:

Returns the maximum of the computed risk index and the floor value.

get_alert_class(value: float, low_thresh: Optional[float], med_thresh: Optional[float], high_thresh: Optional[float], direction: str = "increasing_bad") -> str
Purpose:
Determines a CSS alert class for a metric based on threshold values and the direction of risk (i.e., whether increasing values are considered bad or good).

Parameters:[dash.html](../dashboard/dash.html)

value: The metric value.

low_thresh: The lower threshold.

med_thresh: The medium threshold.

high_thresh: The high threshold.

direction: A string that specifies whether higher values indicate increasing risk ("increasing_bad") or decreasing risk ("decreasing_bad").

Logic:

For increasing_bad:

If value is less than low_thresh, returns "alert-low".

If between low_thresh and med_thresh, returns "alert-medium".

Otherwise, returns "alert-high".

For decreasing_bad:

The logic is reversed.

Default Behavior:

If thresholds are missing, defaults are used (e.g., low_thresh defaults to 0, high_thresh defaults to infinity).

Implementation Details
Logging:

The module makes extensive use of Python's logging library to record debug information, errors, and status updates.

Log entries are formatted to include timestamps, log levels, and descriptive messages.

Database Operations:

SQLite3 is used for database interactions.

A DataLocker instance (assumed to be provided externally) manages the connection and provides methods like read_positions().

Error Handling:

Try-except blocks are used in several functions to safely handle conversion errors and database exceptions.

Default values or None are returned when invalid input data is encountered.

Color Coding:

Predefined ranges for various metrics (e.g., travel percent, heat index, collateral) determine the display colors.

Risk Floor:

A minimum risk floor is applied in composite risk index calculations to ensure a baseline risk score.

Additional Considerations
Data Validation:

The module consistently validates input values (e.g., ensuring prices and collateral are positive) to avoid division by zero or other calculation errors.

Extensibility:

The structure of the module allows for easy extension to include additional metrics or modify existing formulas.

UI Integration:

Functions such as prepare_positions_for_display and calculate_travel_percent_for_slider suggest integration with a user interface where the computed metrics are visually represented.

Duplication Notice:

There is a duplicate definition for calculate_travel_percent_for_slider in the code. It is recommended to clean up redundant code to avoid confusion.