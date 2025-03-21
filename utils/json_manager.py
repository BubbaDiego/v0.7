# json_manager.py

import json
import inspect
from enum import Enum
from utils.unified_logger import UnifiedLogger
from config.config_constants import ALERT_LIMITS_PATH, THEME_CONFIG_PATH, SONIC_SAUCE_PATH

class JsonType(Enum):
    ALERT_LIMITS = "alert_limits.json"
    THEME_CONFIG = "theme_config.json"
    SONIC_SAUCE = "sonic_sauce.json"
    SONIC_CONFIG = "sonic_config.json"
    COMM_CONFIG = "comm_config.json"

class JsonManager:
    def __init__(self, logger=None):
        if logger is None:
            self.logger = UnifiedLogger()
        else:
            self.logger = logger

    def load(self, file_path: str, json_type: JsonType = None):
        """Load and return the JSON data from the specified file path."""
        if json_type:
            path_map = {
                JsonType.ALERT_LIMITS: ALERT_LIMITS_PATH,
                JsonType.THEME_CONFIG: THEME_CONFIG_PATH,
                JsonType.SONIC_SAUCE: SONIC_SAUCE_PATH,
                # Add mappings for SONIC_CONFIG and COMM_CONFIG if needed.
            }
            file_path = str(path_map.get(json_type, file_path))

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            caller = inspect.getframeinfo(inspect.stack()[1][0])
            json_str = json.dumps(data)
            if len(json_str) > 200:
                json_str = json_str[:200] + "..."
            type_info = f" [JSON Type: {json_type.name}]" if json_type else ""

            # --- Verification Block ---
            verification_passed = True
            verification_message = "No verification rules applied."
            if json_type == JsonType.SONIC_SAUCE:
                required_keys = ["hedge_modifiers", "heat_modifiers"]
                missing_keys = [k for k in required_keys if k not in data]
                if missing_keys:
                    verification_passed = False
                    verification_message = f"Missing keys: {missing_keys}"
                else:
                    verification_message = f"All required keys present: {list(data.keys())}"
            elif json_type == JsonType.THEME_CONFIG:
                if not isinstance(data, dict):
                    verification_passed = False
                    verification_message = "Theme config is not a dictionary."
                else:
                    verification_message = f"Theme config keys: {list(data.keys())}"
            # You can add additional verification for other types if needed.

            if verification_passed:
                self.logger.log_operation(
                    operation_type="JSON Verified",
                    primary_text=(f"Verification passed for {file_path} (JSON Type: {json_type.name}). {verification_message}"),
                    source="system",
                    file=file_path,
                    extra_data={"json_type": json_type.name}
                )
            else:
                self.logger.log_operation(
                    operation_type="JSON Verification Failed",
                    primary_text=(f"Verification failed for {file_path} (JSON Type: {json_type.name}). {verification_message}"),
                    source="system",
                    file=file_path,
                    extra_data={"json_type": json_type.name}
                )

            return data
        except Exception as e:
            caller = inspect.getframeinfo(inspect.stack()[1][0])
            type_info = f" [JSON Type: {json_type.name}]" if json_type else ""
            self.logger.log_operation(
                operation_type="Load JSON Failed",
                primary_text=(f"Failed to load {file_path}{type_info} by system at {caller.filename}:{caller.lineno}: {e}"),
                source="system",
                file=f"{file_path} ({caller.filename}:{caller.lineno})",
                extra_data={"json_type": json_type.name if json_type else ""}
            )
            raise

    def save(self, file_path: str, data, json_type: JsonType = None):
        """Save the JSON data to the specified file path."""
        if json_type:
            path_map = {
                JsonType.ALERT_LIMITS: ALERT_LIMITS_PATH,
                JsonType.THEME_CONFIG: THEME_CONFIG_PATH,
                JsonType.SONIC_SAUCE: SONIC_SAUCE_PATH,
                # Add additional mappings if needed.
            }
            file_path = str(path_map.get(json_type, file_path))

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            caller = inspect.getframeinfo(inspect.stack()[1][0])
            json_str = json.dumps(data)
            if len(json_str) > 200:
                json_str = json_str[:200] + "..."
            type_info = f" [JSON Type: {json_type.name}]" if json_type else ""
            self.logger.log_operation(
                operation_type="JSON Saved",
                primary_text=(f"Successfully saved {file_path}{type_info} by system at {caller.filename}:{caller.lineno}. Data: {json_str}"),
                source="system",
                file=f"{file_path} ({caller.filename}:{caller.lineno})",
                extra_data={"json_type": json_type.name if json_type else ""}
            )
        except Exception as e:
            caller = inspect.getframeinfo(inspect.stack()[1][0])
            type_info = f" [JSON Type: {json_type.name}]" if json_type else ""
            self.logger.log_operation(
                operation_type="Save JSON Failed",
                primary_text=(f"Failed to save {file_path}{type_info} by system at {caller.filename}:{caller.lineno}: {e}"),
                source="system",
                file=f"{file_path} ({caller.filename}:{caller.lineno})",
                extra_data={"json_type": json_type.name if json_type else ""}
            )
            raise

    def deep_merge(self, source: dict, updates: dict) -> dict:
        """
        Recursively merges updates into the source dictionary.
        Logs operations for each key update and overall success or failure.
        """
        try:
            for key, value in updates.items():
                if key in source and isinstance(source[key], dict) and isinstance(value, dict):
                    self.logger.log_operation(
                        operation_type="Deep Merge",
                        primary_text=f"Deep merging key: {key}",
                        source="JsonManager",
                        file="JsonManager.deep_merge"
                    )
                    source[key] = self.deep_merge(source[key], value)
                else:
                    self.logger.log_operation(
                        operation_type="Deep Merge",
                        primary_text=f"Updating key: {key} with value: {value}",
                        source="JsonManager",
                        file="JsonManager.deep_merge"
                    )
                    source[key] = value
            self.logger.log_operation(
                operation_type="Deep Merge Success",
                primary_text="Deep merge completed successfully.",
                source="JsonManager",
                file="JsonManager.deep_merge"
            )
            return source
        except Exception as e:
            self.logger.log_operation(
                operation_type="Deep Merge Failure",
                primary_text=f"Deep merge failed with error: {e}",
                source="JsonManager",
                file="JsonManager.deep_merge"
            )
            raise
