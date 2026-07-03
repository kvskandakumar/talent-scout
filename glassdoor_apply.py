from shared_job_board_apply import run_job_board

SITE = {
    "key": "glassdoor",
    "name": "Glassdoor",
    "auth_file": "glassdoor_auth.json",
    "history_file": "glassdoor_application_history.json",
    "attempts_file": "glassdoor_application_attempts.jsonl",
    "defaults": {
        "enabled": False,
        "login_url": "https://www.glassdoor.co.in/profile/login_input.htm",
        "search_url_template": (
            "https://www.glassdoor.co.in/Job/jobs.htm"
            "?sc.keyword={keyword_query}&locKeyword={location_query}"
        ),
        "max_applications": 25,
        "max_application_steps": 8,
        "posted_within_hours": 72,
        "only_instant_apply": True,
        "learn_question_answers": True,
    },
    "card_selectors": [
        "li[data-test='jobListing']",
        "li.react-job-listing",
        "div[data-test='jobListing']",
        "article[data-test='jobListing']",
        "li:has(a[href*='/job-listing/'])",
    ],
    "link_selectors": [
        "a[data-test='job-link']",
        "a[href*='/job-listing/']",
        "a.JobCard_jobTitle__",
        "a",
    ],
    "title_selectors": [
        "h1[data-test='job-title']",
        "h1",
        "[data-test='jobTitle']",
        ".JobDetails_jobTitle__",
    ],
    "company_selectors": [
        "[data-test='employer-name']",
        "[data-test='employerName']",
        ".EmployerProfile_employerName__",
        ".JobDetails_jobDetailsHeader__ a",
    ],
    "apply_selectors": [
        "button[data-test='applyButton']",
        "button[data-test='easyApply']",
        "button:has-text('Easy Apply')",
        "button:has-text('Apply Now')",
        "button:has-text('Apply')",
        "a:has-text('Easy Apply')",
        "a:has-text('Apply Now')",
        "a:has-text('Apply')",
    ],
}


if __name__ == "__main__":
    run_job_board(SITE)
