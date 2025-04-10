import os
from sonic_labs.solflare_manager import SolflareManager
from sonic_labs.jupiter_perps_flow import JupiterPerpsFlow
from dotenv import load_dotenv

load_dotenv()

def main():
    # Set paths and URL (update these as needed)
    EXTENSION_PATH = r"C:\v0.7\sonic_labs\solflare_wallet"  # Use the Solflare wallet unpacked folder
    DAPP_URL = "https://jup.ag/perps-legacy/short/SOL-SOL"
    solflare_password = os.environ.get("SOLFLARE_PASSWORD")

    # Initialize SolflareManager and launch the browser.
    sm = SolflareManager(extension_path=EXTENSION_PATH, headless=False)
    sm.launch_browser()

    # Create the JupiterPerpsFlow instance using our SolflareManager.
    jp = JupiterPerpsFlow(phantom_manager=sm)

    # Try connecting the wallet.
    try:
        sm.connect_wallet(dapp_url=DAPP_URL, solflare_password=solflare_password)
        print("✅ Wallet connected!")
    except Exception as e:
        print("Error connecting wallet:", e)

    # Main interactive menu with Unicode icons.
    while True:
        print("\nAvailable commands:")
        print("1: Connect Wallet 🔗")
        print("2: Approve Transaction ✅")
        print("3: Unlock Solflare 🔓")
        print("4: Set Position Type 📈")
        print("5: Select Payment Asset 💰")
        print("6: Set Order Type 💱")
        print("7: Set Position Size 📏")
        print("8: Set Leverage ⚖️")
        print("9: Open Position 🚀")
        print("10: Capture Order Payload 📦")
        print("11: Withdraw Funds via Row 💸")
        print("12: Exit ❌")
        print("13: Select Position Pencil ✏️")
        print("14: Withdraw Funds via Modal 💸")
        cmd = input("Enter command number: ").strip()

        if cmd == "1":
            try:
                sm.connect_wallet(dapp_url=DAPP_URL, solflare_password=solflare_password)
                print("✅ Wallet connected!")
            except Exception as e:
                print("Error connecting wallet:", e)
        elif cmd == "2":
            try:
                sm.approve_transaction(transaction_trigger_selector="text=Confirm")
                print("✅ Transaction approved!")
            except Exception as e:
                print("Error approving transaction:", e)
        elif cmd == "3":
            if solflare_password:
                try:
                    sm.unlock_solflare(solflare_password)
                    print("🔓 Solflare unlocked!")
                except Exception as e:
                    print("Error unlocking Solflare:", e)
            else:
                print("⚠️ No Solflare password provided. Set SOLFLARE_PASSWORD in your .env file.")
        elif cmd == "4":
            pos_type = input("📈 Enter position type (long/short): ").strip().lower()
            try:
                jp.select_position_type(pos_type)
                print("✅ Position type set to", pos_type)
            except Exception as e:
                print("Error selecting position type:", e)
        elif cmd == "5":
            asset = input("💰 Enter payment asset (e.g., SOL, USDT, USDC, WBTC, WETH): ").strip().upper()
            try:
                jp.select_payment_asset(asset)
                print("✅ Payment asset set to", asset)
            except Exception as e:
                print("Error selecting payment asset:", e)
        elif cmd == "6":
            order_type = input("💱 Enter order type (market/limit): ").strip().lower()
            try:
                jp.select_order_type(order_type)
                print("✅ Order type set to", order_type)
            except Exception as e:
                print("Error selecting order type:", e)
        elif cmd == "7":
            size = input("📏 Enter position size: ").strip()
            try:
                jp.set_position_size(size)
                print("✅ Position size set to", size)
            except Exception as e:
                print("Error setting position size:", e)
        elif cmd == "8":
            leverage = input("⚖️ Enter leverage (e.g., 7.8x): ").strip()
            try:
                jp.set_leverage(leverage)
                print("✅ Leverage set to", leverage)
            except Exception as e:
                print("Error setting leverage:", e)
        elif cmd == "9":
            try:
                jp.open_position()
                print("🚀 Position opened!")
            except Exception as e:
                print("Error opening position:", e)
        elif cmd == "10":
            keyword = input("📦 Enter URL keyword to capture order payload (e.g., 'order-submit'): ").strip()
            try:
                payload = sm.capture_order_payload(keyword)
                print("✅ Captured order payload:")
                print(payload)
            except Exception as e:
                print("Error capturing order payload:", e)
        elif cmd == "11":
            # Withdraw Funds via Row method.
            assets = ["SOL", "USDT", "USDC", "WBTC", "WETH"]
            position_types = ["long", "short"]

            print("\nSelect asset for withdrawal (Row method):")
            for idx, asset in enumerate(assets, start=1):
                print(f"{idx}: {asset}")
            asset_choice = input("Enter choice number: ").strip()
            try:
                selected_asset = assets[int(asset_choice) - 1]
            except (IndexError, ValueError):
                print("Invalid asset selection.")
                continue

            print("\nSelect position type (Row method):")
            for idx, pos in enumerate(position_types, start=1):
                print(f"{idx}: {pos}")
            pos_choice = input("Enter choice number: ").strip()
            try:
                selected_position = position_types[int(pos_choice) - 1]
            except (IndexError, ValueError):
                print("Invalid position type selection.")
                continue

            withdraw_amount = input("\nEnter withdraw amount: ").strip()
            try:
                payload = jp.withdraw_funds_row(selected_asset, selected_position, withdraw_amount)
                print("✅ Withdrawal (Row) request submitted!")
                print("Captured payload:")
                print(payload)
            except Exception as e:
                print("Error during withdrawal (Row):", e)
        elif cmd == "13":
            # Manually select the collateral pencil.
            assets = ["SOL", "USDT", "USDC", "WBTC", "WETH"]
            position_types = ["long", "short"]

            print("\nSelect asset for position pencil:")
            for idx, asset in enumerate(assets, start=1):
                print(f"{idx}: {asset}")
            asset_choice = input("Enter choice number: ").strip()
            try:
                selected_asset = assets[int(asset_choice) - 1]
            except (IndexError, ValueError):
                print("Invalid asset selection.")
                continue

            print("\nSelect position type for position pencil:")
            for idx, pos in enumerate(position_types, start=1):
                print(f"{idx}: {pos}")
            pos_choice = input("Enter choice number: ").strip()
            try:
                selected_position = position_types[int(pos_choice) - 1]
            except (IndexError, ValueError):
                print("Invalid position type selection.")
                continue

            try:
                jp.click_collateral_pencil(selected_asset, selected_position)
                print(f"✅ Collateral pencil for {selected_asset} {selected_position} selected!")
            except Exception as e:
                print("Error selecting collateral pencil:", e)
        elif cmd == "14":
            # Withdraw Funds via Modal method.
            assets = ["SOL", "USDT", "USDC", "WBTC", "WETH"]
            position_types = ["long", "short"]

            print("\nSelect asset for withdrawal (Modal method):")
            for idx, asset in enumerate(assets, start=1):
                print(f"{idx}: {asset}")
            asset_choice = input("Enter choice number: ").strip()
            try:
                selected_asset = assets[int(asset_choice) - 1]
            except (IndexError, ValueError):
                print("Invalid asset selection.")
                continue

            print("\nSelect position type (Modal method):")
            for idx, pos in enumerate(position_types, start=1):
                print(f"{idx}: {pos}")
            pos_choice = input("Enter choice number: ").strip()
            try:
                selected_position = position_types[int(pos_choice) - 1]
            except (IndexError, ValueError):
                print("Invalid position type selection.")
                continue

            withdraw_amount = input("\nEnter withdraw amount: ").strip()
            try:
                payload = jp.withdraw_funds_modal(selected_asset, selected_position, withdraw_amount)
                print("✅ Withdrawal (Modal) request submitted!")
                print("Captured payload:")
                print(payload)
            except Exception as e:
                print("Error during withdrawal (Modal):", e)
        elif cmd == "12":
            print("❌ Exiting...")
            break
        else:
            print("❓ Invalid command. Please try again.")

    sm.close()

if __name__ == "__main__":
    main()
