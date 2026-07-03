from datetime import datetime, timezone
import json
import random
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import TimeoutError, sync_playwright

from shared_answers import capture_visible_answers, fill_known_answers, load_answers

AUTH_FILE = "naukri_auth.json"
HISTORY_FILE = Path("naukri_application_history.json")
ATTEMPTS_FILE = Path("naukri_application_attempts.jsonl")
CONFIG_FILE = "config.json"

DEFAULTS = {
    "enabled": False,
    "login_url": "https://www.naukri.com/nlogin/login",
    "search_url_template": "https://www.naukri.com/jobs-in-{location_slug}?k={keyword_query}&l={location_query}",
    "max_applications": 25,
    "max_application_steps": 8,
    "posted_within_hours": 72,
    "only_instant_apply": True,
    "learn_question_answers": True,
}


def log(message: str):
    print(message, flush=True)


def random_sleep(a=10, b=20):
    time.sleep(random.randint(a, b))


def load_config():
    with open(CONFIG_FILE) as file_obj:
        config = json.load(file_obj)

    naukri_config = {**DEFAULTS, **config.get("naukri", {})}
    naukri_config["keywords"] = naukri_config.get("keywords") or config["keywords"]
    naukri_config["locations"] = naukri_config.get("locations") or config["locations"]
    naukri_config["profile_answers"] = config.get("profile_answers", {})
    naukri_config["headless"] = config.get("headless", False)
    naukri_config["dry_run"] = config.get("dry_run", False)
    return naukri_config


def load_history():
    if not HISTORY_FILE.exists():
        return set()
    try:
        return set(json.loads(HISTORY_FILE.read_text()))
    except (json.JSONDecodeError, OSError) as error:
        log(f"⚠ Could not read {HISTORY_FILE}: {error}")
        return set()


def save_history(job_ids):
    HISTORY_FILE.write_text(json.dumps(sorted(job_ids), indent=2) + "\n")


def record_attempt(job, status, reason=""):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **job,
        "status": status,
        "reason": reason,
    }
    with ATTEMPTS_FILE.open("a") as attempts:
        attempts.write(json.dumps(entry, ensure_ascii=False) + "\n")


def slugify(value):
    return "-".join((value or "").strip().lower().split())


def build_search_url(template, keyword, location):
    return template.format(
        keyword_slug=slugify(keyword),
        location_slug=slugify(location),
        keyword_query=urllib.parse.quote(keyword),
        location_query=urllib.parse.quote(location),
    )


def get_job_cards(page):
    selector_candidates = [
        "article.jobTuple",
        "div.srp-jobtuple-wrapper",
        "div.cust-job-tuple",
        "div.jobTuple",
    ]
    for selector in selector_candidates:
        locator = page.locator(selector)
        if locator.count():
            return locator
    return page.locator("article.jobTuple, div.srp-jobtuple-wrapper, div.cust-job-tuple")


def get_job_id(job_card):
    for attribute in ("data-job-id", "data-jobid", "id"):
        value = job_card.get_attribute(attribute)
        if value:
            return value

    for selector in ("a[href*='job-listings']", "a.title", "a"):
        link = job_card.locator(selector).first
        if link.count():
            href = link.get_attribute("href") or ""
            if href:
                return href.split("?")[0]
    return ""


def get_text(locator, default):
    try:
        if locator.count():
            return locator.first.inner_text().strip()
    except Exception:
        return default
    return default


def find_apply_button(page):
    selectors = [
        "button:has-text('Apply')",
        "button:has-text('Apply on company site')",
        "button.apply-button",
        "button.styles_apply-button__",
        "a:has-text('Apply')",
    ]
    for selector in selectors:
        button = page.locator(f"{selector}:visible").first
        if button.count():
            return button
    return None


def list_visible_button_texts(page, limit=20):
    labels = []
    buttons = page.locator("button:visible, a:visible")
    for index in range(min(buttons.count(), limit)):
        try:
            text = buttons.nth(index).inner_text().strip()
        except Exception:
            continue
        if text:
            labels.append(text)
    return labels


def is_external_apply(button_text):
    text = (button_text or "").strip().lower()
    return any(
        marker in text
        for marker in (
            "company site",
            "external site",
            "redirect",
        )
    )


def resolve_form_container(page):
    selectors = [
        "div[role='dialog']:visible",
        "div.modal:visible",
        "div.popup:visible",
        "form:visible",
    ]
    for selector in selectors:
        container = page.locator(selector).last
        if container.count():
            return container
    return page.locator("body")


def has_visible_questions(container):
    try:
        return container.locator("input:visible, textarea:visible, select:visible").count() > 0
    except Exception:
        return False


def detect_submission_success(page):
    success_markers = (
        "applied",
        "application submitted",
        "successfully applied",
        "your application has been submitted",
        "you have successfully applied",
    )
    try:
        page_text = page.locator("body").inner_text(timeout=3000).lower()
    except Exception:
        return False
    return any(marker in page_text for marker in success_markers)


def find_navigation_button(container, labels):
    for label in labels:
        button = container.locator(f"button:has-text('{label}'):visible").first
        if button.count() and button.is_enabled():
            return button
    return None


def open_job(page, job_card):
    link = job_card.locator("a.title, a[href*='job-listings'], a").first
    if link.count():
        href = link.get_attribute("href") or ""
        if "_blank" in (link.get_attribute("target") or "").lower():
            with page.expect_popup(timeout=10000) as popup_info:
                link.click(timeout=10000)
            detail_page = popup_info.value
            detail_page.wait_for_load_state("domcontentloaded")
            detail_page.wait_for_timeout(2000)
            return detail_page, True

        link.click(timeout=10000)
        page.wait_for_timeout(2000)
        if href and page.url == href:
            return page, False

    job_card.click(timeout=10000)
    page.wait_for_timeout(2000)
    return page, False


def main():
    config = load_config()
    if not config.get("enabled", False):
        log("⚠ Naukri support is disabled. Set config.naukri.enabled to true when ready.")
        return

    if config["dry_run"]:
        log("🧪 DRY RUN enabled: applications will stop before submission")

    applied = 0
    applied_job_ids = load_history()
    question_answers = load_answers(log)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=config["headless"],
            slow_mo=600,
        )
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()

        for keyword in config["keywords"]:
            for location in config["locations"]:
                if applied >= config["max_applications"]:
                    break

                search_url = build_search_url(
                    config["search_url_template"], keyword, location
                )
                log(f"\n🔍 Naukri search: {keyword} | {location}")
                page.goto(search_url, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)

                job_cards = get_job_cards(page)
                total_jobs = job_cards.count()
                log(f"Found {total_jobs} jobs")

                for index in range(total_jobs):
                    if applied >= config["max_applications"]:
                        break

                    form_container = None
                    detail_page = page
                    opened_popup = False
                    try:
                        job_card = job_cards.nth(index)
                        job_card.scroll_into_view_if_needed()
                        job_id = get_job_id(job_card)
                        if job_id and job_id in applied_job_ids:
                            log(f"⏭ Already applied to Naukri job {job_id} — skipped")
                            continue

                        detail_page, opened_popup = open_job(page, job_card)

                        title = get_text(
                            detail_page.locator(
                                "h1, h2, .jd-header-title, .styles_jd-header-title__, "
                                ".job-details-jd-header-title"
                            ),
                            "Unknown title",
                        )
                        company = get_text(
                            detail_page.locator(
                                ".company, .comp-name, .styles_jd-header-comp-name__, "
                                ".job-details-jd-header-company-name"
                            ),
                            "Unknown company",
                        )
                        job = {
                            "job_id": job_id,
                            "title": title,
                            "company": company,
                            "keyword": keyword,
                            "location": location,
                            "url": detail_page.url,
                        }
                        log(f"📄 Naukri job found: {title}")

                        apply_button = find_apply_button(detail_page)
                        if apply_button is None:
                            button_texts = list_visible_button_texts(detail_page)
                            if button_texts:
                                log(f"Visible actions: {button_texts}")
                            log("⏭ No Naukri apply button found — skipped")
                            continue

                        button_text = apply_button.inner_text().strip() or "Apply"
                        if config["only_instant_apply"] and is_external_apply(button_text):
                            log(f"⏭ External apply flow detected ({button_text}) — skipped")
                            continue

                        apply_button.click(timeout=10000)
                        log(f"🟡 {button_text} clicked")
                        detail_page.wait_for_timeout(2500)

                        form_container = resolve_form_container(detail_page)

                        for step in range(config["max_application_steps"]):
                            if detect_submission_success(detail_page):
                                applied += 1
                                if job_id:
                                    applied_job_ids.add(job_id)
                                    save_history(applied_job_ids)
                                record_attempt(job, "applied", "Application confirmed after apply click")
                                log(f"✅ Naukri application confirmed ({applied})")
                                random_sleep()
                                break

                            filled = fill_known_answers(
                                form_container,
                                question_answers,
                                config["profile_answers"],
                                log,
                            )
                            if filled:
                                log(f"📝 Reused {filled} saved answer(s)")
                                page.wait_for_timeout(500)

                            submit_button = find_navigation_button(
                                form_container,
                                ("Submit", "Finish", "Send application", "Apply"),
                            )
                            next_button = find_navigation_button(
                                form_container,
                                ("Next", "Continue", "Review", "Save and next"),
                            )

                            if submit_button is not None:
                                if config["dry_run"]:
                                    log("🧪 Reached Submit — dry run stopped")
                                    record_attempt(job, "dry_run", "Reached submit step")
                                    break

                                submit_button.click()
                                page.wait_for_timeout(3000)
                                applied += 1
                                if job_id:
                                    applied_job_ids.add(job_id)
                                    save_history(applied_job_ids)
                                record_attempt(job, "applied")
                                log(f"✅ Naukri application submitted ({applied})")
                                random_sleep()
                                break

                            if next_button is not None:
                                log(f"➡ Step {step + 1}: Next/Continue")
                                next_button.click()
                                detail_page.wait_for_timeout(1500)
                                form_container = resolve_form_container(detail_page)
                                continue

                            if not has_visible_questions(form_container):
                                if detect_submission_success(detail_page):
                                    applied += 1
                                    if job_id:
                                        applied_job_ids.add(job_id)
                                        save_history(applied_job_ids)
                                    record_attempt(job, "applied", "Application confirmed without form questions")
                                    log(f"✅ Naukri application confirmed ({applied})")
                                else:
                                    record_attempt(
                                        job,
                                        "skipped",
                                        "No visible form questions or navigation after apply click",
                                    )
                                    log("⏭ No visible Naukri questions after apply — skipped")
                                break

                            if config["learn_question_answers"] and not config["headless"]:
                                log(
                                    "❓ New Naukri question detected. Answer it in the browser, "
                                    "then return here."
                                )
                                input("Press Enter after filling the visible questions: ")
                                learned = capture_visible_answers(
                                    form_container,
                                    question_answers,
                                    config["profile_answers"],
                                )
                                if learned:
                                    log(f"💾 Learned {learned} answer(s)")
                                    form_container = resolve_form_container(detail_page)
                                    continue

                            record_attempt(
                                job,
                                "skipped",
                                "Custom questions or unsupported Naukri flow",
                            )
                            log("⚠ Custom questions / unsupported Naukri flow — skipped")
                            break
                        else:
                            record_attempt(job, "skipped", "Application exceeded step limit")
                            log(
                                f"⚠ Naukri application exceeded {config['max_application_steps']} steps — skipped"
                            )

                    except TimeoutError as error:
                        log(f"⚠ Timeout — skipped: {error}")
                    except Exception as error:
                        log(f"⚠ Error — skipped: {error}")
                    finally:
                        if opened_popup and detail_page is not page:
                            try:
                                detail_page.close()
                            except Exception:
                                pass

        browser.close()
        log(f"\n🎉 Naukri run complete. Total jobs applied: {applied}")


if __name__ == "__main__":
    main()
