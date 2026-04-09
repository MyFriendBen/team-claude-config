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
   - **Initial config JSON** and **test cases JSON** — from ticket attachments
     - If the MCP response includes attachment URLs, fetch them
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

**Spec** — summarize eligibility criteria, benefit value, and sources from the ticket:
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

## Phase 5: Open a PR

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

## Phase 6: Summary and Next Steps

Summarize the changes you made (files created, test results, PR link).

Suggest these next steps in order:
1. Review the PR and address any CodeRabbit feedback
2. If fixes are needed, re-run validations to confirm they still pass
3. Run `/playwright-qa-execution {ticket-id}` locally to QA the program end-to-end
