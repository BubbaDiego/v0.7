import asyncio
import logging
import sys
import os
import json
from uuid import uuid4
from config.config_constants import BASE_DIR
from prices.price_monitor import PriceMonitor
from alerts.alert_manager import AlertManager
from data.data_locker import DataLocker
from utils.unified_logger import UnifiedLogger
from sonic_labs.hedge_manager import HedgeManager  # Import HedgeManager directly
from positions.position_service import PositionService
#from alerts.alert_enrichment_helpers import normalize_alert_type as normalize_alert_type_helper
from alerts.alert_controller import AlertController, DummyPositionAlert

class Cyclone:
    def __init__(self, poll_interval=60):
        self.logger = logging.getLogger("Cyclone")
        self.poll_interval = poll_interval
        self.logger.setLevel(logging.DEBUG)
        self.u_logger = UnifiedLogger()  # Unified logging

        # Log the start of Cyclone initialization using cyclone log type
        self.u_logger.logger.info("Cyclone: Initializing Cyclone instance",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Initialization', 'source': 'Cyclone', 'file': 'cyclone.py'})

        # Initialize core components
        self.data_locker = DataLocker.get_instance()
        self.price_monitor = PriceMonitor()  # Market Updates
        self.alert_manager = AlertManager()    # Alert Updates

    async def run_market_updates(self):
        self.logger.info("Starting Market Updates")
        self.u_logger.logger.info("Cyclone: Starting Market Updates",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Market Updates', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            await self.price_monitor.update_prices(source="Market Updates")
            self.u_logger.log_operation(
                operation_type="Market Updates",
                primary_text="Prices updated successfully",
                source="Cyclone",
                file="cyclone.py"
            )
            self.u_logger.logger.info("Cyclone: Market Updates completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Market Updates', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            self.logger.error(f"Market Updates failed: {e}")
            self.u_logger.log_operation(
                operation_type="Market Updates",
                primary_text=f"Failed: {e}",
                source="Cyclone",
                file="cyclone.py"
            )

    async def run_position_updates(self):
        self.logger.info("Starting Position Updates")
        self.u_logger.logger.info("Cyclone: Starting Position Updates",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Position Updates', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            result = PositionService.update_jupiter_positions()
            self.u_logger.log_operation(
                operation_type="Position Updates",
                primary_text=f"{result.get('message', 'No message returned')}",
                source="Cyclone",
                file="cyclone.py"
            )
            self.u_logger.logger.info("Cyclone: Position Updates completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Position Updates', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            self.logger.error(f"Position Updates failed: {e}")
            self.u_logger.log_operation(
                operation_type="Position Updates",
                primary_text=f"Failed: {e}",
                source="Cyclone",
                file="cyclone.py"
            )

    async def run_position_enrichment(self):
        self.logger.info("Starting Position Data Enrichment")
        self.u_logger.logger.info("Cyclone: Starting Position Data Enrichment",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Position Enrichment', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            enriched_positions = PositionService.get_all_positions()
            count = len(enriched_positions)
            self.u_logger.log_operation(
                operation_type="Position Enrichment",
                primary_text=f"Enriched {count} positions",
                source="Cyclone",
                file="cyclone.py"
            )
            print(f"Enriched {count} positions.")
            self.u_logger.logger.info("Cyclone: Position Data Enrichment completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Position Enrichment', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            self.logger.error(f"Position Data Enrichment failed: {e}")
            self.u_logger.log_operation(
                operation_type="Position Enrichment",
                primary_text=f"Failed: {e}",
                source="Cyclone",
                file="cyclone.py"
            )

    async def run_create_market_alerts(self):
        self.logger.info("Creating Market Alerts via AlertController")
        self.u_logger.logger.info("Cyclone: Starting creation of Market Alerts",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Create Market Alerts', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            ac = self.AlertController()

            class DummyPriceAlert:
                def __init__(self):
                    from data.models import AlertType, AlertClass, Status
                    from uuid import uuid4
                    self.id = str(uuid4())
                    self.alert_type = AlertType.PRICE_THRESHOLD.value
                    self.alert_class = None
                    self.asset_type = "BTC"
                    self.trigger_value = 0.0
                    self.condition = "ABOVE"
                    self.notification_type = None
                    self.state = "Normal"
                    self.last_triggered = None
                    self.status = None
                    self.frequency = 1
                    self.counter = 0
                    self.liquidation_distance = 0.0
                    self.target_travel_percent = 0.0
                    self.liquidation_price = 0.0
                    self.notes = "Market price alert created by Cyclone"
                    self.position_reference_id = None
                    self.evaluated_value = 0.0

                def to_dict(self):
                    return {
                        "id": self.id,
                        "alert_type": self.alert_type,
                        "alert_class": self.alert_class,
                        "asset_type": self.asset_type,
                        "trigger_value": self.trigger_value,
                        "condition": self.condition,
                        "notification_type": self.notification_type,
                        "state": self.state,
                        "last_triggered": self.last_triggered,
                        "status": self.status,
                        "frequency": self.frequency,
                        "counter": self.counter,
                        "liquidation_distance": self.liquidation_distance,
                        "target_travel_percent": self.target_travel_percent,
                        "liquidation_price": self.liquidation_price,
                        "notes": self.notes,
                        "position_reference_id": self.position_reference_id,
                        "evaluated_value": self.evaluated_value
                    }

            dummy_alert = DummyPriceAlert()
            if ac.create_alert(dummy_alert):
                self.u_logger.log_operation(
                    operation_type="Create Market Alerts",
                    primary_text="Market alert created successfully via AlertController",
                    source="Cyclone",
                    file="cyclone.py"
                )
                print("Created market alert successfully.")
            else:
                self.u_logger.log_operation(
                    operation_type="Create Market Alerts Failed",
                    primary_text="Failed to create market alert via AlertController",
                    source="Cyclone",
                    file="cyclone.py"
                )
                print("Failed to create market alert.")
            self.u_logger.logger.info("Cyclone: Market Alerts creation step completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Create Market Alerts', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            self.logger.error(f"Error creating market alerts: {e}", exc_info=True)
            print(f"Error creating market alerts: {e}")

    async def run_update_hedges(self):
        self.logger.info("Starting Hedge Update")
        self.u_logger.logger.info("Cyclone: Starting Hedge Update",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Hedge Update', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            hedge_groups = HedgeManager.find_hedges()
            self.logger.info(f"Found {len(hedge_groups)} hedge group(s) using find_hedges.")

            positions = [dict(pos) for pos in self.data_locker.read_positions()]
            hedge_manager = HedgeManager(positions)
            hedges = hedge_manager.get_hedges()
            self.logger.info(f"Built {len(hedges)} hedge(s) using HedgeManager instance.")

            self.u_logger.log_operation(
                operation_type="Update Hedges",
                primary_text=f"Updated hedges: {len(hedge_groups)} hedge group(s) found, {len(hedges)} hedges built.",
                source="Cyclone",
                file="cyclone.py"
            )
            print(f"Updated hedges: {len(hedge_groups)} group(s) found, {len(hedges)} hedge(s) built.")
            self.u_logger.logger.info("Cyclone: Hedge Update completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Hedge Update', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            self.logger.error(f"Hedge Update failed: {e}", exc_info=True)
            self.u_logger.log_operation(
                operation_type="Update Hedges",
                primary_text=f"Failed: {e}",
                source="Cyclone",
                file="cyclone.py"
            )

    async def run_cycle(self, steps=None):
        self.u_logger.logger.info("Cyclone: Starting full cycle",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Cycle Start', 'source': 'Cyclone', 'file': 'cyclone.py'})
        # Master run_cycle method to run various steps
        available_steps = {
            "market": self.run_market_updates,
            "position": self.run_position_updates,
            "cleanse_ids": self.run_cleanse_ids,
            "enrichment": self.run_position_enrichment,
            "create_market_alerts": self.run_create_market_alerts,
            "create_position_alerts": self.run_create_position_alerts,
            "create_system_alerts": self.run_create_system_alerts,
            "update_evaluated_value": self.run_update_evaluated_value,
            "alert": self.run_alert_updates,
            "system": self.run_system_updates
        }
        if steps:
            for step in steps:
                if step in available_steps:
                    await available_steps[step]()
                else:
                    self.logger.warning(f"Unknown step requested: {step}")
        else:
            for step in [
                "market", "position", "enrichment",
                "create_market_alerts", "create_position_alerts",
                "create_system_alerts", "update_evaluated_value",
                "alert", "system"
            ]:
                await available_steps[step]()
        self.u_logger.logger.info("Cyclone: Full cycle completed",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Cycle End', 'source': 'Cyclone', 'file': 'cyclone.py'})

    async def run_create_position_alerts(self):
        self.logger.info("Creating Position Alerts")
        self.u_logger.logger.info("Cyclone: Starting creation of Position Alerts",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Create Position Alerts', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            ac = self.AlertController()
            positions = self.data_locker.read_positions()
            if not positions:
                print("No positions available to create alerts.")
                return

            created = 0
            for pos in positions:
                pos_dict = dict(pos)
                pos_id = pos_dict.get("id")
                if not pos_id:
                    self.logger.error("Position missing id. Skipping alert creation for this position.")
                    continue

                travel_alert = DummyPositionAlert("TravelPercentAlert", pos_dict.get("asset_type", "BTC"), -4.0, "BELOW", "Call", pos_id)
                profit_alert = DummyPositionAlert("ProfitAlert", pos_dict.get("asset_type", "BTC"), 22.0, "ABOVE", "Email", pos_id)
                heat_alert = DummyPositionAlert("HeatIndexAlert", pos_dict.get("asset_type", "BTC"), 12.0, "ABOVE", "Email", pos_id)

                for alert in [travel_alert, profit_alert, heat_alert]:
                    if ac.create_alert(alert):
                        created += 1
                    else:
                        self.logger.error("Failed to create alert for position id: %s", pos_id)
            self.u_logger.log_operation(
                operation_type="Create Position Alerts",
                primary_text=f"Created {created} position alert(s)",
                source="Cyclone",
                file="cyclone.py"
            )
            print(f"Created {created} position alert(s).")
            self.u_logger.logger.info("Cyclone: Position Alerts creation completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Create Position Alerts', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            print(f"Error creating position alerts: {e}")

    async def run_delete_position(self):
        position_id = input("Enter the Position ID to delete: ").strip()
        if not position_id:
            print("No position ID provided.")
            return
        try:
            from positions.position_service import delete_position_and_cleanup
            await asyncio.to_thread(delete_position_and_cleanup, position_id)
            print(f"Position {position_id} deleted along with associated alerts and hedges.")
            self.u_logger.logger.info(f"Cyclone: Position {position_id} deleted",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Delete Position', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            print(f"Error deleting position {position_id}: {e}")

    async def run_create_system_alerts(self):
        self.logger.info("Creating System Alerts")
        self.u_logger.logger.info("Cyclone: Starting creation of System Alerts",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Create System Alerts', 'source': 'Cyclone', 'file': 'cyclone.py'})
        # No additional system alert creation logic provided.
        return

    async def run_update_evaluated_value(self):
        self.logger.info("Updating Evaluated Values for Alerts...")
        self.u_logger.logger.info("Cyclone: Starting update of evaluated alert values",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Update Evaluated Value', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            self.alert_manager.update_alerts_evaluated_value()
            self.u_logger.log_operation(
                operation_type="Update Evaluated Value",
                primary_text="Alert evaluated values updated successfully",
                source="Cyclone",
                file="cyclone.py"
            )
            print("Alert evaluated values updated.")
            self.u_logger.logger.info("Cyclone: Update Evaluated Value completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Update Evaluated Value', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            self.logger.error(f"Updating evaluated values failed: {e}")
            self.u_logger.log_operation(
                operation_type="Update Evaluated Value",
                primary_text=f"Failed: {e}",
                source="Cyclone",
                file="cyclone.py"
            )

    async def run_alert_updates(self):
        self.logger.info("Starting Alert Evaluations")
        self.u_logger.logger.info("Cyclone: Starting Alert Evaluations",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Alert Evaluations', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            positions = self.data_locker.read_positions()
            combined_eval = self.alert_manager.alert_evaluator.evaluate_alerts(positions=positions, market_data={})
            self.u_logger.log_operation(
                operation_type="Alert Evaluations",
                primary_text="Combined alert evaluations completed",
                source="Cyclone",
                file="cyclone.py"
            )
            market_alerts = self.alert_manager.alert_evaluator.evaluate_market_alerts(market_data={})
            for msg in market_alerts:
                self.u_logger.log_operation(
                    operation_type="Market Alert Evaluation",
                    primary_text=msg,
                    source="Cyclone",
                    file="cyclone.py"
                )
            position_alerts = self.alert_manager.alert_evaluator.evaluate_position_alerts(positions)
            for msg in position_alerts:
                self.u_logger.log_operation(
                    operation_type="Position Alert Evaluation",
                    primary_text=msg,
                    source="Cyclone",
                    file="cyclone.py"
                )
            system_alerts = self.alert_manager.alert_evaluator.evaluate_system_alerts()
            for msg in system_alerts:
                self.u_logger.log_operation(
                    operation_type="System Alert Evaluation",
                    primary_text=msg,
                    source="Cyclone",
                    file="cyclone.py"
                )
            self.u_logger.logger.info("Cyclone: Alert Evaluations completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Alert Evaluations', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            self.logger.error(f"Alert Evaluations failed: {e}")
            self.u_logger.log_operation(
                operation_type="Alert Evaluations",
                primary_text=f"Failed: {e}",
                source="Cyclone",
                file="cyclone.py"
            )

    async def run_system_updates(self):
        self.logger.info("Starting System Updates")
        self.u_logger.logger.info("Cyclone: Starting System Updates",
                                    extra={'log_type': 'cyclone', 'operation_type': 'System Updates', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            self.u_logger.log_operation(
                operation_type="System Updates",
                primary_text="System state updated",
                source="Cyclone",
                file="cyclone.py"
            )
            self.u_logger.logger.info("Cyclone: System Updates completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'System Updates', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            self.logger.error(f"System Updates failed: {e}")
            self.u_logger.log_operation(
                operation_type="System Updates",
                primary_text=f"Failed: {e}",
                source="Cyclone",
                file="cyclone.py"
            )

    async def run_cleanse_ids(self):
        self.logger.info("Running cleanse_ids step: clearing stale IDs.")
        self.u_logger.logger.info("Cyclone: Starting cleanse_ids step",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Clear IDs', 'source': 'Cyclone', 'file': 'cyclone.py'})
        try:
            self.alert_manager.clear_stale_alerts()
            self.u_logger.log_operation(
                operation_type="Clear IDs",
                primary_text="Stale alert, position, and hedge IDs cleared successfully",
                source="Cyclone",
                file="cyclone.py"
            )
            print("Stale IDs have been cleansed successfully.")
            self.u_logger.logger.info("Cyclone: cleanse_ids step completed",
                                        extra={'log_type': 'cyclone', 'operation_type': 'Clear IDs', 'source': 'Cyclone', 'file': 'cyclone.py'})
        except Exception as e:
            self.logger.error(f"Error cleansing IDs: {e}", exc_info=True)
            print(f"Error cleansing IDs: {e}")

    def run_prices_menu(self):
        while True:
            print("\n--- Prices Menu ---")
            print("1) 🚀 Market Update")
            print("2) 👁 View Prices")
            print("3) 🧹 Clear Prices")
            print("4) ↩️ Back to Main Menu")
            choice = input("Enter your choice (1-4): ").strip()
            if choice == "1":
                print("Running Market Update...")
                asyncio.run(self.run_cycle(steps=["market"]))
                print("Market Update completed.")
            elif choice == "2":
                print("Viewing Prices...")
                self.view_prices_backend()
            elif choice == "3":
                print("Clearing Prices...")
                self.clear_prices_backend()
            elif choice == "4":
                break
            else:
                print("Invalid choice, please try again.")

    def run_positions_menu(self):
        while True:
            print("\n--- Positions Menu ---")
            print("1) 👁 View Positions")
            print("2) 🔄 Positions Updates")
            print("3) ✨ Position Data Enrichment")
            print("4) 🧹 Clear Positions")
            print("5) ↩️ Back to Main Menu")
            choice = input("Enter your choice (1-5): ").strip()
            if choice == "1":
                print("Viewing Positions...")
                self.view_positions_backend()
            elif choice == "2":
                print("Running Position Updates...")
                asyncio.run(self.run_cycle(steps=["position"]))
                print("Position Updates completed.")
            elif choice == "3":
                print("Running Position Data Enrichment...")
                asyncio.run(self.run_cycle(steps=["enrichment"]))
                print("Position Data Enrichment completed.")
            elif choice == "4":
                print("Clearing Positions...")
                self.clear_positions_backend()
            elif choice == "5":
                break
            else:
                print("Invalid choice, please try again.")

    def run_alerts_menu(self):
        while True:
            print("\n--- Alerts Menu ---")
            print("1) 👁 View Alerts")
            print("2) 💵 Create Market Alerts")
            print("3) 📌 Create Position Alerts")
            print("4) 🖥 Create System Alerts")
            print("5) 🔄 Update Evaluated Value")
            print("6) 🔍 Alert Evaluations")
            print("7) 🧹 Clear Alerts")
            print("8) ♻️ Refresh Alerts")
            print("9) ↩️ Back to Main Menu")
            choice = input("Enter your choice (1-9): ").strip()
            if choice == "1":
                print("Viewing Alerts...")
                self.view_alerts_backend()
            elif choice == "2":
                print("Creating Market Alerts...")
                asyncio.run(self.run_cycle(steps=["create_market_alerts"]))
            elif choice == "3":
                print("Creating Position Alerts...")
                asyncio.run(self.run_cycle(steps=["create_position_alerts"]))
            elif choice == "4":
                print("Creating System Alerts...")
                asyncio.run(self.run_cycle(steps=["create_system_alerts"]))
            elif choice == "5":
                print("Updating Evaluated Values for Alerts...")
                asyncio.run(self.run_cycle(steps=["update_evaluated_value"]))
            elif choice == "6":
                print("Running Alert Evaluations...")
                asyncio.run(self.run_cycle(steps=["alert"]))
                print("Alert Evaluations completed.")
            elif choice == "7":
                print("Clearing Alerts...")
                self.clear_alerts_backend()
            elif choice == "8":
                print("Refreshing Alerts...")
                ac = self.AlertController()
                count = ac.refresh_all_alerts()
                print(f"Refreshed and confirmed {count} alert(s).")
            elif choice == "9":
                break
            else:
                print("Invalid choice, please try again.")

    def run_hedges_menu(self):
        while True:
            print("\n--- Hedge Menu ---")
            print("1) 🔍 Find Hedges")
            print("2) 🧹 Clear Hedges")
            print("3) ↩️ Back to Previous Menu")
            choice = input("Enter your choice (1-3): ").strip()
            if choice == "1":
                print("Finding Hedges...")
                try:
                    hedges = HedgeManager.find_hedges()
                    print(f"Found {len(hedges)} hedge group(s).")
                except Exception as e:
                    print(f"Error finding hedges: {e}")
            elif choice == "2":
                print("Clearing Hedge Data...")
                try:
                    HedgeManager.clear_hedge_data()
                    print("Hedge associations cleared.")
                except Exception as e:
                    print(f"Error clearing hedge data: {e}")
            elif choice == "3":
                break
            else:
                print("Invalid choice, please try again.")

    def run_wallets_menu(self):
        while True:
            print("\n--- Wallets Menu ---")
            print("1) 👁 View Wallets")
            print("2) ➕ Add Wallet")
            print("3) 🧹 Clear Wallets")
            print("4) ↩️ Back to Main Menu")
            choice = input("Enter your choice (1-4): ").strip()
            if choice == "1":
                print("Viewing Wallets...")
                self.view_wallets_backend()
            elif choice == "2":
                print("Adding Wallet...")
                self.add_wallet_backend()
            elif choice == "3":
                print("Clearing Wallets...")
                self.clear_wallets_backend()
            elif choice == "4":
                break
            else:
                print("Invalid choice, please try again.")

    def view_prices_backend(self):
        try:
            from pprint import pprint
            dl = DataLocker.get_instance()
            cursor = dl.conn.cursor()
            cursor.execute("SELECT * FROM prices")
            prices = cursor.fetchall()
            cursor.close()
            print("----- Prices -----")
            print(f"Found {len(prices)} price record(s).")
            for row in prices:
                pprint(dict(row))
        except Exception as e:
            print(f"Error viewing prices: {e}")

    def run_delete_all_data(self):
        confirm = input("WARNING: This will DELETE ALL alerts, prices, and positions from the database. Are you sure? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Deletion aborted.")
            return
        try:
            self.clear_alerts_backend()
            self.clear_prices_backend()
            self.clear_positions_backend()
            self.u_logger.log_operation(
                operation_type="Delete All Data",
                primary_text="All alerts, prices, and positions have been deleted.",
                source="Cyclone",
                file="cyclone.py"
            )
            print("All alerts, prices, and positions have been deleted.")
        except Exception as e:
            print(f"Error deleting data: {e}")

    def clear_prices_backend(self):
        try:
            dl = DataLocker.get_instance()
            cursor = dl.conn.cursor()
            cursor.execute("DELETE FROM prices")
            dl.conn.commit()
            deleted = cursor.rowcount
            cursor.close()
            self.u_logger.log_operation(
                operation_type="Clear Prices",
                primary_text=f"Cleared {deleted} price record(s)",
                source="Cyclone",
                file="cyclone.py"
            )
            print(f"Price data cleared. {deleted} record(s) deleted.")
        except Exception as e:
            print(f"Error clearing price data: {e}")

    def view_positions_backend(self):
        try:
            from pprint import pprint
            dl = DataLocker.get_instance()
            cursor = dl.conn.cursor()
            cursor.execute("SELECT * FROM positions")
            positions = cursor.fetchall()
            cursor.close()
            print("----- Positions -----")
            print(f"Found {len(positions)} position record(s).")
            for row in positions:
                pprint(dict(row))
        except Exception as e:
            print(f"Error viewing positions: {e}")

    def clear_positions_backend(self):
        try:
            dl = DataLocker.get_instance()
            cursor = dl.conn.cursor()
            cursor.execute("DELETE FROM positions")
            dl.conn.commit()
            deleted = cursor.rowcount
            cursor.close()
            self.u_logger.log_operation(
                operation_type="Clear Positions",
                primary_text=f"Cleared {deleted} position record(s)",
                source="Cyclone",
                file="cyclone.py"
            )
            print(f"Positions cleared. {deleted} record(s) deleted.")
        except Exception as e:
            print(f"Error clearing positions: {e}")

    def view_alerts_backend(self):
        try:
            from pprint import pprint
            dl = DataLocker.get_instance()
            cursor = dl.conn.cursor()
            cursor.execute("SELECT * FROM alerts")
            alerts = cursor.fetchall()
            cursor.close()
            print("----- Alerts -----")
            print(f"Found {len(alerts)} alert record(s).")
            for row in alerts:
                alert_dict = dict(row)
                if "evaluated_value" not in alert_dict:
                    alert_dict["evaluated_value"] = None
                pprint(alert_dict)
        except Exception as e:
            print(f"Error viewing alerts: {e}")

    def clear_alerts_backend(self):
        try:
            dl = DataLocker.get_instance()
            cursor = dl.conn.cursor()
            cursor.execute("DELETE FROM alerts")
            dl.conn.commit()
            deleted = cursor.rowcount
            cursor.close()
            self.u_logger.log_operation(
                operation_type="Clear Alerts",
                primary_text=f"Cleared {deleted} alert record(s)",
                source="Cyclone",
                file="cyclone.py"
            )
            print(f"Alerts cleared. {deleted} record(s) deleted.")
        except Exception as e:
            print(f"Error clearing alerts: {e}")

    def view_wallets_backend(self):
        try:
            from pprint import pprint
            dl = DataLocker.get_instance()
            cursor = dl.conn.cursor()
            cursor.execute("SELECT * FROM wallets")
            wallets = cursor.fetchall()
            cursor.close()
            print("----- Wallets -----")
            print(f"Found {len(wallets)} wallet record(s).")
            for row in wallets:
                pprint(dict(row))
        except Exception as e:
            print(f"Error viewing wallets: {e}")

    def add_wallet_backend(self):
        try:
            name = input("Enter wallet name: ").strip()
            public_address = input("Enter public address: ").strip()
            private_address = input("Enter private address: ").strip()
            image_path = input("Enter image path: ").strip()
            balance_str = input("Enter balance: ").strip()
            try:
                balance = float(balance_str)
            except Exception:
                balance = 0.0
            dl = DataLocker.get_instance()
            cursor = dl.conn.cursor()
            cursor.execute(
                "INSERT INTO wallets (name, public_address, private_address, image_path, balance) VALUES (?, ?, ?, ?, ?)",
                (name, public_address, private_address, image_path, balance)
            )
            dl.conn.commit()
            inserted = cursor.rowcount
            cursor.close()
            self.u_logger.log_operation(
                operation_type="Add Wallet",
                primary_text=f"Added wallet '{name}' ({inserted} row inserted)",
                source="Cyclone",
                file="cyclone.py"
            )
            print(f"Wallet added successfully. {inserted} record(s) inserted.")
        except Exception as e:
            print(f"Error adding wallet: {e}")

    def clear_wallets_backend(self):
        try:
            dl = DataLocker.get_instance()
            cursor = dl.conn.cursor()
            cursor.execute("DELETE FROM wallets")
            dl.conn.commit()
            deleted = cursor.rowcount
            cursor.close()
            self.u_logger.log_operation(
                operation_type="Clear Wallets",
                primary_text=f"Cleared {deleted} wallet record(s)",
                source="Cyclone",
                file="cyclone.py"
            )
            print(f"Wallets cleared. {deleted} record(s) deleted.")
        except Exception as e:
            print(f"Error clearing wallets: {e}")

    def generate_cycle_report(self):
        """
        Reads the cyclone log file (cyclone_log.txt) from the logs folder,
        builds a summary and detailed table from the JSON log records,
        and writes a pretty HTML report to cycle_report.html in the same folder.
        """
        logs_dir = os.path.join(os.path.dirname(BASE_DIR), "logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        cyclone_log_path = os.path.join(logs_dir, "cyclone_log.txt")
        cycle_report_path = os.path.join(logs_dir, "cycle_report.html")

        if not os.path.exists(cyclone_log_path):
            print(f"No cyclone log file found at {cyclone_log_path}. Cannot generate report.")
            return

        log_entries = []
        with open(cyclone_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    log_entries.append(record)
                except json.JSONDecodeError:
                    continue

        summary = {}
        for record in log_entries:
            op_type = record.get("operation_type", "Unknown")
            summary[op_type] = summary.get(op_type, 0) + 1

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Cycle Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f4f4f4;
        }}
        h1, h2 {{
            color: #333;
        }}
        .summary {{
            margin-bottom: 20px;
            background-color: #fff;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            background-color: #fff;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #333;
            color: white;
        }}
        tr:nth-child(even) {{background-color: #f2f2f2;}}
    </style>
</head>
<body>
    <h1>Cycle Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <ul>
"""
        for op, count in summary.items():
            html_content += f"            <li><strong>{op}:</strong> {count}</li>\n"
        html_content += """        </ul>
    </div>
    <h2>Detailed Log Entries</h2>
    <table>
        <tr>
            <th>Timestamp</th>
            <th>Operation Type</th>
            <th>Source</th>
            <th>File</th>
            <th>Message</th>
        </tr>
"""
        for record in log_entries:
            ts = record.get("timestamp", "")
            op_type = record.get("operation_type", "")
            source = record.get("source", "")
            file_name = record.get("file", "")
            message = record.get("message", "")
            html_content += f"""        <tr>
            <td>{ts}</td>
            <td>{op_type}</td>
            <td>{source}</td>
            <td>{file_name}</td>
            <td>{message}</td>
        </tr>
"""
        html_content += """    </table>
</body>
</html>
"""

        with open(cycle_report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"Cycle report generated: {cycle_report_path}")
        self.u_logger.log_operation(
            operation_type="Cycle Report Generated",
            primary_text=f"Cycle report generated at {cycle_report_path}",
            source="Cyclone",
            file="cyclone.py"
        )
        self.u_logger.logger.info("Cyclone: Cycle Report generated",
                                    extra={'log_type': 'cyclone', 'operation_type': 'Cycle Report', 'source': 'Cyclone', 'file': 'cyclone.py'})

    def run_console(self):
        # Combined menu, with 1) Full Cycle, 2) Delete All, etc.
        while True:
            print("\n=== Cyclone Interactive Console ===")
            print("1) 🌀 Run Full Cycle")
            print("2) 🗑️ Delete All Data")
            print("3) 💰 Prices")
            print("4) 📊 Positions")
            print("5) 🔔 Alerts")
            print("6) 🛡 Hedge")
            print("7) 🧹 Clear IDs")
            print("8) 💼 Wallets")
            print("9) 📝 Generate Cycle Report")
            print("10) ❌ Exit")
            choice = input("Enter your choice (1-10): ").strip()

            if choice == "1":
                print("Running full cycle (all steps)...")
                asyncio.run(self.run_cycle())
                print("Full cycle completed.")
            elif choice == "2":
                self.run_delete_all_data()
            elif choice == "3":
                self.run_prices_menu()
            elif choice == "4":
                self.run_positions_menu()
            elif choice == "5":
                self.run_alerts_menu()
            elif choice == "6":
                self.run_hedges_menu()
            elif choice == "7":
                print("Clearing stale IDs...")
                asyncio.run(self.run_cleanse_ids())
            elif choice == "8":
                self.run_wallets_menu()
            elif choice == "9":
                self.generate_cycle_report()
            elif choice == "10":
                print("Exiting console mode.")
                break
            else:
                print("Invalid choice, please try again.")

if __name__ == "__main__":
    cyclone = Cyclone(poll_interval=60)
    cyclone.run_console()
