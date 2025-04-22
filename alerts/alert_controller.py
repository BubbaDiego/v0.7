from data.data_locker import DataLocker
from utils.json_manager import JsonManager, JsonType
from uuid import uuid4
from data.models import AlertType, AlertClass, Status
from typing import Optional
from datetime import datetime
import logging
import sqlite3
from utils.unified_logger import UnifiedLogger
from utils.update_ledger import log_alert_update
from alerts.alert_enrichment import enrich_alert_data


class DummyPositionAlert:
    """
    Minimal alert object for creating position alerts.
    """
    def __init__(self, alert_type, asset_type, trigger_value, condition,
                 notification_type, position_reference_id, position_type):
        self.id = str(uuid4())
        self.alert_type = alert_type
        self.alert_class = AlertClass.POSITION.value
        self.asset_type = asset_type
        self.trigger_value = trigger_value
        self.condition = condition
        self.notification_type = notification_type
        self.level = "Normal"
        self.last_triggered = None
        self.status = Status.ACTIVE.value
        self.frequency = 1
        self.counter = 0
        self.liquidation_distance = 0.0
        self.travel_percent = 0.0
        self.liquidation_price = 0.0
        self.notes = f"Position {alert_type} alert created by Cyclone"
        self.position_reference_id = position_reference_id
        self.evaluated_value = 0.0
        self.position_type = position_type

    def to_dict(self):
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "alert_class": self.alert_class,
            "asset_type": self.asset_type,
            "trigger_value": self.trigger_value,
            "condition": self.condition,
            "notification_type": self.notification_type,
            "level": self.level,
            "last_triggered": self.last_triggered,
            "status": self.status,
            "frequency": self.frequency,
            "counter": self.counter,
            "liquidation_distance": self.liquidation_distance,
            "travel_percent": self.travel_percent,
            "liquidation_price": self.liquidation_price,
            "notes": self.notes,
            "description": f"Position {self.alert_type} alert created by Cyclone",
            "position_reference_id": self.position_reference_id,
            "evaluated_value": self.evaluated_value,
            "position_type": self.position_type
        }


class AlertController:
    """
    Manages creation, refresh, and deletion of alerts.
    """
    def __init__(self, db_path: Optional[str] = None):
        self.u_logger = UnifiedLogger()
        self.logger = logging.getLogger(__name__)
        self.data_locker = DataLocker.get_instance(db_path) if db_path else DataLocker.get_instance()
        self.json_manager = JsonManager()

    def get_position_type(self, position_id: str) -> str:
        try:
            positions = self.data_locker.read_positions()
            pos = next((p for p in positions if p.get("id") == position_id), None)
            ptype = pos.get("position_type") if pos else None
            return ptype.upper() if ptype and ptype.strip() else "LONG"
        except Exception:
            self.logger.exception("Error retrieving position type; defaulting to LONG.")
            return "LONG"

    def initialize_alert_data(self, alert_data: dict = None) -> dict:
        defaults = {
            "id": str(uuid4()),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": "Normal",
            "status": Status.ACTIVE.value,
            "frequency": 1,
            "counter": 0,
            "liquidation_distance": 0.0,
            "travel_percent": 0.0,
            "liquidation_price": 0.0,
            "notes": "",
            "description": "",
            "last_triggered": None
        }
        alert = alert_data.copy() if alert_data else {}
        for k, v in defaults.items():
            alert.setdefault(k, v)
        return alert

    def create_alert(self, alert_obj) -> bool:
        try:
            alert = alert_obj.to_dict() if not isinstance(alert_obj, dict) else alert_obj
            alert["alert_class"] = (
                AlertClass.MARKET.value
                if alert["alert_type"] == AlertType.PRICE_THRESHOLD.value
                else AlertClass.POSITION.value
            )
            alert = self.initialize_alert_data(alert)
            if alert["alert_type"] != AlertType.PRICE_THRESHOLD.value:
                pid = alert.get("position_reference_id")
                alert["position_type"] = self.get_position_type(pid) if pid else "LONG"
            else:
                alert["position_type"] = None
            cols = ", ".join(alert.keys())
            vals = ", ".join(f":{k}" for k in alert.keys())
            sql = f"INSERT INTO alerts ({cols}) VALUES ({vals})"
            self.data_locker.conn.execute(sql, alert)
            self.data_locker.conn.commit()
            log_alert_update(self.data_locker, alert['id'], 'system', 'Initial creation', '', 'Created')
            return True
        except sqlite3.IntegrityError:
            self.logger.error("IntegrityError creating alert.")
            return False
        except Exception:
            self.logger.exception("Unexpected error in create_alert.")
            return False

    def create_price_alerts(self) -> list[dict]:
        created = []
        cfg = self.json_manager.load("", JsonType.ALERT_LIMITS)
        for asset, settings in cfg.get("alert_ranges", {}).get("price_alerts", {}).items():
            if not settings.get("enabled"): continue
            try:
                trigger = float(settings.get("trigger_value", 0))
            except:
                continue
            nt = "Call" if settings.get("notifications", {}).get("call") else "Email"
            alert = DummyPositionAlert(
                AlertType.PRICE_THRESHOLD.value,
                asset,
                trigger,
                settings.get("condition", "ABOVE"),
                nt,
                None,
                None
            )
            if self.create_alert(alert):
                created.append(alert.to_dict())
        return created

    def create_alert_for_position(self, pos: dict, alert_type: str, trigger_value: float, condition: str,
                                  notification_type: str) -> Optional[dict]:
        alert = DummyPositionAlert(
            alert_type,
            pos.get("asset_type", "BTC"),
            trigger_value,
            condition,
            notification_type,
            pos.get("id"),
            self.get_position_type(pos.get("id"))
        )
        if self.create_alert(alert):
            # Record mapping by alert type
            pos_id = pos.get("id")
            self.data_locker.add_position_alert_mapping(pos_id, alert.alert_type)
            # Persist reference on position to prevent evaluator duplicates
            cursor = self.data_locker.conn.cursor()
            cursor.execute(
                "UPDATE positions SET alert_reference_id = ? WHERE id = ?",
                (alert.id, pos_id)
            )
            self.data_locker.conn.commit()
            return alert.to_dict()
        return None

    def create_all_position_alerts(self) -> list[dict]:
        created = []
        cfg = self.json_manager.load("", JsonType.ALERT_LIMITS)
        tp_cfg = cfg.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
        pr_cfg = cfg.get("alert_ranges", {}).get("profit_ranges", {})
        hi_cfg = cfg.get("alert_ranges", {}).get("heat_index_ranges", {})
        for pos in self.data_locker.read_positions():
            pid = pos.get("id")
            if tp_cfg.get("enabled") and not self.data_locker.has_alert_mapping(pid, AlertType.TRAVEL_PERCENT_LIQUID.value):
                ta = self.create_alert_for_position(pos, AlertType.TRAVEL_PERCENT_LIQUID.value,
                                                   float(tp_cfg.get("low", 0)), "BELOW", "Call")
                if ta: created.append(ta)
            if pr_cfg.get("enabled") and not self.data_locker.has_alert_mapping(pid, AlertType.PROFIT.value):
                pa = self.create_alert_for_position(pos, AlertType.PROFIT.value,
                                                   float(pr_cfg.get("low", 0)), "ABOVE", "Call")
                if pa: created.append(pa)
            if hi_cfg.get("enabled") and not self.data_locker.has_alert_mapping(pid, AlertType.HEAT_INDEX.value):
                ha = self.create_alert_for_position(pos, AlertType.HEAT_INDEX.value,
                                                   float(hi_cfg.get("low", 7)), "ABOVE", "Call")
                if ha: created.append(ha)
        return created

    def create_all_alerts(self) -> list[dict]:
        self.u_logger.log_operation(operation_type="Create Alerts", primary_text="Creating all alerts", source="AlertController", file="alert_controller.py")
        return self.create_price_alerts() + self.create_all_position_alerts()

    def get_all_alerts(self) -> list[dict]:
        try:
            return self.data_locker.get_alerts()
        except Exception:
            self.logger.exception("Error retrieving alerts.")
            return []

    def populate_evaluated_value_for_alert(self, alert: dict) -> float:
        evaluated = 0.0
        tp = alert.get("alert_type")
        positions = {p.get("id"): p for p in self.data_locker.read_positions()}
        pid = alert.get("position_reference_id") or alert.get("id")
        try:
            if tp == AlertType.PRICE_THRESHOLD.value:
                pr = self.data_locker.get_latest_price(alert.get("asset_type", ""))
                evaluated = float(pr.get("current_price", 0)) if pr else 0
            elif tp == AlertType.TRAVEL_PERCENT_LIQUID.value:
                evaluated = float(positions[pid].get("travel_percent", 0))
            elif tp == AlertType.PROFIT.value:
                evaluated = float(positions[pid].get("pnl_after_fees_usd", 0))
            elif tp == AlertType.HEAT_INDEX.value:
                evaluated = float(positions[pid].get("current_heat_index", 0))
        except Exception:
            self.logger.exception("Error populating evaluated value.")
        return evaluated

    def refresh_position_alerts(self) -> int:
        updated = 0
        for alert in self.get_all_alerts():
            if alert.get("alert_class") != AlertClass.POSITION.value: continue
            pid = alert.get("position_reference_id")
            if not pid: continue
            enriched = self.enrich_alert(alert.copy())
            val = self.populate_evaluated_value_for_alert(enriched)
            updates = {
                "liquidation_distance": enriched.get("liquidation_distance", 0),
                "liquidation_price": enriched.get("liquidation_price", 0),
                "travel_percent": enriched.get("travel_percent", 0),
                "evaluated_value": val
            }
            if self.data_locker.update_alert_conditions(alert["id"], updates) > 0:
                updated += 1
        self.logger.info(f"Refreshed {updated} position alerts.")
        return updated

    def refresh_all_alerts(self) -> int:
        count = self.refresh_position_alerts()
        self.logger.info(f"Refreshed {count} alerts total.")
        return count

    def delete_alert(self, alert_id: str) -> bool:
        try:
            cursor = self.data_locker.conn.cursor()
            cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            self.data_locker.conn.commit()
            return True
        except Exception:
            self.logger.exception("Error deleting alert.")
            return False

    def delete_all_alerts(self) -> int:
        count = 0
        for alert in self.get_all_alerts():
            if self.delete_alert(alert["id"]):
                count += 1
        return count
