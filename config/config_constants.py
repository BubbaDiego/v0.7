import os
import sys
from pathlib import Path


import sys
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

ALERT_MONITOR_LOG_FILENAME = os.getenv("ALERT_MONITOR_LOG_FILENAME", "alert_monitor_log.txt")
ALERT_MONITOR_LOG_PATH = BASE_DIR / ALERT_MONITOR_LOG_FILENAME

ALERT_LIMITS_FILENAME = os.getenv("ALERT_LIMITS_FILENAME", "alert_limits.json")
ALERT_LIMITS_PATH = BASE_DIR / "config" / ALERT_LIMITS_FILENAME

SONIC_SAUCE_FILENAME = os.getenv("SONIC_SAUCE_FILENAME", "sonic_sauce.json")
SONIC_SAUCE_PATH = BASE_DIR / SONIC_SAUCE_FILENAME

# Added new theme config constants
THEME_CONFIG_FILENAME = os.getenv("THEME_CONFIG_FILENAME", "theme_config.json")
THEME_CONFIG_PATH = BASE_DIR / "config" / THEME_CONFIG_FILENAME

HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", os.path.join(BASE_DIR, "monitor", "heartbeat.txt"))

#HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", "/home/BubbaDiego/v0.7/monitor/heartbeat.txt")



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
