Basic Playwright Python Script for Jupiter Perps
Goal: Automate a simple user workflow on the Jupiter Perps web page using Playwright in Python. We will simulate: (1) navigating to the Perps page, (2) selecting a token (e.g. SOL), (3) setting a leverage value (e.g. 39.3x), and (4) clicking the “Open Long” button. This example uses Playwright’s synchronous Python API for simplicity.
Workflow Outline
Navigate to Jupiter Perps: Launch a browser and go to the Perps trading page (https://jup.ag/perps).
Select the Token (SOL): Open the market selector and choose SOL (as the token to trade).
Set Leverage (39.3x): Adjust the leverage slider or input field to 39.3x.
Click “Open Long”: Locate and click the Open Long button to simulate opening a long position.
Each step corresponds to a user action on the interface, which we will replicate with Playwright commands.
Playwright Automation Script Example
Before running the script, ensure Playwright is installed and browsers are set up (e.g. via pip install playwright and playwright install). The script below uses headless mode by default (no visible UI) – we’ll note how to toggle this for debugging. Comments in the code explain each action:
python
Copy
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Launch a headless browser (set headless=False to see the browser UI)
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 1. Navigate to the Jupiter Perps page
    page.goto("https://jup.ag/perps")

    # 2. Select the token (e.g., SOL) using the market selector
    # (Assuming a dropdown or menu with token options; using a text locator for "SOL")
    page.click("text=SOL")
    # If a dropdown needs to be opened first, you might need:
    # page.click("selector-for-token-dropdown")
    # page.click("text=SOL")  # then choose SOL from the options

    # 3. Set the leverage value to 39.3x.
    # If there's an input field for leverage, fill it:
    page.fill("input[type=number]", "39.3")
    # Alternatively, if only a slider is present (input[type=range]):
    # page.locator("input[type=range]").evaluate("(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }", 39.3)
    # The above JavaScript sets the slider value and triggers input/change events&#8203;:contentReference[oaicite:0]{index=0}.

    # 4. Click the "Open Long" button to open a long position
    page.get_by_role("button", name="Open Long").click()  # Uses accessible name&#8203;:contentReference[oaicite:1]{index=1}

    # (Optional) Wait for confirmation or any resulting behavior here, if needed
    # e.g., page.wait_for_selector("text=Position Opened")

    # Close the browser
    browser.close()
In the code above, we used Playwright’s locator strategies to interact with elements:
page.click("text=SOL") finds an element containing the text “SOL” and clicks it (this selects the SOL market). You might adapt the selector if the token button has a specific role or attribute (for example, a more robust approach could be using an aria-label or test ID if available). Playwright’s test generator tool can help find unique selectors for such elements​
PLAYWRIGHT.DEV
.
For the leverage slider, if the UI provides a numeric input box, we use page.fill(...). If it’s a pure slider (<input type="range">), we cannot fill it directly. In that case, we programmatically set its value and dispatch events (as shown in the commented code) to simulate moving the slider to 39.3x​
GITHUB.COM
. Another approach is to focus the slider and use keyboard arrow keys or drag the slider knob via mouse events, but directly setting the value is straightforward for a known target.
page.get_by_role("button", name="Open Long").click() clicks the Open Long button by targeting it through its accessible role and name. This is a Playwright-recommended practice for reliable selectors (e.g., clicking a button by its text label)​
PLAYWRIGHT.DEV
. It will automatically wait for the button to be visible and enabled before clicking.
Note: In a real scenario, clicking "Open Long" would trigger a wallet transaction confirmation. This script does not handle wallet interactions – it only automates the web UI up to the point of clicking the button. For testing purposes, you might use a devnet or a stub if you need to go through the complete flow.
Tips for Running and Adapting the Script
Headless vs. Visible Browser: By default, Playwright runs in headless mode (no GUI)​
PLAYWRIGHT.DEV
. In the browser.launch() call, we set headless=True. To see the browser perform the actions (useful for debugging or development), set headless=False. For example: browser = p.chromium.launch(headless=False, slow_mo=50). The slow_mo=50 (50 ms delay) is optional and slows down actions so you can observe the steps.
Finding Reliable Selectors (Playwright Codegen): Playwright provides a code generation tool to help identify selectors. Running a command like npx playwright codegen https://jup.ag/perps in your terminal will launch a browser and record your interactions, producing example code​
PLAYWRIGHT.DEV
. This is a great way to grab accurate selectors for complex elements. Playwright’s codegen tries to use roles, text, and test IDs for robust locators​
PLAYWRIGHT.DEV
. You can copy these selectors into your script for further refinement.
Adapting to Other Actions: The script can be extended or modified easily. For example, to open a short position instead, you would click the “Short” toggle (if one exists) and then click the “Open Short” button (which you can locate similarly by its name). To select a different token, change the text in the token selector (e.g., "text=ETH" for Ethereum). If you need to set collateral or other inputs, use page.fill() on the respective input fields. The same pattern of page.get_by_role or page.locator(...).click() can be used for other buttons and interactive elements on the page. Remember that Playwright will auto-wait for elements to appear, but you can always add explicit waits (e.g., page.wait_for_selector(...)) if needed for slow-loading components.