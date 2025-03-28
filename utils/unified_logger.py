#!/usr/bin/env python
"""
unified_logger.py

This module implements a unified logger for the application.
It writes logs in JSON format to separate files for operations, alerts, and now cyclone events,
and also outputs logs to the console.
The log records include custom fields such as source, operation type, file name,
and an optional 'json_type' field.
Timestamps are formatted in US/Pacific time using a configurable date format.
"""

import os
import sys
import json
import logging
import pytz
from datetime import datetime
from config.config_constants import BASE_DIR, LOG_DATE_FORMAT

# Custom JSON Formatter for log entries.
class JsonFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=LOG_DATE_FORMAT):
        super().__init__(fmt, datefmt)

    def formatTime(self, record, datefmt=None):
        # Convert the record's creation time to US/Pacific time.
        pst = pytz.timezone("US/Pacific")
        dt = datetime.fromtimestamp(record.created, pytz.utc).astimezone(pst)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()

    def format(self, record):
        record_dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "source": getattr(record, "source", ""),
            "operation_type": getattr(record, "operation_type", ""),
            "file": getattr(record, "file", ""),
            "json_type": getattr(record, "json_type", ""),
            "log_type": getattr(record, "log_type", "")
        }
        return json.dumps(record_dict, ensure_ascii=False)

# Filter that allows only log records matching a given log type.
class LogTypeFilter(logging.Filter):
    def __init__(self, log_type):
        super().__init__()
        self.log_type = log_type

    def filter(self, record):
        return getattr(record, "log_type", "") == self.log_type

# The UnifiedLogger class configures multiple handlers for logging.
class UnifiedLogger:
    def __init__(self, operations_log_filename: str = None, alert_log_filename: str = None, cyclone_log_filename: str = None):
        if operations_log_filename is None:
            operations_log_filename = os.path.join(str(BASE_DIR), "operations_log.txt")
        if alert_log_filename is None:
            alert_log_filename = os.path.join(str(BASE_DIR), "alert_monitor_log.txt")
        if cyclone_log_filename is None:
            cyclone_log_filename = os.path.join(str(BASE_DIR), "cyclone_log.txt")

        self.operations_log_filename = operations_log_filename
        self.alert_log_filename = alert_log_filename
        self.cyclone_log_filename = cyclone_log_filename

        # Create a logger named "UnifiedLogger" and set its level to DEBUG.
        self.logger = logging.getLogger("UnifiedLogger")
        self.logger.setLevel(logging.DEBUG)

        # Remove any pre-existing handlers.
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create a JSON formatter with the defined LOG_DATE_FORMAT.
        json_formatter = JsonFormatter(datefmt=LOG_DATE_FORMAT)

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

        # File handler for cyclone logs.
        cyclone_handler = logging.FileHandler(self.cyclone_log_filename, encoding="utf-8")
        cyclone_handler.setLevel(logging.INFO)
        cyclone_handler.setFormatter(json_formatter)
        cyclone_handler.addFilter(LogTypeFilter("cyclone"))

        # Optional console handler.
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(json_formatter)

        # Add handlers to the logger.
        self.logger.addHandler(op_handler)
        self.logger.addHandler(alert_handler)
        self.logger.addHandler(cyclone_handler)
        self.logger.addHandler(console_handler)

    def log_operation(self, operation_type: str, primary_text: str, source: str = "", file: str = "", extra_data: dict = None):
        self.logger.debug("About to log operation: operation_type=%s, primary_text=%s, source=%s, file=%s",
                          operation_type, primary_text, source, file)
        extra = {
            "source": source,
            "operation_type": operation_type,
            "log_type": "operation",
            "file": file
        }
        if extra_data:
            extra.update(extra_data)
        self.logger.info(primary_text, extra=extra)
        self.logger.debug("Logged operation entry with operation_type=%s", operation_type)

    def log_alert(self, operation_type: str, primary_text: str, source: str = "", file: str = "", extra_data: dict = None):
        self.logger.debug("About to log alert: operation_type=%s, primary_text=%s, source=%s, file=%s",
                          operation_type, primary_text, source, file)
        extra = {
            "source": source,
            "operation_type": operation_type,
            "log_type": "alert",
            "file": file
        }
        if extra_data:
            extra.update(extra_data)
        self.logger.info(primary_text, extra=extra)
        self.logger.debug("Logged alert entry with operation_type=%s", operation_type)

    def log_cyclone(self, operation_type: str, primary_text: str, source: str = "", file: str = "", extra_data: dict = None):
        """
        Logs cyclone-related events to the dedicated cyclone log file.
        """
        self.logger.debug("About to log cyclone event: operation_type=%s, primary_text=%s, source=%s, file=%s",
                          operation_type, primary_text, source, file)
        extra = {
            "source": source,
            "operation_type": operation_type,
            "log_type": "cyclone",
            "file": file
        }
        if extra_data:
            extra.update(extra_data)
        self.logger.info(primary_text, extra=extra)
        self.logger.debug("Logged cyclone entry with operation_type=%s", operation_type)

# Example usage:
if __name__ == "__main__":
    u_logger = UnifiedLogger()
    u_logger.log_operation(
        operation_type="Launch pad started",
        primary_text="Launch Pad - Started",
        source="System Start-up",
        file="launch_pad",
        extra_data={"json_type": ""}
    )
    u_logger.log_alert(
        operation_type="Alert Check",
        primary_text="Checking 5 positions for alerts",
        source="System",
        file="alert_manager",
        extra_data={"json_type": ""}
    )
    u_logger.log_cyclone(
        operation_type="Cycle Report",
        primary_text="Cycle report generated successfully",
        source="Cyclone",
        file="cyclone.py"
    )
