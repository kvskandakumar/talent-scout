import json
import re
from pathlib import Path

ANSWERS_FILE = Path("question_answers.json")


def load_answers(log):
    if not ANSWERS_FILE.exists():
        return {}
    try:
        return json.loads(ANSWERS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as error:
        log(f"Could not read {ANSWERS_FILE}: {error}")
        return {}


def save_answers(answers):
    ANSWERS_FILE.write_text(
        json.dumps(answers, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )


def normalize_question(question):
    question = re.sub(r"\s*\(required\)\s*", " ", question or "", flags=re.IGNORECASE)
    question = question.replace("*", " ")
    return " ".join(question.lower().split()).strip(" :")


def has_any(text, words):
    return any(word in text for word in words)


def detect_profile_answer_key(question):
    text = normalize_question(question)
    if not text:
        return None

    has_current = has_any(text, ("current", "currently", "present", "existing", "last"))
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
            "total years of experience",
            "total it experience",
            "it experience",
            "professional experience",
            "relevant experience",
        ),
    ):
        return "total_experience"
    return None


def find_saved_answer(question, answers, profile_answers):
    key = normalize_question(question)
    if key and answers.get(key):
        return answers[key]

    profile_key = detect_profile_answer_key(question)
    if profile_key and answers.get(profile_key):
        return answers[profile_key]
    if profile_key and profile_answers.get(profile_key) not in (None, ""):
        return {
            "question": question,
            "answer": str(profile_answers[profile_key]),
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
            'fieldset, form, .form-group, .formField, .form-field, '
            + '.questions, .qsb, .wzrd, .chatbot, .dialog, .modal, .popup'
          ) || element.parentElement;
          const directLabel = id
            ? document.querySelector(`label[for="${CSS.escape(id)}"]`)
            : null;
          const legend = group ? group.querySelector('legend') : null;
          const labelledBy = element.getAttribute('aria-labelledby');
          const labelledNode = labelledBy
            ? document.getElementById(labelledBy)
            : null;
          const fallbackLabel = group ? group.querySelector('label') : null;
          const questionNode = element.type === 'radio'
            ? (legend || labelledNode || group?.querySelector('span'))
            : (directLabel || labelledNode || legend || fallbackLabel);
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


def fill_known_answers(container, answers, profile_answers, log):
    filled = 0
    controls = container.locator("input:visible, textarea:visible, select:visible")
    for index in range(controls.count()):
        control = controls.nth(index)
        details = get_control_details(control)
        question = details["question"]
        key = normalize_question(question)
        saved = find_saved_answer(question, answers, profile_answers)
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
            log(f"Could not reuse answer for '{question}': {error}")
    return filled


def capture_visible_answers(container, answers, profile_answers):
    learned = 0
    controls = container.locator("input:visible, textarea:visible, select:visible")
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
