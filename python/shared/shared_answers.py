import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
ANSWERS_FILE = ROOT_DIR / "data" / "question_answers.json"

PRIMARY_TECH_STACK = (
    "React.js, TypeScript, JavaScript, HTML5, CSS3, Redux, Node.js, Express.js, REST APIs, Docker, AWS, Git"
)
FRONTEND_TECH_STACK = (
    "React.js, TypeScript, JavaScript, HTML5, CSS3, Redux, responsive UI development"
)
BACKEND_TECH_STACK = "Node.js, Express.js, REST APIs, SQL, Docker"
FULLSTACK_TECH_STACK = (
    "React.js, TypeScript, JavaScript, HTML5, CSS3, Redux, Node.js, Express.js, REST APIs, Docker, AWS, Git"
)
CORE_TECH_EXPERIENCE = {
    "react": "6",
    "react.js": "6",
    "javascript": "6",
    "typescript": "5",
    "html": "6",
    "html5": "6",
    "css": "6",
    "css3": "6",
    "redux": "5",
    "rest api": "5",
    "rest apis": "5",
    "git": "6",
    "node": "3",
    "node.js": "3",
    "express": "3",
    "express.js": "3",
    "aws": "3",
    "docker": "3",
    "kubernetes": "2",
    "cloud": "3",
    "sql": "4",
    "mysql": "4",
    "postgresql": "4",
    "mongodb": "3",
    "graphql": "2",
    "microservices": "3",
    "microservice": "3",
    "database": "4",
}
CORE_TECH_KEYWORDS = tuple(CORE_TECH_EXPERIENCE.keys())
NON_PROFILE_TECH_KEYWORDS = (
    "angular",
    "vue",
    "java ",
    "spring",
    "python",
    "django",
    "flask",
    "php",
    "laravel",
    "ruby",
    "rails",
    "go ",
    "golang",
    "c#",
    ".net",
)


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


def answer_payload(question, answer, control_type="text", source="expected_question_match"):
    return {
        "question": question,
        "answer": str(answer),
        "type": control_type,
        "source": source,
    }


def has_all(text, words):
    return all(word in text for word in words)


def detect_tech_keyword(text):
    for keyword in CORE_TECH_KEYWORDS:
        if keyword in text:
            return keyword
    return None


def asks_for_experience_amount(text):
    return has_any(
        text,
        (
            "how many years",
            "years of",
            "year of",
            "experience in",
            "experience with",
            "worked with",
        ),
    )


def answer_tech_stack_question(question, text):
    if has_any(text, ("full-stack", "full stack", "fullstack")):
        if has_any(
            text,
            (
                "tech stack",
                "technology stack",
                "technical skills",
                "skills",
                "skill set",
                "tools and technologies",
            ),
        ):
            return answer_payload(question, FULLSTACK_TECH_STACK, "text")
        if asks_for_experience_amount(text):
            return answer_payload(question, "6", "text")
        return answer_payload(question, "Yes", "radio")

    tech_keyword = detect_tech_keyword(text)
    if tech_keyword and has_any(
        text,
        (
            "do you have",
            "have you used",
            "are you experienced",
            "hands-on",
            "proficient",
            "comfortable with",
            "experience",
            "worked with",
        ),
    ):
        return answer_payload(question, "Yes", "radio")

    if tech_keyword and asks_for_experience_amount(text):
        return answer_payload(question, CORE_TECH_EXPERIENCE[tech_keyword], "text")

    if has_any(text, NON_PROFILE_TECH_KEYWORDS) and has_any(
        text,
        (
            "do you have",
            "have you used",
            "are you experienced",
            "hands-on",
            "proficient",
            "comfortable with",
        ),
    ):
        return answer_payload(question, "No", "radio")

    if has_any(text, ("frontend", "front-end", "front end")) and has_any(
        text,
        ("tech stack", "technology stack", "technologies", "skills", "framework", "library"),
    ):
        return answer_payload(question, FRONTEND_TECH_STACK, "text")

    if has_any(text, ("backend", "back-end", "back end", "server side")) and has_any(
        text,
        ("tech stack", "technology stack", "technologies", "skills", "framework"),
    ):
        return answer_payload(question, BACKEND_TECH_STACK, "text")

    if has_any(
        text,
        (
            "tech stack",
            "technology stack",
            "technical skills",
            "primary skills",
            "key skills",
            "skills set",
            "skill set",
            "tools and technologies",
            "technologies used",
        ),
    ):
        return answer_payload(question, PRIMARY_TECH_STACK, "text")

    if has_any(text, ("frontend framework", "front-end framework", "javascript framework", "ui framework")):
        return answer_payload(question, "React.js", "text")

    return None


def expected_answer_for_question(question, profile_answers):
    text = normalize_question(question)
    if not text:
        return None

    current_location = profile_answers.get("current_location", "Bengaluru")
    total_experience = profile_answers.get("total_experience", "6")
    notice_period = profile_answers.get("notice_period", "Immediate Joiner")
    current_ctc = profile_answers.get("current_ctc", "1550000")
    expected_ctc = profile_answers.get("expected_ctc", "1800000")

    tech_answer = answer_tech_stack_question(question, text)
    if tech_answer:
        return tech_answer

    if has_any(text, ("email", "e-mail")):
        return answer_payload(question, "kvskandakumar@gmail.com", "text")
    if has_any(text, ("mobile", "phone", "contact number", "telephone")):
        if has_any(text, ("country code", "dialing code", "dial code")):
            return answer_payload(question, "India (+91)", "select")
        return answer_payload(question, "7981611434", "text")
    if has_all(text, ("first", "name")):
        return answer_payload(question, "Skanda", "text")
    if has_all(text, ("last", "name")) or has_any(text, ("surname", "family name")):
        return answer_payload(question, "Kumar", "text")
    if has_any(text, ("full name", "legal name")):
        return answer_payload(question, "Skanda Kumar", "text")

    if has_any(text, ("current location", "present location", "city", "where are you located")):
        return answer_payload(question, current_location, "text")
    if has_any(text, ("notice period", "serving notice", "when can you start", "available to start", "joining time")):
        return answer_payload(question, notice_period, "text")
    if has_any(text, ("current ctc", "current salary", "current compensation", "current package")):
        return answer_payload(question, current_ctc, "text")
    if has_any(text, ("expected ctc", "expected salary", "salary expectation", "desired salary", "expected compensation", "expected package")):
        return answer_payload(question, expected_ctc, "text")
    if has_any(text, ("total experience", "overall experience", "years of experience", "professional experience")):
        return answer_payload(question, total_experience, "text")

    if has_any(text, ("authorized to work", "eligible to work", "work authorization", "right to work")):
        return answer_payload(question, "Yes", "radio")
    if has_any(text, ("sponsorship", "visa sponsor", "require visa", "need visa")):
        return answer_payload(question, "No", "radio")
    if has_any(text, ("relocate", "relocation")):
        return answer_payload(question, "Yes", "radio")
    if has_any(text, ("remote", "hybrid", "work from office", "office location", "onsite", "on-site")):
        return answer_payload(question, "Yes", "radio")
    if has_any(text, ("background check", "reference check")):
        return answer_payload(question, "Yes", "radio")

    if has_any(text, ("currently employed", "are you employed")):
        return answer_payload(question, "Yes", "radio")
    if has_any(text, ("worked for us", "previously employed", "former employee")):
        return answer_payload(question, "No", "radio")
    if has_any(text, ("non-compete", "non compete", "bond", "service agreement")):
        return answer_payload(question, "No", "radio")

    if has_any(text, ("gender", "race", "ethnicity", "disability", "veteran")):
        return answer_payload(question, "Prefer not to say", "select")
    if has_any(text, ("terms", "privacy", "consent", "acknowledge", "certify", "accurate", "true and complete")):
        return answer_payload(question, "true", "checkbox")

    return None


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

    return expected_answer_for_question(question, profile_answers)


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


def answers_match(option, answer):
    option_text = normalize_question(option)
    answer_text = normalize_question(answer)
    if not option_text or not answer_text:
        return False
    if option_text == answer_text:
        return True
    if answer_text in option_text or option_text in answer_text:
        return True
    if answer_text == "yes":
        return option_text.startswith("yes") or option_text in ("y", "true")
    if answer_text == "no":
        return option_text.startswith("no") or option_text in ("n", "false")
    if "prefer not" in answer_text:
        return any(
            marker in option_text
            for marker in ("prefer not", "do not wish", "decline", "not disclose")
        )
    return False


def select_matching_option(control, answer):
    try:
        control.select_option(label=answer)
        return True
    except Exception:
        pass
    try:
        control.select_option(value=answer)
        return True
    except Exception:
        pass

    options = control.locator("option")
    for option_index in range(options.count()):
        option = options.nth(option_index)
        option_text = option.inner_text().strip()
        option_value = option.get_attribute("value") or ""
        if answers_match(option_text, answer) or answers_match(option_value, answer):
            control.select_option(index=option_index)
            return True
    return False


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
        saved_type = saved.get("type")
        control_type = details["type"]
        if control_type not in ("radio", "checkbox", "select") and saved_type in ("radio", "checkbox"):
            continue

        try:
            if control_type == "radio":
                if answers_match(details["option"], answer):
                    if not control.is_checked():
                        control.check()
                        filled += 1
            elif control_type == "checkbox":
                should_check = answer.lower() in ("true", "yes", "1")
                if control.is_checked() != should_check:
                    control.set_checked(should_check)
                    filled += 1
            elif control_type == "select":
                if select_matching_option(control, answer):
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
