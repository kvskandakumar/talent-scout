import json

from playwright.sync_api import sync_playwright

AUTH_FILE = "indeed_auth.json"
CONFIG_FILE = "config.json"
DEFAULT_LOGIN_URL = "https://secure.indeed.com/auth?hl=en_IN&co=IN"


def load_login_url():
    try:
        with open(CONFIG_FILE) as file_obj:
            config = json.load(file_obj)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_LOGIN_URL
    return config.get("indeed", {}).get("login_url", DEFAULT_LOGIN_URL)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context()
    page = context.new_page()

    page.goto(load_login_url(), wait_until="domcontentloaded")

    print("\nLogin manually in the opened browser")
    print("WAIT until Indeed is fully logged in")
    print("Then come back here and press ENTER\n")
    input()

    context.storage_state(path=AUTH_FILE)
    print("indeed_auth.json created successfully")

    browser.close()
