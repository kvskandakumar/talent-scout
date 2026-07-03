from job_board_apply import run_job_board

SITE = {
    "key": "indeed",
    "name": "Indeed",
    "auth_file": "indeed_auth.json",
    "history_file": "indeed_application_history.json",
    "attempts_file": "indeed_application_attempts.jsonl",
    "defaults": {
        "enabled": False,
        "login_url": "https://secure.indeed.com/auth?hl=en_IN&co=IN",
        "search_url_template": (
            "https://in.indeed.com/jobs"
            "?q={keyword_query}&l={location_query}&fromage={posted_within_days}"
        ),
        "max_applications": 25,
        "max_application_steps": 8,
        "posted_within_hours": 72,
        "only_instant_apply": True,
        "learn_question_answers": True,
    },
    "card_selectors": [
        "div.job_seen_beacon",
        "div.cardOutline",
        "div[data-jk]",
        "li:has(a[data-jk])",
        "li:has(a[href*='/viewjob'])",
    ],
    "link_selectors": [
        "a[data-jk]",
        "a.jcs-JobTitle",
        "a[href*='/viewjob']",
        "a[href*='jk=']",
        "a",
    ],
    "title_selectors": [
        "h1[data-testid='jobsearch-JobInfoHeader-title']",
        "h1.jobsearch-JobInfoHeader-title",
        "h1",
        "[data-testid='job-title']",
    ],
    "company_selectors": [
        "[data-testid='inlineHeader-companyName']",
        "[data-company-name='true']",
        ".jobsearch-InlineCompanyRating a",
        ".jobsearch-CompanyInfoContainer a",
    ],
    "apply_selectors": [
        "button[data-testid='indeedApplyButton']",
        "button:has-text('Apply now')",
        "button:has-text('Apply')",
        "a:has-text('Apply now')",
        "a:has-text('Apply')",
    ],
}


if __name__ == "__main__":
    run_job_board(SITE)
