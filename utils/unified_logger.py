import os
import sys
import json
import logging
import pytz
from datetime import datetime
from config.config_constants import BASE_DIR

if sys.platform.startswith('win'):
    DATE_FORMAT = "%#m-%#d-%y : %#I:%M:%S %p"
else:
    DATE_FORMAT = "%-m-%-d-%y : %-I:%M:%S %p"

# Custom JSON formatter using the unified DATE_FORMAT.
class JsonFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=DATE_FORMAT):
        super().__init__(fmt, datefmt)

    def format(self, record):
        record_dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "source": getattr(record, "source", ""),
            "operation_type": getattr(record, "operation_type", ""),
            "file": getattr(record, "file", ""),
            "log_type": getattr(record, "log_type", "")
        }
        return json.dumps(record_dict, ensure_ascii=False)

# Filter to allow only records of a given log_type.
class LogTypeFilter(logging.Filter):
    def __init__(self, log_type):
        super().__init__()
        self.log_type = log_type

    def filter(self, record):
        return getattr(record, "log_type", "") == self.log_type

class UnifiedLogger:
    def __init__(self,
                 operations_log_filename: str = None,
                 alert_log_filename: str = None):
        if operations_log_filename is None:
            operations_log_filename = os.path.join(str(BASE_DIR), "operations_log.txt")
        if alert_log_filename is None:
            alert_log_filename = os.path.join(str(BASE_DIR), "alert_monitor_log.txt")

        self.operations_log_filename = operations_log_filename
        self.alert_log_filename = alert_log_filename

        self.logger = logging.getLogger("UnifiedLogger")
        self.logger.setLevel(logging.DEBUG)
        # Remove any existing handlers.
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        json_formatter = JsonFormatter(datefmt=DATE_FORMAT)

        # File handler for operations logs.
        op_handler = logging.FileHandler(self.operations_log_filename, encoding="utf-8")
        op_handler.setLevel(logging.INFO)
        op_handler.setFormatter(json_formatter)
        op_handler.addFilter(LogTypeFilter("operation"))

        # File handler for alert logs.
        alert_handler = logging.FileHandler(self.alert_log_filename, encoding="utf-8")
        alert_handler.setLevel(logging.INFO)
        alert_handler.setFormatter(json_formatter)
        alert_handler.addFilter(LogTypeFilter("alert"))

        # Optional: Console handler.
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(json_formatter)

        self.logger.addHandler(op_handler)
        self.logger.addHandler(alert_handler)
        self.logger.addHandler(console_handler)

        self.pst = pytz.timezone("US/Pacific")

    def log_operation(self, operation_type: str, primary_text: str, source: str = "", file: str = ""):
        self.logger.debug("About to log operation: operation_type=%s, primary_text=%s, source=%s, file=%s",
                          operation_type, primary_text, source, file)
        extra = {"source": source, "operation_type": operation_type, "log_type": "operation", "file": file}
        self.logger.info(primary_text, extra=extra)
        self.logger.debug("Logged operation entry with operation_type=%s", operation_type)

    def log_alert(self, operation_type: str, primary_text: str, source: str = "", file: str = ""):
        self.logger.debug("About to log alert: operation_type=%s, primary_text=%s, source=%s, file=%s",
                          operation_type, primary_text, source, file)
        extra = {"source": source, "operation_type": operation_type, "log_type": "alert", "file": file}
        self.logger.info(primary_text, extra=extra)
        self.logger.debug("Logged alert entry with operation_type=%s", operation_type)

# Example usage:
if __name__ == "__main__":
    u_logger = UnifiedLogger()
    u_logger.log_operation(
        operation_type="Launch pad started",
        primary_text="Launch Pad - Started",
        source="System Start-up",
        file="launch_pad"
    )
    u_logger.log_alert(
        operation_type="Alert Check",
        primary_text="Checking 5 positions for alerts",
        source="System",
        file="alert_manager"
    )
