import asyncio
from alerts.alert_controller import AlertController
from cyclone import Cyclone

class CycloneConsoleHelper:
    def __init__(self, cyclone_instance):
        self.cyclone = cyclone_instance

    def run(self):
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
                asyncio.run(self.cyclone.run_cycle())
                print("Full cycle completed.")
            elif choice == "2":
                self.cyclone.run_delete_all_data()
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
                asyncio.run(self.cyclone.run_cleanse_ids())
            elif choice == "8":
                self.cyclone.run_wallets_menu()
            elif choice == "9":
                print("Generating cycle report...")
                try:
                    from cyclone_report_generator import generate_cycle_report
                    generate_cycle_report()
                    self.cyclone.u_logger.log_cyclone(
                        operation_type="Cycle Report Generated",
                        primary_text="Cycle report generated successfully",
                        source="Cyclone",
                        file="cyclone.py"
                    )
                    print("Cycle report generated.")
                except Exception as e:
                    self.cyclone.logger.error(f"Cycle report generation failed: {e}", exc_info=True)
                    print(f"Cycle report generation failed: {e}")
            elif choice == "10":
                print("Exiting console mode.")
                break
            else:
                print("Invalid choice, please try again.")

    def run_console(self):
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
                asyncio.run(self.cyclone.run_cycle())
                print("Full cycle completed.")
            elif choice == "2":
                self.cyclone.run_delete_all_data()
            elif choice == "3":
                self.run_prices_menu()
            elif choice == "4":
                self.run_positions_menu()
            elif choice == "5":
                self.run_alerts_menu()
            elif choice == "6":
                self.cyclone.run_hedges_menu()
            elif choice == "7":
                print("Clearing stale IDs...")
                asyncio.run(self.cyclone.run_cleanse_ids())
            elif choice == "8":
                self.run_wallets_menu()
            elif choice == "9":
                print("Generating cycle report...")
                try:
                    from cyclone_report_generator import generate_cycle_report
                    generate_cycle_report()  # External report generator
                    self.cyclone.u_logger.log_cyclone(
                        operation_type="Cycle Report Generated",
                        primary_text="Cycle report generated successfully",
                        source="Cyclone",
                        file="cyclone.py"
                    )
                except Exception as e:
                    self.cyclone.logger.error(f"Cycle report generation failed: {e}", exc_info=True)
                    print(f"Cycle report generation failed: {e}")
            elif choice == "10":
                print("Exiting console mode.")
                break
            else:
                print("Invalid choice, please try again.")

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
                asyncio.run(self.cyclone.run_cycle(steps=["market"]))
                print("Market Update completed.")
            elif choice == "2":
                print("Viewing Prices...")
                self.cyclone.view_prices_backend()
            elif choice == "3":
                print("Clearing Prices...")
                self.cyclone.clear_prices_backend()
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
                self.cyclone.view_positions_backend()
            elif choice == "2":
                print("Running Position Updates...")
                asyncio.run(self.cyclone.run_cycle(steps=["position"]))
                print("Position Updates completed.")
            elif choice == "3":
                print("Running Position Data Enrichment...")
                asyncio.run(self.cyclone.run_cycle(steps=["enrichment"]))
                print("Position Data Enrichment completed.")
            elif choice == "4":
                print("Clearing Positions...")
                self.cyclone.clear_positions_backend()
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
            print("9) 🧹 Clear Alert Ledger")  # New option added here
            print("10) ↩️ Back to Main Menu")
            choice = input("Enter your choice (1-10): ").strip()
            if choice == "1":
                print("Viewing Alerts...")
                self.cyclone.view_alerts_backend()
            elif choice == "2":
                print("Creating Market Alerts...")
                asyncio.run(self.cyclone.run_cycle(steps=["create_market_alerts"]))
            elif choice == "3":
                print("Creating Position Alerts...")
                asyncio.run(self.cyclone.run_cycle(steps=["create_position_alerts"]))
            elif choice == "4":
                print("Creating System Alerts...")
                asyncio.run(self.cyclone.run_cycle(steps=["create_system_alerts"]))
            elif choice == "5":
                print("Updating Evaluated Values for Alerts...")
                asyncio.run(self.cyclone.run_cycle(steps=["update_evaluated_value"]))
            elif choice == "6":
                print("Running Alert Evaluations...")
                asyncio.run(self.cyclone.run_cycle(steps=["alert"]))
                print("Alert Evaluations completed.")
            elif choice == "7":
                print("Clearing Alerts...")
                self.cyclone.clear_alerts_backend()
            elif choice == "8":
                print("Refreshing Alerts...")
                ac = AlertController()
                count = ac.refresh_all_alerts()
                print(f"Refreshed and confirmed {count} alert(s).")
            elif choice == "9":
                print("Clearing Alert Ledger...")
                self.cyclone.clear_alert_ledger_backend()
            elif choice == "10":
                break
            else:
                print("Invalid choice, please try again.")

    def run_hedges_menu(self):
        """
        Display a submenu for managing hedge data with these options:
          1) View Hedges – display current hedge data using the HedgeManager.
          2) Find Hedges – run the HedgeManager.find_hedges method to scan positions and assign new hedge IDs.
          3) Clear Hedges – clear all hedge associations from the database.
          4) Back to Main Menu.
        """
        from data.data_locker import DataLocker
        from sonic_labs.hedge_manager import HedgeManager

        while True:
            print("\n--- Hedges Menu ---")
            print("1) 👁 View Hedges")
            print("2) 🔍 Find Hedges")
            print("3) 🧹 Clear Hedges")
            print("4) ↩️ Back to Main Menu")
            choice = input("Enter your choice (1-4): ").strip()

            if choice == "1":
                # View hedges using current positions
                dl = DataLocker.get_instance()
                raw_positions = dl.read_positions()
                hedge_manager = HedgeManager(raw_positions)
                hedges = hedge_manager.get_hedges()
                if hedges:
                    print("\nCurrent Hedges:")
                    for hedge in hedges:
                        print(f"Hedge ID: {hedge.id}")
                        print(f"  Positions: {hedge.positions}")
                        print(f"  Total Long Size: {hedge.total_long_size}")
                        print(f"  Total Short Size: {hedge.total_short_size}")
                        print(f"  Long Heat Index: {hedge.long_heat_index}")
                        print(f"  Short Heat Index: {hedge.short_heat_index}")
                        print(f"  Total Heat Index: {hedge.total_heat_index}")
                        print(f"  Notes: {hedge.notes}")
                        print("-" * 40)
                else:
                    print("No hedges found.")
            elif choice == "2":
                # Find hedges: use the static method that scans positions, updates hedge_buddy_id, and returns hedge groups.
                dl = DataLocker.get_instance()
                groups = HedgeManager.find_hedges()
                if groups:
                    print(f"Found {len(groups)} hedge group(s) after scanning positions:")
                    for idx, group in enumerate(groups, start=1):
                        print(f"Group {idx}:")
                        for pos in group:
                            print(f"  Position ID: {pos.get('id')} (Type: {pos.get('position_type')})")
                        print("-" * 30)
                else:
                    print("No hedge groups found.")
            elif choice == "3":
                # Clear hedges: clear hedge associations from all positions.
                try:
                    HedgeManager.clear_hedge_data()
                    print("Hedge associations cleared.")
                except Exception as e:
                    print(f"Error clearing hedges: {e}")
            elif choice == "4":
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
                self.cyclone.view_wallets_backend()
            elif choice == "2":
                print("Adding Wallet...")
                self.cyclone.add_wallet_backend()
            elif choice == "3":
                print("Clearing Wallets...")
                self.cyclone.clear_wallets_backend()
            elif choice == "4":
                break
            else:
                print("Invalid choice, please try again.")
