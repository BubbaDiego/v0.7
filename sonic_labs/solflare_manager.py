import logging
import os
from playwright.sync_api import sync_playwright, Error
from dotenv import load_dotenv
load_dotenv()

# =============================================================================
# Logging Configuration
# -----------------------------------------------------------------------------
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh = logging.FileHandler('solflare_manager.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)


# =============================================================================
# SolflareManager Class
# -----------------------------------------------------------------------------
class SolflareManager:
    def __init__(self, extension_path: str, user_data_dir: str = "playwright-data", headless: bool = False):
        """
        Initialize the SolflareManager.
        
        :param extension_path: Path to the unpacked Solflare extension folder.
        :param user_data_dir: Directory for persistent browser data.
        :param headless: Whether to run the browser in headless mode.
        """
        self.extension_path = extension_path
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.browser_context = None
        self.playwright = None
        self.page = None
        self.popup = None
        self.solflare_id = None

        if self.extension_path.lower().endswith('.crx'):
            logger.warning("Provided extension_path is a .crx file. Please extract it to an unpacked folder.")

    def launch_browser(self):
        logger.debug("Launching browser with Solflare extension from %s", self.extension_path)
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
            logger.error("Error launching browser context: %s", e)
            raise

        self.page = self.browser_context.new_page()
        self.page.on("console", lambda msg: logger.debug("PAGE CONSOLE: %s", msg.text))

        # Adjust timeout based on whether user data already exists.
        timeout_value = 2500 if os.path.exists(self.user_data_dir) and os.listdir(self.user_data_dir) else 30000
        logger.debug("Using service worker timeout: %d ms", timeout_value)

        logger.debug("Waiting for service worker to register Solflare extension (timeout %d ms)...", timeout_value)
        try:
            sw = self.browser_context.wait_for_event("serviceworker", timeout=timeout_value)
            # Extract the extension ID from the service worker URL.
            self.solflare_id = sw.url.split("/")[2]
            logger.debug("Solflare extension loaded with ID: %s", self.solflare_id)
        except Error as e:
            logger.error("Service worker not registered within timeout: %s", e)
            # Fallback ID if needed (this ID might differ; update accordingly)
            fallback_id = "solflarefallbackid"
            logger.debug("Assuming Solflare extension ID as fallback: %s", fallback_id)
            self.solflare_id = fallback_id

    def open_solflare_popup(self):
        if not self.solflare_id:
            logger.error("Solflare extension not loaded. Call launch_browser() first.")
            raise Exception("Solflare extension not loaded. Call launch_browser() first.")
        logger.debug("Opening Solflare popup UI...")
        self.popup = self.browser_context.new_page()
        self.popup.on("console", lambda msg: logger.debug("POPUP CONSOLE: %s", msg.text))
        try:
            self.popup.goto(f"chrome-extension://{self.solflare_id}/popup.html", timeout=10000)
            self.popup.wait_for_load_state()
            logger.debug("Solflare popup UI loaded. URL: %s", self.popup.url)
        except Error as e:
            logger.error("Error loading Solflare popup: %s", e)
            raise
        return self.popup

    def unlock_solflare(self, solflare_password: str):
        """
        Unlocks the Solflare wallet by:
          1. Waiting for the password input field (using its data-testid attribute).
          2. Filling in the password.
          3. Clicking the unlock/submit button.
        """
        logger.debug("Unlocking Solflare: selecting password input field.")
        if self.popup is None or self.popup.is_closed():
            logger.debug("Solflare popup not open; opening popup for unlocking.")
            self.open_solflare_popup()
        try:
            # Wait for the password input field.
            self.popup.wait_for_selector("input[data-testid='solflare-unlock-password-input']", timeout=5000)
            logger.debug("Solflare password input detected. Filling in password.")
            self.popup.fill("input[data-testid='solflare-unlock-password-input']", solflare_password, timeout=2000)
            logger.debug("Clicking the Solflare unlock button.")
            self.popup.click("button[data-testid='solflare-unlock-submit-button']", timeout=5000)
            logger.debug("Clicked unlock button. Waiting briefly for unlock to complete...")
            self.popup.wait_for_timeout(2000)
        except Error as e:
            logger.error("Error unlocking Solflare: %s", e)
            raise

    def approve_transaction(self, transaction_trigger_selector: str,
                            confirm_selectors: list = None,
                            trigger_timeout: int = 10000,
                            confirm_timeout: int = 5000):
        """
        Triggers the transaction and approves it in Solflare by clicking the Confirm button.
        Candidate selectors are used to handle potential UI variations.
        """
        logger.debug("Triggering transaction with selector: %s", transaction_trigger_selector)
        try:
            self.page.click(transaction_trigger_selector, timeout=trigger_timeout)
        except Error as e:
            logger.error("Error triggering transaction: %s", e)
            raise

        if not self.popup or self.popup.is_closed():
            logger.debug("Solflare popup not open; opening popup for transaction approval.")
            self.open_solflare_popup()
        else:
            logger.debug("Bringing Solflare popup to front and reloading to update state.")
            self.popup.bring_to_front()
            self.popup.reload()

        if confirm_selectors is None:
            confirm_selectors = [
                "button[data-testid='primary-button']:has-text('Confirm Transaction')",
                "button[data-testid='primary-button']:has-text('Confirm')",
                "text=Confirm"
            ]
        success = False
        for selector in confirm_selectors:
            try:
                logger.debug("Waiting for confirm button with selector: %s", selector)
                self.popup.wait_for_selector(selector, timeout=confirm_timeout)
                logger.debug("Clicking confirm button with selector: %s", selector)
                self.popup.click(selector, timeout=confirm_timeout)
                success = True
                break
            except Error as e:
                logger.warning("Confirm button not found with selector %s: %s", selector, e)
                continue

        if not success:
            logger.error("Failed to click any confirm button with provided selectors.")
            raise Exception("Transaction approval failed: No confirm button found.")

        logger.debug("Transaction approved (Confirm clicked).")

    def connect_wallet(self, dapp_url: str,
                       dapp_connect_selector: str = "css=span.text-v2-primary",
                       popup_connect_selector: str = "text=Connect",
                       wallet_selection_selector: str = "text=Use this wallet",
                       dapp_connected_selector: str = "text=Connected",
                       solflare_password: str = None):
        """
        Connects the Solflare wallet to the dApp by navigating to the dApp,
        triggering the connect flow, opening the Solflare popup, and unlocking it.
        """
        logger.debug("Navigating to dApp: %s", dapp_url)
        try:
            self.page.goto(dapp_url, timeout=15000)
            logger.debug("dApp page loaded. Current URL: %s", self.page.url)
        except Error as e:
            logger.error("Error navigating to dApp: %s", e)
            raise

        logger.debug("Checking if wallet is already connected using selector: %s", dapp_connected_selector)
        try:
            self.page.wait_for_selector(dapp_connected_selector, timeout=5000)
            logger.debug("Wallet already connected on dApp. Skipping connect flow.")
            return
        except Error:
            logger.debug("Wallet not connected; proceeding with connect flow.")

        logger.debug("Waiting for dApp connect button with selector: %s", dapp_connect_selector)
        try:
            self.page.wait_for_selector(dapp_connect_selector, timeout=15000)
            logger.debug("Clicking dApp connect button with selector: %s", dapp_connect_selector)
            self.page.click(dapp_connect_selector, timeout=10000)
        except Error as e:
            logger.error("Error clicking dApp connect button: %s", e)
            raise

        logger.debug("Opening Solflare popup to approve wallet connection.")
        popup = self.open_solflare_popup()
        if solflare_password:
            self.unlock_solflare(solflare_password)
        else:
            logger.warning("No Solflare password provided. Please disable auto-lock in Solflare settings as a backup.")

        self.handle_onboarding()  # if Solflare has an onboarding flow
        if popup.is_closed():
            logger.debug("Solflare popup closed after onboarding, reopening.")
            popup = self.open_solflare_popup()

        success = False
        attempts = 0
        max_attempts = 2
        while not success and attempts < max_attempts:
            try:
                popup.wait_for_selector(popup_connect_selector, timeout=10000)
                logger.debug("Clicking Solflare popup connect button with selector: %s", popup_connect_selector)
                popup.click(popup_connect_selector, timeout=10000)
                success = True
            except Error as e:
                if popup.is_closed():
                    logger.warning("Solflare popup closed unexpectedly; assuming connection is approved.")
                    success = True
                else:
                    attempts += 1
                    logger.error("Error in Solflare connect button flow (attempt %d): %s", attempts, e)
                    logger.debug("Reopening Solflare popup and retrying...")
                    popup = self.open_solflare_popup()
        if not success:
            logger.warning("Solflare connect button not found after multiple attempts; assuming connection is approved.")

        self.handle_wallet_selection(wallet_selector=wallet_selection_selector)
        logger.debug("Waiting for dApp to confirm wallet association using selector: %s", dapp_connected_selector)
        try:
            self.page.wait_for_selector(dapp_connected_selector, timeout=10000)
            logger.debug("dApp wallet association confirmed.")
        except Error as e:
            logger.warning("dApp wallet association not confirmed: %s", e)

    def capture_order_payload(self, url_keyword: str, timeout: int = 10000):
        """
        Waits for a network request whose URL contains the given keyword and returns its payload.
        This is intended to capture the final order data before it is signed.
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
            logger.debug("Captured order payload: %s", payload)
            return payload
        except Error as e:
            logger.error("Error capturing order payload: %s", e)
            raise

    def close(self):
        logger.debug("Closing browser context.")
        if self.browser_context:
            self.browser_context.close()
        if self.playwright:
            self.playwright.stop()
        logger.debug("Browser closed.")
