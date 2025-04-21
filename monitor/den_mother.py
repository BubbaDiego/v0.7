#!/usr/bin/env python3
import os
import sys
import time
import json
import logging
import argparse
import inspect
from datetime import datetime, timedelta, timezone
import pytz

# Set logging to use Pacific Standard Time (PST)
PST = pytz.timezone("America/Los_Angeles")
logging.Formatter.converter = lambda *args: datetime.now(PST).timetuple()
logger = logging.getLogger("DenMother")
logger.setLevel(logging.INFO)

# Ensure BASE_DIR is added to the path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from config.config_constants import BASE_DIR, CONFIG_PATH
from common_monitor_utils import load_timer_config, update_timer_config
from utils.unified_logger import UnifiedLogger
from alerts.alert_manager import trigger_twilio_flow
from xcom.xcom import send_email, send_sms, load_com_config

# Define ledger files for separate monitors
LEDGER_FILES = {
    "PriceMonitor": os.path.join(BASE_DIR, "monitor", "price_ledger.json"),
    "PositionMonitor": os.path.join(BASE_DIR, "monitor", "position_ledger.json")
}
HTML_REPORT_FILE = os.path.join(BASE_DIR, "monitor", "den_mother_report.html")

# Shared logger
u_logger = UnifiedLogger()


def log_operation(operation_type: str, primary_text: str, source: str, file: str):
    lineno = inspect.currentframe().f_back.f_lineno
    extra = {
        "source": source,
        "operation_type": operation_type,
        "log_type": "operation",
        "file": file,
        "caller_lineno": lineno
    }
    u_logger.logger.info(primary_text, extra=extra)


def write_ledger(component: str, status: str, message: str, metadata: dict = None):
    path = LEDGER_FILES.get(component)
    if not path:
        logger.error(f"Unknown component for ledger: {component}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = {
        "timestamp": timestamp,
        "component": component,
        "status": status,
        "message": message,
        "metadata": metadata or {}
    }
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    # Update last-run in timer_config
    cfg = load_timer_config()
    key = component.lower() + "_last_run"
    cfg[key] = timestamp
    update_timer_config(cfg)


def check_heartbeat():
    cfg = load_timer_config()
    com_cfg = load_com_config()
    notifications = com_cfg.get("notification_config", {})

    now = datetime.now(timezone.utc)
    for comp, path in LEDGER_FILES.items():
        interval_key = comp.lower() + "_loop_interval"
        interval = cfg.get(interval_key, cfg.get("den_mother_loop_interval", 30))
        try:
            with open(path, "r") as f:
                lines = [l for l in f.read().splitlines() if l]
            last = json.loads(lines[-1]) if lines else None
            last_ts = datetime.fromisoformat(last.get("timestamp")) if last else None
            elapsed = (now - last_ts).total_seconds() / 60 if last_ts else None
            if not last_ts or elapsed > interval * 1.5:
                msg = f"No {comp} heartbeat for {elapsed:.1f}m > {interval}m"
                level = "error"
            else:
                msg = f"{comp} heartbeat OK: {elapsed:.1f}m ago"
                level = "success"
        except Exception as e:
            msg = f"Error reading {comp} ledger: {e}"
            level = "error"
        write_ledger(comp, level, msg)
        log_operation("HeartbeatCheck", msg, source="DenMother", file=__file__)
        if level == "error":
            subject = f"Alert: {comp} missed heartbeat"
            body = msg
            try:
                trigger_twilio_flow(body, com_cfg.get("twilio_config", {}))
                log_operation("TwilioNotification", f"Sent Twilio for {comp}", "DenMother", __file__)
            except Exception as te:
                log_operation("TwilioFailed", str(te), "DenMother", __file__)
                # fallback
                send_email(
                    notifications.get("email", {}).get("recipient_email"),
                    subject, body, config=com_cfg
                )
                send_sms(
                    notifications.get("sms", {}).get("recipient_number"),
                    body, config=com_cfg
                )
                log_operation("FallbackNotification", f"Email/SMS fallback for {comp}", "DenMother", __file__)


def generate_html_report():
    rows = []
    for comp, path in LEDGER_FILES.items():
        try:
            with open(path) as f:
                entries = [json.loads(line) for line in f if line.strip()]
        except:
            entries = []
        rows.extend(entries[-20:])
    rows.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    html = [
        "<html><body><h2>DenMother Report</h2><table border='1'><tr>"
        "<th>Timestamp</th><th>Component</th><th>Status</th><th>Message</th></tr>"
    ]
    for e in rows:
        ts = e.get("timestamp", "")
        comp = e.get("component", "")
        status = e.get("status", "")
        message = e.get("message", "")
        html.append(
            f"<tr><td>{ts}</td><td>{comp}</td><td>{status}</td><td>{message}</td></tr>"
        )
    html.append("</table></body></html>")

    os.makedirs(os.path.dirname(HTML_REPORT_FILE), exist_ok=True)
    with open(HTML_REPORT_FILE, "w") as f:
        f.write("".join(html))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['oneshot', 'monitor'], default='oneshot')
    args = parser.parse_args()

    if args.mode == 'oneshot':
        check_heartbeat()
        generate_html_report()
    else:
        while True:
            check_heartbeat()
            generate_html_report()
            interval = load_timer_config().get("den_mother_loop_interval", 35)
            time.sleep(interval * 60)
