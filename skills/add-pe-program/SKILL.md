---
name: add-pe-program
description: Implements a new PolicyEngine-based benefit program from a Linear ticket into benefits-api — research files, program class, dependency tests, validation, and PR.
usage: /add-pe-program <ticket-id>
example: /add-pe-program MFB-1234
---

<command-name>add-pe-program</command-name>

# Add PolicyEngine Program

Implements a new PolicyEngine-based benefit program in the `benefits-api` repository. Takes a Linear ticket with program research and produces: research files (spec, initial config, test cases), a PolicyEngine program class, dependency test coverage, passing validations, and an open PR.

## Phase 1: Fetch Linear Ticket

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

## Phase 2: Add Research to Codebase

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

After writing all three files, commit:
```
git add .
git commit -m "Add {state} {program} research files"
```

## Phase 3: Implement the Program

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

5. Commit the implementation:
   ```
   git add .
   git commit -m "Implement {State}{Program} PolicyEngine program class"
   ```

## Phase 4: Test the Implementation

Run all commands from the `benefits-api/` directory.

### 4.1 Import the initial config (program stays inactive)

Read `benefits-api/programs/management/commands/import_program_config.py` to understand the command's interface, then run it for the new config file.

- If you encounter any errors during import, fix them and commit the fixes before continuing.

### 4.2 Import the validations

Read `benefits-api/validations/management/commands/import_validations.py` to understand the command's interface, then run it for the new test case file.

- If you encounter any errors during import, fix them and commit the fixes before continuing.

### 4.3 Run validations (program inactive)

Read `benefits-api/validations/management/commands/validate.py` to understand how to target a specific white label, then run validations for the program's white label.

Verify:
- The new program's validations appear as **skipped** (expected — program is inactive)
- Note any other programs that are currently failing so you have a baseline

### 4.4 Activate the program

Set `Program.active = True` for the new program. Read the `import_program_config` command to understand how activation works (Django shell, fixture, or admin).

### 4.5 Re-run validations (program active)

Run validations for the program's white label again.

Verify and fix:
- The new program's validations are **no longer skipped**
- If any of the new program's validations are **failing** → fix the implementation and commit
- If any **other** programs' validations are newly failing (compare against your Phase 4.3 baseline) → fix and commit

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

1. Read `benefits-api/.github/pull_request_template.md`
2. Create the PR:
   ```bash
   gh pr create \
     --title "Add {State} {Program} ({state_abbrev})" \
     --body "$(cat <<'EOF'
   {contents of PR template, filled in}
   EOF
   )" \
     --assignee @me
   ```
3. Include a link to the Linear ticket in the PR body

## Phase 7: Comment QA Scenarios on Linear Ticket

1. Read `benefits-api/programs/programs/{state}/{program}/spec.md`
2. Extract the **Test Scenarios** section verbatim — everything from the `## Test Scenarios` heading to the end of the file (or the next top-level `##` heading, whichever comes first)
3. Post it as a comment on the Linear ticket:
   ```
   mcp__linear-server__save_comment(issue_id="{ticket-id}", body="{test scenarios section}")
   ```
   The comment body must be the extracted markdown exactly as written — no reformatting, no summarizing.

## Phase 8: Summary and Next Steps

Summarize the changes you made (files created, test results, PR link).

Suggest these next steps in order:
1. Review the PR and address any CodeRabbit feedback
2. If fixes are needed, re-run validations to confirm they still pass
3. Run `/playwright-qa-execution {ticket-id}` locally to QA the program end-to-end
