import logging
import os
from playwright.sync_api import sync_playwright, Error

# Set up logging to both file and console.
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# File handler: logs to phantom_manager.log in the current directory.
fh = logging.FileHandler('phantom_manager.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

# Console handler: logs to the console.
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)


class PhantomManager:
    """
    Manages launching a Playwright browser with the Phantom wallet extension,
    and automates connecting the wallet, handling onboarding, and approving transactions.
    """

    def __init__(self, extension_path: str, user_data_dir: str = "playwright-data", headless: bool = False):
        """
        :param extension_path: Path to the unpacked Phantom extension folder.
        :param user_data_dir: Directory to store persistent browser data (for caching wallet state).
        :param headless: Run in headless mode (may require special configuration for extensions).
        """
        self.extension_path = extension_path
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.browser_context = None
        self.playwright = None
        self.page = None
        self.popup = None
        self.phantom_id = None

        # Warn if a .crx file is provided since Chrome requires an unpacked extension.
        if self.extension_path.lower().endswith('.crx'):
            logger.warning("Provided extension_path is a .crx file. Chrome requires an unpacked extension folder. Please extract the CRX file.")

    def launch_browser(self):
        """
        Launches the system Chrome browser with the Phantom extension loaded,
        and retrieves the extension ID from the service worker.
        Uses a shorter service worker timeout if an existing user_data_dir is detected.
        """
        logger.debug("Launching browser with Phantom extension from %s", self.extension_path)
        self.playwright = sync_playwright().start()
        try:
            self.browser_context = self.playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                channel="chrome",  # Use installed system Chrome for better extension support.
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

        # Determine timeout based on whether user_data_dir already exists and is non-empty.
        if os.path.exists(self.user_data_dir) and os.listdir(self.user_data_dir):
            timeout_value = 5000  # 5 seconds if reusing profile.
            logger.debug("Existing user data detected. Using shorter service worker timeout: %d ms", timeout_value)
        else:
            timeout_value = 30000  # 30 seconds for a fresh profile.
            logger.debug("Fresh user data. Using longer service worker timeout: %d ms", timeout_value)

        logger.debug("Waiting for service worker to register Phantom extension (timeout %d ms)...", timeout_value)
        try:
            sw = self.browser_context.wait_for_event("serviceworker", timeout=timeout_value)
            self.phantom_id = sw.url.split("/")[2]
            logger.debug("Phantom extension loaded with ID: %s", self.phantom_id)
        except Error as e:
            logger.error("Service worker not registered within timeout: %s", e)
            # Log the open pages for debugging.
            for idx, page in enumerate(self.browser_context.pages):
                logger.debug("Open page %s: %s", idx, page.url)
            # Fallback: use Phantom's known extension ID.
            fallback_id = "bfnaelmomeimhlpmgjnjophhpkkoljpa"
            logger.debug("Assuming Phantom extension ID as fallback: %s", fallback_id)
            self.phantom_id = fallback_id

    def open_phantom_popup(self):
        """
        Opens Phantom's popup UI in a new page for user interactions.
        """
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

    def handle_onboarding(self):
        """
        Handles the Phantom onboarding process by selecting 'I already have a wallet'.
        Adjust the text selector as needed based on your Phantom UI.
        """
        logger.debug("Handling Phantom onboarding...")
        try:
            self.popup.wait_for_selector("text=I already have a wallet", timeout=15000)
            self.popup.click("text=I already have a wallet", timeout=10000)
            logger.debug("Selected 'I already have a wallet' in onboarding.")
        except Error as e:
            logger.warning("Onboarding UI not detected or already handled: %s", e)

    def handle_wallet_selection(self, wallet_selector: str = "text=Use this wallet"):
        """
        Handles the wallet selection UI if Phantom asks which wallet to use.
        :param wallet_selector: The selector for the desired wallet option.
        """
        logger.debug("Handling wallet selection with selector: %s", wallet_selector)
        try:
            self.popup.wait_for_selector(wallet_selector, timeout=15000)
            self.popup.click(wallet_selector, timeout=10000)
            logger.debug("Wallet selection completed.")
        except Error as e:
            logger.warning("Wallet selection UI not detected or already handled: %s", e)

    def connect_wallet(self, dapp_url: str,
                       dapp_connect_selector: str = "text=Connect Wallet",
                       popup_connect_selector: str = "text=Connect",
                       wallet_selection_selector: str = "text=Use this wallet"):
        """
        Navigates to the dApp, clicks the connect button, and handles the Phantom onboarding/wallet selection.
        """
        logger.debug("Navigating to dApp: %s", dapp_url)
        try:
            self.page.goto(dapp_url, timeout=15000)
            logger.debug("dApp page loaded. Current URL: %s", self.page.url)
        except Error as e:
            logger.error("Error navigating to dApp: %s", e)
            raise

        logger.debug("Clicking dApp connect button with selector: %s", dapp_connect_selector)
        try:
            self.page.click(dapp_connect_selector, timeout=10000)
        except Error as e:
            logger.error("Error clicking dApp connect button: %s", e)
            raise

        logger.debug("Opening Phantom popup to approve wallet connection.")
        popup = self.open_phantom_popup()
        # Handle onboarding if it appears.
        self.handle_onboarding()
        try:
            popup.wait_for_selector(popup_connect_selector, timeout=10000)
            logger.debug("Clicking Phantom popup connect button with selector: %s", popup_connect_selector)
            popup.click(popup_connect_selector, timeout=10000)
        except Error as e:
            logger.error("Error in Phantom connect button flow: %s", e)
            raise

        # Handle wallet selection if Phantom asks which wallet to use.
        self.handle_wallet_selection(wallet_selector=wallet_selection_selector)
        logger.debug("Wallet connected.")

    def approve_transaction(self, transaction_trigger_selector: str,
                            popup_approve_selector: str = "text=Approve"):
        """
        Triggers a transaction on the dApp and approves it via Phantom.
        """
        logger.debug("Triggering transaction with selector: %s", transaction_trigger_selector)
        try:
            self.page.click(transaction_trigger_selector, timeout=10000)
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

        try:
            logger.debug("Waiting for transaction approval button with selector: %s", popup_approve_selector)
            self.popup.wait_for_selector(popup_approve_selector, timeout=10000)
            logger.debug("Clicking transaction approval button.")
            self.popup.click(popup_approve_selector, timeout=10000)
        except Error as e:
            logger.error("Error approving transaction: %s", e)
            raise
        logger.debug("Transaction approved.")

    def close(self):
        """
        Closes the browser context and stops Playwright.
        """
        logger.debug("Closing browser context.")
        if self.browser_context:
            self.browser_context.close()
        if self.playwright:
            self.playwright.stop()
        logger.debug("Browser closed.")


# Example usage:
if __name__ == "__main__":
    EXTENSION_PATH = r"C:\v0.7\sonic_labs\phantom_wallet"  # Path to your unpacked Phantom extension folder.
    dapp_url = "https://jup.ag/perps-legacy/short/SOL-SOL"  # Replace with your dApp's URL

    phantom_manager = PhantomManager(extension_path=EXTENSION_PATH, headless=False)
    try:
        phantom_manager.launch_browser()
        phantom_manager.connect_wallet(dapp_url=dapp_url)
        phantom_manager.approve_transaction(transaction_trigger_selector="text=Send Transaction")
    except Exception as e:
        logger.error("An error occurred in main: %s", e)
    finally:
        phantom_manager.close()
