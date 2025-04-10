import logging
import os
from playwright.sync_api import sync_playwright, Error
from jupiter_perps_flow import JupiterPerpsFlow

# =============================================================================
# Logging Configuration
# -----------------------------------------------------------------------------
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh = logging.FileHandler('phantom_manager.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

# =============================================================================
# PhantomManager Class
# -----------------------------------------------------------------------------
class PhantomManager:
    def __init__(self, extension_path: str, user_data_dir: str = "playwright-data", headless: bool = False):
        """
        Initializes the PhantomManager.
        :param extension_path: Path to the unpacked Phantom extension folder.
        :param user_data_dir: Directory to store persistent browser data.
        :param headless: Whether to run in headless mode.
        """
        self.extension_path = extension_path
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.browser_context = None
        self.playwright = None
        self.page = None
        self.popup = None
        self.phantom_id = None

        if self.extension_path.lower().endswith('.crx'):
            logger.warning("Provided extension_path is a .crx file. Please extract it to an unpacked folder.")

    def launch_browser(self):
        logger.debug("🚀 Launching browser with Phantom extension from %s", self.extension_path)
        self.playwright = sync_playwright().start()
        try:
            self.browser_context = self.playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                channel="chrome",
                args=[
                    f"--disable-extensions-except={self.extension_path}",
                    f"--load-extension={self.extension_path}",
                    "--window-size=1280,720",
                    "--start-maximized"
                ]
            )
        except Error as e:
            logger.error("❌ Error launching browser context: %s", e)
            raise

        self.page = self.browser_context.new_page()
        self.page.on("requestfinished", lambda req: logger.debug("Request finished: %s", req.url))

        self.page.on("console", lambda msg: logger.debug("PAGE CONSOLE: %s", msg.text))

        if os.path.exists(self.user_data_dir) and os.listdir(self.user_data_dir):
            timeout_value = 5000
            logger.debug("🗃 Existing user data detected. Using shorter service worker timeout: %d ms", timeout_value)
        else:
            timeout_value = 30000
            logger.debug("🆕 Fresh user data. Using longer service worker timeout: %d ms", timeout_value)

        logger.debug("⏳ Waiting for service worker to register Phantom extension (timeout %d ms)...", timeout_value)
        try:
            sw = self.browser_context.wait_for_event("serviceworker", timeout=timeout_value)
            self.phantom_id = sw.url.split("/")[2]
            logger.debug("✅ Phantom extension loaded with ID: %s", self.phantom_id)
        except Error as e:
            logger.error("❌ Service worker not registered within timeout: %s", e)
            for idx, page in enumerate(self.browser_context.pages):
                logger.debug("Open page %s: %s", idx, page.url)
            fallback_id = "bfnaelmomeimhlpmgjnjophhpkkoljpa"
            logger.debug("🔄 Assuming Phantom extension ID as fallback: %s", fallback_id)
            self.phantom_id = fallback_id

    def open_phantom_popup(self):
        if not self.phantom_id:
            logger.error("❌ Phantom extension not loaded. Call launch_browser() first.")
            raise Exception("Phantom extension not loaded. Call launch_browser() first.")
        logger.debug("📨 Opening Phantom popup UI...")
        self.popup = self.browser_context.new_page()
        self.popup.on("console", lambda msg: logger.debug("POPUP CONSOLE: %s", msg.text))
        try:
            self.popup.goto(f"chrome-extension://{self.phantom_id}/popup.html", timeout=10000)
            self.popup.wait_for_load_state()
            logger.debug("✅ Phantom popup UI loaded. URL: %s", self.popup.url)
        except Error as e:
            logger.error("❌ Error loading Phantom popup: %s", e)
            raise
        return self.popup

    def unlock_phantom(self, phantom_password: str):
        logger.debug("🔓 Checking if Phantom is locked...")
        try:
            self.popup.wait_for_selector("input[type=password]", timeout=5000)
            logger.debug("Phantom password input detected. Attempting to unlock.")
            self.popup.fill("input[type=password]", phantom_password, timeout=2000)
            self.popup.click("text=Unlock", timeout=5000)
            logger.debug("✅ Clicked 'Unlock'. Waiting briefly for unlock to complete...")
            self.popup.wait_for_timeout(2000)
        except Error as e:
            logger.debug("ℹ️ No password field found or Phantom already unlocked: %s", e)

    def handle_onboarding(self):
        logger.debug("📝 Handling Phantom onboarding...")
        try:
            self.popup.wait_for_selector("text=I already have a wallet", timeout=15000)
            self.popup.click("text=I already have a wallet", timeout=10000)
            logger.debug("✅ Selected 'I already have a wallet' in onboarding.")
        except Error as e:
            if "Target page, context or browser has been closed" in str(e):
                logger.warning("⚠️ Phantom onboarding popup was closed. Skipping onboarding handling.")
            else:
                logger.warning("⚠️ Onboarding UI not detected or already handled: %s", e)

    def handle_wallet_selection(self, wallet_selector: str = "text=Use this wallet"):
        logger.debug("🔄 Handling wallet selection with selector: %s", wallet_selector)
        try:
            self.popup.wait_for_selector(wallet_selector, timeout=15000)
            self.popup.click(wallet_selector, timeout=10000)
            logger.debug("✅ Wallet selection completed.")
        except Error as e:
            logger.warning("⚠️ Wallet selection UI not detected or already handled: %s", e)

    def connect_wallet(self, dapp_url: str,
                       dapp_connect_selector: str = "css=span.text-v2-primary",
                       popup_connect_selector: str = "text=Connect",
                       wallet_selection_selector: str = "text=Use this wallet",
                       dapp_connected_selector: str = "text=Connected",
                       phantom_password: str = None):
        logger.debug("🌐 Navigating to dApp: %s", dapp_url)
        try:
            self.page.goto(dapp_url, timeout=15000)
            logger.debug("✅ dApp page loaded. Current URL: %s", self.page.url)
        except Error as e:
            logger.error("❌ Error navigating to dApp: %s", e)
            raise

        logger.debug("🔎 Checking if wallet is already connected using selector: %s", dapp_connected_selector)
        try:
            self.page.wait_for_selector(dapp_connected_selector, timeout=5000)
            logger.debug("✅ Wallet already connected on dApp. Skipping connect flow.")
            return
        except Error:
            logger.debug("❌ Wallet not connected; proceeding with connect flow.")

        logger.debug("⏳ Waiting for dApp connect button with selector: %s", dapp_connect_selector)
        try:
            self.page.wait_for_selector(dapp_connect_selector, timeout=15000)
            logger.debug("👉 Clicking dApp connect button with selector: %s", dapp_connect_selector)
            self.page.click(dapp_connect_selector, timeout=10000)
        except Error as e:
            logger.error("❌ Error clicking dApp connect button: %s", e)
            raise

        logger.debug("📨 Opening Phantom popup to approve wallet connection.")
        popup = self.open_phantom_popup()
        if phantom_password:
            self.unlock_phantom(phantom_password)
        else:
            logger.warning("⚠️ No Phantom password provided. Please disable auto-lock in Phantom settings as a backup.")

        self.handle_onboarding()
        if popup.is_closed():
            logger.debug("🔄 Phantom popup closed after onboarding, reopening.")
            popup = self.open_phantom_popup()

        success = False
        attempts = 0
        max_attempts = 2
        while not success and attempts < max_attempts:
            try:
                popup.wait_for_selector(popup_connect_selector, timeout=10000)
                logger.debug("👉 Clicking Phantom popup connect button with selector: %s", popup_connect_selector)
                popup.click(popup_connect_selector, timeout=10000)
                success = True
            except Error as e:
                if popup.is_closed():
                    logger.warning("⚠️ Phantom popup closed unexpectedly; assuming connection is approved.")
                    success = True
                else:
                    attempts += 1
                    logger.error("❌ Error in Phantom connect button flow (attempt %d): %s", attempts, e)
                    logger.debug("🔄 Reopening Phantom popup and retrying...")
                    popup = self.open_phantom_popup()
        if not success:
            logger.warning("⚠️ Phantom connect button not found after multiple attempts; assuming connection is approved.")

        self.handle_wallet_selection(wallet_selector=wallet_selection_selector)
        logger.debug("⏳ Waiting for dApp to confirm wallet association using selector: %s", dapp_connected_selector)
        try:
            self.page.wait_for_selector(dapp_connected_selector, timeout=10000)
            logger.debug("✅ DApp wallet association confirmed.")
        except Error as e:
            logger.warning("⚠️ DApp wallet association not confirmed: %s", e)

    def capture_order_payload(self, url_keyword: str, timeout: int = 10000):
        """
        Waits for a network request whose URL contains the given keyword and returns its payload.
        This is intended to capture the final order data before it is signed.

        :param url_keyword: A string that should appear in the order submission endpoint URL.
        :param timeout: Maximum wait time in milliseconds.
        :return: The order payload as a dictionary if JSON, else raw post data.
        """
        logger.debug("Waiting for network request with keyword: %s", url_keyword)
        try:
            request = self.page.wait_for_event(
                "requestfinished",
                predicate=lambda req: url_keyword in req.url,
                timeout=timeout
            )
            try:
                payload = request.post_data_json()
            except Exception:
                payload = request.post_data()
            logger.debug("✅ Captured order payload: %s", payload)
            return payload
        except Error as e:
            logger.error("❌ Error capturing order payload: %s", e)
            raise

    def approve_transaction(self, transaction_trigger_selector: str,
                            popup_approve_selector: str = "text=Approve"):
        logger.debug("💸 Triggering transaction with selector: %s", transaction_trigger_selector)
        try:
            self.page.click(transaction_trigger_selector, timeout=10000)
        except Error as e:
            logger.error("❌ Error triggering transaction: %s", e)
            raise

        if not self.popup:
            logger.debug("📨 Opening Phantom popup for transaction approval.")
            self.open_phantom_popup()
        else:
            logger.debug("🔄 Bringing Phantom popup to front and reloading to update state.")
            self.popup.bring_to_front()
            self.popup.reload()

        try:
            logger.debug("⏳ Waiting for transaction approval button with selector: %s", popup_approve_selector)
            self.popup.wait_for_selector(popup_approve_selector, timeout=5000)
            logger.debug("👉 Clicking transaction approval button.")
            self.popup.click(popup_approve_selector, timeout=5000)
        except Error as e:
            logger.error("❌ Error approving transaction: %s", e)
            raise
        logger.debug("✅ Transaction approved.")

    def close(self):
        logger.debug("🔒 Closing browser context.")
        if self.browser_context:
            self.browser_context.close()
        if self.playwright:
            self.playwright.stop()
        logger.debug("✅ Browser closed.")


# =============================================================================
# JupiterPerpsFlow Class (in jupiter_perps_flow.py)
# -----------------------------------------------------------------------------
class JupiterPerpsFlow:
    def __init__(self, phantom_manager):
        """
        Initializes with an existing PhantomManager instance.
        :param phantom_manager: An instance of PhantomManager.
        """
        self.pm = phantom_manager
        self.page = phantom_manager.page

    def select_position_type(self, position_type: str):
        logger.debug("Selecting position type: %s", position_type)
        if position_type.lower() == "long":
            try:
                self.page.click("button:has-text('Long')", timeout=10000)
                logger.debug("✅ Long position selected.")
            except Error as e:
                logger.error("❌ Error selecting Long position: %s", e)
                raise
        elif position_type.lower() == "short":
            try:
                self.page.click("button:has-text('Short')", timeout=10000)
                logger.debug("✅ Short position selected.")
            except Error as e:
                logger.error("❌ Error selecting Short position: %s", e)
                raise
        else:
            logger.error("❌ Invalid position type provided: %s", position_type)
            raise Exception("Invalid position type provided. Choose 'long' or 'short'.")

    def select_order_type(self, order_type: str):
        logger.debug("Selecting order type: %s", order_type)
        if order_type.lower() == "market":
            try:
                self.page.click("button:has-text('Market')", timeout=10000)
                logger.debug("✅ Market order type selected.")
            except Error as e:
                logger.error("❌ Error selecting Market order type: %s", e)
                raise
        elif order_type.lower() == "limit":
            try:
                self.page.click("button:has-text('Limit')", timeout=10000)
                logger.debug("✅ Limit order type selected.")
            except Error as e:
                logger.error("❌ Error selecting Limit order type: %s", e)
                raise
        else:
            logger.error("❌ Invalid order type provided: %s", order_type)
            raise Exception("Invalid order type provided. Choose 'market' or 'limit'.")

    def select_payment_asset(self, asset_symbol: str):
        logger.debug("Selecting payment asset: %s", asset_symbol)
        try:
            # Click the pulldown button that opens the asset list.
            self.page.click("button.bg-v3-input-secondary-background", timeout=5000)
            logger.debug("Pulldown button clicked to reveal asset options.")
            # Click on the asset option in the dropdown (either a div or span).
            self.page.click(f"li:has-text('{asset_symbol}')", timeout=5000)
            logger.debug("✅ Payment asset selected: %s", asset_symbol)
        except Error as e:
            logger.error("❌ Error selecting payment asset (%s): %s", asset_symbol, e)
            raise

    def set_position_size(self, size: str):
        logger.debug("Setting position size: %s", size)
        try:
            # Use a selector that targets the input within the container labeled "Size of"
            self.page.fill("div:has-text('Size of') input[type='text']", size, timeout=5000)
            logger.debug("✅ Position size set to %s", size)
        except Error as e:
            logger.error("❌ Error setting position size: %s", e)
            raise

    def set_leverage(self, leverage: str):
        logger.debug("Setting leverage: %s", leverage)
        try:
            # Use a selector that targets the input within the container labeled "Leverage"
            self.page.fill("div:has-text('Leverage') input[type='text']", leverage, timeout=5000)
            logger.debug("✅ Leverage set to %s", leverage)
        except Error as e:
            logger.error("❌ Error setting leverage: %s", e)
            raise

    def open_position(self):
        logger.debug("Opening position on dApp...")
        try:
            self.page.click("text=Open Position", timeout=10000)
            logger.debug("✅ Position open triggered on dApp.")
        except Error as e:
            logger.error("❌ Error opening position: %s", e)
            raise
        print("Position opened.")


# =============================================================================
# Interactive Console App
# -----------------------------------------------------------------------------
def interactive_console():
    EXTENSION_PATH = r"C:\v0.7\sonic_labs\phantom_wallet"
    dapp_url = "https://jup.ag/perps-legacy/short/SOL-SOL"
    phantom_password = os.environ.get("PHANTOM_PASSWORD")

    pm = PhantomManager(extension_path=EXTENSION_PATH, headless=False)
    pm.launch_browser()

    # Uncomment if you need to manually complete onboarding:
    # input("🔑 Please complete Phantom onboarding manually (enter your security phrase, set up your wallet, etc.), then press Enter to continue...")

    jp = JupiterPerpsFlow(phantom_manager=pm)

    # Example scenario using the new calls:
    try:
        pm.connect_wallet(dapp_url=dapp_url, phantom_password=phantom_password)
        print("✅ Wallet connected!")
    except Exception as e:
        print("❌ Error connecting wallet:", e)

#    try:
#        jp.select_position_type("long")
#        jp.select_order_type("market")
##        jp.select_payment_asset("USDT")
#        jp.set_position_size("1.5")
#        jp.set_leverage("3")
#        jp.open_position()
#        print("✅ Transaction workflow executed!")
#    except Exception as e:
#        print("❌ Error executing transaction workflow:", e)

    # Optionally capture order payload right before signing.
    try:
        payload = pm.capture_order_payload("order")
        print("📦 Captured Order Payload:", payload)
    except Exception as e:
        print("❌ Error capturing order payload:", e)

    while True:
        print("\nAvailable commands:")
        print("1: Connect Wallet 🔗")
        print("2: Approve Transaction ✅")
        print("3: Unlock Phantom 🔓")
        print("4: Set Position Type 📈")
        print("5: Select Payment Asset 💰")
        print("6: Set Order Type 💱")
        print("7: Set Position Size 📏")
        print("8: Set Leverage ⚖️")
        print("9: Open Position 🚀")
        print("10: Capture Order Payload 📦")
        print("11: Exit ❌")
        cmd = input("Enter command number: ").strip()

        if cmd == "1":
            try:
                pm.connect_wallet(dapp_url=dapp_url, phantom_password=phantom_password)
                print("✅ Wallet connected!")
            except Exception as e:
                print("❌ Error connecting wallet:", e)
        elif cmd == "2":
            try:
                pm.approve_transaction(transaction_trigger_selector="text=Send Transaction")
                print("✅ Transaction approved!")
            except Exception as e:
                print("❌ Error approving transaction:", e)
        elif cmd == "3":
            if phantom_password:
                try:
                    pm.unlock_phantom(phantom_password)
                    print("🔓 Phantom unlocked!")
                except Exception as e:
                    print("❌ Error unlocking Phantom:", e)
            else:
                print("⚠️ No Phantom password provided. Please set PHANTOM_PASSWORD or disable auto-lock in Phantom settings.")
        elif cmd == "4":
            pos_type = input("📈 Enter position type (long/short): ").strip().lower()
            try:
                jp.select_position_type(pos_type)
            except Exception as e:
                print("❌ Error selecting position type:", e)
        elif cmd == "5":
            asset = input("💰 Enter payment asset (e.g., SOL, USDT, USDC, WBTC, WETH): ").strip().upper()
            try:
                jp.select_payment_asset(asset)
            except Exception as e:
                print("❌ Error selecting payment asset:", e)
        elif cmd == "6":
            order_type = input("💱 Enter order type (market/limit): ").strip().lower()
            try:
                jp.select_order_type(order_type)
            except Exception as e:
                print("❌ Error selecting order type:", e)
        elif cmd == "7":
            size = input("📏 Enter position size: ").strip()
            try:
                jp.set_position_size(size)
            except Exception as e:
                print("❌ Error setting position size:", e)
        elif cmd == "8":
            leverage = input("⚖️ Enter leverage: ").strip()
            try:
                jp.set_leverage(leverage)
            except Exception as e:
                print("❌ Error setting leverage:", e)
        elif cmd == "9":
            try:
                jp.open_position()
                print("🚀 Position opened!")
            except Exception as e:
                print("❌ Error opening position:", e)
        elif cmd == "10":
            try:
                payload = pm.capture_order_payload("order")
                print("📦 Captured Order Payload:", payload)
            except Exception as e:
                print("❌ Error capturing order payload:", e)
        elif cmd == "11":
            print("❌ Exiting...")
            break
        else:
            print("❓ Invalid command. Please try again.")

    pm.close()

# =============================================================================
# Main Execution Block
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    interactive_console()
