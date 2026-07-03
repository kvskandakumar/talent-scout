import json

from playwright.sync_api import sync_playwright

AUTH_FILE = "naukri_auth.json"
CONFIG_FILE = "config.json"
DEFAULT_LOGIN_URL = "https://www.naukri.com/nlogin/login"


def load_login_url():
    try:
        with open(CONFIG_FILE) as file_obj:
            config = json.load(file_obj)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_LOGIN_URL
    return config.get("naukri", {}).get("login_url", DEFAULT_LOGIN_URL)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context()
    page = context.new_page()

    page.goto(load_login_url(), wait_until="domcontentloaded")

    print("\n👉 Login manually in the opened browser")
    print("👉 WAIT until the Naukri homepage or jobs page loads")
    print("👉 Then come back here and press ENTER\n")
    input()

    context.storage_state(path=AUTH_FILE)
    print("✅ naukri_auth.json created successfully")

    browser.close()
