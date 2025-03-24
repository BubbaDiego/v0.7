from enum import Enum
from typing import Optional
from datetime import datetime
from uuid import uuid4

class AssetType(str, Enum):
    BTC = "BTC"
    ETH = "ETH"
    SOL = "SOL"
    OTHER = "OTHER"  # New generic type for additional assets

class SourceType(str, Enum):
    AUTO = "Auto"
    MANUAL = "Manual"
    IMPORT = "Import"
    COINGECKO = "CoinGecko"
    COINMARKETCAP = "CoinMarketCap"
    COINPAPRIKA = "CoinPaprika"
    BINANCE = "Binance"

class Status(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"

class AlertType(str, Enum):
    PRICE_THRESHOLD = "PriceThreshold"
    DELTA_CHANGE = "DeltaChange"
    TRAVEL_PERCENT_LIQUID = "TravelPercent"
    TIME = "Time"
    PROFIT = "Profit"         # New alert type for profit alerts
    HEAT_INDEX = "HeatIndex"  # New alert type for heat index alerts

class AlertClass(str, Enum):
    SYSTEM = "System"
    MARKET = "Market"
    POSITION = "Position"

class NotificationType(str, Enum):
    EMAIL = "Email"
    SMS = "SMS"
    ACTION = "Action"


class Price:
    """
    Represents pricing details for a given asset.
    Manually validates current_price > 0, previous_price >= 0, and
    ensures previous_update_time <= last_update_time if both set.
    """
    def __init__(
        self,
        id: Optional[str],
        asset_type: AssetType,
        current_price: float,
        previous_price: float,
        last_update_time: datetime,
        previous_update_time: Optional[datetime],
        source: SourceType
    ):
        if current_price <= 0:
            raise ValueError("current_price must be > 0")
        if previous_price < 0:
            raise ValueError("previous_price cannot be negative")

        if not last_update_time:
            last_update_time = datetime.utcnow()

        if previous_update_time and previous_update_time > last_update_time:
            raise ValueError("previous_update_time cannot be after last_update_time")

        self.id = id
        self.asset_type = asset_type
        self.current_price = current_price
        self.previous_price = previous_price
        self.last_update_time = last_update_time
        self.previous_update_time = previous_update_time
        self.source = source

    def __repr__(self):
        return (
            f"Price(id={self.id!r}, asset_type={self.asset_type!r}, "
            f"current_price={self.current_price}, previous_price={self.previous_price}, "
            f"last_update_time={self.last_update_time}, previous_update_time={self.previous_update_time}, "
            f"source={self.source!r})"
        )


class Alert:
    """
    Represents alert configuration for monitoring certain thresholds.
    """
    def __init__(
        self,
        id: str,
        alert_type: AlertType,
        alert_class: AlertClass,  # New field: indicates if the alert is Market or Position related
        trigger_value: float,
        notification_type: NotificationType,
        last_triggered: Optional[datetime],
        status: Status,
        frequency: int,
        counter: int,
        liquidation_distance: float,
        target_travel_percent: float,
        liquidation_price: float,
        notes: Optional[str],
        position_reference_id: Optional[str]
    ):
        self.id = id
        self.alert_type = alert_type
        self.alert_class = alert_class
        self.trigger_value = trigger_value
        self.notification_type = notification_type
        self.last_triggered = last_triggered
        self.status = status
        self.frequency = frequency
        self.counter = counter
        self.liquidation_distance = liquidation_distance
        self.target_travel_percent = target_travel_percent
        self.liquidation_price = liquidation_price
        self.notes = notes
        self.position_reference_id = position_reference_id

    def __repr__(self):
        return (
            f"Alert(id={self.id!r}, alert_type={self.alert_type!r}, alert_class={self.alert_class!r}, "
            f"trigger_value={self.trigger_value}, notification_type={self.notification_type!r}, "
            f"last_triggered={self.last_triggered}, status={self.status!r}, frequency={self.frequency}, "
            f"counter={self.counter}, liquidation_distance={self.liquidation_distance}, "
            f"target_travel_percent={self.target_travel_percent}, liquidation_price={self.liquidation_price}, "
            f"notes={self.notes!r}, position_reference_id={self.position_reference_id!r})"
        )


class Position:
    """
    Represents a trading position, with manual validation for current_travel_percent.
    """
    def __init__(
        self,
        id: Optional[str] = None,
        asset_type: str = AssetType.OTHER,  # default now uses a generic type if not specified
        position_type: str = "",
        entry_price: float = 0.0,
        liquidation_price: float = 0.0,
        current_travel_percent: float = 0.0,
        value: float = 0.0,
        collateral: float = 0.0,
        size: float = 0.0,
        leverage: float = 0.0,
        wallet: str = "Default",
        last_updated: Optional[datetime] = None,
        alert_reference_id: Optional[str] = None,
        hedge_buddy_id: Optional[str] = None,
        current_price: Optional[float] = 0.0,
        liquidation_distance: Optional[float] = None,
        heat_index: float = 0.0,
        current_heat_index: float = 0.0,
        pnl_after_fees_usd: float = 0.0  # NEW: pnlAfterFeesUsd field
    ):
        # Autogenerate an 'id' if not provided
        if id is None:
            id = str(uuid4())

        if last_updated is None:
            last_updated = datetime.now()

        # Validate current_travel_percent
        if not -11500.0 <= current_travel_percent <= 1000.0:
            raise ValueError("current_travel_percent must be between -11500 and 1000")

        self.id = id
        self.asset_type = asset_type
        self.position_type = position_type
        self.entry_price = entry_price
        self.liquidation_price = liquidation_price
        self.current_travel_percent = current_travel_percent
        self.value = value
        self.collateral = collateral
        self.size = size
        self.leverage = leverage
        self.wallet = wallet
        self.last_updated = last_updated
        self.alert_reference_id = alert_reference_id
        self.hedge_buddy_id = hedge_buddy_id
        self.current_price = current_price
        self.liquidation_distance = liquidation_distance
        self.heat_index = heat_index
        self.current_heat_index = current_heat_index
        self.pnl_after_fees_usd = pnl_after_fees_usd

    def __repr__(self):
        return (
            f"Position(id={self.id!r}, asset_type={self.asset_type!r}, position_type={self.position_type!r}, "
            f"entry_price={self.entry_price}, liquidation_price={self.liquidation_price}, "
            f"current_travel_percent={self.current_travel_percent}, value={self.value}, "
            f"collateral={self.collateral}, size={self.size}, leverage={self.leverage}, wallet={self.wallet!r}, "
            f"last_updated={self.last_updated}, alert_reference_id={self.alert_reference_id!r}, "
            f"hedge_buddy_id={self.hedge_buddy_id!r}, current_price={self.current_price}, "
            f"liquidation_distance={self.liquidation_distance}, heat_index={self.heat_index}, "
            f"current_heat_index={self.current_heat_index}, pnl_after_fees_usd={self.pnl_after_fees_usd})"
        )


from typing import Optional, List
from datetime import datetime
from uuid import uuid4


class Hedge:
    """
    Represents a hedge comprising two or more positions with associated alerts.
    Tracks long and short exposures as well as aggregated heat index values.

    Attributes:
        id (str): Unique identifier for the hedge.
        positions (List[str]): List of position IDs included in this hedge.
        total_long_size (float): Total size of all long positions.
        total_short_size (float): Total size of all short positions.
        long_heat_index (float): Aggregated heat index for long positions.
        short_heat_index (float): Aggregated heat index for short positions.
        total_heat_index (float): Overall heat index (could be computed as a function of long and short indices).
        created_at (datetime): Timestamp when the hedge was created.
        updated_at (datetime): Timestamp when the hedge was last updated.
        notes (Optional[str]): Optional notes or description about the hedge.
    """

    def __init__(
            self,
            id: Optional[str] = None,
            positions: Optional[List[str]] = None,
            total_long_size: float = 0.0,
            total_short_size: float = 0.0,
            long_heat_index: float = 0.0,
            short_heat_index: float = 0.0,
            total_heat_index: float = 0.0,
            created_at: Optional[datetime] = None,
            updated_at: Optional[datetime] = None,
            notes: Optional[str] = None
    ):
        if id is None:
            id = str(uuid4())
        if positions is None:
            positions = []
        if created_at is None:
            created_at = datetime.now()
        if updated_at is None:
            updated_at = datetime.now()

        self.id = id
        self.positions = positions
        self.total_long_size = total_long_size
        self.total_short_size = total_short_size
        self.long_heat_index = long_heat_index
        self.short_heat_index = short_heat_index
        self.total_heat_index = total_heat_index
        self.created_at = created_at
        self.updated_at = updated_at
        self.notes = notes

    def __repr__(self):
        return (
            f"Hedge(id={self.id!r}, positions={self.positions!r}, "
            f"total_long_size={self.total_long_size}, total_short_size={self.total_short_size}, "
            f"long_heat_index={self.long_heat_index}, short_heat_index={self.short_heat_index}, "
            f"total_heat_index={self.total_heat_index}, created_at={self.created_at}, "
            f"updated_at={self.updated_at}, notes={self.notes!r})"
        )


class CryptoWallet:
    """
    Represents a crypto wallet with:
      - name:           e.g., "VaderVault"
      - public_address: a single public address (for demonstration)
      - private_address: not recommended for production usage, but okay for dev
      - image_path:     path or URL to an identifying image
      - balance:        total balance in USD (or any currency you like)
    """
    def __init__(
            self,
            name: str,
            public_address: str,
            private_address: str,
            image_path: str = "",
            balance: float = 0.0
    ):
        self.name = name
        self.public_address = public_address
        self.private_address = private_address
        self.image_path = image_path
        self.balance = balance

    def __repr__(self):
        return (
            f"CryptoWallet(name={self.name!r}, "
            f"public_address={self.public_address!r}, "
            f"private_address={self.private_address!r}, "
            f"image_path={self.image_path!r}, "
            f"balance={self.balance})"
        )


class Broker:
    """
    Represents a broker (e.g., an exchange or trading platform).
    """
    def __init__(
        self,
        name: str,
        image_path: str,
        web_address: str,
        total_holding: float = 0.0
    ):
        self.name = name
        self.image_path = image_path
        self.web_address = web_address
        self.total_holding = total_holding

    def __repr__(self):
        return (
            f"Broker(name={self.name!r}, "
            f"image_path={self.image_path!r}, "
            f"web_address={self.web_address!r}, "
            f"total_holding={self.total_holding})"
        )
