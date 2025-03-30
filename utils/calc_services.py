# calc_services.py

from typing import Optional, List, Dict
import sqlite3
import logging


@staticmethod
def get_profit_alert_class(profit, low_thresh, med_thresh, high_thresh):
    """
    Returns an alert level based on the profit value:
      - If profit is below the 'low' threshold, return an empty string (no alert).
      - If profit is at or above the 'low' threshold but below the 'med' threshold, return "alert-low".
      - If profit is at or above the 'med' threshold but below the 'high' threshold, return "alert-medium".
      - If profit is at or above the 'high' threshold, return "alert-high".
    """
    try:
        low = float(low_thresh) if low_thresh not in (None, "") else float('inf')
    except Exception:
        low = float('inf')
    try:
        med = float(med_thresh) if med_thresh not in (None, "") else float('inf')
    except Exception:
        med = float('inf')
    try:
        high = float(high_thresh) if high_thresh not in (None, "") else float('inf')
    except Exception:
        high = float('inf')

    if profit < low:
        return ""
    elif profit < med:
        return "alert-low"
    elif profit < high:
        return "alert-medium"
    else:
        return "alert-high"


class CalcServices:
    """
    This class provides all aggregator/analytics logic for positions:
     - Calculating value (long/short),
     - Leverage,
     - Travel %,
     - Heat index,
     - Summaries/Totals,
     - Optional color coding for display.
    """

    def __init__(self):
        # Set up a logger for this class that writes DEBUG-level logs to a file.
        self.logger = logging.getLogger("CalcServices")
        self.logger.setLevel(logging.DEBUG)
        # Create a file handler that logs debug messages
        fh = logging.FileHandler("calc_services.log")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(name)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Ranges for color coding (used by get_color) for some metrics.
        self.color_ranges = {
            "travel_percent": [
                (0, 25, "green"),
                (25, 50, "yellow"),
                (50, 75, "orange"),
                (75, 100, "red")
            ],
            "heat_index": [
                (0, 20, "blue"),
                (20, 40, "green"),
                (40, 60, "yellow"),
                (60, 80, "orange"),
                (80, 100, "red")
            ],
            "collateral": [
                (0, 500, "lightgreen"),
                (500, 1000, "yellow"),
                (1000, 2000, "orange"),
                (2000, 10000, "red")
            ]
        }

    def update_calcs_for_cyclone(self, data_locker) -> (list, dict):
        """
        Refreshes all calculation data for positions.
        Reads all positions from DataLocker, updates their aggregated metrics,
        and computes totals.
        Then, immediately reads from the database to confirm the updates.
        Returns a tuple: (confirmed_positions, totals)
        """
        # Read the current positions from the database.
        positions = data_locker.read_positions()
        self.logger.debug(f"Read {len(positions)} positions from DB for update.")

        # Update positions (this calls aggregator_positions which runs UPDATE queries).
        updated_positions = self.aggregator_positions(positions, data_locker.db_path)
        totals = self.calculate_totals(updated_positions)

        # Immediately re-read positions from the database using the same DataLocker connection.
        confirmed_positions = data_locker.read_positions()
        self.logger.info("CalcServices: Updated calculations for cyclone and confirmed DB updates.")

        return confirmed_positions, totals

    def calculate_composite_risk_index(self, position: dict) -> Optional[float]:
        """
        Calculates the composite risk index (heat index) for a given position using the multiplicative model.
        The formula is:
            R = (1 - NDL)^(0.45) * (Normalized Leverage)^(0.35) * (1 - Collateral Ratio)^(0.20) * 100
        where:
          - For a long position:
                NDL = (current_price - liquidation_price) / (entry_price - liquidation_price)
          - For a short position:
                NDL = (liquidation_price - current_price) / (liquidation_price - entry_price)
          - Normalized Leverage = leverage / 100
          - Collateral Ratio = collateral / size (capped at 1)

        Returns a score between 0 and 100, where a higher score indicates greater risk.
        """
        try:
            entry_price = float(position.get("entry_price", 0.0))
            current_price = float(position.get("current_price", 0.0))
            liquidation_price = float(position.get("liquidation_price", 0.0))
            collateral = float(position.get("collateral", 0.0))
            size = float(position.get("size", 0.0))
            leverage = float(position.get("leverage", 0.0))
            position_type = (position.get("position_type") or "LONG").upper()

            self.logger.debug(
                "Calculating composite risk index: entry=%f, current=%f, liq=%f, collateral=%f, size=%f, leverage=%f, type=%s",
                entry_price, current_price, liquidation_price, collateral, size, leverage, position_type)

            # Validate necessary values
            if entry_price <= 0 or liquidation_price <= 0 or collateral <= 0 or size <= 0:
                self.logger.debug("Invalid input values; returning None")
                return None
            if abs(entry_price - liquidation_price) < 1e-6:
                self.logger.debug("Entry price and liquidation price too close; avoiding division by zero")
                return None  # Avoid division by zero

            # Compute normalized distance to liquidation (NDL)
            if position_type == "LONG":
                ndl = (current_price - liquidation_price) / (entry_price - liquidation_price)
            else:  # SHORT
                ndl = (liquidation_price - current_price) / (liquidation_price - entry_price)
            ndl = max(0.0, min(ndl, 1.0))
            self.logger.debug("Computed NDL: %f", ndl)

            # Risk contribution from price distance
            distance_factor = 1.0 - ndl
            self.logger.debug("Distance factor: %f", distance_factor)

            # Normalize leverage (cap at 100x)
            normalized_leverage = leverage / 100.0
            self.logger.debug("Normalized leverage: %f", normalized_leverage)

            # Compute collateral ratio (capped at 1)
            collateral_ratio = collateral / size
            if collateral_ratio > 1.0:
                collateral_ratio = 1.0
            risk_collateral_factor = 1.0 - collateral_ratio
            self.logger.debug("Collateral ratio: %f, Risk collateral factor: %f", collateral_ratio,
                              risk_collateral_factor)

            risk_index = (distance_factor ** 0.45) * (normalized_leverage ** 0.35) * (
                        risk_collateral_factor ** 0.20) * 100.0
            self.logger.debug("Composite risk index before applying risk floor: %f", risk_index)

            # Apply minimum risk floor of 5
            risk_index = self.apply_minimum_risk_floor(risk_index, 5.0)
            self.logger.debug("Composite risk index after applying risk floor: %f", risk_index)

            return round(risk_index, 2)
        except Exception as e:
            self.logger.error(f"Error calculating composite risk index: {e}", exc_info=True)
            return None

    def calculate_value(self, position):
        # Since size is already in USD, just return it.
        size = float(position.get("size") or 0.0)
        return round(size, 2)

    def calculate_leverage(self, size: float, collateral: float) -> float:
        if size <= 0 or collateral <= 0:
            return 0.0
        return round(size / collateral, 2)

    def calculate_travel_percent(self,
                                 position_type: str,
                                 entry_price: float,
                                 current_price: float,
                                 liquidation_price: float) -> float:
        """
        Calculates travel percent for a position.
        For LONG positions:
          - At entry_price, travel percent = 0.
          - At liquidation_price, travel percent = -100%.
          - At profit target (entry_price + (entry_price - liquidation_price)), travel percent = +100%.
        For SHORT positions:
          - At entry_price, travel percent = 0.
          - At liquidation_price, travel percent = -100%.
          - At profit target (entry_price - (liquidation_price - entry_price)), travel percent = +100%.
        """
        # Log the input parameters.
        self.logger.debug(
            "calculate_travel_percent called with: position_type=%s, entry_price=%f, current_price=%f, liquidation_price=%f",
            position_type, entry_price, current_price, liquidation_price)

        if entry_price <= 0 or liquidation_price <= 0 or entry_price == liquidation_price:
            self.logger.debug("Invalid input values; returning 0.0")
            return 0.0

        ptype = position_type.upper()
        result = 0.0

        if ptype == "LONG":
            if current_price <= entry_price:
                denom = entry_price - liquidation_price
                numer = current_price - entry_price
                result = (numer / denom) * 100
                self.logger.debug("LONG (current_price <= entry_price): numer=%f, denom=%f, result=%f", numer, denom,
                                  result)
            else:
                profit_target = entry_price + (entry_price - liquidation_price)
                denom = profit_target - entry_price
                numer = current_price - entry_price
                result = (numer / denom) * 100
                self.logger.debug("LONG (current_price > entry_price): profit_target=%f, numer=%f, denom=%f, result=%f",
                                  profit_target, numer, denom, result)
        elif ptype == "SHORT":
            if current_price >= entry_price:
                denom = liquidation_price - entry_price
                numer = current_price - entry_price
                result = -((numer / denom) * 100)
                self.logger.debug("SHORT (current_price >= entry_price): numer=%f, denom=%f, result=%f", numer, denom,
                                  result)
            else:
                profit_target = entry_price - (liquidation_price - entry_price)
                denom = entry_price - profit_target
                numer = entry_price - current_price
                result = (numer / denom) * 100
                self.logger.debug(
                    "SHORT (current_price < entry_price): profit_target=%f, numer=%f, denom=%f, result=%f",
                    profit_target, numer, denom, result)
        else:
            self.logger.debug("Unknown position type '%s'; returning 0.0", position_type)
            return 0.0

        self.logger.debug("calculate_travel_percent returning result: %f", result)
        return result

    def aggregator_positions(self, positions: List[dict], db_path: str) -> List[dict]:
        """
        For each position in `positions`, compute travel percent,
        liquidation distance, value, leverage, and heat index.
        Also updates the DB with the new travel_percent, liquidation_distance,
        heat_index, current_heat_index, and current_price.
        After the update, it performs a read to confirm the updated values.
        """
        import sqlite3
        conn = DataLocker.get_instance(db_path).conn

        cursor = conn.cursor()

        for pos in positions:
            position_type = (pos.get("position_type") or "LONG").upper()
            entry_price = float(pos.get("entry_price", 0.0))
            current_price = float(pos.get("current_price", 0.0))
            liquidation_price = float(pos.get("liquidation_price", 0.0))
            collateral = float(pos.get("collateral", 0.0))
            size = float(pos.get("size", 0.0))

            travel_percent = self.calculate_travel_percent(
                position_type,
                entry_price,
                current_price,
                liquidation_price
            )
            pos["travel_percent"] = travel_percent

            # Calculate liquidation distance
            liq_distance = self.calculate_liquid_distance(
                current_price=current_price,
                liquidation_price=liquidation_price
            )
            pos["liquidation_distance"] = liq_distance

            # Update travel percent in DB
            try:
                cursor.execute(
                    "UPDATE positions SET travel_percent = ? WHERE id = ?",
                    (travel_percent, pos["id"])
                )
            except Exception as e:
                print(f"Error updating travel_percent for position {pos['id']}: {e}")

            # Update liquidation distance in DB
            try:
                cursor.execute(
                    "UPDATE positions SET liquidation_distance = ? WHERE id = ?",
                    (liq_distance, pos["id"])
                )
            except Exception as e:
                print(f"Error updating liquidation_distance for position {pos['id']}: {e}")

            # Calculate value and leverage for completeness
            if entry_price > 0:
                token_count = size / entry_price
                if position_type == "LONG":
                    pnl = (current_price - entry_price) * token_count
                else:
                    pnl = (entry_price - current_price) * token_count
            else:
                pnl = 0.0
            pos["value"] = round(collateral + pnl, 2)

            if collateral > 0:
                pos["leverage"] = round(size / collateral, 2)
            else:
                pos["leverage"] = 0.0

            # Calculate heat index and set current_heat_index (using the same value)
            heat_index = self.calculate_heat_index(pos) or 0.0
            pos["heat_index"] = heat_index
            pos["current_heat_index"] = heat_index

            # Update heat index and current heat index in DB
            try:
                cursor.execute(
                    "UPDATE positions SET heat_index = ?, current_heat_index = ? WHERE id = ?",
                    (heat_index, heat_index, pos["id"])
                )
            except Exception as e:
                print(f"Error updating heat indexes for position {pos['id']}: {e}")

            # Update current price in DB
            try:
                cursor.execute(
                    "UPDATE positions SET current_price = ? WHERE id = ?",
                    (current_price, pos["id"])
                )
            except Exception as e:
                print(f"Error updating current_price for position {pos['id']}: {e}")

            # Confirm update: Read the updated record for these fields
            try:
                cursor.execute(
                    "SELECT heat_index, current_heat_index, current_price FROM positions WHERE id = ?",
                    (pos["id"],)
                )
                updated_row = cursor.fetchone()
                if updated_row:
                    print(
                        f"[DEBUG] Confirmed update for position {pos['id']}: heat_index = {updated_row[0]}, current_heat_index = {updated_row[1]}, current_price = {updated_row[2]}")
                else:
                    print(f"[DEBUG] No updated record found for position {pos['id']}")
            except Exception as e:
                print(f"Error reading back updated values for position {pos['id']}: {e}")

        conn.commit()
        conn.close()
        return positions

    def calculate_liquid_distance(self, current_price: float, liquidation_price: float) -> float:
        """
        Returns the absolute difference between current_price and liquidation_price.
        """
        if current_price is None:
            current_price = 0.0
        if liquidation_price is None:
            liquidation_price = 0.0
        return round(abs(liquidation_price - current_price), 2)

    def calculate_heat_index(self, position: dict) -> Optional[float]:
        """
        Example "heat index" = (size * leverage) / collateral.
        Returns None if collateral <= 0.
        Logs detailed calculation info.
        """
        size = float(position.get("size", 0.0) or 0.0)
        leverage = float(position.get("leverage", 0.0) or 0.0)
        collateral = float(position.get("collateral", 0.0) or 0.0)
        if collateral <= 0:
            self.logger.debug("Collateral is zero or negative; heat index calculation skipped.")
            return None
        hi = (size * leverage) / collateral
        self.logger.debug("Heat index calculation: size=%f, leverage=%f, collateral=%f, raw hi=%f", size, leverage,
                          collateral, hi)
        return round(hi, 2)

    def calculate_travel_percent_no_profit(self,
                                           position_type: str,
                                           entry_price: float,
                                           current_price: float,
                                           liquidation_price: float) -> float:
        """
        Calculates Travel Percent with NO profit anchor.
        - At entry_price => 0%.
        - Approaching liquidation_price => goes down to -100%.
        """
        if entry_price <= 0 or liquidation_price <= 0 or entry_price == liquidation_price:
            return 0.0

        ptype = position_type.upper()

        def safe_ratio(numer, denom):
            if denom == 0:
                return 0.0
            return (numer / denom) * 100

        if ptype == "LONG":
            denom = abs(entry_price - liquidation_price)
            numer = current_price - entry_price
            travel_percent = safe_ratio(numer, denom)
        else:  # SHORT
            denom = abs(entry_price - liquidation_price)
            numer = entry_price - current_price
            travel_percent = safe_ratio(numer, denom)

        return travel_percent

    def prepare_positions_for_display(self, positions: List[dict]) -> List[dict]:
        processed_positions = []

        for idx, pos in enumerate(positions, start=1):
            print(f"\n[DEBUG] Position #{idx} BEFORE aggregator => {pos}")

            raw_ptype = pos.get("position_type", "LONG")
            ptype_lower = raw_ptype.strip().lower()
            if "short" in ptype_lower:
                position_type = "SHORT"
            else:
                position_type = "LONG"

            entry_price = float(pos.get("entry_price", 0.0))
            current_price = float(pos.get("current_price", 0.0))
            collateral = float(pos.get("collateral", 0.0))
            size = float(pos.get("size", 0.0))
            liquidation_price = float(pos.get("liquidation_price", 0.0))

            pos["travel_percent"] = self.calculate_travel_percent(
                position_type,
                entry_price,
                current_price,
                liquidation_price
            )

            print(
                f"[DEBUG] Normalized => type={position_type}, entry={entry_price}, current={current_price}, collat={collateral}, size={size}, travel_percent={pos['travel_percent']}")

            if entry_price <= 0:
                pnl = 0.0
            else:
                token_count = size / entry_price
                if position_type == "LONG":
                    pnl = (current_price - entry_price) * token_count
                else:
                    pnl = (entry_price - current_price) * token_count

            pos["value"] = round(collateral + pnl, 2)
            if collateral > 0:
                pos["leverage"] = round(size / collateral, 2)
            else:
                pos["leverage"] = 0.0

            pos["heat_index"] = self.calculate_heat_index(pos) or 0.0

            print(f"[DEBUG] Position #{idx} AFTER aggregator => {pos}")

            processed_positions.append(pos)

        return processed_positions

    def calculate_totals(self, positions: List[dict]) -> dict:
        total_size = 0.0
        total_value = 0.0
        total_collateral = 0.0
        total_heat_index = 0.0
        heat_index_count = 0
        weighted_leverage_sum = 0.0
        weighted_travel_percent_sum = 0.0

        for pos in positions:
            size = float(pos.get("size") or 0.0)
            value = float(pos.get("value") or 0.0)
            collateral = float(pos.get("collateral") or 0.0)
            leverage = float(pos.get("leverage") or 0.0)
            travel_percent = float(pos.get("travel_percent") or 0.0)
            heat_index = float(pos.get("heat_index") or 0.0)

            total_size += size
            total_value += value
            total_collateral += collateral
            weighted_leverage_sum += (leverage * size)
            weighted_travel_percent_sum += (travel_percent * size)

            if heat_index != 0.0:
                total_heat_index += heat_index
                heat_index_count += 1

        if total_size > 0:
            avg_leverage = weighted_leverage_sum / total_size
            avg_travel_percent = weighted_travel_percent_sum / total_size
        else:
            avg_leverage = 0.0
            avg_travel_percent = 0.0

        avg_heat_index = total_heat_index / heat_index_count if heat_index_count > 0 else 0.0

        return {
            "total_size": total_size,
            "total_value": total_value,
            "total_collateral": total_collateral,
            "avg_leverage": avg_leverage,
            "avg_travel_percent": avg_travel_percent,
            "avg_heat_index": avg_heat_index
        }

    def get_color(self, value: float, metric: str) -> str:
        if metric not in self.color_ranges:
            return "white"
        for (lower, upper, color) in self.color_ranges[metric]:
            if lower <= value < upper:
                return color
        return "red"

    def calculate_travel_percent_for_slider(self, position_type: str, entry_price: float, current_price: float,
                                            liquidation_price: float) -> float:
        """
        Calculates a normalized travel percent for slider usage.
        For LONG positions:
          - At entry_price, the slider value is 0.
          - At liquidation_price, the slider value is -100.
          - At a defined profit target (entry_price + (entry_price - liquidation_price)), the slider value is +100.
        For SHORT positions, the logic is inverted.
        """
        if entry_price <= 0 or liquidation_price <= 0 or entry_price == liquidation_price:
            return 0.0
        ptype = position_type.upper()
        if ptype == "LONG":
            if current_price <= entry_price:
                # Scale linearly between entry (0) and liquidation (-100)
                return ((current_price - entry_price) / (entry_price - liquidation_price)) * 100
            else:
                profit_target = entry_price + (entry_price - liquidation_price)
                return ((current_price - entry_price) / (profit_target - entry_price)) * 100
        else:  # SHORT
            if current_price >= entry_price:
                # Scale between entry (0) and liquidation (-100)
                return ((entry_price - current_price) / (liquidation_price - entry_price)) * 100
            else:
                profit_target = entry_price - (liquidation_price - entry_price)
                return ((entry_price - current_price) / (entry_price - profit_target)) * 100

    def calculate_travel_percent_for_slider(self, position_type: str, entry_price: float, current_price: float,
                                            liquidation_price: float) -> float:
        """
        Calculates a normalized travel percent for slider usage.
        For LONG positions:
          - At entry_price, the slider value is 0.
          - At liquidation_price, the slider value is -100.
          - At a defined profit target (entry_price + (entry_price - liquidation_price)), the slider value is +100.
        For SHORT positions, the logic is inverted.
        """
        if entry_price <= 0 or liquidation_price <= 0 or entry_price == liquidation_price:
            return 0.0
        ptype = position_type.upper()
        if ptype == "LONG":
            if current_price <= entry_price:
                # Scale linearly between entry (0) and liquidation (-100)
                return ((current_price - entry_price) / (entry_price - liquidation_price)) * 100
            else:
                profit_target = entry_price + (entry_price - liquidation_price)
                return ((current_price - entry_price) / (profit_target - entry_price)) * 100
        else:  # SHORT
            if current_price >= entry_price:
                # Scale between entry (0) and liquidation (-100)
                return ((entry_price - current_price) / (liquidation_price - entry_price)) * 100
            else:
                profit_target = entry_price - (liquidation_price - entry_price)
                return ((entry_price - current_price) / (entry_price - profit_target)) * 100

    def apply_minimum_risk_floor(self, risk_index: float, floor: float = 5.0) -> float:
        """
        Enforces a minimum risk floor.
        Even if the computed risk index is very low (e.g., for a fully collateralized position),
        this function ensures that the risk index never drops below the specified floor.
        """
        return max(risk_index, floor)

    def get_alert_class(self, value: float, low_thresh: Optional[float], med_thresh: Optional[float],
                        high_thresh: Optional[float], direction: str = "increasing_bad") -> str:
        """
        Returns a CSS class string based on thresholds and metric direction.
        For metrics with direction "increasing_bad" (e.g. size, where higher is worse):
          - If value < low_thresh: returns "alert-low" (green, OK)
          - If low_thresh <= value < med_thresh: returns "alert-medium" (yellow, caution)
          - If value >= med_thresh: returns "alert-high" (red, alert)
        For metrics with direction "decreasing_bad", the logic is reversed.
        """
        if low_thresh is None:
            low_thresh = 0.0
        if med_thresh is None:
            med_thresh = 0.0
        if high_thresh is None:
            high_thresh = float('inf')

        if direction == "increasing_bad":
            if value < low_thresh:
                return "alert-low"
            elif value < med_thresh:
                return "alert-medium"
            else:
                return "alert-high"
        elif direction == "decreasing_bad":
            if value > low_thresh:
                return "alert-low"
            elif value > med_thresh:
                return "alert-medium"
            else:
                return "alert-high"
        else:
            return ""

# End of calc_services.py
