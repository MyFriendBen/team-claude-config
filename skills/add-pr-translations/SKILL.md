---
name: add-pr-translations
description: Extract the new react-intl translation IDs introduced by a benefits-calculator PR and add them to one or more chosen environments (local / staging / prod, in any combination) via the benefits-api `add_translations` management command, which auto-translates to all supported languages. Use when a frontend PR adds new copy strings that must exist in the Translation table before a feature flag is flipped on.
---

# Add PR Translations

Adds the new `react-intl` translation labels introduced by a **benefits-calculator** PR
into the **benefits-api** `Translation` table for a chosen environment, auto-translating
English defaults into every supported language.

This is the "Deployment → Admin updates" step many CESN / energy-calculator PRs require:
new `FormattedMessage` / `intl.formatMessage` IDs must exist in the DB (or the UI falls
back to raw English defaults) before the gating feature flag is turned on.

It drives the generic backend command:
`benefits-api: python manage.py add_translations <map.json> [--dry-run] [--no-translate]`
(reads a flat `{label: english_text}` JSON map, adds English rows, batched auto-translate
to all languages, idempotent).

## Core Principles

1. **Code is the source of truth, not the PR description.** PR "Deployment" tables go stale
   (the MFB-979 table listed 14 IDs; the merged component used 36 with different names).
   ALWAYS extract IDs from the changed `.tsx`/`.ts` files on the PR branch. Use the PR table
   only as a cross-check.
2. **Environment-gated execution — the user chooses which environments, one or many.**
   The user specifies any combination (e.g. "local", "staging and prod", "all three"). Apply
   to each selected environment in a safe order: **local → staging → prod**. The gating rules
   are per-environment regardless of how many were requested:
   - **local** — Claude may run the command directly.
   - **staging / prod** — ALWAYS `--dry-run` first, show the output, get explicit
     confirmation, then run. **prod requires a typed confirmation** (see CHECKPOINT 3).
   The same temp map file is reused across every selected environment in one run.
3. **Idempotent + re-runnable.** The map is written to a temp file (not committed). If a run
   is interrupted or something was missed, re-running the skill regenerates the map from the
   code and the command safely no-ops unchanged rows.
4. **Never invent IDs or English text.** Every entry must come verbatim from the code.

## Inputs

- **PR** — a benefits-calculator PR number or URL (required).
- **Environment(s)** — any combination of `local`, `staging`, `prod` (e.g. "staging and prod",
  "all"). Ask if not given. Multiple selected envs are applied in order local → staging → prod,
  each with its own gating per the rules above.

## Repos & Commands

- Frontend: `benefits-calculator/` (where the IDs live)
- Backend: `benefits-api/` (where `add_translations` lives)
- Heroku apps (from team memory): staging = `cobenefits-api-staging`, prod = `cobenefits-api`

Command invocations by environment:
```bash
# local (from benefits-api/, venv active)
python manage.py add_translations /tmp/mfb-translations/<pr>.json --dry-run
python manage.py add_translations /tmp/mfb-translations/<pr>.json

# staging  (--no-tty is required: heroku run allocates a TTY by default, which breaks stdin piping)
heroku run --no-tty -a cobenefits-api-staging "python manage.py add_translations - --dry-run" < /tmp/mfb-translations/<pr>.json
heroku run --no-tty -a cobenefits-api-staging "python manage.py add_translations -" < /tmp/mfb-translations/<pr>.json

# prod
heroku run --no-tty -a cobenefits-api "python manage.py add_translations - --dry-run" < /tmp/mfb-translations/<pr>.json
heroku run --no-tty -a cobenefits-api "python manage.py add_translations -" < /tmp/mfb-translations/<pr>.json
```
> `-` (or omitting the arg) makes the command read the JSON map from **stdin**, which is how
> the map reaches a Heroku one-off dyno. `heroku run` allocates a TTY by default, which breaks
> stdin piping — `--no-tty` (shown above) is required for the piped form. If piping still fails
> in the user's setup, fall back to a `heroku run bash` session and write the map to a temp
> file on the dyno (heredoc), then run against that path. Never commit the map into the repo.

## Workflow Phases

### Phase 1: Resolve the PR and environment(s)

1. Confirm the PR number/URL. Determine the target environment(s); if not specified, ask:
   "Which environment(s) — local, staging, prod, or a combination?" Accept a list. Sort the
   selected envs into apply order: local → staging → prod.
2. Fetch PR metadata for context (title, branch, body):
   ```bash
   gh pr view <PR> --repo MyFriendBen/benefits-calculator --json title,headRefName,body,files
   ```
3. Note the branch name and the list of changed files (you'll grep the `.tsx`/`.ts` ones).

### Phase 2: Extract translation IDs from the code (source of truth)

1. In `benefits-calculator/`, check out the PR branch (or fetch it) so you read the merged/HEAD
   version of the changed files:
   ```bash
   git fetch origin <headRefName> && git checkout <headRefName>
   # or: gh pr checkout <PR>
   ```
   If the working tree is dirty, stash or warn the user first — do not clobber local work.
2. For each changed `.tsx`/`.ts` file, extract every translation usage. Capture the `id` and
   the colocated `defaultMessage`. Patterns to cover:
   - `<FormattedMessage id="..." defaultMessage="..." />`
   - `intl.formatMessage({ id: '...', defaultMessage: '...' })`
   - IDs/defaults stored in option arrays (e.g. `messageId` / `defaultMessage`,
     `descriptionId` / `descriptionDefault` pairs) — read the data structures, don't just regex.
   Use `grep`/`rg` to locate, then **read the surrounding code** to get exact defaults
   (multi-line template strings, ICU placeholders like `{rewiringAmerica}`, etc.).
3. Determine which IDs are **new** vs. pre-existing/shared:
   - An ID referenced but defined/used elsewhere in the codebase (e.g.
     `co.energy.rewiring_america_link`) is likely already in the DB — flag it, default to
     NOT re-adding unless the user wants to refresh it.
   - `git diff origin/main...<branch> -- <files>` helps confirm which IDs the PR introduces.
4. Build the `{label: english_text}` map. Preserve ICU placeholders and exact wording.

### Phase 3: Cross-check against the PR description (optional but recommended)

1. If the PR body has a "Deployment" / "Admin updates" translation table, diff it against the
   code-extracted map.
2. Report discrepancies explicitly:
   - IDs in code but missing from the table (table is incomplete/stale)
   - IDs in the table but not in code (renamed/removed)
   - Different English text for the same ID
3. **Trust the code.** If they disagree, the code-extracted map wins. Offer to update the PR
   description's Deployment table to match (separate, optional action).

### Phase 4: Write the temp map file + CHECKPOINT 1

1. Write the map to a temp file:
   ```
   /tmp/mfb-translations/<PR>.json
   ```
   (`mkdir -p /tmp/mfb-translations` first.)
2. **CHECKPOINT 1 — review the map.** Show:
   - Target environment(s), in apply order
   - Count of new IDs, plus any shared/pre-existing IDs being skipped
   - The full `{label: english}` map (or a clear summary if large)
   - Any Phase 3 discrepancies
   Ask: "This map will be applied to **<env list>**. Proceed? (y/n)"
   If no, stop or let the user edit the temp file.

### Phases 5–6: Per-environment dry-run + apply (loop)

Run the following for **each** selected environment in order (local → staging → prod), reusing
the same temp map file. Complete one environment before starting the next; if any env is
aborted, ask whether to continue with the remaining envs or stop.

**Dry run (mandatory for staging/prod):**
1. Run the command with `--dry-run` against this env (see invocations above).
   - For **local**, the dry-run boots Django against the local DB.
   - For **staging/prod**, dry-run runs on a one-off dyno and makes **no writes and no
     translation-API calls** — it only classifies new / changed / unchanged labels.
2. Show the dry-run output for this env: labels new / English-changed / unchanged, and target
   languages. (Dry-run results can differ per env — e.g. staging may already have some labels
   that prod doesn't.)

**Apply (branch by this env):**
- **local:** run the command (no `--dry-run`).
- **staging:** **CHECKPOINT 2** — confirm the staging dry-run looks correct, then run.
- **prod:** **CHECKPOINT 3 (typed confirmation):**
  - Restate: target = prod (`cobenefits-api`), N new labels, M English changes, languages list.
  - If the map contains any **pre-existing** labels, warn that the run will reset their
    `active` / `no_auto` flags (a plain run reactivates inactivated labels) — see Safety.
  - Require the user to type the exact phrase: `apply to prod` (anything else aborts prod;
    ask whether to continue with any remaining envs).
  - Only then run the prod command.

After each env, capture and show that env's success summary (labels added/updated, number of
translated records written across languages) before moving on.

### Phase 7: Verify & report

1. Confirm a couple of representative labels exist in the target env. Options:
   - Re-run with `--dry-run`; previously-new labels should now report as "unchanged".
   - Or a quick read via `heroku run` Django shell (read-only) for one label across langs.
2. Final report — one block per environment applied:
   ```
   Translations applied
     Map file: /tmp/mfb-translations/<PR>.json (temp, not committed)

     local:    N new, M updated, langs <list>      (or: skipped)
     staging:  N new, M updated, langs <list>      (or: skipped)
     prod:     N new, M updated, langs <list>      (or: skipped / aborted)
   Reminder: confirm the gating feature flag (e.g. cesn_heat_pump_journey) is set as intended
   in each environment you applied to.
   ```
3. If the PR table was stale, remind the user you can update the PR Deployment section to match.

## Safety

- **prod is gated behind a typed `apply to prod` confirmation.** No exceptions.
- Staging and prod always get a dry-run first; never apply blind.
- The command is idempotent for *text* — re-running after an interruption safely backfills
  English and missing-language rows, and is the intended recovery path. The temp map is
  regenerable from the code, so a lost temp file is not a problem.
- **Re-runs are NOT flag-safe.** `add_translations` rewrites `active` / `no_auto` on a
  pre-existing label to match the run's options — a plain re-run (no `--inactive` / `--no-auto`)
  sets `active=True`, silently reactivating a label someone deliberately deactivated in the
  admin. When the map might contain already-live labels, prefer scoping it to genuinely new IDs,
  and call this out at the prod checkpoint.
- Never invent labels or English text; everything comes verbatim from the PR's code.
- `co.energy.rewiring_america_link` and similar shared IDs are usually already in the DB —
  don't re-add unless explicitly asked.
- Do not commit the map file or leave the benefits-calculator repo on the PR branch without
  telling the user (offer to switch back to their original branch at the end).

## Notes on the backend command

`add_translations` (in `benefits-api/translations/management/commands/add_translations.py`):
- Reads `{label: english_text}` JSON from a file arg or **stdin** (`-` / no arg).
- `--dry-run` — classify and print only; no writes, no API calls.
- `--no-translate` — adds English rows only; re-run without the flag to backfill the other
  languages.
- `--no-auto` — sets `no_auto=True` on the labels. Note this only protects translations that
  have *already been manually edited* (`edited=True`); a freshly-created label's blank
  non-English rows are still auto-filled on the same run. Do not rely on `--no-auto` to block
  auto-translation of new labels — use `--no-translate` for that.
- `--inactive` — creates the labels as inactive (`active=False`).
- Related command: for importing a *pre-translated* full export (per-language text + flags),
  use `bulk_add_translations` instead — it takes the export shape and does not auto-translate.
- Auto-translate is **batched** (dedups identical English strings, one bulk Google Translate
  call set per unique text) — efficient for PRs introducing many strings.

## Troubleshooting

- **`heroku run` won't accept stdin** — use a `heroku run bash` session, write the JSON to a
  temp file on the dyno (heredoc into e.g. `/tmp/map.json`), and run the command against that
  path. Do NOT commit the map into the repo — translation maps are never checked in; they are
  regenerated from PR code each run.
- **Django won't boot locally** (`ModuleNotFoundError: django`) — the local `venv` isn't set
  up; have the user activate/install deps, or run the dry-run against staging instead.
- **ICU placeholder mangled by translation** (e.g. `{rewiringAmerica}` altered in a language) —
  spot-check after applying; re-run that label with a manually-corrected map, or set `--no-auto`
  and have a human translate it.
- **Extracted map looks short** — you may have missed IDs in option arrays or `formatMessage`
  calls; re-grep for `id:`/`messageId`/`descriptionId` and read the data structures, not just JSX.
