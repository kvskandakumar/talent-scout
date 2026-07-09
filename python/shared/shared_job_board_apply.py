from datetime import datetime, timezone
import json
import random
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import TimeoutError, sync_playwright

ROOT_DIR = Path(__file__).resolve().parents[2]

from shared_answers import capture_visible_answers, fill_known_answers, load_answers


def log(message: str):
    print(message, flush=True)


def random_sleep(a=10, b=20):
    time.sleep(random.randint(a, b))


def slugify(value):
    return "-".join((value or "").strip().lower().split())


def build_search_url(template, keyword, location, posted_within_hours, only_instant_apply=True):
    return template.format(
        keyword_slug=slugify(keyword),
        location_slug=slugify(location),
        keyword_query=urllib.parse.quote(keyword),
        location_query=urllib.parse.quote(location),
        posted_within_hours=posted_within_hours,
        posted_within_seconds=posted_within_hours * 3600,
        posted_within_days=max(1, int(posted_within_hours / 24)),
        easy_apply_filter="&f_AL=true" if only_instant_apply else "",
    )


def first_visible(page_or_locator, selectors):
    for selector in selectors:
        locator = page_or_locator.locator(f"{selector}:visible").first
        if locator.count():
            return locator
    return None


def get_text(locator, default):
    try:
        if locator.count():
            return locator.first.inner_text().strip()
    except Exception:
        return default
    return default


def load_site_config(site_key, defaults):
    with (ROOT_DIR / "config.json").open() as file_obj:
        config = json.load(file_obj)

    site_overrides = config.get(site_key, {})
    site_config = {**defaults, **site_overrides}
    if site_config.get("use_global_settings"):
        for key in (
            "max_applications",
            "max_application_steps",
            "posted_within_hours",
            "learn_question_answers",
        ):
            if key in config and key not in site_overrides:
                site_config[key] = config[key]
        if "only_instant_apply" not in site_overrides:
            site_config["only_instant_apply"] = config.get("easy_apply_only", True)
    site_config["keywords"] = site_config.get("keywords") or config["keywords"]
    site_config["locations"] = site_config.get("locations") or config["locations"]
    site_config["profile_answers"] = config.get("profile_answers", {})
    if "only_instant_apply" not in site_config:
        site_config["only_instant_apply"] = config.get("easy_apply_only", True)
    site_config["headless"] = config.get("headless", False)
    site_config["dry_run"] = config.get("dry_run", False)
    return site_config


def load_history(history_file):
    if not history_file.exists():
        return set()
    try:
        return set(json.loads(history_file.read_text()))
    except (json.JSONDecodeError, OSError) as error:
        log(f"Could not read {history_file}: {error}")
        return set()


def save_history(history_file, job_ids):
    history_file.write_text(json.dumps(sorted(job_ids), indent=2) + "\n")


def record_attempt(attempts_file, job, status, reason=""):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **job,
        "status": status,
        "reason": reason,
    }
    with attempts_file.open("a") as attempts:
        attempts.write(json.dumps(entry, ensure_ascii=False) + "\n")


def locator_from_selectors(page_or_locator, selectors):
    return page_or_locator.locator(", ".join(selectors))


def get_job_cards(page, selectors):
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count():
            return locator
    return locator_from_selectors(page, selectors)


def get_job_id(job_card, link_selectors):
    for attribute in (
        "data-job-id",
        "data-jobid",
        "data-occludable-job-id",
        "data-jk",
        "data-id",
        "data-listing-id",
        "id",
    ):
        value = job_card.get_attribute(attribute)
        if value:
            return value

    for selector in link_selectors:
        link = job_card.locator(selector).first
        if not link.count():
            continue
        href = link.get_attribute("href") or ""
        if not href:
            continue
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("jk"):
            return query["jk"][0]
        parts = [part for part in parsed.path.split("/") if part]
        if "view" in parts and parts.index("view") + 1 < len(parts):
            return parts[parts.index("view") + 1]
        return href.split("?")[0]
    return ""


def open_job(page, job_card, link_selectors):
    link = first_visible(job_card, link_selectors)
    if link is not None:
        if "_blank" in (link.get_attribute("target") or "").lower():
            with page.expect_popup(timeout=10000) as popup_info:
                link.click(timeout=10000)
            detail_page = popup_info.value
            detail_page.wait_for_load_state("domcontentloaded")
            detail_page.wait_for_timeout(2500)
            return detail_page, True

        link.click(timeout=10000)
        page.wait_for_timeout(2500)
        return page, False

    job_card.click(timeout=10000)
    page.wait_for_timeout(2500)
    return page, False


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
            "employer site",
            "external site",
            "redirect",
            "continue to company",
        )
    )


def resolve_form_container(page):
    selectors = [
        "div[role='dialog']:visible",
        "aside:visible",
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
        "application sent",
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


def run_job_board(site):
    config = load_site_config(site["key"], site["defaults"])
    if not config.get("enabled", False):
        log(f"{site['name']} support is disabled. Set config.{site['key']}.enabled to true when ready.")
        return

    if config["dry_run"]:
        log("DRY RUN enabled: applications will stop before submission")

    def project_path(relative_path):
        path = Path(relative_path)
        return path if path.is_absolute() else ROOT_DIR / relative_path

    history_file = project_path(site["history_file"])
    attempts_file = project_path(site["attempts_file"])
    auth_file = project_path(site["auth_file"])
    applied = 0
    applied_job_ids = load_history(history_file)
    question_answers = load_answers(log)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=config["headless"],
            slow_mo=600,
        )
        context_options = {
            "storage_state": str(auth_file),
            "viewport": {"width": 1280, "height": 800},
        }
        context_options.update(site.get("context_options", {}))
        context = browser.new_context(**context_options)
        page = context.new_page()

        for keyword in config["keywords"]:
            for location in config["locations"]:
                if applied >= config["max_applications"]:
                    break

                search_url = build_search_url(
                    config["search_url_template"],
                    keyword,
                    location,
                    config["posted_within_hours"],
                    config.get("only_instant_apply", True),
                )
                log(f"\nSearching {site['name']}: {keyword} | {location}")
                page.goto(search_url, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)

                job_cards = get_job_cards(page, site["card_selectors"])
                total_jobs = job_cards.count()
                log(f"Found {total_jobs} jobs")

                for index in range(total_jobs):
                    if applied >= config["max_applications"]:
                        break

                    detail_page = page
                    opened_popup = False
                    form_container = None
                    try:
                        job_card = get_job_cards(page, site["card_selectors"]).nth(index)
                        job_card.scroll_into_view_if_needed()
                        job_id = get_job_id(job_card, site["link_selectors"])
                        if job_id and job_id in applied_job_ids:
                            log(f"Already applied to {site['name']} job {job_id} - skipped")
                            continue

                        if site.get("click_card_to_open"):
                            job_card.click(force=True, timeout=10000)
                            page.wait_for_timeout(site.get("after_open_wait_ms", 2500))
                            detail_page = page
                        else:
                            detail_page, opened_popup = open_job(
                                page,
                                job_card,
                                site["link_selectors"],
                            )

                        title = get_text(
                            locator_from_selectors(detail_page, site["title_selectors"]),
                            "Unknown title",
                        )
                        company = get_text(
                            locator_from_selectors(detail_page, site["company_selectors"]),
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
                        log(f"Job found: {title}")

                        if site.get("apply_button_wait_selector"):
                            try:
                                detail_page.locator(
                                    site["apply_button_wait_selector"]
                                ).first.wait_for(state="visible", timeout=10000)
                            except TimeoutError:
                                pass

                        apply_button = first_visible(
                            detail_page,
                            site["apply_selectors"],
                        )
                        if apply_button is None:
                            button_texts = list_visible_button_texts(detail_page)
                            if button_texts:
                                log(f"Visible actions: {button_texts}")
                            log(f"No {site['name']} apply button found - skipped")
                            record_attempt(
                                attempts_file,
                                job,
                                "skipped",
                                "No apply button found",
                            )
                            continue

                        button_text = apply_button.inner_text().strip() or "Apply"
                        if config["only_instant_apply"] and is_external_apply(button_text):
                            log(f"External apply flow detected ({button_text}) - skipped")
                            record_attempt(
                                attempts_file,
                                job,
                                "skipped",
                                f"External apply flow: {button_text}",
                            )
                            continue

                        apply_button.click(timeout=10000)
                        log(f"{button_text} clicked")
                        detail_page.wait_for_timeout(site.get("after_apply_wait_ms", 3000))
                        if site.get("form_container_wait_selector"):
                            detail_page.locator(
                                site["form_container_wait_selector"]
                            ).last.wait_for(state="visible", timeout=10000)
                        form_container = resolve_form_container(detail_page)

                        for step in range(config["max_application_steps"]):
                            if detect_submission_success(detail_page):
                                applied += 1
                                if job_id:
                                    applied_job_ids.add(job_id)
                                    save_history(history_file, applied_job_ids)
                                record_attempt(
                                    attempts_file,
                                    job,
                                    "applied",
                                    "Application confirmed after apply click",
                                )
                                log(f"{site['name']} application confirmed ({applied})")
                                random_sleep()
                                break

                            filled = fill_known_answers(
                                form_container,
                                question_answers,
                                config["profile_answers"],
                                log,
                            )
                            if filled:
                                log(f"Reused {filled} saved answer(s)")
                                detail_page.wait_for_timeout(500)

                            submit_button = find_navigation_button(
                                form_container,
                                ("Submit application", "Submit", "Finish", "Send application", "Apply"),
                            )
                            next_button = find_navigation_button(
                                form_container,
                                ("Next", "Continue", "Review", "Save and continue"),
                            )

                            if submit_button is not None:
                                if config["dry_run"]:
                                    log("Reached Submit - dry run stopped")
                                    record_attempt(
                                        attempts_file,
                                        job,
                                        "dry_run",
                                        "Reached submit step",
                                    )
                                    if site.get("close_application"):
                                        site["close_application"](detail_page, form_container)
                                    break

                                submit_button.click()
                                if site.get("submit_confirmation_text"):
                                    confirmation = detail_page.get_by_text(
                                        site["submit_confirmation_text"],
                                        exact=False,
                                    ).first
                                    try:
                                        confirmation.wait_for(state="visible", timeout=10000)
                                    except TimeoutError:
                                        record_attempt(
                                            attempts_file,
                                            job,
                                            "unconfirmed",
                                            "Submit clicked but no confirmation appeared",
                                        )
                                        log("Submit clicked, but submission was not confirmed")
                                        break
                                else:
                                    detail_page.wait_for_timeout(4000)
                                applied += 1
                                if job_id:
                                    applied_job_ids.add(job_id)
                                    save_history(history_file, applied_job_ids)
                                record_attempt(attempts_file, job, "applied")
                                log(f"{site['name']} application submitted ({applied})")
                                random_sleep()
                                break

                            if next_button is not None:
                                log(f"Step {step + 1}: Next/Continue")
                                next_button.click()
                                detail_page.wait_for_timeout(1500)
                                form_container = resolve_form_container(detail_page)
                                continue

                            if not has_visible_questions(form_container):
                                if detect_submission_success(detail_page):
                                    applied += 1
                                    if job_id:
                                        applied_job_ids.add(job_id)
                                        save_history(history_file, applied_job_ids)
                                    record_attempt(
                                        attempts_file,
                                        job,
                                        "applied",
                                        "Application confirmed without form questions",
                                    )
                                    log(f"{site['name']} application confirmed ({applied})")
                                else:
                                    record_attempt(
                                        attempts_file,
                                        job,
                                        "skipped",
                                        "No visible form questions or navigation after apply click",
                                    )
                                    log(f"No visible {site['name']} questions after apply - skipped")
                                if site.get("close_application"):
                                    site["close_application"](detail_page, form_container)
                                break

                            if config["learn_question_answers"] and not config["headless"]:
                                log(
                                    f"New {site['name']} question detected. Answer it in the browser, "
                                    "then return here."
                                )
                                input("Press Enter after filling the visible questions: ")
                                learned = capture_visible_answers(
                                    form_container,
                                    question_answers,
                                    config["profile_answers"],
                                )
                                if learned:
                                    log(f"Learned {learned} answer(s)")
                                    form_container = resolve_form_container(detail_page)
                                    continue

                            record_attempt(
                                attempts_file,
                                job,
                                "skipped",
                                f"Custom questions or unsupported {site['name']} flow",
                            )
                            log(f"Custom questions / unsupported {site['name']} flow - skipped")
                            if site.get("close_application"):
                                site["close_application"](detail_page, form_container)
                            break
                        else:
                            record_attempt(
                                attempts_file,
                                job,
                                "skipped",
                                "Application exceeded step limit",
                            )
                            log(
                                f"{site['name']} application exceeded "
                                f"{config['max_application_steps']} steps - skipped"
                            )
                            if site.get("close_application"):
                                site["close_application"](detail_page, form_container)

                    except TimeoutError as error:
                        if site.get("close_application") and form_container is not None:
                            site["close_application"](detail_page, form_container)
                        log(f"Timeout - skipped: {error}")
                    except Exception as error:
                        if site.get("close_application") and form_container is not None:
                            site["close_application"](detail_page, form_container)
                        log(f"Error - skipped: {error}")
                    finally:
                        if opened_popup and detail_page is not page:
                            try:
                                detail_page.close()
                            except Exception:
                                pass

        browser.close()
        log(f"\n{site['name']} run complete. Total jobs applied: {applied}")
