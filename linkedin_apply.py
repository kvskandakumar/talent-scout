from playwright.sync_api import sync_playwright, TimeoutError
from datetime import datetime, timezone
import json
import re
import time
import random
import urllib.parse
from pathlib import Path

AUTH_FILE = "auth.json"
HISTORY_FILE = Path("application_history.json")
ATTEMPTS_FILE = Path("application_attempts.jsonl")
ANSWERS_FILE = Path("question_answers.json")

# ---------- Load config ----------
with open("config.json") as f:
    config = json.load(f)

KEYWORDS = config["keywords"]
LOCATIONS = config["locations"]
MAX_APPS = config["max_applications"]
DRY_RUN = config.get("dry_run", False)
MAX_STEPS = config.get("max_application_steps", 7)
POSTED_WITHIN_HOURS = config.get("posted_within_hours", 24)
EASY_APPLY_ONLY = config.get("easy_apply_only", True)
LEARN_ANSWERS = config.get("learn_question_answers", True)
PROFILE_ANSWERS = config.get("profile_answers", {})


def log(msg: str):
    print(msg, flush=True)


def random_sleep(a=15, b=30):
    time.sleep(random.randint(a, b))


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


def load_answers():
    if not ANSWERS_FILE.exists():
        return {}
    try:
        return json.loads(ANSWERS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as error:
        log(f"⚠ Could not read {ANSWERS_FILE}: {error}")
        return {}


def save_answers(answers):
    ANSWERS_FILE.write_text(
        json.dumps(answers, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )


def normalize_question(question):
    question = re.sub(r"\s*\(required\)\s*", " ", question, flags=re.IGNORECASE)
    question = question.replace("*", " ")
    return " ".join(question.lower().split()).strip(" :")


def normalize_text(value):
    return normalize_question(value or "")


def has_any(text, words):
    return any(word in text for word in words)


def detect_profile_answer_key(question):
    text = normalize_text(question)
    if not text:
        return None

    has_current = has_any(
        text,
        ("current", "currently", "present", "existing"),
    )
    has_expected = has_any(
        text,
        ("expected", "expecting", "desired", "target", "looking for"),
    )
    has_salary = has_any(
        text,
        (
            "ctc",
            "salary",
            "compensation",
            "pay",
            "package",
            "remuneration",
            "fixed",
            "annual",
            "lpa",
            "lakhs",
        ),
    )

    if has_current and has_salary:
        return "current_ctc"
    if has_expected and has_salary:
        return "expected_ctc"
    if has_any(text, ("notice period", "serving notice", "notice")):
        return "notice_period"
    if has_any(text, ("current location", "present location")):
        return "current_location"
    if has_any(
        text,
        (
            "total experience",
            "overall experience",
            "years of experience",
            "total it experience",
            "it experience",
        ),
    ):
        return "total_experience"
    return None


def find_saved_answer(question, answers):
    key = normalize_question(question)
    if key and answers.get(key):
        return answers[key]

    profile_key = detect_profile_answer_key(question)
    if profile_key and answers.get(profile_key):
        return answers[profile_key]
    if profile_key and PROFILE_ANSWERS.get(profile_key) not in (None, ""):
        return {
            "question": question,
            "answer": str(PROFILE_ANSWERS[profile_key]),
            "type": "text",
            "source": "profile_answers",
        }

    return None


def get_control_details(control):
    return control.evaluate(
        """
        (element) => {
          const id = element.id;
          const group = element.closest(
            'fieldset, .fb-dash-form-element, '
            + '.jobs-easy-apply-form-section__grouping'
          ) || element.parentElement;
          const directLabel = id
            ? document.querySelector(`label[for="${CSS.escape(id)}"]`)
            : null;
          const legend = group ? group.querySelector('legend') : null;
          const fallbackLabel = group ? group.querySelector('label') : null;
          const questionNode = element.type === 'radio'
            ? (legend || group?.querySelector('span'))
            : (directLabel || legend || fallbackLabel);
          return {
            question: (element.getAttribute('aria-label')
              || element.getAttribute('placeholder')
              || element.name
              || questionNode?.innerText || '').trim(),
            option: (directLabel?.innerText || '').trim(),
            type: element.tagName === 'SELECT'
              ? 'select'
              : element.tagName === 'TEXTAREA'
                ? 'textarea'
                : (element.type || 'text').toLowerCase(),
          };
        }
        """
    )


def fill_known_answers(dialog, answers):
    filled = 0
    controls = dialog.locator("input:visible, textarea:visible, select:visible")
    for index in range(controls.count()):
        control = controls.nth(index)
        details = get_control_details(control)
        question = details["question"]
        key = normalize_question(question)
        saved = find_saved_answer(question, answers)
        if not key or not saved:
            continue

        answer = str(saved["answer"])
        control_type = details["type"]
        try:
            if control_type == "radio":
                if normalize_question(details["option"]) == normalize_question(answer):
                    if not control.is_checked():
                        control.check()
                        filled += 1
            elif control_type == "checkbox":
                should_check = answer.lower() == "true"
                if control.is_checked() != should_check:
                    control.set_checked(should_check)
                    filled += 1
            elif control_type == "select":
                control.select_option(label=answer)
                filled += 1
            elif control_type not in ("file", "hidden") and not control.input_value():
                control.fill(answer)
                filled += 1
        except Exception as error:
            log(f"⚠ Could not reuse answer for '{details['question']}': {error}")
    return filled


def capture_visible_answers(dialog, answers):
    learned = 0
    controls = dialog.locator("input:visible, textarea:visible, select:visible")
    for index in range(controls.count()):
        control = controls.nth(index)
        details = get_control_details(control)
        question = details["question"]
        key = normalize_question(question)
        control_type = details["type"]
        if not key or control_type in ("file", "hidden"):
            continue

        if control_type == "radio":
            if not control.is_checked():
                continue
            answer = details["option"]
        elif control_type == "checkbox":
            answer = str(control.is_checked()).lower()
        elif control_type == "select":
            answer = control.locator("option:checked").inner_text().strip()
        else:
            answer = control.input_value().strip()

        if not answer:
            continue
        new_value = {"question": question, "answer": answer, "type": control_type}
        if answers.get(key) != new_value:
            answers[key] = new_value
            learned += 1

        profile_key = detect_profile_answer_key(question)
        if profile_key:
            canonical_value = {
                "question": question,
                "answer": answer,
                "type": control_type,
                "source": "canonical_question_match",
            }
            if answers.get(profile_key) != canonical_value:
                answers[profile_key] = canonical_value
                learned += 1

    if learned:
        save_answers(answers)
    return learned


def record_attempt(job, status, reason=""):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **job,
        "status": status,
        "reason": reason,
    }
    with ATTEMPTS_FILE.open("a") as attempts:
        attempts.write(json.dumps(entry, ensure_ascii=False) + "\n")


def close_application_dialog(page, dialog):
    dismiss = dialog.locator("button[aria-label='Dismiss']:visible").first
    if dismiss.count():
        dismiss.click()
        discard = page.get_by_role("button", name="Discard", exact=True)
        try:
            discard.wait_for(state="visible", timeout=2000)
            discard.click()
        except TimeoutError:
            pass


def get_job_id(job_card):
    for attribute in ("data-job-id", "data-occludable-job-id"):
        value = job_card.get_attribute(attribute)
        if value:
            return value

    link = job_card.locator("a[href*='/jobs/view/']").first
    if link.count():
        href = link.get_attribute("href") or ""
        parts = [part for part in urllib.parse.urlparse(href).path.split("/") if part]
        if "view" in parts and parts.index("view") + 1 < len(parts):
            return parts[parts.index("view") + 1]
    return ""


# ---------- Main ----------
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=config.get("headless", False),
        slow_mo=600,
    )

    context = browser.new_context(
        storage_state=AUTH_FILE,
        viewport={"width": 1280, "height": 800},
    )

    page = context.new_page()
    applied = 0
    applied_job_ids = load_history()
    question_answers = load_answers()

    if DRY_RUN:
        log("🧪 DRY RUN enabled: applications will stop before submission")

    for keyword in KEYWORDS:
        for location in LOCATIONS:
            if applied >= MAX_APPS:
                break

            encoded_keyword = urllib.parse.quote(keyword)
            encoded_location = urllib.parse.quote(location)

            search_url = (
                "https://www.linkedin.com/jobs/search/"
                f"?keywords={encoded_keyword}"
                f"&location={encoded_location}"
                f"&f_TPR=r{POSTED_WITHIN_HOURS * 3600}"
            )
            if EASY_APPLY_ONLY:
                search_url += "&f_AL=true"

            log(f"\n🔍 Searching: {keyword} | {location}")
            page.goto(search_url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            job_cards = page.locator("div.job-card-container")
            total_jobs = job_cards.count()
            log(f"Found {total_jobs} jobs")

            for i in range(total_jobs):
                if applied >= MAX_APPS:
                    break

                application_dialog = None
                try:
                    job_card = page.locator("div.job-card-container").nth(i)
                    job_card.scroll_into_view_if_needed()
                    job_id = get_job_id(job_card)
                    if job_id and job_id in applied_job_ids:
                        log(f"⏭ Already applied to job {job_id} — skipped")
                        continue

                    job_card.click(force=True, timeout=10000)

                    # LinkedIn now labels this button either "Easy Apply" or "Apply".
                    # The jobs-apply-button class is more stable than its visible text.
                    apply_button = page.locator(
                        "button.jobs-apply-button:visible"
                    ).first
                    try:
                        apply_button.wait_for(state="visible", timeout=10000)
                    except TimeoutError:
                        details_buttons = page.locator(
                            ".jobs-search__job-details--container button:visible, "
                            ".jobs-details button:visible"
                        )
                        btn_texts = []
                        for k in range(min(details_buttons.count(), 15)):
                            try:
                                btn_texts.append(
                                    details_buttons.nth(k).inner_text().strip()
                                )
                            except Exception:
                                pass
                        log(f"Job detail buttons: {btn_texts}")
                        # Screenshot capture is disabled to avoid creating diagnostic
                        # image files during normal runs.
                        # page.screenshot(path=f"screenshot-job-{i + 1}.png")
                        log("⏭ No LinkedIn Apply button — skipped")
                        continue

                    # Log some context if available
                    title_locator = page.locator(
                        ".jobs-details__main-content h1, "
                        ".jobs-details__main-content h2, "
                        ".job-details-jobs-unified-top-card__job-title"
                    ).first
                    title = (
                        title_locator.inner_text().strip()
                        if title_locator.count() > 0
                        else "Unknown title"
                    )
                    company_locator = page.locator(
                        ".job-details-jobs-unified-top-card__company-name, "
                        ".jobs-unified-top-card__company-name"
                    ).first
                    company = (
                        company_locator.inner_text().strip()
                        if company_locator.count() > 0
                        else "Unknown company"
                    )
                    job = {
                        "job_id": job_id,
                        "title": title,
                        "company": company,
                        "keyword": keyword,
                        "location": location,
                        "url": page.url,
                    }
                    log(f"📄 Job found: {title}")

                    button_text = apply_button.inner_text().strip() or "Apply"
                    apply_button.click(timeout=10000)
                    log(f"🟡 {button_text} clicked")

                    application_dialog = page.locator("div[role='dialog']:visible").last
                    application_dialog.wait_for(state="visible", timeout=10000)

                    # ---- Multi-step Easy Apply ----
                    for step in range(MAX_STEPS):
                        filled = fill_known_answers(
                            application_dialog, question_answers
                        )
                        if filled:
                            log(f"📝 Reused {filled} saved answer(s)")
                            page.wait_for_timeout(500)

                        submit = application_dialog.locator(
                            "button:has-text('Submit application'):visible, "
                            "button:has-text('Submit'):visible"
                        ).first
                        next_btn = application_dialog.locator(
                            "button:has-text('Next'):visible, "
                            "button:has-text('Review'):visible, "
                            "button:has-text('Continue'):visible"
                        ).first

                        if submit.count() > 0 and submit.is_enabled():
                            if DRY_RUN:
                                log("🧪 Reached Submit — dry run stopped")
                                record_attempt(job, "dry_run", "Reached submit step")
                                close_application_dialog(page, application_dialog)
                                break

                            submit.click()
                            confirmation = page.get_by_text(
                                "Application sent", exact=False
                            ).first
                            try:
                                confirmation.wait_for(state="visible", timeout=10000)
                            except TimeoutError:
                                record_attempt(
                                    job,
                                    "unconfirmed",
                                    "Submit clicked but no confirmation appeared",
                                )
                                log("⚠ Submit clicked, but submission was not confirmed")
                                break

                            applied += 1
                            if job_id:
                                applied_job_ids.add(job_id)
                                save_history(applied_job_ids)
                            record_attempt(job, "applied")
                            log(f"✅ Application confirmed ({applied})")
                            random_sleep()
                            break

                        elif next_btn.count() > 0 and next_btn.is_enabled():
                            log(f"➡ Step {step + 1}: Next/Review")
                            next_btn.click()
                            page.wait_for_timeout(1500)

                        else:
                            if LEARN_ANSWERS and not config.get("headless", False):
                                log(
                                    "❓ New required question detected. Answer it in "
                                    "the browser, then return here."
                                )
                                input("Press Enter after filling the visible questions: ")
                                learned = capture_visible_answers(
                                    application_dialog, question_answers
                                )
                                if learned:
                                    log(f"💾 Learned {learned} answer(s)")
                                    continue

                            log("⚠ Custom questions / unsupported flow — skipped")
                            record_attempt(
                                job,
                                "skipped",
                                "Custom questions or unsupported application flow",
                            )
                            close_application_dialog(page, application_dialog)
                            break
                    else:
                        record_attempt(job, "skipped", "Application exceeded step limit")
                        close_application_dialog(page, application_dialog)
                        log(f"⚠ Application exceeded {MAX_STEPS} steps — skipped")

                except TimeoutError as error:
                    if application_dialog is not None:
                        close_application_dialog(page, application_dialog)
                    log(f"⚠ Timeout — skipped: {error}")
                    continue
                except Exception as e:
                    if application_dialog is not None:
                        close_application_dialog(page, application_dialog)
                    log(f"⚠ Error — skipped: {e}")
                    continue

    log(f"\n🎉 DONE. Total jobs applied: {applied}")
    browser.close()
