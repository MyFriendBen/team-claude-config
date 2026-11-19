---
name: accelerate-qa
description: Work through every Linear ticket assigned to you in "Prod QA" or "Staging QA" (required argument, prod or staging). Sorts the tickets by how much can be scripted, runs the scripts or hands them over, moves passing tickets on with a results comment, and walks you through the manual checks. Use when the user asks to clear, speed up, or batch their Prod QA or Staging QA tickets.
argument-hint: prod | staging
---

# Accelerate QA

<!-- Editing note: never put a dollar sign directly before a digit in this file. When the skill loads, a dollar sign followed by a number is replaced by an argument. Write amounts as plain numbers or "N dollars". -->

Clear one of your QA columns in batches. Scripted checks come first and manual checks last. Every ticket moves on with a comment that says what was verified and how.

"The user" below means whoever is running the skill.

## Environment argument (required)

The argument must be exactly `prod` or `staging`. If it's missing or anything else, stop and ask which one. Never guess.

|                    | `prod`                                       | `staging`                                          |
|--------------------|----------------------------------------------|----------------------------------------------------|
| Linear column      | **Prod QA**                                  | **Staging QA**                                     |
| Heroku app         | `cobenefits-api`                             | `cobenefits-api-staging`                           |
| API base           | `https://cobenefits-api.herokuapp.com`       | `https://cobenefits-api-staging.herokuapp.com`     |
| Who runs scripts   | the user (Claude hands them over)            | Claude, directly                                   |
| Deployed when      | GitHub release published                     | every push to `main` (api and calculator)          |
| Passing ticket →   | **Done**                                     | **Ready for Release**                              |
| Comment heading    | **Prod QA passed (date)**                    | **Staging QA passed (date)**                       |

Everything below applies to both, unless it's marked **prod** or **staging**.

**Batch folder:** `qa/<env>-qa-<YYYY-MM-DD>/` in the workspace, created if missing. Add `-<ticket>` for a single-ticket run (`qa/staging-qa-2026-11-19-mfb-1234/`). Every script, output file and results note for the batch goes there.

**Templates:** start from `${CLAUDE_SKILL_DIR}/templates/`. Copy them into the batch folder; don't write them from scratch.
- `preflight.py` is the read-only state check, run in a Django shell.
- `scenarios.py` is the stdlib-only scenario runner. It reads `API_BASE` and `API_KEY` from the environment, so the same file runs against either environment.

## Who runs what

**prod:** Claude never runs anything against prod. That means no `cobenefits-api` shell, no database queries and no HTTP to `cobenefits-api.herokuapp.com`, read-only included. So:

- Claude **writes and tests** every script against staging. **The user runs it in prod** and pastes the output, and Claude grades it.
- Hand over a **table: ticket → exact command → staging result**, so the user runs a whole bucket in one go.
- Staging is fine to query directly. Use it to tell a code bug from a prod-config problem: the same code passing on staging means prod config.
- Say up front that this is the flow. Don't ask how to handle prod each time.

**staging:** Claude runs everything itself: the state check via `heroku run` on `cobenefits-api-staging`, and the scenarios over HTTP.
- **API key:** read it in-process from wherever the user keeps it (an environment variable or the workspace `.env`), in the same command that runs the script. Never echo, log or write it, and never edit a `.env` file. If you can't find it, ask.
- **Read-only:** scripts stay read-only even though staging allows writes. Any data change, such as activating a program or importing a program, is the user's call.

## Steps

### 1. Gather
- Run `list_issues(assignee="me", state="Prod QA" | "Staging QA")`, then `get_issue` on each one for the description, attachments, acceptance criteria and open checkboxes. Read the comments with `list_comments`.
- For every linked PR, check that it's deployed to the environment:
  - **prod:** it's in the latest prod release. Prod deploys come from GitHub releases (`gh release list`). Check with `git merge-base --is-ancestor <merge-sha> <release-tag>`.
  - **staging:** it's merged to `main`, and a `Deploy to Staging` run succeeded on or after the merge commit (`gh run list --workflow deploy-staging.yml --branch main`). A failed staging deploy leaves the previous build up.
  - **Baby Ben** (family-affordability-tax-credit-calculator): `gh api repos/MyFriendBen/family-affordability-tax-credit-calculator/deployments`. The environments are `baby-ben` and `baby-ben-staging`.
  - **co-tax-credit-calculator:** it has no GitHub deployments. It deploys by pushing to Heroku (see its README), so ask the user if you can't confirm what's live.
- An unmerged or undeployed PR means the ticket isn't ready. Say so instead of testing it.
- Tickets with no program or screener change (tooling, skills, docs) have nothing to deploy. Check them against their acceptance criteria, and expect them to land in bucket 3.

### 2. State check first (one read-only script for all tickets)
Copy `templates/preflight.py` and add one block per ticket covering every row it touches:
- migrations applied;
- programs exist, are active, have a registered calculator and the right year;
- replaced rows are inactive;
- warnings and the programs they link;
- referrers and config keys.

It prints `PASS/FAIL/INFO [ticket] …` and a summary.

```
cd <workspace>/benefits-api && heroku run --no-tty -a <heroku app> "python manage.py shell" < <batch folder>/preflight.py
```

Keep `--no-tty`; without it the shell reads the file line by line and the summary is wrong. Quote the management command, or its flags collide with `heroku run`'s own.

- **Dry-run it locally first** to catch errors, but **don't trust local data**. The local database is often stale, and it holds rows from other branches. Treat a local-only FAIL as unconfirmed until the target environment agrees.
- **Inactive program:** an inactive program is never calculated, so scenarios against it are meaningless. Ask the user whether to switch it on, skip the ticket, or move it back.
- **staging, missing or out-of-date program:** this usually means the program hasn't been imported on staging yet. Program records import through program-ops `scripts/import_programs.py`, v2 specs through benefits-api's `apply_program`, and a program can only be imported once its calculator has deployed. Report it; don't import it unasked.

### 3. Sort into buckets
- **Bucket 1, fully scriptable:** the state check plus the API scenarios cover every acceptance criterion that can be tested in the environment. Anything that can't be triggered safely there (outages, crashes, Sentry paths) is covered by the PR's tests; say so in the comment.
- **Bucket 2, partly scriptable:** the scripted part, plus something only a browser shows (rendering, branding, the network tab, other apps).
- **Bucket 3, fully manual.**

Give the user the buckets, with one line of reasoning per ticket.

### 4. Scenario runner
Copy `templates/scenarios.py` and encode each ticket's spec scenarios as data. Find the spec in program-ops, as `/api-qa-execution` Phase 1 does.

**Payloads and grading follow `/api-qa-execution`.** Use Phase 2 for payloads (ages, flags, insurance, counties, federal programs) and Phase 3 for grading (outcomes, value tolerance, `missing_programs`, ERROR and BLOCKED). The template already implements them. When the two disagree, `/api-qa-execution` wins, so fix the template.

Batch-specific conventions:

- **Current benefits:** resolve each one against `GET /api/screener-options/<wl>/has-benefits-programs/`.
  - Name not offered → **SKIP**, with the reason. The comment names it as covered by unit tests only.
  - `=name` sends a known row directly. Flag that it isn't in the has-benefits step, because a real household can't report it.
- **400 on POST** means the payload is wrong, not the program. The API rejects a ZIP or county the white label doesn't serve ("Did you mean 'Essex County'?") and any value the screener doesn't send (relationship, income or expense type). Fix the payload and rerun.
- **A program absent with `missing_programs: true`** is an ERROR, not a FAIL. On staging, `why_dropped(<screen uuid>)` in the preflight template reads the screen's `EligibilitySnapshot.dropped_programs` and names the reason.
- **Federal programs:** also smoke-test a few scenarios on white labels that newly gain the program (e.g. `co_tax_calculator`, `_default`), plus one or two states.
- **PolicyEngine version:** staging and prod both ride PE `current`. A spec validated at `frontier` can fail its boundary scenarios until PE promotes. Rerun the failing screen with `?pe_version=frontier` before calling it a code bug.
- **Known PolicyEngine failures count as passing.** If a scenario fails only because of a PolicyEngine issue that's already reported (a strict xfail in the PR's tests, matching the local baseline), the ticket passes, provided there are 0 ERROR rows (no 4xx or 5xx) and no failures outside the known set. List those failures in the comment as open upstream. A new failure or any ERROR means the ticket doesn't pass.
- **Test the runner on staging before it counts:**
  - **prod:** run it against staging as a rehearsal. Staging has the same code and a working key. Tell the user this tested the script, not prod. Every scenario should pass there, so a prod FAIL points at prod.
  - **staging:** the staging run is the test. A local dry run only proves the script works, because local data is unreliable (see step 2). Don't start a local server or switch rows on just to make it pass.

### 5. Move bucket 1 on as it passes
When every check passes, post the comment and move the ticket (**prod:** Done; **staging:** Ready for Release) without checking in first; running the skill is the go-ahead. On any FAIL or ERROR, leave the ticket in its QA column, post nothing, and diagnose it with the user.

When you report a failure, give the technical cause, a plain-language version, and the household from the scenario that shows it.

### 6. Bucket 2/3 manual steps
List them per ticket, numbered. Each step has:
- the exact URL in the environment, with `test=true` (`?test` for the tax apps);
- the household to enter;
- what to click;
- a concrete **Pass:** line (exact copy, dollar value, request method, empty grep output).

Things that cost time:
- **staging:** the screener is `benefits-calculator-staging.herokuapp.com`; the API host serves no pages.
- **Partner links:** use `?referrer=<code>&test=true`. Adding `referrer=test` as well overwrites the partner attribution.
- **Feature flags:** before failing a missing UI element, check that its flag is on for that white label. Some results-page features render only where their flag is set.
- **Raw translation IDs on the page:** the copy wasn't added to the Translation table. Use `/add-pr-translations`; it's a deploy gap, not a code bug.
- **Checking the screener locally:** use `npm run dev`. `npm start` serves the last build, not the current source.

Wait for the user's results. Then post one combined scripted + manual comment per ticket and move the ticket on. Move tickets one at a time as results come in; don't wait for the whole batch.

### 7. Comment format
Head the comment **Prod QA passed (date)** or **Staging QA passed (date)**, then list:
- what shipped: the PRs, plus **prod:** the release tag and deploy date, or **staging:** the merge commit and staging deploy date;
- the state check results;
- the scenario counts and the key values, quoting the spec's figures rather than a bare section number;
- skipped scenarios and why;
- known PolicyEngine failures left open upstream, if any;
- manual steps confirmed;
- anything not testable in the environment, and what covers it;
- any acceptance-criteria item still open (named, not hidden).

Facts only, no screen UUIDs needed, no real household data.

## Recurring setups

- **Tax apps run locally against the environment's API.** Both CO Get Ahead apps (co-tax-credit-calculator and Baby Ben, i.e. family-affordability-tax-credit-calculator) work locally against the prod or staging API, because the API allows any origin.
  - Switch to `main` and run `npm ci`.
  - Pass env vars inline; never write a `.env`. First list every variable the app imports (`git grep -hoE 'PUBLIC_[A-Z_]+' -- src` for Baby Ben, `'VITE_[A-Z_]+'` for co-tax). Both need the frontend domain as well as the API domain and key.
  - Open the app with `?test` so screens are test screens.
- **prod, prod-only 502 from an upstream API:** run the same request on staging. If staging passes, the cause is prod config, usually the upstream key or its billing. Hand the user a shell snippet that calls the upstream and prints its status and error message, never the key.
- **Brief third-party errors** (e.g. Rewiring America `third_party_error`): rerun before calling it a failure.

## Finish
- Move the batch folder to `qa/archive/`.
- Report:
  - the tickets moved on;
  - anything left in the QA column, and why;
  - any follow-ups found. Offer to open tickets; don't create them unasked.
