import os
import sys
from pathlib import Path
import json

if sys.platform.startswith('win'):
    LOG_DATE_FORMAT = "%#m-%#d-%y : %#I:%M:%S %p %Z"
else:
    LOG_DATE_FORMAT = "%-m-%-d-%y : %-I:%M:%S %p %Z"

# Determine BASE_DIR from an environment variable, or default to one level up from this file
BASE_DIR = Path(os.getenv("BASE_DIR", Path(__file__).resolve().parent.parent))

# Use environment variables for file names, with defaults provided
DB_FILENAME = os.getenv("DB_FILENAME", "mother_brain.db")
CONFIG_FILENAME = os.getenv("CONFIG_FILENAME", "sonic_config.json")

# Construct the full paths using pathlib for cross-platform compatibility
DB_PATH = BASE_DIR / "data" / DB_FILENAME
CONFIG_PATH = BASE_DIR / CONFIG_FILENAME

# Add LOG_DIR constant (use pathlib for consistency)
LOG_DIR = BASE_DIR / "logs"

ALERT_MONITOR_LOG_FILENAME = os.getenv("ALERT_MONITOR_LOG_FILENAME", "alert_monitor_log.txt")
ALERT_MONITOR_LOG_PATH = BASE_DIR / ALERT_MONITOR_LOG_FILENAME

ALERT_LIMITS_FILENAME = os.getenv("ALERT_LIMITS_FILENAME", "alert_limits.json")
ALERT_LIMITS_PATH = BASE_DIR / "config" / ALERT_LIMITS_FILENAME

SONIC_SAUCE_FILENAME = os.getenv("SONIC_SAUCE_FILENAME", "sonic_sauce.json")
SONIC_SAUCE_PATH = BASE_DIR / "config" / SONIC_SAUCE_FILENAME

COM_CONFIG_FILENAME = os.getenv("COM_CONFIG_FILENAME", "com_config.json")
COM_CONFIG_PATH = BASE_DIR / "config" / COM_CONFIG_FILENAME

# Added new theme config constants
THEME_CONFIG_FILENAME = os.getenv("THEME_CONFIG_FILENAME", "theme_config.json")
THEME_CONFIG_PATH = BASE_DIR / "config" / THEME_CONFIG_FILENAME

HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", os.path.join(BASE_DIR, "monitor", "sonic_ledger.json"))
# HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", "/home/BubbaDiego/v0.7/monitor/heartbeat.txt")

# Image asset paths
SPACE_WALL_IMAGE = "images/space_wall2.jpg"

BTC_LOGO_IMAGE = "images/btc_logo.png"
ETH_LOGO_IMAGE = "images/eth_logo.png"
SOL_LOGO_IMAGE = "images/sol_logo.png"
THEME_CONFIG_WALLPAPER = "images/wallpaper_theme_page"

R2VAULT_IMAGE = "images/r2vault.jpg"
OBIVAULT_IMAGE = "images/obivault.jpg"
LANDOVAULT_IMAGE = "images/landovault.jpg"
VADERVAULT_IMAGE = "images/vadervault.jpg"

# Polygon RPC endpoint (you can replace with your preferred RPC URL)
POLYGON_RPC_URL = "https://polygon-rpc.com"

# Aave V3 contract addresses on Polygon
# Use your provided valid contract addresses or test ones:
POOL_ADDRESS = "0x794a61358D6845594F94dc1DB02A252b5b4814aD"             # Aave V3 Pool contract on Polygon
POOL_PROVIDER_ADDR = "0xa97684ead0e402DC232d5A977953DF7ECBaB3CDb"         # PoolAddressesProvider
# Updated DATA_PROVIDER_ADDR with correct EIP-55 checksum:
DATA_PROVIDER_ADDR = "0x69C7C30F2D9A9355Ab0F2F05aF28805F131B18C9"         # UI Pool Data Provider
LIQUIDATION_DATA_ADDR = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdefABCD"         # Example Liquidation Data Provider

# Minimal ABI definitions for public wallet information access

# For the Pool contract (not needed for read-only wallet info, so we leave it empty)
POOL_ABI = []

# Minimal ABI for the UI Pool Data Provider (for getUserReservesData)
UI_POOL_DATA_PROVIDER_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "provider", "type": "address"},
            {"internalType": "address", "name": "user", "type": "address"}
        ],
        "name": "getUserReservesData",
        "outputs": [
            {
                "components": [
                    {"internalType": "address", "name": "reserve", "type": "address"},
                    {"internalType": "uint256", "name": "currentATokenBalance", "type": "uint256"},
                    {"internalType": "uint256", "name": "stableDebt", "type": "uint256"},
                    {"internalType": "uint256", "name": "variableDebt", "type": "uint256"}
                ],
                "internalType": "struct DataTypes.UserReserveData[]",
                "name": "",
                "type": "tuple[]"
            },
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# Minimal ABI for the Liquidation Data Provider (for getUserPositionFullInfo)
LIQ_DATA_PROVIDER_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "user", "type": "address"}
        ],
        "name": "getUserPositionFullInfo",
        "outputs": [
            {"internalType": "uint256", "name": "totalCollateralBase", "type": "uint256"},
            {"internalType": "uint256", "name": "totalDebtBase", "type": "uint256"},
            {"internalType": "uint256", "name": "availableBorrowsBase", "type": "uint256"},
            {"internalType": "uint256", "name": "currentLiquidationThreshold", "type": "uint256"},
            {"internalType": "uint256", "name": "ltv", "type": "uint256"},
            {"internalType": "uint256", "name": "healthFactor", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# Optional: Mappings for assets (if needed)
ASSET_SYMBOLS = {
    # "0xAssetAddress": "USDC",
    # Add your asset addresses and symbols here.
}
ASSET_DECIMALS = {
    # "0xAssetAddress": 6,
    # Add your asset addresses and decimal values here.
}
