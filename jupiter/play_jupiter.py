import logging
import os
from playwright.sync_api import sync_playwright, TimeoutError

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():
    logging.info("Starting Playwright automation script with crypto wallet extension")

    # Set the path to your unpacked crypto wallet extension directory.
    extension_path = r"C:\path\to\your\crypto_wallet_extension"  # <-- update this!
    if not os.path.exists(extension_path):
        logging.error(f"Extension path {extension_path} does not exist. Verify the path and try again.")
        return

    # Set a persistent user data directory (needed for extensions)
    user_data_dir = r"C:\path\to\your\user_data_dir"  # <-- update this!
    os.makedirs(user_data_dir, exist_ok=True)

    with sync_playwright() as p:
        logging.info("Launching Chromium with persistent context to load the wallet extension")
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            slow_mo=50,
            args=[
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}"
            ]
        )

        # Open a new page (or use an existing one from the context)
        page = context.new_page()

        # (Optional) Go to chrome://extensions/ to confirm the extension loaded
        page.goto("chrome://extensions/")
        logging.info("Check chrome://extensions/ to verify your wallet extension is loaded.")

        # Pause so you can sign in manually with your crypto wallet extension.
        logging.info("Please complete wallet sign-in in the opened browser window.")
        input("Press Enter once you've signed in with your crypto wallet extension...")

        # Now, navigate to the target page (Jupiter Perps) and continue with automation
        target_url = "https://jup.ag/perps"
        logging.info(f"Navigating to {target_url}")
        page.goto(target_url)

        # Continue with your automation steps...
        # Example: select the token (SOL)
        logging.info("Selecting token: SOL")
        page.click("text=SOL")

        # Example: attempt to set leverage (using an input or slider)
        logging.info("Attempting to set leverage to 39.3x")
        try:
            leverage_input = page.wait_for_selector("input[type=number]", timeout=10000)
            leverage_input.fill("39.3")
        except TimeoutError as te:
            logging.error("Leverage input not found with selector 'input[type=number]'. Verify the selector. Error: %s",
                          te)
            # Alternative: if a slider is used, you can use this code instead:
            # slider = page.locator("input[type=range]")
            # page.evaluate(
            #     "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }",
            #     slider,
            #     39.3
            # )

        # Example: click the "Open Long" button
        logging.info("Clicking the 'Open Long' button")
        try:
            page.get_by_role("button", name="Open Long").click()
        except Exception as e:
            logging.error("Error clicking 'Open Long' button: %s", e)

        logging.info("Workflow automation complete. Browser will remain open for debugging.")
        input("Press Enter to close the browser...")

        context.close()
        logging.info("Browser closed. Script finished.")


if __name__ == "__main__":
    main()
