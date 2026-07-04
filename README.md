# Talent Scout

Talent Scout is a Playwright-based job application helper for LinkedIn, Naukri, Glassdoor, and Indeed. It searches configured keywords and locations, opens job cards, reuses saved answers for application forms, and records application attempts/history locally.

This project is designed for supervised use. Keep `headless` disabled while tuning selectors and answers so you can see what the browser is doing.

## Supported Job Boards

| Board | Login script | Apply script | Session file | Notes |
| --- | --- | --- | --- | --- |
| LinkedIn | `linkedin_login.py` | `linkedin_apply.py` | `auth.json` | Uses LinkedIn Easy Apply flow. |
| Naukri | `naukri_login.py` | `naukri_apply.py` | `naukri_auth.json` | Uses Naukri instant/internal apply where possible. |
| Glassdoor | `glassdoor_login.py` | `glassdoor_apply.py` | `glassdoor_auth.json` | Uses shared job-board runner. |
| Indeed | `indeed_login.py` | `indeed_apply.py` | `indeed_auth.json` | Uses shared job-board runner. |

## Requirements

- Python 3.10+
- Playwright for Python
- Chromium browser installed through Playwright

Install dependencies:

```sh
python -m venv venv
source venv/bin/activate
pip install playwright
python -m playwright install chromium
```

If you already have a working virtual environment, activate it and skip the venv creation.

## Configuration

Main settings live in `config.json`.

Important top-level keys:

- `keywords`: job titles/search terms to apply for.
- `locations`: locations searched for each keyword.
- `posted_within_hours`: age filter for supported search URLs.
- `max_applications`: maximum applications per run.
- `max_application_steps`: maximum form steps before the script skips a job.
- `easy_apply_only`: LinkedIn Easy Apply filter.
- `learn_question_answers`: when true, the script can pause for you to fill unknown questions and then save those answers.
- `dry_run`: when true, scripts stop before final submission.
- `headless`: when false, browser windows are visible.
- `profile_answers`: canonical values reused for salary, notice period, location, and experience prompts.

Each board can also have its own section, for example:

```json
"glassdoor": {
  "enabled": true,
  "keywords": [],
  "locations": [],
  "max_applications": 25,
  "max_application_steps": 8,
  "posted_within_hours": 72,
  "only_instant_apply": true,
  "learn_question_answers": true
}
```

Empty board-level `keywords` or `locations` fall back to the top-level lists.

## Login Sessions

Before applying on a board, create its browser session file:

```sh
python linkedin_login.py
python naukri_login.py
python glassdoor_login.py
python indeed_login.py
```

Each login script opens a browser. Log in manually, wait until the site is fully loaded, then return to the terminal and press Enter. The script writes a storage-state JSON file such as `auth.json` or `glassdoor_auth.json`.

These auth files contain session data and should not be shared.

## Running Applications

Run the apply script for the board you want:

```sh
python linkedin_apply.py
python naukri_apply.py
python glassdoor_apply.py
python indeed_apply.py
```

For boards with an `enabled` flag, set it to `true` in `config.json` first. If the script prints a message like:

```txt
Glassdoor support is disabled. Set config.glassdoor.enabled to true when ready.
```

then update that board's config section.

Recommended first run:

```json
"dry_run": true,
"headless": false
```

This lets you inspect the flow before the script submits applications.

## Answer Reuse

`question_answers.json` stores known application-question answers. The script normalizes question labels and reuses matching answers for text inputs, selects, radios, and checkboxes.

`shared_answers.py` also contains intent-based matching for common prompts, including:

- name, email, phone, country code
- current location
- total experience
- current and expected CTC
- notice period
- work authorization and sponsorship
- remote/hybrid/onsite comfort
- relocation and background checks
- consent/terms checkboxes
- common tech-stack prompts based on this profile, including React, TypeScript, JavaScript, HTML/CSS, Redux, REST APIs, Git, Node.js, and Express.js

When `learn_question_answers` is enabled and the browser is visible, unsupported questions can pause the run. Fill the visible form fields manually, return to the terminal, and press Enter. The script captures the visible answers into `question_answers.json`.

## Output Files

The scripts write local run state:

- `application_history.json`: LinkedIn applied job IDs.
- `application_attempts.jsonl`: LinkedIn attempt log.
- `naukri_application_history.json`: Naukri applied job IDs.
- `naukri_application_attempts.jsonl`: Naukri attempt log.
- `glassdoor_application_history.json`: Glassdoor applied job IDs, created when Glassdoor runs.
- `glassdoor_application_attempts.jsonl`: Glassdoor attempt log, created when Glassdoor runs.
- `indeed_application_history.json`: Indeed applied job IDs, created when Indeed runs.
- `indeed_application_attempts.jsonl`: Indeed attempt log, created when Indeed runs.

Attempt logs are JSON Lines files. Each line records the timestamp, job metadata, status, and reason.

## Project Structure

```txt
config.json                  Main search/profile/apply settings
question_answers.json        Saved application answers
shared_answers.py            Shared answer matching and answer learning
shared_job_board_apply.py    Generic runner used by Glassdoor and Indeed
linkedin_login.py            Manual LinkedIn session capture
linkedin_apply.py            LinkedIn Easy Apply automation
naukri_login.py              Manual Naukri session capture
naukri_apply.py              Naukri apply automation
glassdoor_login.py           Manual Glassdoor session capture
glassdoor_apply.py           Glassdoor apply config wrapper
indeed_login.py              Manual Indeed session capture
indeed_apply.py              Indeed apply config wrapper
bot.py                       Older/simple LinkedIn login helper
```

## Safety Notes

- Use `dry_run: true` when changing selectors, answers, or config.
- Keep `headless: false` until you trust a flow.
- Review `question_answers.json` before running live applications.
- Do not commit or share auth/session files.
- Job-board UIs change often; selectors may need periodic maintenance.

## Troubleshooting

If a script cannot find jobs or apply buttons:

- Confirm you are logged in by rerunning the matching login script.
- Run with `headless: false` and watch the browser.
- Check whether the board is enabled in `config.json`.
- Reduce `max_applications` and enable `dry_run` while debugging.
- Inspect attempt logs for skip reasons.

If a form question is not answered:

- Add an exact normalized entry to `question_answers.json`, or
- Run with `learn_question_answers: true`, fill the question manually, and let the script capture it.
