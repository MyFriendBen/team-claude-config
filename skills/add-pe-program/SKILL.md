---
name: add-pe-program
description: Implements a new PolicyEngine-based benefit program into benefits-api from a Linear ticket or local research files — research files, program class, dependency tests, spec-scenario verification against PolicyEngine, and PR.
usage: /add-pe-program <ticket-id>
example: /add-pe-program MFB-1234
---

<command-name>add-pe-program</command-name>

# Add PolicyEngine Program

Implements a new PolicyEngine-based benefit program in the `benefits-api` repository. Takes a Linear ticket with program research and produces: research files (spec, initial config), a PolicyEngine program class, dependency test coverage, the spec.md test scenarios verified against PolicyEngine, and an open PR.

The research artifacts are two files — the spec.md and the initial config JSON. The spec.md **Test Scenarios** are the single source of truth for correctness; for a PE program they are verified by running each scenario's household through PolicyEngine and confirming it matches the spec. There is no separate validation `.json` artifact or importable validation suite. (Config-only federal programs have no spec and therefore no scenarios to run.)


## Phase 1: Gather Inputs

Ask the user how they want to provide the artifacts:

> How would you like to provide the program files?
> 1. **Linear ticket** — I'll fetch the attachments from a ticket ID
> 2. **Local files** — Point me to the two files on disk

### Option 1: Linear Ticket

1. Fetch the ticket with `mcp__Linear__get_issue`
2. Extract:
   - **Branch name** — from the `branchName` field on the issue object
   - **PolicyEngine variable name** — from the ticket description
   - **Spec markdown** and **initial config JSON** — from ticket attachments
     - If the MCP response includes attachment URLs, fetch them. Both files must be written exactly as-is from the attachment — do not summarize, paraphrase, or reformat either of them.
     - If attachments can't be fetched automatically, ask the user to paste the file contents
3. If any piece is still missing after attempting to extract it, prompt the user before continuing
4. In `benefits-api/`, create or switch to the branch:
   ```bash
   git checkout -b {branch-name}
   # or if the branch already exists:
   git checkout {branch-name}
   ```

### Option 2: Local Files

Ask the user for the paths to the two files. Read each one and confirm you have both before proceeding.

### After gathering inputs

1. Derive the **state** (e.g. `tx`, `co`, `il`) and **PolicyEngine variable name** in snake_case (e.g. `hse`, `ccad`) from the config's `white_label.code` and `program.name_abbreviated`.
2. In `benefits-api/`, create or switch to a feature branch:
   ```bash
   git checkout -b {username}/mfb-{ticket}-implement-{program_name}
   # or if the branch already exists:
   git checkout {branch-name}
   ```

## Phase 2: PolicyEngine Pre-Flight Check (Gate)

Before doing any implementation work, confirm that PolicyEngine actually exposes a variable for this program. This is a **hard gate**: if PE has no matching variable, there is no data source to build a calculator on, and the rest of the skill cannot succeed.

Run `/check-pe-support` with the PE variable name (from the ticket description or the local spec/config) and state (two-letter code, e.g. `co`, `ma`, `tx`) derived in Phase 1.

Follow all steps in that skill — it covers how to run the command, interpret the output, and decide whether to proceed or halt.

## Phase 3: Add Research to Codebase

Derive the **state** and **program name** (snake_case) from the ticket title or description.

Write the following two files:

**Spec** — write the markdown from the ticket attachment exactly as-is:
```
benefits-api/programs/programs/{state}/{program}/spec.md
```

**Initial config** — write the JSON from the ticket attachment exactly:
```
benefits-api/programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
```

After writing both files, commit. Stage the specific files (not `git add .`/`-A`) so an auto-formatter doesn't sweep unrelated changes into the commit:
```
git add benefits-api/programs/programs/{state}/{program}/spec.md
git add benefits-api/programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
git commit -m "Add {state} {program} research files"
```

## Phase 4: Implement the Program

1. **Read the PolicyEngine variable** to understand the formula and its inputs:
   ```
   ../policyengine-us/policyengine_us/variables/{path_to_variable}.py
   ```
   Use the variable name from the ticket to find the file (e.g. `head_start` → search for it under `variables/`).

2. **Read existing PE program classes** to understand the implementation pattern:
   ```
   benefits-api/programs/programs/{state}/pe/member.py
   ```
   If this file doesn't exist yet, find a similar state's `pe/member.py` to use as a reference.

3. **Add the new program class** to `benefits-api/programs/programs/{state}/pe/member.py` following the observed pattern (e.g. `TxHeadStart`).

4. **Ensure test coverage for the calculator's dependencies.** Review:
   ```
   benefits-api/programs/programs/policyengine/calculators/dependencies/
   ```
   Add any missing tests for dependencies your program class relies on:
   ```
   benefits-api/programs/programs/policyengine/calculators/dependencies/tests/test_member.py
   ```

5. Commit the implementation. Stage the specific files you touched (not `git add .`/`-A`) so an auto-formatter doesn't sweep unrelated changes into the commit:
   ```
   git add benefits-api/programs/programs/{state}/pe/member.py
   git add benefits-api/programs/programs/policyengine/calculators/dependencies/tests/test_member.py
   git commit -m "Implement {State}{Program} PolicyEngine program class"
   ```

## Phase 5: Test the Implementation

Run all commands from the `benefits-api/` directory. Use `venv/bin/python` for all `manage.py` commands — `python` may not resolve in non-interactive shells.

Correctness is verified by running the spec.md test scenarios against PolicyEngine and confirming they match — there is no separate validation suite to import or run.

### 5.1 Import the initial config (program stays inactive)

Read `benefits-api/programs/management/commands/import_program_config.py` to understand the command's interface, then run it for the new config file.

- If you encounter any errors during import, fix them and commit the fixes before continuing.

### 5.2 Run the spec scenarios against PolicyEngine

The spec.md **Test Scenarios** are the source of truth. Because a PE program resolves to `fraction × <PE variable>`, each scenario's household can be run directly through PolicyEngine (live API or a pinned local install) and compared to the spec's stated expected eligibility and value — you do not need our own validation suite to confirm correctness.

- Build each spec scenario's household, run the relevant PE variable(s), and record PE's output next to the spec's expected outcome.
- **Flag every mismatch** — both value drift and eligibility flips — and resolve it (fix the implementation/config, or escalate a genuine PE bug as an `mfb-policy-engine` fix request).
- Run **all** spec scenarios, not a selected subset.

> Config-only federal programs have no spec.md, and therefore no scenarios to run — skip this step for them.

### 5.3 Activate the program

Set `Program.active = True` for the new program. Read the `import_program_config` command to understand how activation works (Django shell, fixture, or admin).

After activating, re-confirm the spec scenarios still match PolicyEngine, and fix any regressions before continuing.

## Phase 6: "Already Have" Checkbox (Conditional)

> Only complete this phase if the program belongs on the "I already have this benefit" screener step. The rule: if participation in this program explicitly informs eligibility for *another* program — through presumptive eligibility or disqualification — it belongs on the step. Otherwise it doesn't.

Ask the user: "Does participation in this program inform eligibility for another program, through presumptive eligibility or disqualification? If yes, it belongs on the 'already have' step; if not, it doesn't."

If yes, proceed. If no, skip to Phase 7.

### How this works now

The current-benefits step is driven entirely by two fields on the `Program` model — there is **no longer** a `category_benefits` config, a per-program `has_{name}` column, a serializer `has_*` field, or any frontend wiring to add:

- The screener step fetches `GET /api/screener-options/<wl>/has-benefits-programs/`, which returns every program with `show_in_has_benefits_step=True` **and** `active=True` for that white label (`screener/views.py`).
- The serializer reads/writes the selection as `current_benefits: [name_abbreviated, ...]` (`screener/serializers.py`); the frontend stores it as a `Set<string>` of `name_abbreviated` values and renders the tile list straight from the API. No `has_*` fields are involved anywhere.

> The old `category_benefits` blocks still physically sit in `configuration/white_labels/*.py`, but they are orphaned legacy config — nothing reads them. Do **not** add the program there.

### 6.1 Set `show_in_has_benefits_step` on the Program

Set `show_in_has_benefits_step=True` on the program (and confirm `active=True`). The program's `name_abbreviated` is the key the screener uses — no migration, serializer, or frontend change is required.

Do this in the program's initial config / fixture if it's defined there, otherwise via the Program record. Verify it surfaces:
```bash
venv/bin/python manage.py shell -c "from programs.models import Program; print(Program.objects.filter(show_in_has_benefits_step=True, active=True, white_label__code='{state_code}').values_list('name_abbreviated', flat=True))"
```

### 6.2 Commit

Stage the specific files you touched (not `git add .`/`-A`):
```
git commit -m "Show {program} in 'already have' screener step (show_in_has_benefits_step)"
```

## Phase 7: Open a PR


## Phase 5: "Already Have" Screener Step (Conditional)

Decide whether this program should appear as a tile on the "I already have this benefit" screener step. This is driven entirely by the `Program` row's `show_in_has_benefits_step` flag, set from the program's `initial_config.json` at import time — there is **no** white-label `category_benefits` edit, **no** `has_*` column/serializer/frontend work. (Current benefits live in the `CurrentBenefit` join table, read via `screen.has_benefit(...)` / `screen.has_base_benefit(...)`.)

**The criterion is functional, not size-based.** A program belongs on this step only if knowing a household already receives it changes the eligibility result of *another* program — i.e. it confers categorical/presumed eligibility (or is a disqualifier) elsewhere. It does **not** have to be a "major" program; a large program nothing else keys off of doesn't belong here. Don't guess from prominence — verify:

1. **Does our code base already key off this benefit?** Grep the calculators for the program's `name_abbreviated` and its `base_program`:
   ```bash
   grep -rnE "has_benefit(_from_list)?\(|has_base_benefit\(|presumptive_eligibility|categorically_eligible" programs/programs/ \
     | grep -vE "/tests/|test_" \
     | grep -iE "<name_abbreviated>|<base_program>"
   ```
   A hit means another calculator reads this benefit's state → it needs `show_in_has_benefits_step: true`. **But no hit is not proof it's unneeded** — the program is new, so nothing could have referenced it yet. Always also do check #2.

2. **Should it confer eligibility on any program we already have — even if our code doesn't reflect that yet?** Because this program is new, check #1 can only find dependencies written ahead of it — usually none. Verify with the program's spec **and an up-to-date web search of its official eligibility policy** (don't rely on training data — rules change), then compare against the programs we offer (`programs/programs/{state}/` and the program config). If receipt of this program *should* gate one of ours but no calculator reads it, that's a missing dependency: flag it so the existing calculator is updated to read `has_benefit("<this program>")` **and** this program gets `show_in_has_benefits_step: true` — don't silently leave it off.

Then:

- If either check says yes, set `"show_in_has_benefits_step": true` (and `"active": true`) in the program's `initial_config.json` and re-run the program config import so the `Program` row reflects it. The tile's display name, description, and category grouping come from the program's own `name`, `website_description`, and `category` fields.
- Otherwise (the common case), leave `show_in_has_benefits_step: false` and move on.

## Phase 6: Open a PR

  Opening the PR is part of this workflow — always complete this phase.


1. Read the canonical PR body template at `team-claude-config/docs/PR_TEMPLATE.md` and fill it in (this is the single source of truth — do not hand-roll a different structure).
2. Create the PR:
   ```bash
   gh pr create \
     --title "Add {State} {Program} ({state_abbrev})" \
     --body "$(cat <<'EOF'
   {contents of PR_TEMPLATE.md, filled in}
   EOF
   )" \
     --assignee @me
   ```
3. Include a link to the Linear ticket in the PR body (under **Context & Motivation**) when the program came from a ticket.

## Phase 8: Comment QA Scenarios on Linear Ticket


1. Read `benefits-api/programs/programs/{state}/{program}/spec.md`
2. Extract the **Test Scenarios** section verbatim — everything from the `## Test Scenarios` heading to the end of the file (or the next top-level `##` heading, whichever comes first)
3. Post it as a comment on the Linear ticket:
   ```
   mcp__linear-server__save_comment(issue_id="{ticket-id}", body="{test scenarios section}")
   ```
   The comment body must be the extracted markdown exactly as written — no reformatting, no summarizing.

## Phase 9: Summary and Next Steps


Summarize the changes you made (files created, test results, PR link).

Suggest these next steps in order:
1. Review the PR and address any CodeRabbit feedback
2. If fixes are needed, re-run the spec scenarios against PolicyEngine to confirm they still match
3. Run `/playwright-qa-execution {ticket-id}` locally to QA the program end-to-end