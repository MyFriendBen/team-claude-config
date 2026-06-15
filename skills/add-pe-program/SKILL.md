---
name: add-pe-program
description: Implements a new PolicyEngine-based benefit program into benefits-api from a Linear ticket or local research files — research files, program class, dependency tests, validation, and PR.
usage: /add-pe-program <ticket-id>
example: /add-pe-program MFB-1234
---

<command-name>add-pe-program</command-name>

# Add PolicyEngine Program

Implements a new PolicyEngine-based benefit program in the `benefits-api` repository. Takes a Linear ticket with program research and produces: research files (spec, initial config, test cases), a PolicyEngine program class, dependency test coverage, passing validations, and an open PR.


## Phase 1: Gather Inputs

Ask the user how they want to provide the artifacts:

> How would you like to provide the program files?
> 1. **Linear ticket** — I'll fetch the attachments from a ticket ID
> 2. **Local files** — Point me to the three files on disk

### Option 1: Linear Ticket

1. Fetch the ticket with `mcp__Linear__get_issue`
2. Extract:
   - **Branch name** — from the `branchName` field on the issue object
   - **PolicyEngine variable name** — from the ticket description
   - **Spec markdown**, **initial config JSON**, and **test cases JSON** — from ticket attachments
     - If the MCP response includes attachment URLs, fetch them. All three files must be written exactly as-is from the attachment — do not summarize, paraphrase, or reformat any of them.
     - If attachments can't be fetched automatically, ask the user to paste the file contents
3. If any piece is still missing after attempting to extract it, prompt the user before continuing
4. In `benefits-api/`, create or switch to the branch:
   ```bash
   git checkout -b {branch-name}
   # or if the branch already exists:
   git checkout {branch-name}
   ```

### Option 2: Local Files

Ask the user for the paths to the three files. Read each one and confirm you have all three before proceeding.

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

1. From Phase 1 you have the **PolicyEngine variable name** (from the ticket description or the local spec/config) and can derive the **state** (two-letter code, e.g. `co`, `ma`, `tx`). Check both the name and the state.

2. From `benefits-api/`, run the discovery command (use `venv/bin/python` — `python` may not resolve in non-interactive shells). Prefer the exact variable-name lookup:
   ```bash
   venv/bin/python manage.py check_pe_support --exact {pe_variable_name}
   ```
   If you don't yet have an exact variable name, search by program concept scoped to the state:
   ```bash
   venv/bin/python manage.py check_pe_support {program_name} --state {state_abbrev}
   ```
   This hits the free, public PolicyEngine metadata endpoint — no API key required. See `benefits-api/programs/management/commands/check_pe_support.py` for full flag documentation.

3. Interpret the result and gate on it:
   - **Variable found** — the exact lookup prints the variable's details, or the search lists a variable matching the program and state. PolicyEngine supports the program → **proceed to Phase 3.**
   - **Variable NOT found** — the exact lookup exits non-zero with "NOT in PolicyEngine", or the search returns no match for that state. **STOP. Do not proceed.** Alert the user that PolicyEngine does not appear to support this program for this state, show them the command output, and ask whether to continue anyway.
     - If the user confirms it's OK to proceed (e.g. they know the variable lives under a different name, or believe the cached metadata is stale — try `--refresh` first), **continue as normal to Phase 3.**
     - Otherwise, **halt the skill.**

## Phase 3: Add Research to Codebase

Derive the **state** and **program name** (snake_case) from the ticket title or description.

Write the following three files:

**Spec** — write the markdown from the ticket attachment exactly as-is:
```
benefits-api/programs/programs/{state}/{program}/spec.md
```

**Initial config** — write the JSON from the ticket attachment exactly:
```
benefits-api/programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
```

**Test cases** — write the JSON from the ticket attachment exactly:
```
benefits-api/validations/management/commands/import_validations/data/{state}_{program}.json
```

After writing all three files, commit. Stage the specific files (not `git add .`/`-A`) so an auto-formatter doesn't sweep unrelated changes into the commit:
```
git add benefits-api/programs/programs/{state}/{program}/spec.md
git add benefits-api/programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
git add benefits-api/validations/management/commands/import_validations/data/{state}_{program}.json
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

### 5.1 Import the initial config (program stays inactive)

Read `benefits-api/programs/management/commands/import_program_config.py` to understand the command's interface, then run it for the new config file.

- If you encounter any errors during import, fix them and commit the fixes before continuing.

### 5.2 Import the validations

Read `benefits-api/validations/management/commands/import_validations.py` to understand the command's interface, then run it for the new test case file.

- If you encounter any errors during import, fix them and commit the fixes before continuing.

### 5.3 Run validations (program inactive)

Read `benefits-api/validations/management/commands/validate.py` to understand how to target a specific white label, then run validations for the program's white label.

Verify:
- The new program's validations appear as **skipped** (expected — program is inactive)
- Note any other programs that are currently failing so you have a baseline

### 5.4 Activate the program

Set `Program.active = True` for the new program. Read the `import_program_config` command to understand how activation works (Django shell, fixture, or admin).

### 5.5 Re-run validations (program active)

Run validations for the program's white label again.

Verify and fix:
- The new program's validations are **no longer skipped**
- If any of the new program's validations are **failing** → fix the implementation and commit
- If any **other** programs' validations are newly failing (compare against your Phase 5.3 baseline) → fix and commit

## Phase 6: "Already Have" Checkbox (Conditional)

> Only complete this phase if the program belongs on the "I already have this benefit" screener step. The rule: if participation in this program explicitly informs eligibility for *another* program — through presumptive eligibility or disqualification — it belongs on the step. Otherwise it doesn't.

Ask the user: "Does participation in this program inform eligibility for another program, through presumptive eligibility or disqualification? If yes, it belongs on the 'already have' step; if not, it doesn't."

If yes, proceed. If no, skip to Phase 7.

### How this works now (post MFB-862 / MFB-720)

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
2. If fixes are needed, re-run validations to confirm they still pass
3. Run `/playwright-qa-execution {ticket-id}` locally to QA the program end-to-end