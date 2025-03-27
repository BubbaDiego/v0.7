"""
hedge_manager.py

This module defines the HedgeManager class which is responsible for:
  - Scanning positions for hedge links (via hedge_buddy_id).
  - Creating Hedge instances that represent grouped positions.
  - Aggregating metrics such as total long size, total short size, long/short heat indices,
    and total heat index.
  - Providing access to hedge data via methods like get_hedges().
  - Logging an operations entry when hedges are checked.
  - New: Finding and clearing hedge associations based on raw positions.

Assumptions:
  - The Position objects include a 'hedge_buddy_id' field to denote grouping.
  - The Position object has a 'position_type' field (e.g., "long" or "short"),
    a 'size' field (numeric), and a 'heat_index' field.
  - The Hedge class is defined (e.g., in models.py) with fields for positions,
    total_long_size, total_short_size, long_heat_index, short_heat_index, total_heat_index,
    created_at, updated_at, and notes.
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
from data.models import Position, Hedge  # Assuming Hedge is defined in models.py

# Import the UnifiedLogger for operations logging.
from utils.unified_logger import UnifiedLogger
from config.config_constants import DB_PATH
from data.data_locker import DataLocker
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class HedgeManager:
    def __init__(self, positions: Optional[List[Position]] = None):
        """
        Initialize the HedgeManager with an optional list of positions.
        If positions are provided, build hedges immediately.
        """
        self.logger = UnifiedLogger()  # Instantiate the unified logger for ops logging.
        self.positions: List[Position] = positions if positions is not None else []
        self.hedges: List[Hedge] = []
        self.build_hedges()

    def build_hedges(self):
        hedge_groups = {}
        for pos in self.positions:
            hedge_buddy_id = pos.get("hedge_buddy_id")
            if hedge_buddy_id:
                if hedge_buddy_id not in hedge_groups:
                    hedge_groups[hedge_buddy_id] = []
                hedge_groups[hedge_buddy_id].append(pos)

        self.hedges = []
        for key, pos_group in hedge_groups.items():
            if len(pos_group) >= 2:
                hedge = Hedge(id=str(uuid4()))
                hedge.positions = [p.get("id") for p in pos_group]

                total_long = 0.0
                total_short = 0.0
                long_heat = 0.0
                short_heat = 0.0

                for p in pos_group:
                    position_type = str(p.get("position_type", "")).lower()
                    size = float(p.get("size", 0))
                    heat_index = float(p.get("heat_index", 0))
                    if position_type == "long":
                        total_long += size
                        long_heat += heat_index
                    elif position_type == "short":
                        total_short += size
                        short_heat += heat_index

                hedge.total_long_size = total_long
                hedge.total_short_size = total_short
                hedge.long_heat_index = long_heat
                hedge.short_heat_index = short_heat
                hedge.total_heat_index = long_heat + short_heat
                hedge.created_at = datetime.now()
                hedge.updated_at = datetime.now()
                hedge.notes = f"Hedge created from positions with hedge_buddy_id: {key}"

                self.hedges.append(hedge)

        self.logger.log_operation(
            operation_type="Hedge Check",
            primary_text=f"Hedge check complete: {len(self.hedges)} hedges found.",
            source="HedgeManager",
            file="hedge_manager.py",
            extra_data={"hedge_count": len(self.hedges)}
        )

    def update_positions(self, positions: List[Position]):
        """
        Update the positions list and rebuild hedges.
        """
        self.positions = positions
        self.build_hedges()

    def get_hedges(self) -> List[Hedge]:
        """
        Return the list of Hedge instances.
        """
        return self.hedges

    @staticmethod
    def find_hedges(db_path: str = DB_PATH) -> List[list]:
        logger.debug("Entering HedgeManager.find_hedges")
        try:
            from uuid import uuid4
            dl = DataLocker.get_instance(db_path)
            raw_positions = dl.read_positions()
            logger.debug(f"Retrieved {len(raw_positions)} raw positions from the database.")

            positions = [dict(pos) for pos in raw_positions]
            logger.debug(
                f"Converted raw positions to dictionaries. Position IDs: {[pos.get('id') for pos in positions]}")

            groups = {}
            for pos in positions:
                wallet = pos.get("wallet_name")
                asset = pos.get("asset_type")
                if wallet and asset:
                    key = (wallet.strip(), asset.strip())
                    groups.setdefault(key, []).append(pos)
                    logger.debug(
                        f"Added position id={pos.get('id')} with type '{pos.get('position_type')}' to group {key}.")
                else:
                    logger.debug(f"Skipping position id={pos.get('id')} due to missing wallet or asset info.")
            logger.debug(f"Formed {len(groups)} groups from positions.")

            for key, pos_list in groups.items():
                pos_types = [pos.get("position_type", "").strip().lower() for pos in pos_list]
                logger.debug(f"Group {key}: contains positions with types {pos_types} (Total: {len(pos_list)})")

            hedged_groups = []
            for key, pos_list in groups.items():
                has_long = any(pos.get("position_type", "").strip().lower() == "long" for pos in pos_list)
                has_short = any(pos.get("position_type", "").strip().lower() == "short" for pos in pos_list)
                logger.debug(f"Group {key}: has_long={has_long}, has_short={has_short}")
                if has_long and has_short:
                    hedge_id = str(uuid4())
                    logger.debug(f"Group {key} qualifies for hedge. Assigning hedge_id {hedge_id}.")
                    for pos in pos_list:
                        pos["hedge_buddy_id"] = hedge_id
                        cursor = dl.conn.cursor()
                        cursor.execute("UPDATE positions SET hedge_buddy_id = ? WHERE id = ?", (hedge_id, pos["id"]))
                        dl.conn.commit()
                        cursor.close()
                        logger.debug(f"Updated position id={pos.get('id')} with hedge_buddy_id {hedge_id}.")
                    hedged_groups.append(pos_list)
                    logger.debug(f"Group {key} added as a hedge group. Total positions in group: {len(pos_list)}")
                else:
                    logger.debug(f"Group {key} does not qualify (requires both long and short).")
            logger.info(f"Found {len(hedged_groups)} hedge group(s).")
            logger.debug("Exiting HedgeManager.find_hedges successfully.")
            return hedged_groups
        except Exception as e:
            logger.error(f"Error in find_hedges: {e}", exc_info=True)
            return []

    @staticmethod
    def clear_hedge_data(db_path: str = DB_PATH) -> None:
        """
        Clears hedge association data by setting the hedge_buddy_id field to NULL for all positions in the database.
        """
        try:
            dl = DataLocker.get_instance(db_path)
            cursor = dl.conn.cursor()
            cursor.execute("UPDATE positions SET hedge_buddy_id = NULL WHERE hedge_buddy_id IS NOT NULL")
            dl.conn.commit()
            cursor.close()
            logger.info("Hedge association data cleared.")
        except Exception as e:
            logger.error(f"Error in clear_hedge_data: {e}", exc_info=True)
