#!/usr/bin/env python
"""
unified_logger.py

This module implements a unified logger for the application.
It writes logs in JSON format to separate files for operations, alerts, and cyclone events,
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
from config.config_constants import BASE_DIR, LOG_DATE_FORMAT, LOG_DIR

# Ensure the logs directory exists using LOG_DIR.
LOGS_DIR = str(LOG_DIR)
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Custom JSON Formatter for log entries.
class JsonFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=LOG_DATE_FORMAT):
        super().__init__(fmt, datefmt)

    def formatTime(self, record, datefmt=None):
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

class LogTypeFilter(logging.Filter):
    def __init__(self, log_type):
        super().__init__()
        self.log_type = log_type

    def filter(self, record):
        return getattr(record, "log_type", "") == self.log_type

class UnifiedLogger:
    def __init__(self, operations_log_filename: str = None, alert_log_filename: str = None, cyclone_log_filename: str = None):
        if operations_log_filename is None:
            operations_log_filename = os.path.join(LOGS_DIR, "operations_log.txt")
        if alert_log_filename is None:
            alert_log_filename = os.path.join(LOGS_DIR, "alert_monitor_log.txt")
        if cyclone_log_filename is None:
            cyclone_log_filename = os.path.join(LOGS_DIR, "cyclone_log.txt")

        self.operations_log_filename = operations_log_filename
        self.alert_log_filename = alert_log_filename
        self.cyclone_log_filename = cyclone_log_filename

        self.logger = logging.getLogger("UnifiedLogger")
        self.logger.setLevel(logging.DEBUG)

        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        json_formatter = JsonFormatter(datefmt=LOG_DATE_FORMAT)

        op_handler = logging.FileHandler(self.operations_log_filename, encoding="utf-8")
        op_handler.setLevel(logging.INFO)
        op_handler.setFormatter(json_formatter)
        op_handler.addFilter(LogTypeFilter("operation"))

        alert_handler = logging.FileHandler(self.alert_log_filename, encoding="utf-8")
        alert_handler.setLevel(logging.INFO)
        alert_handler.setFormatter(json_formatter)
        alert_handler.addFilter(LogTypeFilter("alert"))

        cyclone_handler = logging.FileHandler(self.cyclone_log_filename, encoding="utf-8")
        cyclone_handler.setLevel(logging.INFO)
        cyclone_handler.setFormatter(json_formatter)
        cyclone_handler.addFilter(LogTypeFilter("cyclone"))

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(json_formatter)

        self.logger.addHandler(op_handler)
        self.logger.addHandler(alert_handler)
        self.logger.addHandler(cyclone_handler)
        self.logger.addHandler(console_handler)

    def log_operation(self, operation_type: str, primary_text: str, source: str = "", file: str = "", extra_data: dict = None):
        extra = {
            "source": source,
            "operation_type": operation_type,
            "log_type": "operation",
            "file": file
        }
        if extra_data:
            extra.update(extra_data)
        self.logger.info(primary_text, extra=extra)

    def log_alert(self, operation_type: str, primary_text: str, source: str = "", file: str = "", extra_data: dict = None):
        extra = {
            "source": source,
            "operation_type": operation_type,
            "log_type": "alert",
            "file": file
        }
        if extra_data:
            extra.update(extra_data)
        self.logger.info(primary_text, extra=extra)

    def log_cyclone(self, operation_type: str, primary_text: str, source: str = "", file: str = "", extra_data: dict = None):
        extra = {
            "source": source,
            "operation_type": operation_type,
            "log_type": "cyclone",
            "file": file
        }
        if extra_data:
            extra.update(extra_data)
        self.logger.info(primary_text, extra=extra)

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
