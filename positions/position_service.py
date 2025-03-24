#!/usr/bin/env python
"""
Module: position_service.py
Description:
    Provides services for retrieving, enriching, and updating positions data.
    This includes methods to:
      - Get and enrich all positions.
      - Update Jupiter positions by fetching from the external API.
      - Delete existing Jupiter positions.
      - Record snapshots of aggregated positions data.
"""

import logging
from typing import List, Dict, Any
import requests
from datetime import datetime
from data.data_locker import DataLocker
from config.config_constants import DB_PATH
from utils.calc_services import CalcServices
from alerts.alert_evaluator import AlertEvaluator
from utils.unified_logger import UnifiedLogger
from sonic_labs.hedge_manager import HedgeManager
from api.dydx_api import DydxAPI

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    import sys
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(name)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class PositionService:
    # Mapping for market mints to asset types
    MINT_TO_ASSET = {
        "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh": "BTC",
        "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": "ETH",
        "So11111111111111111111111111111111111111112": "SOL"
    }

    def update_position_and_alert(pos: dict, data_locker):
        """
        After updating a position, re-evaluate its alert state and update the alert record.
        """
        # (Your code here to update the position in the DB using data_locker)
        # For example:
        data_locker.create_position(pos)  # Or update_position() as appropriate

        # Now load configuration (this could be cached or passed in)
        config_manager = UnifiedConfigManager(CONFIG_PATH)
        config = config_manager.load_config()

        # Create an AlertEvaluator instance and update the alert for this position
        evaluator = AlertEvaluator(config, data_locker)
        evaluator.update_alert_for_position(pos)

    @staticmethod
    def get_all_positions(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
        """
        Retrieve all positions from the database and enrich each one with calculated data.
        Converts sqlite3.Row objects to dicts for easier processing.
        """
        try:
            dl = DataLocker.get_instance(db_path)
            raw_positions = dl.read_positions()
            positions = []
          #  for pos in raw_positions:
                # Explicitly convert sqlite3.Row to a dict using its keys.
           #     pos_dict = { key: pos[key] for key in pos.keys() }
                # Optionally, you can enrich each position here.
             #   positions.append(pos_dict)

            for pos in raw_positions:
                pos_dict = {key: pos[key] for key in pos.keys()}
                enriched = PositionService.enrich_position(pos_dict)
                positions.append(enriched)
            return positions
        except Exception as e:
            logger.error(f"Error retrieving positions: {e}", exc_info=True)
            raise

    @staticmethod
    def enrich_position(position: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.debug(f"Enriching position: {position}")
            calc = CalcServices()
            # List of required numeric fields and their fallbacks
            required_fields = ['entry_price', 'current_price', 'liquidation_price', 'collateral', 'size']
            for field in required_fields:
                if position.get(field) is None:
                    if field == 'current_price' and position.get('entry_price') is not None:
                        logger.debug(f"Field '{field}' is None, defaulting to entry_price: {position['entry_price']}")
                        position[field] = position['entry_price']
                    else:
                        logger.debug(f"Field '{field}' is None, defaulting to 0.0")
                        position[field] = 0.0

            # Convert values to float explicitly
            try:
                position['entry_price'] = float(position['entry_price'])
                position['current_price'] = float(position['current_price'])
                position['liquidation_price'] = float(position['liquidation_price'])
                position['collateral'] = float(position['collateral'])
                position['size'] = float(position['size'])
                logger.debug("Converted required fields to float.")
            except Exception as conv_err:
                logger.error(f"Error converting fields to float: {conv_err}")
                raise

            # Compute profit value
            profit = calc.calculate_value(position)
            position['profit'] = profit
            logger.debug(f"Calculated profit: {profit}")

            # Compute leverage
            collateral = position['collateral']
            size = position['size']
            if collateral > 0:
                leverage = calc.calculate_leverage(size, collateral)
                position['leverage'] = leverage
                logger.debug(f"Calculated leverage: {leverage}")
            else:
                position['leverage'] = None
                logger.debug("Collateral is zero or negative; leverage set to None.")

            # Compute travel percent if relevant data exists
            if all(k in position for k in ['entry_price', 'current_price', 'liquidation_price']):
                travel_percent = calc.calculate_travel_percent(
                    position.get('position_type', ''),
                    position['entry_price'],
                    position['current_price'],
                    position['liquidation_price']
                )
                position['travel_percent'] = travel_percent
                logger.debug(f"Calculated travel_percent: {travel_percent}")
            else:
                position['travel_percent'] = None
                logger.debug("Missing one of entry_price, current_price, or liquidation_price; travel_percent set to None.")

            # Compute liquidation distance (absolute difference)
            liq_distance = calc.calculate_liquid_distance(
                position['current_price'],
                position['liquidation_price']
            )
            position['liquidation_distance'] = liq_distance
            logger.debug(f"Calculated liquidation_distance: {liq_distance}")

            # Compute composite risk index using the multiplicative model (our new composite risk index)
            composite_risk = calc.calculate_composite_risk_index(position)
            position["heat_index"] = composite_risk
            logger.debug(f"Computed composite risk index (heat_index): {composite_risk}")

            logger.debug(f"Enriched position: {position}")
            return position
        except Exception as e:
            logger.error(f"Error enriching position data: {e}", exc_info=True)
            raise

    @staticmethod
    def fill_positions_with_latest_price(positions: List[Any]) -> List[Dict[str, Any]]:
        try:
            dl = DataLocker.get_instance()
            for i, pos in enumerate(positions):
                # Convert sqlite3.Row to a dict if necessary.
                if not isinstance(pos, dict):
                    pos = dict(pos)
                    positions[i] = pos
                asset_type = pos.get('asset_type')
                if asset_type:
                    latest_price_data = dl.get_latest_price(asset_type)
                    if latest_price_data and 'current_price' in latest_price_data:
                        try:
                            pos['current_price'] = float(latest_price_data['current_price'])
                        except (ValueError, TypeError) as conv_err:
                            logger.error(f"Error converting latest price for asset '{asset_type}': {conv_err}")
                            pos['current_price'] = pos.get('current_price')
                    else:
                        logger.warning(f"No latest price found for asset type: {asset_type}")
                else:
                    logger.warning("Position missing 'asset_type' field.")
            return positions
        except Exception as e:
            logger.error(f"Error in fill_positions_with_latest_price: {e}", exc_info=True)
            raise

    @staticmethod
    def update_jupiter_positions(db_path: str = DB_PATH) -> Dict[str, Any]:
        """
        Fetch Jupiter positions for all wallets in the database, update the positions table,
        update balance variables, and update hedges via HedgeManager.
        Returns a dictionary with a result message and counts.
        """
        logger.info(f"Jupiter: 💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀💀")


        try:
            dl = DataLocker.get_instance(db_path)
            wallets_list = dl.read_wallets()
            if not wallets_list:
                logger.info("No wallets found in DB.")
                return {"message": "No wallets found in DB", "imported": 0, "skipped": 0}

            new_positions = []
            for w in wallets_list:

                public_addr = w.get("public_address", "").strip()
                if not public_addr:
                    logger.info(f"Skipping wallet {w['name']} (no public_address).")
                    continue

                jupiter_url = f"https://perps-api.jup.ag/v1/positions?walletAddress={public_addr}&showTpslRequests=true"
                resp = requests.get(jupiter_url)
                resp.raise_for_status()
                data = resp.json()
                data_list = data.get("dataList", [])
                if not data_list:
                    logger.info(f"No positions for wallet {w['name']} ({public_addr}).")
                    continue

                for item in data_list:
                    try:
                        pos_pubkey = item.get("positionPubkey")
                        if not pos_pubkey:
                            logger.warning(f"Skipping item for wallet {w['name']} due to missing positionPubkey")
                            continue
                        epoch_time = float(item.get("updatedTime", 0))
                        updated_dt = datetime.fromtimestamp(epoch_time)
                        mint = item.get("marketMint", "")
                        asset_type = PositionService.MINT_TO_ASSET.get(mint, "BTC")
                        side = item.get("side", "short").capitalize()
                        travel_pct_value = item.get("pnlChangePctAfterFees")
                        travel_percent = float(travel_pct_value) if travel_pct_value is not None else 0.0
                        pos_dict = {
                            "id": pos_pubkey,
                            "asset_type": asset_type,
                            "position_type": side,
                            "entry_price": float(item.get("entryPrice", 0.0)),
                            "liquidation_price": float(item.get("liquidationPrice", 0.0)),
                            "collateral": float(item.get("collateral", 0.0)),
                            "size": float(item.get("size", 0.0)),
                            "leverage": float(item.get("leverage", 0.0)),
                            "value": float(item.get("value", 0.0)),
                            "last_updated": updated_dt.isoformat(),
                            "wallet_name": w["name"],
                            "pnl_after_fees_usd": float(item.get("pnlAfterFeesUsd", 0.0)),
                            "current_travel_percent": travel_percent
                        }
                        new_positions.append(pos_dict)
                    except Exception as map_err:
                        logger.warning(f"Skipping item for wallet {w['name']} due to mapping error: {map_err}")

            new_count = 0
            duplicate_count = 0
            for p in new_positions:
                cursor = dl.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM positions WHERE id = ?", (p["id"],))
                dup_count = cursor.fetchone()
                cursor.close()
                if dup_count[0] == 0:
                    dl.create_position(p)
                    new_count += 1
                else:
                    duplicate_count += 1
                    logger.info(f"Skipping duplicate Jupiter position: {p['id']}")

            # Update balance variables
            all_positions = dl.get_positions()
            total_brokerage_value = sum(float(pos.get("value", 0)) for pos in all_positions)
           # balance_vars = dl.get_balance_vars()
           # old_wallet_balance = balance_vars.get("total_wallet_balance", 0.0)
          #  new_total_balance = old_wallet_balance + total_brokerage_value
           # dl.set_balance_vars(
          #      brokerage_balance=total_brokerage_value,
           #     total_balance=new_total_balance
          #  )
          #  msg = (f"Imported {new_count} new Jupiter position(s); Skipped {duplicate_count} duplicate(s). "
         #          f"BrokerageBalance={total_brokerage_value:.2f}, TotalBalance={new_total_balance:.2f}")
         #   logger.info(msg)

            #logger.info(f"Jupiter:  💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸 💸")

            # --- New Code: Update hedges via HedgeManager ---
            try:
                from sonic_labs.hedge_manager import HedgeManager
                # Get the updated positions again.
                updated_positions = PositionService.get_all_positions(db_path)
                hedge_manager = HedgeManager(updated_positions)
                hedges = hedge_manager.get_hedges()
                # Log the hedge update operation.
                from utils.unified_logger import UnifiedLogger
                op_logger = UnifiedLogger()
                op_logger.log_operation(
                    operation_type="Hedge Updated",
                    primary_text=f"{len(hedges)} hedges updated via Jupiter positions.",
                    source="System",
                    file="position_service.py"
                )
            except Exception as hedge_err:
                op_logger = UnifiedLogger()
                op_logger.log_operation(
                    operation_type="Hedge Fucked",
                    primary_text=f"{len(hedges)} hedges fucked",
                    source="System",
                    file="position_service.py")

            msg = "Jupiter positions updated successfully."
            return {"message": msg, "imported": new_count, "skipped": duplicate_count}
        except Exception as e:
            logger.error(f"Error in update_jupiter_positions: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def delete_all_jupiter_positions(db_path: str = DB_PATH):
        """
        Delete all Jupiter positions from the database.
        """
        try:
            dl = DataLocker.get_instance(db_path)
            cursor = dl.conn.cursor()  # Create a new cursor
            cursor.execute("DELETE FROM positions WHERE wallet_name IS NOT NULL")
            dl.conn.commit()
            cursor.close()  # Close the cursor after use
            logger.info("All Jupiter positions deleted.")
        except Exception as e:
            logger.error(f"Error deleting Jupiter positions: {e}", exc_info=True)
            raise

    @staticmethod
    def update_dydx_positions(db_path: str = DB_PATH) -> dict:
        """
        Fetches perpetual positions from dYdX via the DydxAPI client,
        maps them to our Position model, and inserts new positions into the database.
        """
        try:
            from uuid import uuid4  # Needed for generating IDs if absent
            client = DydxAPI()
            wallet_address = "dydx1unfl20nw9xep6vyl78jktjgrywvr5m7z7ru9e8"
            subaccount_number = 0  # Or get from config as needed

            dydx_positions = client.get_perpetual_positions(wallet_address, subaccount_number)
            dl = DataLocker.get_instance(db_path)
            new_count = 0

            for pos in dydx_positions:
                pos_dict = {
                    "id": pos.get("id", str(uuid4())),
                    "asset_type": pos.get("market", "BTC"),
                    "position_type": pos.get("side", ""),
                    "entry_price": float(pos.get("entryPrice", 0.0)),
                    "liquidation_price": 0.0,
                    "current_travel_percent": 0.0,
                    "value": float(pos.get("size", 0.0)) * float(pos.get("entryPrice", 0.0)),
                    "collateral": 0.0,
                    "size": float(pos.get("size", 0.0)),
                    "leverage": 0.0,
                    # Set wallet_name so that create_position sets a proper value (default "Default" otherwise)
                    "wallet_name": wallet_address,
                    "last_updated": pos.get("createdAt", datetime.now().isoformat()),
                    "current_price": float(pos.get("entryPrice", 0.0)),
                    "liquidation_distance": None,
                    "heat_index": 0.0,
                    "current_heat_index": 0.0,
                    "pnl_after_fees_usd": float(pos.get("pnlAfterFeesUsd", 0.0)) if pos.get("pnlAfterFeesUsd") else 0.0,
                }
                cursor = dl.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM positions WHERE id = ?", (pos_dict["id"],))
                dup_count = cursor.fetchone()[0]
                cursor.close()
                if dup_count == 0:
                    dl.create_position(pos_dict)
                    new_count += 1

            msg = f"Imported {new_count} new dYdX position(s)."
            logger.info(msg)
            return {"message": msg, "imported": new_count}
        except Exception as e:
            logger.error("Error updating dYdX positions: %s", e, exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def record_positions_snapshot(db_path: str = DB_PATH):
        """
        Retrieve all enriched positions, calculate aggregated totals, and store a snapshot
        in the positions_totals_history table.
        """
        try:
            positions = PositionService.get_all_positions(db_path)
            calc_services = CalcServices()
            totals = calc_services.calculate_totals(positions)
            dl = DataLocker.get_instance(db_path)
            dl.record_positions_totals_snapshot(totals)
            logger.info("Positions snapshot recorded.")
        except Exception as e:
            logger.error(f"Error recording positions snapshot: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    try:
        positions = PositionService.get_all_positions()
        updated_positions = PositionService.fill_positions_with_latest_price(positions)
        for pos in updated_positions:
            asset = pos.get('asset_type', 'Unknown')
            current_price = pos.get('current_price', 'N/A')
            print(f"Position for asset {asset} updated with current_price: {current_price}")
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)
