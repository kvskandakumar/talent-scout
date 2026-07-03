from playwright.sync_api import sync_playwright

AUTH_FILE = "auth.json"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        slow_mo=1000
    )

    context = browser.new_context()
    page = context.new_page()

    page.goto("https://www.linkedin.com/login")

    print("\n👉 Login manually in the opened browser")
    print("👉 WAIT until LinkedIn FEED loads")
    print("👉 Then come back here and press ENTER\n")
    input()

    context.storage_state(path=AUTH_FILE)
    print("✅ auth.json created successfully")

    browser.close()
