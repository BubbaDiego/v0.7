"""
hedge_manager.py

This module defines the HedgeManager class which is responsible for:
  - Scanning positions for hedge links (via hedge_buddy_id).
  - Creating Hedge instances that represent grouped positions.
  - Aggregating metrics such as total long size, total short size, long/short heat indices,
    and total heat index.
  - Providing access to hedge data via methods like get_hedges().
  - Logging an operations entry when hedges are checked.

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
        """
        Build hedge groups by scanning positions for a common hedge_buddy_id.
        Only groups with two or more positions are turned into Hedge instances.
        Aggregated metrics such as total long/short sizes and heat indices are computed.
        Logs an operations entry upon successful hedge checking.
        """
        # Group positions by hedge_buddy_id
        hedge_groups = {}
        for pos in self.positions:
            # Only consider positions with a defined hedge_buddy_id
            if pos.hedge_buddy_id:
                key = pos.hedge_buddy_id
                if key not in hedge_groups:
                    hedge_groups[key] = []
                hedge_groups[key].append(pos)

        # Clear any existing hedges
        self.hedges = []
        # Create Hedge objects for groups with at least 2 positions
        for key, pos_group in hedge_groups.items():
            if len(pos_group) >= 2:
                hedge = Hedge(id=str(uuid4()))
                hedge.positions = [p.id for p in pos_group]

                total_long = 0.0
                total_short = 0.0
                long_heat = 0.0
                short_heat = 0.0

                for p in pos_group:
                    # Determine if position is long or short based on position_type.
                    # (Assumes position_type is set to "long" or "short" in lowercase.)
                    if p.position_type.lower() == "long":
                        total_long += p.size
                        long_heat += p.heat_index
                    elif p.position_type.lower() == "short":
                        total_short += p.size
                        short_heat += p.heat_index
                    else:
                        # If position_type isn't set, ignore or handle differently.
                        pass

                hedge.total_long_size = total_long
                hedge.total_short_size = total_short
                hedge.long_heat_index = long_heat
                hedge.short_heat_index = short_heat
                # For total heat index, we simply sum here (consider weighting if needed).
                hedge.total_heat_index = long_heat + short_heat
                hedge.created_at = datetime.now()
                hedge.updated_at = datetime.now()
                hedge.notes = f"Hedge created from positions with hedge_buddy_id: {key}"

                self.hedges.append(hedge)

        # Log an operations entry for the hedge check
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


# Example usage:
if __name__ == "__main__":
    # Dummy positions for testing
    from data.models import Position

    # Create some test Position instances with hedge_buddy_id set.
    pos1 = Position(
        asset_type="BTC",
        position_type="long",
        size=1.5,
        heat_index=10.0,
        hedge_buddy_id="group1"
    )
    pos2 = Position(
        asset_type="BTC",
        position_type="short",
        size=0.5,
        heat_index=5.0,
        hedge_buddy_id="group1"
    )
    pos3 = Position(
        asset_type="ETH",
        position_type="long",
        size=2.0,
        heat_index=8.0,
        hedge_buddy_id="group2"
    )
    pos4 = Position(
        asset_type="ETH",
        position_type="long",
        size=1.0,
        heat_index=6.0,
        hedge_buddy_id="group2"
    )
    pos5 = Position(
        asset_type="SOL",
        position_type="long",
        size=3.0,
        heat_index=4.0,
        hedge_buddy_id=None  # This one will not be grouped
    )

    positions = [pos1, pos2, pos3, pos4, pos5]
    manager = HedgeManager(positions)
    hedges = manager.get_hedges()
    for hedge in hedges:
        print(hedge)
