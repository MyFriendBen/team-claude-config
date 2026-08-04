---
name: add-pe-program
description: Implements a new PolicyEngine-based benefit program into benefits-api from a Linear ticket or local research files — research files, program class, spec-scenario VCR tests, and PR.
usage: /add-pe-program <ticket-id>
example: /add-pe-program MFB-1234
---

<command-name>add-pe-program</command-name>

# Add PolicyEngine Program

Implements a new PolicyEngine-based benefit program in the `benefits-api` repository. Takes a Linear ticket with program research and produces: research files (spec, initial config), a PolicyEngine program class, spec-scenario VCR tests with recorded cassettes, dependency test coverage, and an open PR.

**Two rules govern this skill:**

1. **No hybrids.** A PolicyEngine calculator contains no eligibility or value logic of our own. Every calculator is either a PE calculator, a state PE calculator inheriting the federal one, or a fully custom calculator (`/add-custom-program`). If PolicyEngine can't supply the answer, this skill halts — it does not close the gap in code. See Phase 2.
2. **Tests are 1:1 with the spec.** One test per `spec.md` Test Scenario, asserting eligibility *and* value, recorded live once as a VCR cassette and replayed thereafter. See Phase 5.

## Phase 1: Gather Inputs

Ask the user how they want to provide the artifacts:

> How would you like to provide the program files?
> 1. **Linear ticket** — I'll fetch the attachments from a ticket ID
> 2. **Local files** — Point me to the two files on disk

### Option 1: Linear Ticket

1. Fetch the ticket with `mcp__linear-server__get_issue`
2. Extract:
   - **Branch name** — from the `branchName` field on the issue object
   - **PolicyEngine variable name** — from the ticket description
   - **Spec markdown** and **initial config JSON** — from ticket attachments
     - If the MCP response includes attachment URLs, fetch them. Both files must be written exactly as-is from the attachment — do not summarize, paraphrase, or reformat either of them.
     - If attachments can't be fetched automatically, ask the user to paste the file contents
3. If any piece is still missing after attempting to extract it, prompt the user before continuing

### Option 2: Local Files

Ask the user for the paths to the two files. Read each one and confirm you have both before proceeding.

### After gathering inputs

1. Derive the **state** (e.g. `tx`, `co`, `il`) and **program name** (snake_case) from the config's `white_label.code` and `program.name_abbreviated`, and the **PolicyEngine variable name** from the ticket or spec.
2. In `benefits-api/`, create or switch to the feature branch (use the ticket's `branchName` when there is one):
   ```bash
   git checkout -b {branch-name}
   # or if the branch already exists:
   git checkout {branch-name}
   ```

## Phase 2: PolicyEngine Pre-Flight and Engine Decision (Gate)

This is a **hard gate** with two questions. Answer both before writing any implementation code.

### 2.1 Does PolicyEngine expose a variable?

Run `/check-pe-support` with the PE variable name and the two-letter state code derived in Phase 1. Follow that skill's steps for running the command, interpreting the output, and deciding whether to proceed.

No matching variable → halt. There is no data source to build a PE calculator on.

### 2.2 Does PolicyEngine supply *everything* the spec describes?

Read the spec's eligibility criteria and benefit-value methodology against what the PE variable actually computes. There are exactly three outcomes:

| Outcome | What you write |
|---|---|
| **Federal PE program** | A class in `programs/programs/federal/pe/{member,spm,tax}.py` — wiring attributes only |
| **State PE program** | A subclass of the federal class in `programs/programs/{state}/pe/{member,spm,tax}.py`, adding only the state-code dependency and any state-specific inputs |
| **Neither** | Nothing here. Halt and hand off to `/add-custom-program` as a full custom calculator |

**The allowed surface of a PE calculator** — class attributes and nothing else:

- `pe_name`, `pe_category`, `pe_sub_category`
- `pe_inputs`, `pe_outputs`
- `pe_period` / `pe_output_period`, `dependencies`
- A `member_value` / `household_value` override **only** when it is a bare delegation to PolicyEngine, e.g. `return self.get_member_variable(member.id)` (the `TxWic` pattern in `programs/programs/tx/pe/member.py`, which exists to *stop* using a hardcoded federal amount)
- Returning the sentinel `1` when PolicyEngine's variable is an eligibility flag with no dollar amount (the `IlHbwd` pattern), with the displayed amount carried by the program config's `estimated_value` / `value_format`. A `$0` value would be filtered out of results by the frontend, so the sentinel is how a no-dollar program stays visible.

**Not allowed — these are the hybrids we no longer write:**

- Conditional gates inside `member_value` / `household_value`: age, insurance, relationship, county, income checks. See `TxMedicaidForParents` (`programs/programs/tx/pe/member.py`) for the shape being retired.
- Helper methods that read screen or member data to decide eligibility (e.g. `_has_child_with_medicaid`).
- Hardcoded dollar figures, category-amount dicts, or averaged value estimates in the calculator. See `IlBccp` (`programs/programs/il/pe/member.py`).
- Anything that makes our code, rather than PolicyEngine, the source of the eligibility decision or the amount.

**When the spec needs something PolicyEngine doesn't provide, halt and report.** State plainly which criterion or value PolicyEngine can't supply, then give the user the options:

1. Add a PolicyEngine **input** dependency that feeds the answer (an input is wiring, not custom logic — this is often the right fix for a gate PE *does* model but isn't being told about).
2. Ask PolicyEngine to model it, and descope this ticket until they do.
3. Implement the whole program as a custom calculator via `/add-custom-program`.
4. Descope the criterion, with the user's explicit sign-off, and note it in the spec's data gaps.

Do not write a partial override while waiting for that decision.

## Phase 3: Add Research to Codebase

Write the following two files:

**Spec** — write the markdown from the ticket attachment exactly as-is:
```
benefits-api/programs/programs/{state}/{program}/spec.md
```

**Initial config** — write the JSON from the ticket attachment exactly:
```
benefits-api/programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
```

> A pure federal passthrough with no state-level divergence has no `spec.md` and no Test Scenarios ticket comment — it is config only (the `ks_ssi` precedent). In that case write just the config file, and in Phase 5 write a single smoke test instead of a scenario suite.

After writing both files, commit. Stage the specific files (not `git add .`/`-A`) so an auto-formatter doesn't sweep unrelated changes into the commit:
```bash
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
   If this file doesn't exist yet, find a similar state's `pe/member.py` to use as a reference. `TxHeadStart` and `TxSsi` in `programs/programs/tx/pe/member.py` are the canonical shape of a state PE subclass: inherit the federal class, add the state-code dependency, add nothing else.

3. **Add the new program class**, staying inside the allowed surface from Phase 2. If while writing it you find you need a conditional, a dollar figure, or a helper that reads the screen, stop — you've hit the Phase 2 gate late. Go back and report it.

4. **Ensure test coverage for the calculator's dependencies.** Review:
   ```
   benefits-api/programs/programs/policyengine/calculators/dependencies/
   ```
   Add any missing tests for dependencies your program class relies on:
   ```
   benefits-api/programs/programs/policyengine/calculators/dependencies/tests/test_member.py
   ```
   These stay plain unit tests over the assembled payload — no `integration` marker, no cassette.

5. Commit the implementation. Stage the specific files you touched:
   ```bash
   git add benefits-api/programs/programs/{state}/pe/member.py
   git add benefits-api/programs/programs/policyengine/calculators/dependencies/tests/test_member.py
   git commit -m "Implement {State}{Program} PolicyEngine program class"
   ```

## Phase 5: Spec-Scenario VCR Tests

Write **one test per `## Test Scenarios` entry** in the program's `spec.md`, asserting eligibility *and* benefit value. The spec is the source of truth: don't invent tests outside it, and don't drop scenarios that are in it. If implementing the program revealed a scenario the spec is missing, back-fill it into `spec.md` and flag it on the ticket — an automated check watches for drift between the spec and the codified tests.

Read `benefits-api/docs/TESTING.md` ("PolicyEngine Spec-Scenario Tests") and the helper module before writing:
```
benefits-api/programs/programs/policyengine/tests/spec_scenarios.py
```

### 5.1 Write the tests

Location:
```
benefits-api/programs/programs/{state}/{program}/tests/__init__.py
benefits-api/programs/programs/{state}/{program}/tests/test_{program}.py
```

```python
import pytest
from programs.programs.{state}.pe.member import {State}{Program}
from programs.programs.policyengine.tests.spec_scenarios import (
    PeSpecScenarioTestCase, add_income, add_member, calc_pe_program, make_program, make_screen,
    screener_value,
)


@pytest.mark.integration                      # applies VCR — without it the test hits PE live every run
class Test{State}{Program}(PeSpecScenarioTestCase):
    pe_version = "1.779.3"                    # exact version these cassettes were recorded at

    def test_scenario_1_{short_scenario_name}(self):
        """Scenario 1 from spec.md: {one-line restatement}."""
        screen = make_screen(screen_id=1, white_label_code="{state}", state_code="{ST}",
                             household_size=2, zipcode="{zip}", county="{county}")
        parent = add_member(screen, member_id=1, relationship="headOfHousehold", age=34)
        add_income(parent, amount=1_496)                   # as stated by the scenario
        add_member(screen, member_id=2, relationship="child", age=3)
        program = make_program("{state}", "{name_abbreviated}", year="2025")

        eligibility = calc_pe_program(screen, {State}{Program}, program)

        self.assertTrue(eligibility.eligible)
        self.assertEqual(screener_value(eligibility), {expected value from spec.md})
```

Non-negotiables, each of which is what makes a cassette replayable:

- **Explicit primary keys** on the screen and every member. The PolicyEngine request *and response* are keyed by member id, so auto-assigned pks produce a cassette that can't be replayed. Use the helpers; don't call `HouseholdMember.objects.create` directly.
- **`pe_version` set to an exact version PolicyEngine currently serves** (`curl -s https://household.api.policyengine.org/versions/us`). PolicyEngine rejects exact versions other than what `current`/`frontier` resolve to.
- **Assert with `screener_value(...)`**, which truncates to whole dollars the way the API does. Build the household from the scenario's stated income, ages, county, and current benefits — a scenario tests nothing if its household doesn't match the spec.
- **A federal passthrough with no spec** gets one smoke test proving the state's variable resolves (a household you expect to be eligible comes back eligible with a non-zero value). Don't re-test federal math per state.

### 5.2 Record the cassettes

Run with `pytest`, **never** `venv/bin/python manage.py test` — VCR is a pytest fixture, so under the Django runner these tests silently call PolicyEngine live on every run.

```bash
# Record. Needs POLICY_ENGINE_CLIENT_ID / POLICY_ENGINE_CLIENT_SECRET in .env
VCR_MODE=once venv/bin/pytest programs/programs/{state}/{program}/tests/ -v

# Prove every scenario replays with no network
VCR_MODE=none venv/bin/pytest programs/programs/{state}/{program}/tests/ -q
```

Both commands must be green before moving on. A failed recording never writes a cassette, so if recording fails, fix the cause and re-run.

### 5.3 Reconcile the recorded values with the spec

For each scenario, compare what PolicyEngine returned against the spec:

- **Spec states an expected value and PolicyEngine agrees** → done.
- **Spec states only `Expected: Eligible` / `Not eligible` with no dollar amount** (the common case) → assert the eligibility the spec states, take the recorded value as the expected value, and **write it back into `spec.md`** for that scenario. Note the back-fill on the Linear ticket so a reviewer can sanity-check the amounts.
- **PolicyEngine contradicts the spec's stated expectation** → **halt.** Do not re-point the assertion at whatever PolicyEngine returned. Report the scenario, the spec's expectation, and PolicyEngine's answer, and let the user decide whether the spec, the wiring, or PolicyEngine is wrong. This disagreement is the whole reason the tests exist.

### 5.4 Commit tests, cassettes, and any spec edits together

```bash
git add benefits-api/programs/programs/{state}/{program}/tests/
git add benefits-api/programs/programs/{state}/{program}/spec.md   # if values were back-filled
git commit -m "Add spec-scenario tests for {State}{Program}"
```

Review the cassettes before committing — they should contain exactly one `household.api.policyengine.org/us/calculate` interaction each, with no bearer token.

> CI replays these cassettes; it does not currently *fail* on a missing one (PR runs use `VCR_MODE=new_episodes`). Committing the cassette is on you.

## Phase 6: Import and Activate

Run all commands from the `benefits-api/` directory. Use `venv/bin/python` for all `manage.py` commands — `python` may not resolve in non-interactive shells.

### 6.1 Import the initial config

Read `benefits-api/programs/management/commands/import_program_config.py` to understand the command's interface, then run it for the new config file.

- If you encounter any errors during import, fix them and commit the fixes before continuing.

### 6.2 Activate the program

The config must carry `"active": true` — omitting it imports the program inactive. Confirm the `Program` row reflects it after import.

## Phase 7: "Already Have" Screener Step (Conditional)

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

## Phase 8: Open a PR

Opening the PR is part of this workflow — always complete this phase.

1. Read the canonical PR body template at `team-claude-config/docs/PR_TEMPLATE.md` and fill it in (this is the single source of truth — do not hand-roll a different structure).
2. State in the PR body which PolicyEngine version the cassettes were recorded at, and how many spec scenarios are covered.
3. Create the PR:
   ```bash
   gh pr create \
     --title "Add {State} {Program} ({state_abbrev})" \
     --body "$(cat <<'EOF'
   {contents of PR_TEMPLATE.md, filled in}
   EOF
   )" \
     --assignee @me
   ```
4. Include a link to the Linear ticket in the PR body (under **Context & Motivation**) when the program came from a ticket.

## Phase 9: Comment QA Scenarios on Linear Ticket

1. Read `benefits-api/programs/programs/{state}/{program}/spec.md`
2. Extract the **Test Scenarios** section verbatim — everything from the `## Test Scenarios` heading to the end of the file (or the next top-level `##` heading, whichever comes first). Include any values back-filled in Phase 5.3.
3. Post it as a comment on the Linear ticket:
   ```
   mcp__linear-server__save_comment(issue_id="{ticket-id}", body="{test scenarios section}")
   ```
   The comment body must be the extracted markdown exactly as written — no reformatting, no summarizing.

Skip this phase for a config-only federal passthrough (no spec, no scenarios).

## Phase 10: Summary and Next Steps

Summarize what you did: files created, the engine decision from Phase 2, how many spec scenarios are covered by tests, the PolicyEngine version the cassettes were recorded at, any values back-filled into the spec, anything you halted on, and the PR link.

Suggest these next steps in order:
1. Review the PR and address any CodeRabbit feedback
2. Re-run the program's tests in strict replay mode (`VCR_MODE=none`) after any fix
3. Run `/api-qa-execution {ticket-id}` to QA the program end-to-end against the screener API
