---
name: accelerate-qa
description: Work through every Linear ticket assigned to you in "Prod QA" or "Staging QA" (required argument, prod or staging). Imports program tickets' programs first (staging), sorts the tickets by how much can be scripted, runs the scripts or hands them over, moves passing tickets on with a results comment, and walks you through the manual checks. Use when the user asks to clear, speed up, or batch their Prod QA or Staging QA tickets.
argument-hint: prod | staging
---

# Accelerate QA

<!-- Editing note: never put a dollar sign directly before a digit in this file. When the skill loads, a dollar sign followed by a number is replaced by an argument. Write amounts as plain numbers or "N dollars". -->

Clear one of your QA columns in batches. Scripted checks come first and manual checks last. Every ticket moves on with a comment that says what was verified and how.

"The user" below means whoever is running the skill. `<mfb-workspace>` is the folder that holds the user's `benefits-api`, `program-ops` and `.claude` clones and config: the one passed to `setup.sh`. It isn't necessarily a git repo, so run git and `gh` against a named clone or repo, as the commands below do.

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

**Batch folder:** `<mfb-workspace>/qa/<env>-qa-<YYYY-MM-DD>/`, created if missing. Add `-<ticket>` for a single-ticket run (`qa/staging-qa-2026-11-19-mfb-1234/`). Every script, output file and results note for the batch goes there.

**Templates:** start from `${CLAUDE_SKILL_DIR}/templates/`. Copy them into the batch folder; don't write them from scratch.
- `preflight.py` is the read-only state check, run in a Django shell.
- `scenarios.py` is the stdlib-only scenario runner. It reads `API_BASE` and `API_KEY` from the environment, so the same file runs against either environment.

## Who runs what

**prod:** Claude never runs anything against prod. That means no `cobenefits-api` shell, no database queries and no HTTP to `cobenefits-api.herokuapp.com`, read-only included. So:

- Claude **writes and tests** every script against staging. **The user runs it in prod** and pastes the output, and Claude grades it.
- Hand over a **table: ticket → exact command → staging result**, so the user runs a whole bucket in one go.
- Staging is fine to query directly, and comparing with it helps narrow a prod failure. Staging follows `main` and prod follows the last release, so first compare what each has deployed. A staging pass on the same code points at prod config or data, but it isn't proof: data differences and flaky upstream APIs can produce the same split.
- Say up front that this is the flow. Don't ask how to handle prod each time.

**staging:** Claude runs everything itself: the state check via `heroku run` on `cobenefits-api-staging`, and the scenarios over HTTP.
- **API key:** `STAGING_API_KEY` in `<mfb-workspace>/.env`, the same key `/api-qa-execution` uses. The runner reads `API_KEY`, so pass the key in the same command that runs it, without printing it:
  ```
  API_KEY="$(grep '^STAGING_API_KEY=' "<mfb-workspace>/.env" | cut -d= -f2-)" API_BASE=https://cobenefits-api-staging.herokuapp.com python3 scenarios.py <TICKET>
  ```
  Never echo, log or write the key, and never edit a `.env` file. If it isn't there, ask the user where they keep it.
- **Read-only:** scripts stay read-only even though staging allows writes. There are two exceptions: the program import in step 2, and the test screens (`is_test: true`) the scenario runner creates, one per scenario. Any other data change, such as activating a program, is the user's call.

## Steps

### 1. Gather
- Run `list_issues(assignee="me", state="Prod QA" | "Staging QA")`, then `get_issue` on each one for the description, attachments, acceptance criteria and open checkboxes. Read every comment with `list_comments`, following the cursor through every page, and open the related, parent and blocking tickets the same way.
- **Flag decision-changing comments before testing.** A comment or related ticket that changes scope, a rule or an expected value is a decision. Check whether the linked PRs implement it. List each one for the user with the ticket, the comment's author and date, what it decided and whether the PR handles it, and wait for their call before testing that ticket. A decision the PR doesn't implement isn't a pass.
- **Capture extra checks from comments.** Comments often name things worth testing that aren't in the acceptance criteria (an edge case found during a local test, a household that misbehaved). Add each one to the ticket's checks, scripted or manual, and name where it came from.
- For every linked PR, check that it's deployed to the environment:
  - **prod:** it's in the latest prod release. Prod deploys come from GitHub releases. Check with `git -C "<mfb-workspace>/<repo>" fetch -q --tags origin && git -C "<mfb-workspace>/<repo>" merge-base --is-ancestor <merge-sha> <release-tag>`, and list releases with `gh release list --repo MyFriendBen/<repo>`.
  - **staging:** it's merged to `main`, and a `Deploy to Staging` run succeeded on or after the merge commit (`gh run list --repo MyFriendBen/<repo> --workflow deploy-staging.yml --branch main`). A failed staging deploy leaves the previous build up.
  - **Baby Ben** (family-affordability-tax-credit-calculator): `gh api repos/MyFriendBen/family-affordability-tax-credit-calculator/deployments`. The environments are `baby-ben` and `baby-ben-staging`.
  - **co-tax-credit-calculator:** it has no GitHub deployments. It deploys by pushing to Heroku (see its README), so ask the user if you can't confirm what's live.
- An unmerged or undeployed PR means the ticket isn't ready. Say so instead of testing it.
- Tickets with no program or screener change (tooling, skills, docs) have nothing to deploy. Check them against their acceptance criteria, and expect them to land in bucket 3.

### 2. Import program tickets' programs (before any test)
A ticket is a program ticket when it adds or changes one program, named by its program key: a white label code, an underscore, and an abbreviated program name (`nj_head_start`, `co_snap`, `federal_ssdi`). Find the key in the ticket's title, description or linked PRs. Confirm that its record is on program-ops `main`, because staging and prod import only merged records:

```
git -C "<mfb-workspace>/program-ops" fetch -q origin
git -C "<mfb-workspace>/program-ops" ls-tree -r --name-only origin/main | grep '/<key>_program_record.json$'
```

If there's no record on `main` (not merged yet, or the program has only a v2 spec), the program change hasn't shipped. Stop that ticket: leave it in its QA column, tell the user, and go on with the others. If you can't tell which key a ticket is about, ask.

**staging:** import each program before running anything else. Run these from `<mfb-workspace>/program-ops` (quote the path if it has spaces):
1. Dry run: `python3 scripts/import_programs.py --env staging --dry-run-only --program <key>`.
2. Read the summary counts:
   - **`Failed`, `Waiting`, `Conflicts`, `Admin edits kept` or `Not applied yet` above 0:** stop and show the user that part of the output. `Waiting` means the calculator hasn't deployed. The others need a person to decide which value wins.
   - **Only `Current`:** nothing to import; go on.
   - **`To create` or `To update` above 0, and nothing else:** apply it with `echo y | python3 scripts/import_programs.py --env staging --program <key>`. The `y` answers the single "Apply the changes above to staging?" prompt.
3. Note the result (created, updated or current) for the ticket comment.

An import never switches a program on or off. A newly created program is inactive, so step 3's inactive-program rule applies.

**prod:** never run the import. Before step 3, list each program key and ask the user to run `python3 scripts/import_programs.py --env prod --program <key>` from program-ops. Wait for them to confirm before going on.

### 3. State check first (one read-only script for all tickets)
Copy `templates/preflight.py` and add one block per ticket covering every row it touches:
- migrations applied;
- programs exist, are active, have a registered calculator and the right year (`navigators(p)` lists navigators in display order);
- replaced rows are inactive;
- warnings and the programs they link;
- referrers and config keys.

It prints `PASS/FAIL/INFO [ticket] …` and a summary.

```
cd "<mfb-workspace>/benefits-api" && heroku run --no-tty -a <heroku app> "python manage.py shell" < "<batch folder>/preflight.py"
```

Keep `--no-tty`; without it the shell reads the file line by line and the summary is wrong. Quote the management command, or its flags collide with `heroku run`'s own.

- **Dry-run it locally first** to catch errors, but **don't trust local data**. The local database is often stale, and it holds rows from other branches. Treat a local-only FAIL as unconfirmed until the target environment agrees.
- **Inactive program:** an inactive program is never calculated, so scenarios against it are meaningless. Ask the user whether to switch it on, skip the ticket, or move it back.
- **Missing or out-of-date program after step 2:** check the import output first. A program can only be imported once its calculator has deployed. Report anything left over; don't import beyond step 2 unasked.

### 4. Sort into buckets
Sort on the acceptance criteria plus the extra checks from step 1.

- **Bucket 1, fully scriptable:** the state check plus the API scenarios cover every acceptance criterion that can be tested in the environment. Anything that can't be triggered safely there (outages, crashes, Sentry paths) is covered by the PR's tests; say so in the comment.
- **Bucket 2, partly scriptable:** the scripted part, plus something only a browser shows (rendering, branding, the network tab, other apps).
- **Bucket 3, fully manual.**

Give the user the buckets, with one line of reasoning per ticket.

### 5. Scenario runner
Copy `templates/scenarios.py` and encode each ticket's spec scenarios as data. Find the spec in program-ops, as `/api-qa-execution` Phase 1 does.

**Payloads and grading follow `/api-qa-execution`.** Use Phase 2 for payloads (ages, flags, insurance, counties, federal programs) and Phase 3 for grading (outcomes, value tolerance, `missing_programs`, ERROR and BLOCKED). The template already implements them. When the two disagree, `/api-qa-execution` wins, so fix the template.

Batch-specific conventions:

- **Current benefits:** resolve each one against `GET /api/screener-options/<wl>/has-benefits-programs/`.
  - Name not offered → **SKIP**, with the reason. The comment names it as covered by unit tests only.
  - `=name` sends a known row directly. Flag that it isn't in the has-benefits step, because a real household can't report it.
- **No HTTP response (status 0)** is a network blip, not an API answer. Rerun that scenario alone before reporting it.
- **400 on POST** means the payload is wrong, not the program. The API rejects a ZIP or county the white label doesn't serve ("Did you mean 'Essex County'?") and any value the screener doesn't send (relationship, income or expense type). Fix the payload and rerun.
- **A program absent with `missing_programs: true`** is an ERROR, not a FAIL. On staging, `why_dropped(<screen uuid>)` in the preflight template reads the screen's `EligibilitySnapshot.dropped_programs` and names the reason.
- **Federal programs:** also smoke-test a few scenarios on white labels that newly gain the program (e.g. `co_tax_calculator`, `_default`), plus one or two states.
- **PolicyEngine version:** staging and prod both ride PE `current`. A spec validated at `frontier` can fail its boundary scenarios until PE promotes. Rerun the failing screen with `?pe_version=frontier` before calling it a code bug.
- **Known PolicyEngine failures count as passing.** If a scenario fails only because of a PolicyEngine issue that's already reported (a strict xfail in the PR's tests, matching the local baseline), the ticket passes, provided there are 0 ERROR rows (no 4xx or 5xx) and no failures outside the known set. List those failures in the comment as open upstream. A new failure or any ERROR means the ticket doesn't pass.
- **Test the runner on staging before it counts:**
  - **prod:** run it against staging as a rehearsal. Staging runs `main`, which is the same as or newer than prod's release; compare the two deploys before reading a prod result against it. Tell the user this tested the script, not prod. Every scenario should pass there, so a prod FAIL points at prod.
  - **staging:** the staging run is the test. A local dry run only proves the script works, because local data is unreliable (see step 3). Don't start a local server or switch rows on just to make it pass.

### 6. Move bucket 1 on as it passes
When every check passes, post the comment and move the ticket (**prod:** Done; **staging:** Ready for Release) without checking in first; running the skill is the go-ahead. On any FAIL or ERROR, leave the ticket in its QA column, post nothing, and diagnose it with the user.

When you report a failure, give the technical cause, a plain-language version, and the household from the scenario that shows it.

### 7. Bucket 2/3 manual steps
List them per ticket, numbered. Each step has:
- the exact URL in the environment, with `test=true` (`?test` for the tax apps);
- the household to enter;
- what to click;
- a concrete **Pass:** line (exact copy, dollar value, request method, empty grep output).

Things that cost time:
- **Results pages without re-entering households:** each scenario screen opens directly at `<screener>/<wl>/<screen uuid>/results/benefits`. Take the UUIDs from the runner's output.
- **One button on the program details page:** it's the apply button (`apply_button_link`), labelled with `apply_button_description` or "Apply Online" when that's blank. `learn_more_link` isn't on the results pages; it's the program-name link on `<screener>/<wl>/current-benefits`. Write **Pass:** lines to match.
- **staging:** the screener is `benefits-calculator-staging.herokuapp.com`; the API host serves no pages.
- **Partner links:** use `?referrer=<code>&test=true`. Adding `referrer=test` as well overwrites the partner attribution.
- **Feature flags:** before failing a missing UI element, check that its flag is on for that white label. Some results-page features render only where their flag is set.
- **Raw translation IDs on the page:** the copy wasn't added to the Translation table. Use `/add-pr-translations`; it's a deploy gap, not a code bug.
- **Checking the screener locally:** use `npm run dev`. `npm start` serves the last build, not the current source.

Wait for the user's results. Then post one combined scripted + manual comment per ticket and move the ticket on. Move tickets one at a time as results come in; don't wait for the whole batch.

### 8. Comment format
Head the comment **Prod QA passed (date)** or **Staging QA passed (date)**, then list:
- what shipped: the PRs, plus **prod:** the release tag and deploy date, or **staging:** the merge commit and staging deploy date;
- the program import (staging: created, updated or already current; prod: run by the user);
- the state check results;
- the scenario counts and the key values, quoting the spec's figures rather than a bare section number;
- skipped scenarios and why;
- known PolicyEngine failures left open upstream, if any;
- manual steps confirmed;
- checks added from comments, each with its source, and how comment decisions were resolved;
- anything not testable in the environment, and what covers it;
- any acceptance-criteria item still open (named, not hidden).

Facts only, no screen UUIDs needed, no real household data.

## Recurring setups

- **Tax apps run locally against the environment's API.** Both CO Get Ahead apps (co-tax-credit-calculator and Baby Ben, i.e. family-affordability-tax-credit-calculator) work locally against the prod or staging API, because the API allows any origin.
  - Switch to `main` and run `npm ci`.
  - Pass env vars inline; never write a `.env`. First list every variable the app imports (`git grep -hoE 'PUBLIC_[A-Z_]+' -- src` for Baby Ben, `'VITE_[A-Z_]+'` for co-tax). Both need the frontend domain as well as the API domain and key.
  - Open the app with `?test` so screens are test screens.
- **prod, prod-only 502 from an upstream API:** run the same request on staging. If staging passes and runs the same code, suspect prod config, usually the upstream key or its billing, but rerun first to rule out a brief upstream error. Hand the user a shell snippet that calls the upstream and prints its status and error message, never the key.
- **Brief third-party errors** (e.g. Rewiring America `third_party_error`): rerun before calling it a failure.

## Finish
- Move the batch folder to `<mfb-workspace>/qa/archive/`.
- Report:
  - the tickets moved on;
  - anything left in the QA column, and why;
  - any follow-ups found. Offer to open tickets; don't create them unasked.
