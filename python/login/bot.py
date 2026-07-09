from playwright.sync_api import sync_playwright
from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parents[2]
AUTH_FILE = ROOT_DIR / "auth" / "auth.json"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        slow_mo=1000
    )

    # First time: no session yet
    if not os.path.exists(AUTH_FILE):
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.linkedin.com/login")

        print("\n👉 Please login manually in the opened browser")
        print("👉 After login, press ENTER here\n")
        input()

        context.storage_state(path=AUTH_FILE)
        print("✅ Login session saved to auth.json")

    else:
        # Reuse saved session
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()

        page.goto("https://www.linkedin.com/feed")
        print("✅ Logged in using saved session")

    input("\nPress ENTER to close browser...")
    browser.close()
