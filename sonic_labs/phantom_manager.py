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
        logger.debug("Launching browser with Phantom extension from %s", self.extension_path)
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

        if os.path.exists(self.user_data_dir) and os.listdir(self.user_data_dir):
            timeout_value = 2500
            logger.debug("Existing user data detected. Using shorter service worker timeout: %d ms", timeout_value)
        else:
            timeout_value = 30000
            logger.debug("Fresh user data. Using longer service worker timeout: %d ms", timeout_value)

        logger.debug("Waiting for service worker to register Phantom extension (timeout %d ms)...", timeout_value)
        try:
            sw = self.browser_context.wait_for_event("serviceworker", timeout=timeout_value)
            self.phantom_id = sw.url.split("/")[2]
            logger.debug("Phantom extension loaded with ID: %s", self.phantom_id)
        except Error as e:
            logger.error("Service worker not registered within timeout: %s", e)
            for idx, page in enumerate(self.browser_context.pages):
                logger.debug("Open page %s: %s", idx, page.url)
            fallback_id = "bfnaelmomeimhlpmgjnjophhpkkoljpa"
            logger.debug("Assuming Phantom extension ID as fallback: %s", fallback_id)
            self.phantom_id = fallback_id

    def open_phantom_popup(self):
        if not self.phantom_id:
            logger.error("Phantom extension not loaded. Call launch_browser() first.")
            raise Exception("Phantom extension not loaded. Call launch_browser() first.")
        logger.debug("Opening Phantom popup UI...")
        self.popup = self.browser_context.new_page()
        self.popup.on("console", lambda msg: logger.debug("POPUP CONSOLE: %s", msg.text))
        try:
            self.popup.goto(f"chrome-extension://{self.phantom_id}/popup.html", timeout=10000)
            self.popup.wait_for_load_state()
            logger.debug("Phantom popup UI loaded. URL: %s", self.popup.url)
        except Error as e:
            logger.error("Error loading Phantom popup: %s", e)
            raise
        return self.popup

    def dismiss_post_unlock_dialog(self):
        """
        Sometimes Phantom shows a dialog saying 'Click this dialog to continue.'
        This method clicks that dialog to dismiss it if present.
        """
        overlay_selector = "text=Click this dialog to continue"
        try:
            # Wait briefly for the overlay to appear.
            self.popup.wait_for_selector(overlay_selector, timeout=3000)
            # Click it to dismiss.
            self.popup.click(overlay_selector)
            logger.debug("Dismissed the 'Click this dialog to continue' overlay.")
            # Optionally wait a moment for Phantom to settle.
            self.popup.wait_for_timeout(1000)
        except Error as e:
            # If not found or times out, just log it. It's not always present.
            logger.debug("No post-unlock dialog overlay found or timed out: %s", e)


    def approve_transaction(
            self,
            transaction_trigger_selector: str,
            primary_confirm_selector: str = "button[data-testid='primary-button']:has-text('Confirm Transaction')",
            fallback_confirm_selector: str = "button[data-testid='primary-button']:has-text('Confirm')",
            trigger_timeout: int = 10000,
            confirm_timeout: int = 5000
    ):
        """
        Triggers the transaction and approves it by clicking the Confirm button.
        Uses a primary and fallback selector for robustness.
        """
        logger.debug("Triggering transaction with selector: %s", transaction_trigger_selector)
        try:
            self.page.click(transaction_trigger_selector, timeout=trigger_timeout)
        except Error as e:
            logger.error("Error triggering transaction: %s", e)
            raise

        if not self.popup:
            logger.debug("Opening Phantom popup for transaction approval.")
            self.open_phantom_popup()
        else:
            logger.debug("Bringing Phantom popup to front and reloading to update state.")
            self.popup.bring_to_front()
            self.popup.reload()

        # Try to click the primary Confirm button; if that fails, try the fallback.
        try:
            logger.debug("Waiting for primary confirm button with selector: %s", primary_confirm_selector)
            self.popup.wait_for_selector(primary_confirm_selector, timeout=confirm_timeout)
            logger.debug("Clicking the primary confirm button.")
            self.popup.click(primary_confirm_selector, timeout=confirm_timeout)
        except Error as e:
            logger.warning("Primary confirm selector failed: %s", e)
            logger.debug("Falling back to fallback confirm selector: %s", fallback_confirm_selector)
            try:
                self.popup.wait_for_selector(fallback_confirm_selector, timeout=confirm_timeout)
                logger.debug("Clicking the fallback confirm button.")
                self.popup.click(fallback_confirm_selector, timeout=confirm_timeout)
            except Error as e2:
                logger.error("Error approving transaction with fallback: %s", e2)
                raise

        logger.debug("Transaction approved (Confirm clicked).")

    def handle_onboarding(self):
        logger.debug("Handling Phantom onboarding...")
        try:
            self.popup.wait_for_selector("text=I already have a wallet", timeout=15000)
            self.popup.click("text=I already have a wallet", timeout=10000)
            logger.debug("Selected 'I already have a wallet' in onboarding.")
        except Error as e:
            if "Target page, context or browser has been closed" in str(e):
                logger.warning("Phantom onboarding popup was closed. Skipping onboarding handling.")
            else:
                logger.warning("Onboarding UI not detected or already handled: %s", e)

    def handle_wallet_selection(self, wallet_selector: str = "text=Use this wallet"):
        logger.debug("Handling wallet selection with selector: %s", wallet_selector)
        try:
            self.popup.wait_for_selector(wallet_selector, timeout=15000)
            self.popup.click(wallet_selector, timeout=10000)
            logger.debug("Wallet selection completed.")
        except Error as e:
            logger.warning("Wallet selection UI not detected or already handled: %s", e)

    def connect_wallet(self, dapp_url: str,
                       dapp_connect_selector: str = "css=span.text-v2-primary",
                       popup_connect_selector: str = "text=Connect",
                       wallet_selection_selector: str = "text=Use this wallet",
                       dapp_connected_selector: str = "text=Connected",
                       phantom_password: str = None):
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

        logger.debug("Opening Phantom popup to approve wallet connection.")
        popup = self.open_phantom_popup()
        if phantom_password:
            self.unlock_phantom(phantom_password)
        else:
            logger.warning("No Phantom password provided. Please disable auto-lock in Phantom settings as a backup.")

        self.handle_onboarding()
        if popup.is_closed():
            logger.debug("Phantom popup closed after onboarding, reopening.")
            popup = self.open_phantom_popup()

        success = False
        attempts = 0
        max_attempts = 2
        while not success and attempts < max_attempts:
            try:
                popup.wait_for_selector(popup_connect_selector, timeout=10000)
                logger.debug("Clicking Phantom popup connect button with selector: %s", popup_connect_selector)
                popup.click(popup_connect_selector, timeout=10000)
                success = True
            except Error as e:
                if popup.is_closed():
                    logger.warning("Phantom popup closed unexpectedly; assuming connection is approved.")
                    success = True
                else:
                    attempts += 1
                    logger.error("Error in Phantom connect button flow (attempt %d): %s", attempts, e)
                    logger.debug("Reopening Phantom popup and retrying...")
                    popup = self.open_phantom_popup()
        if not success:
            logger.warning("Phantom connect button not found after multiple attempts; assuming connection is approved.")

        self.handle_wallet_selection(wallet_selector=wallet_selection_selector)
        logger.debug("Waiting for dApp to confirm wallet association using selector: %s", dapp_connected_selector)
        try:
            self.page.wait_for_selector(dapp_connected_selector, timeout=10000)
            logger.debug("DApp wallet association confirmed.")
        except Error as e:
            logger.warning("DApp wallet association not confirmed: %s", e)

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
            logger.debug("Captured order payload: %s", payload)
            return payload
        except Error as e:
            logger.error("Error capturing order payload: %s", e)
            raise

    def unlock_phantom(self, phantom_password: str):
        logger.debug("Unlocking Phantom: selecting password input field.")
        # Ensure the popup is open.
        if self.popup is None or self.popup.is_closed():
            logger.debug("Phantom popup not open; opening popup for unlocking.")
            self.open_phantom_popup()
        try:
            # Wait for the password input field using its data-testid.
            self.popup.wait_for_selector("input[data-testid='unlock-form-password-input']", timeout=5000)
            logger.debug("Phantom password input detected. Filling in password.")
            self.popup.fill("input[data-testid='unlock-form-password-input']", phantom_password, timeout=2000)
            logger.debug("Password entered; now clicking the unlock button.")
            self.popup.click("button[data-testid='unlock-form-submit-button']", timeout=5000)
            logger.debug("Clicked unlock button. Waiting briefly for unlock to complete...")
            self.popup.wait_for_timeout(2000)
            # Dismiss any extra overlay if present.
            self.dismiss_post_unlock_dialog()
        except Error as e:
            logger.error("Error unlocking Phantom: %s", e)
            raise

    def approve_transaction(
            self,
            transaction_trigger_selector: str,
            confirm_selectors: list = None,
            trigger_timeout: int = 10000,
            confirm_timeout: int = 5000
    ):
        """
        Triggers the transaction and approves it in Phantom by clicking the Confirm button.
        It attempts a list of candidate selectors (for example, one that contains 'Confirm Transaction' and one with 'Confirm')
        so that if one selector fails the fallback is used.
        """
        logger.debug("Triggering transaction with selector: %s", transaction_trigger_selector)
        try:
            self.page.click(transaction_trigger_selector, timeout=trigger_timeout)
        except Error as e:
            logger.error("Error triggering transaction: %s", e)
            raise

        # Ensure the Phantom popup is available.
        if not self.popup or self.popup.is_closed():
            logger.debug("Phantom popup not open; opening popup for transaction approval.")
            self.open_phantom_popup()
        else:
            logger.debug("Bringing Phantom popup to front and reloading to update state.")
            self.popup.bring_to_front()
            self.popup.reload()

        # Define candidate confirm button selectors if none provided.
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

    def close(self):
        logger.debug("Closing browser context.")
        if self.browser_context:
            self.browser_context.close()
        if self.playwright:
            self.playwright.stop()
        logger.debug("Browser closed.")


def dismiss_post_unlock_dialog(self):
    """
    Some users have reported an extra overlay dialog that must be dismissed.
    This method waits for an element with text "Click this dialog to continue" and clicks it.
    """
    overlay_selector = "text=Click this dialog to continue"
    try:
        self.popup.wait_for_selector(overlay_selector, timeout=3000)
        self.popup.click(overlay_selector)
        logger.debug("Dismissed the post-unlock overlay dialog.")
        self.popup.wait_for_timeout(1000)
    except Error as e:
        logger.debug("No post-unlock dialog overlay found or timed out: %s", e)
