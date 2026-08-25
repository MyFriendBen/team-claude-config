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

## Where things live

**Read `benefits-api/programs/framework/README.md` first.** It is the maintained source of truth for this layout; the paths below are a summary and the README wins any disagreement. Do not trust remembered paths — this tree has been restructured before.

Two layouts, chosen by whether other white labels have the same program:

| | Shared program (SNAP, CHIP, WIC, TANF, ACA, Medicaid…) | State-only program |
|---|---|---|
| Calculator | `programs/programs/cross_white_label/{family}/{state}.py` | `programs/programs/white_labels/{state}/{program}/calculator.py` |
| Spec | `cross_white_label/{family}/specs/{state}.md` | `white_labels/{state}/{program}/spec.md` |
| Tests | `cross_white_label/{family}/tests/test_{state}.py` | `white_labels/{state}/{program}/tests/` |
| Cassettes | `…/tests/cassettes/` beside the tests | `…/tests/cassettes/` beside the tests |

A family that already has a `base.py` may be inheritable; check whether the base is a real PE calculator or an abstract shell before subclassing it (`medicaid/chip/base.py` is abstract and unused — the state CHIP classes sit beside it, not under it).

Everything else:

| What | Where |
|---|---|
| PE base classes | `programs/framework/pe_base.py` — `PolicyEngineCalulator` (note the spelling) and its `…SpmCalulator` / `…TaxUnitCalulator` / `…MembersCalculator` variants |
| PE input/output dependencies | `programs/framework/pe_dependencies/` — one module per entity (`member.py`, `spm.py`, `tax.py`, `household.py`), imported as `import programs.framework.pe_dependencies as dependency` then `dependency.member.X` |
| Dependency bundles | `pe_dependencies/__init__.py` — `irs_gross_income`, `wic_income`, `tanf_income`, `receipt_contract`. Read the comments; they document what each bundle does and does not reach |
| Payload assembly | `pe_dependencies/payload.py` (`pe_input`) |
| Test helpers | `programs/programs/testing_fixtures/pe_integration.py` |
| Initial config | `programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json` |
| HTTP client | `integrations/clients/policyengine/` — `engines.py`, `versions.py` |

> `docs/TESTING.md`'s example imports the helpers from `programs.framework.tests.integration_test_helpers`, which does not exist. Import from `programs.programs.testing_fixtures.pe_integration` — that is what every real test does.

**Registration is automatic.** `programs/framework/registry.py` walks the package and reads `program_code` off each class, so writing the file registers the calculator. Every class must declare either `program_code` (the `Program.name_abbreviated` it backs) or `abstract=True`; declaring neither raises at import.

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

1. Ask whether this is a spec-backed program or a config-only federal passthrough (the `ks_ssi` precedent — see Phase 3).
   - **Spec-backed** — ask for the paths to both the `spec.md` and the initial config JSON.
   - **Config-only** — ask for the initial config JSON path alone, and ask for the **PolicyEngine variable name** directly. With no ticket and no spec there is no other source for it.

   Read each file you were given and confirm it before proceeding.
2. Ask for the **branch name** — there is no ticket to derive one from, so it has to be supplied.
3. Ask for a **Linear ticket ID**, and say it's optional. With no ticket: skip Phase 9 (nowhere to post QA scenarios), omit the ticket link from the PR body in Phase 8, and drop the `/api-qa-execution` step from Phase 10.

### After gathering inputs

1. Derive the **state** (e.g. `tx`, `co`, `il`) and **program name** (snake_case) from the config's `white_label.code` and `program.name_abbreviated`, and the **PolicyEngine variable name** from the ticket or spec.
2. In `benefits-api/`, create or switch to the feature branch (the ticket's `branchName` under Option 1, the name you collected under Option 2):
   ```bash
   git checkout -b {branch-name}
   # or if the branch already exists:
   git checkout {branch-name}
   ```

## Phase 2: PolicyEngine Pre-Flight and Engine Decision (Gate)

This is a **hard gate** with two questions. Answer both before writing any implementation code.

### 2.1 Does PolicyEngine expose a variable?

**Probe the live private API.** There is no metadata endpoint on `household.api` and no `check_pe_support` management command in this repo — `/check-pe-support` describes a command that does not exist. Ask PolicyEngine for the variable directly instead. This is a better gate anyway: one call confirms the variable exists, which **entity** owns it, and what it returns at the version we would actually ship.

Never probe `api.policyengine.org` — it ignores the `version` field, so its answers aren't comparable to ours.

```bash
curl -s https://household.api.policyengine.org/versions/us   # what current/frontier resolve to
```

Then POST a minimal household requesting the variable, using the repo's own token helper so no credential is ever read out:

```python
# venv/bin/python manage.py shell < probe.py   (prefix PE_RECORD=1 to allow the live auth call)
import requests
from integrations.clients.policyengine.engines import _fetch_pe_bearer_token

TOK = _fetch_pe_bearer_token()
ids = ["1", "2"]
household = {
    "people": {"1": {"age": {"2026": 35}, "employment_income": {"2026": 30000}},
               "2": {"age": {"2026": 7}, "employment_income": {"2026": 0}}},
    "tax_units": {"tax_unit": {"members": ids}},
    "families": {"family": {"members": ids}},
    "households": {"household": {"members": ids, "state_code": {"2026": "MO"}}},
    "spm_units": {"spm_unit": {"members": ids}},
    "marital_units": {},
}
# Ask for the variable under the entity you think owns it; add {period: None} to request it.
household["people"]["2"]["<pe_variable>"] = {"2026": None}

r = requests.post("https://household.api.policyengine.org/us/calculate",
                  json={"household": household, "version": "<exact version>"},
                  headers={"Authorization": f"Bearer {TOK}"}, timeout=60)
print(r.status_code, r.text[:400])
```

Reading the result:

| Response | Meaning |
|---|---|
| `200` with a number | Variable exists on that entity. Note the value — this is also your first real data point for the spec's scenarios |
| `500` … `"You tried to compute the variable 'X' for the entity 'people'; however the variable is defined for 'tax_units'"` | Variable exists, **wrong entity** — the message names the right one. Retry there |
| `500` … variable not found at all | No such variable at this version |
| `422 unsupported_version` | The version isn't `current` or `frontier` right now. Re-read `/versions/us` |

Entity → base class: `person` → `PolicyEngineMembersCalculator`, `spm_unit` → `PolicyEngineSpmCalulator`, `tax_unit` → `PolicyEngineTaxUnitCalulator`, `household`/`family` → `PolicyEngineCalulator`.

**Also probe the period.** A variable PolicyEngine defines per month returns its twelve months *summed* at the annual period, which silently blends a schedule that changes mid-year. Request it at both `"2026"` and a `"2026-MM"` inside the window your spec's values are stated against, and compare. If they disagree, the variable is monthly — see Phase 4's `pe_monthly_outputs`.

No matching variable → halt. There is no data source to build a PE calculator on.

### 2.2 Does PolicyEngine supply *everything* the spec describes?

Read the spec's eligibility criteria and benefit-value methodology against what the PE variable actually computes.

**Resolve any gap before picking a row.** A gap is not by itself a verdict: an input dependency may close it, PolicyEngine may agree to model it, or the user may descope it — each of those keeps the program a PE program. Work the halt-and-report step below first, and only pick a row once nothing is outstanding.

| Outcome | What you write |
|---|---|
| **Federal PE program** | A class in `programs/programs/federal/pe/{member,spm,tax}.py` — wiring attributes only |
| **State PE program** | A class in `{PROGRAM_DIR}/{state}.py` — subclassing the family's `base.py` when that base is itself a real PE calculator, otherwise standing beside its siblings. Adds only the state-code dependency and any state-specific inputs |
| **Neither** — a gap the user has decided PolicyEngine won't close | Nothing here. Halt and hand off to `/add-custom-program` as a full custom calculator |
| **Unresolved** | No row applies yet. Stay halted; don't route an input-solvable gap to `/add-custom-program` |

**The allowed surface of a PE calculator** — class attributes and nothing else:

- `program_code` (the `Program.name_abbreviated` it backs), or `abstract=True` for a base
- `pe_name`, `pe_category`, `pe_sub_category`
- `pe_inputs`, `pe_outputs`
- `pe_monthly_outputs` + `pe_period_month` for any output PolicyEngine defines per month, `dependencies`
- A `member_value` / `household_value` override **only** when it is a bare delegation to PolicyEngine, e.g. `return self.get_member_variable(member.id)` (the `TxWic` pattern in `cross_white_label/wic/tx.py`, which exists to *stop* using a hardcoded federal amount)
- Returning the sentinel `1` when PolicyEngine's variable is an eligibility flag with no dollar amount (the `IlHbwd` pattern, `cross_white_label/medicaid/disability/il_hbwd.py`), with the displayed amount carried by the program config's `estimated_value` / `value_format`. A `$0` value would be filtered out of results by the frontend, so the sentinel is how a no-dollar program stays visible.
- Arithmetic that combines PolicyEngine's *own* outputs — annualizing a monthly figure (`× 12`), summing a per-member value, subtracting one PE output from another. `Snap` annualizes; `MoChip` computes `max(1, sum(chip_gross) − mo_chip_premium × 12)`. The test is whether every term came from PolicyEngine: combining PE's numbers is wiring, introducing one of our own is a hybrid.
- Overriding `household_eligible(self, e)` to place a household-level PE figure once, when a per-member override can't express it. It runs after member eligibility, so `e.eligible_members` is populated — that's how `MoChip` charges a single household premium against a per-child gross.

**Never floor a netted value at `$0`.** `PolicyEngineCalulator.eligible()` sets `eligible = value > 0`, and the frontend drops the program again on `programValue(program) > 0` (`benefits-calculator/src/Components/Results/Filter/filterPrograms.ts`). A `$0` program is therefore reported ineligible *and* invisible — hiding it from exactly the households it applies to. Floor at `1`, and amend the spec scenario to match.

**Not allowed — these are the hybrids we no longer write:**

- Conditional gates inside `member_value` / `household_value`: age, insurance, relationship, county, income checks. See `TxMedicaidForParents` (`cross_white_label/medicaid/for_parents_and_caretakers/tx.py`) and the `has_insurance_types(("none",))` gate in `cross_white_label/medicaid/chip/tx.py` / `ks.py` / `co.py` for the shape being retired.
- Helper methods that read screen or member data to decide eligibility (e.g. `_has_child_with_medicaid`).
- Hardcoded dollar figures, category-amount dicts, or averaged value estimates in the calculator. See `IlBccp` (`white_labels/il/ibccp/calculator.py`).
- Anything that makes our code, rather than PolicyEngine, the source of the eligibility decision or the amount.

**When the spec needs something PolicyEngine doesn't provide, halt and report.** State plainly which criterion or value PolicyEngine can't supply, then give the user the options:

1. Add a PolicyEngine **input** dependency that feeds the answer (an input is wiring, not custom logic — this is often the right fix for a gate PE *does* model but isn't being told about).
2. Ask PolicyEngine to model it, and descope this ticket until they do.
3. Implement the whole program as a custom calculator via `/add-custom-program`.
4. Descope the criterion, with the user's explicit sign-off, and note it in the spec's data gaps.

Do not write a partial override while waiting for that decision.

## Phase 3: Add Research to Codebase

Paths below use `{PROGRAM_DIR}` for whichever of the two locations in **Where things live** applies — `programs/programs/cross_white_label/{family}` for a shared program, `programs/programs/white_labels/{state}/{program}` for a state-only one.

Write the following two files:

**Spec** — write the markdown from the ticket attachment exactly as-is:
```text
benefits-api/{PROGRAM_DIR}/specs/{state}.md      # shared program
benefits-api/{PROGRAM_DIR}/spec.md              # state-only program
```

**Initial config** — write the JSON from the ticket attachment exactly:
```text
benefits-api/programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
```

> A pure federal passthrough with no state-level divergence has no `spec.md` and no Test Scenarios ticket comment — it is config only (the `ks_ssi` precedent). In that case write just the config file, and in Phase 5 write a single smoke test instead of a scenario suite.

After writing the file(s), commit. Stage the specific files (not `git add .`/`-A`) so an auto-formatter doesn't sweep unrelated changes into the commit:
```bash
git add benefits-api/{PROGRAM_DIR}/specs/{state}.md
git add benefits-api/programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
git commit -m "Add {state} {program} research files"
```

For a config-only federal passthrough there is no `spec.md`, so stage the config alone — `git add` fails on a path that doesn't exist:
```bash
git add benefits-api/programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
git commit -m "Add {state} {program} config"
```

## Phase 4: Implement the Program

1. **Read the PolicyEngine variable** to understand the formula and its inputs:
   ```text
   ../policyengine-us/policyengine_us/variables/{path_to_variable}.py
   ```
   Use the variable name from the ticket to find the file (e.g. `head_start` → search for it under `variables/`).

2. **Read existing PE program classes** to understand the implementation pattern:
   ```text
   benefits-api/{PROGRAM_DIR}/{state}.py
   ```
   For a new file, read the siblings in the same family — they are the pattern. `cross_white_label/tanf/mo.py` is the canonical shape of a state PE class: declare `program_code`, extend the family base's `pe_inputs`, add the state-code dependency, and document *why* each input is sent. `cross_white_label/medicaid/chip/mo.py` shows the same with two outputs on different periods.

3. **Add the new program class**, staying inside the allowed surface from Phase 2. If while writing it you find you need a conditional, a dollar figure, or a helper that reads the screen, stop — you've hit the Phase 2 gate late. Go back and report it.

4. **Ensure test coverage for the calculator's dependencies.** Review:
   ```text
   benefits-api/programs/framework/pe_dependencies/
   ```
   Add any missing tests for dependencies your program class relies on:
   ```text
   benefits-api/programs/framework/pe_dependencies/tests/test_member.py
   ```
   These stay plain unit tests over the assembled payload — no `integration` marker, no cassette.

5. Commit the implementation. Stage the specific files you touched:
   ```bash
   git add benefits-api/{PROGRAM_DIR}/{state}.py
   git add benefits-api/programs/framework/pe_dependencies/
   git commit -m "Implement {State}{Program} PolicyEngine program class"
   ```

## Phase 5: Spec-Scenario VCR Tests

Write **one test per `## Test Scenarios` entry** in the program's `spec.md`, asserting eligibility *and* benefit value. The spec is the source of truth: don't invent tests outside it, and don't drop scenarios that are in it. If implementing the program revealed a scenario the spec is missing, back-fill it into `spec.md` and flag it on the ticket — an automated check watches for drift between the spec and the codified tests.

Read `benefits-api/docs/TESTING.md` ("PolicyEngine Spec-Scenario Tests") and the helper module before writing:
```text
benefits-api/programs/programs/testing_fixtures/pe_integration.py
```

### 5.1 Write the tests

Location:
```text
benefits-api/{PROGRAM_DIR}/tests/test_{state}.py             # wiring + value arithmetic, no cassette
benefits-api/{PROGRAM_DIR}/tests/test_{state}_scenarios.py   # one test per spec Test Scenario
benefits-api/{PROGRAM_DIR}/tests/cassettes/                  # written by the recording run
```

```python
import pytest
from programs.programs.cross_white_label.{family}.{state} import {State}{Program}
from programs.programs.testing_fixtures.pe_integration import (
    PeIntegrationTestCase, add_income, add_member, calc_pe_program, make_program, make_screen,
    screener_value,
)


@pytest.mark.integration                      # applies VCR — without it the test hits PE live every run
class Test{State}{Program}(PeIntegrationTestCase):
    pe_version = "1.815.1"                    # exact version these cassettes were recorded at

    def test_scenario_1_{short_scenario_name}(self):
        """Scenario 1 from spec.md: {one-line restatement}."""
        screen = make_screen(screen_id=1, white_label_code="{state}", state_code="{ST}",
                             household_size=2, zipcode="{zip}", county="{county}")
        parent = add_member(screen, member_id=1, relationship="headOfHousehold", age=34)
        add_income(parent, amount=1_496)                   # as stated by the scenario
        add_member(screen, member_id=2, relationship="child", age=3)
        program = make_program("{state}", "{name_abbreviated}", year="2026")

        eligibility = calc_pe_program(screen, {State}{Program}, program)

        self.assertTrue(eligibility.eligible)
        self.assertEqual(screener_value(eligibility), {expected value from spec.md})
```

Non-negotiables, each of which is what makes a cassette replayable:

- **Explicit primary keys** on the screen and every member. The PolicyEngine request *and response* are keyed by member id, so auto-assigned pks produce a cassette that can't be replayed. Use the helpers; don't call `HouseholdMember.objects.create` directly.
- **`pe_version` set to an exact version PolicyEngine currently serves** (`curl -s https://household.api.policyengine.org/versions/us`). PolicyEngine rejects exact versions other than what `current`/`frontier` resolve to.
- **Assert with `screener_value(...)`**, which truncates to whole dollars the way the API does. Build the household from the scenario's stated income, ages, county, and current benefits — a scenario tests nothing if its household doesn't match the spec.
- **Fixed integer ages, not `birth_year_month`.** A birth date makes every age a function of `timezone.now()`, and VCR matches on the exact request body — so the whole suite breaks on a calendar boundary. Derive the age once against the spec's stated evaluation date.
- **Two test files per program.** The scenario file carries the cassettes; a sibling wiring file (no `integration` marker) covers the payload shape and any value arithmetic with a stub `Sim`. Arithmetic tested there needs no cassette and keeps passing when PolicyEngine moves.
- **A federal passthrough with no spec** gets one smoke test proving the state's variable resolves (a household you expect to be eligible comes back eligible with a non-zero value). Don't re-test federal math per state.

### 5.2 Record the cassettes

Run with `pytest`, **never** `venv/bin/python manage.py test` — VCR is a pytest fixture, so under the Django runner these tests silently call PolicyEngine live on every run.

```bash
# Record. Needs POLICY_ENGINE_CLIENT_ID / POLICY_ENGINE_CLIENT_SECRET in .env
PE_RECORD=1 VCR_MODE=once venv/bin/pytest {PROGRAM_DIR}/tests/ -v

# Prove every scenario replays with no network
VCR_MODE=none venv/bin/pytest {PROGRAM_DIR}/tests/ -q
```

`PE_RECORD=1` is what permits the live auth call; without it every run seeds a placeholder token and no recording can succeed. Leave it off for the replay command, and off in normal work.

Both commands must be green before moving on. A failed recording never writes a cassette, so if recording fails, fix the cause and re-run.

**If you recorded against `frontier`, check `current` too.** A spec whose values depend on a recent PolicyEngine fix will only reproduce on the version carrying it. Unpinned production traffic rides `current`, so cassettes that pass at `frontier` prove nothing about what users will see. Re-run the key scenarios against both versions and diff them:

```bash
curl -s https://household.api.policyengine.org/versions/us   # e.g. {"current":"1.794.2","frontier":"1.815.1"}
```

Reuse the Phase 2.1 probe with each version string. If any scenario differs, say so in the PR's **Deployment** section as a required `PolicyEngineConfig.policyengine_version` pin — this is a launch blocker, not a footnote. Hand the production check to the user; don't query production yourself.

Note the standing fragility: `PolicyEngineConfig` rejects the floating aliases and `household.api` returns `422 unsupported_version` for any exact version that isn't currently `current` or `frontier`, so a pin has to move — and these cassettes have to be re-recorded — every time PolicyEngine promotes past it.

### 5.3 Reconcile the recorded values with the spec

For each scenario, compare what PolicyEngine returned against the spec:

- **Spec states an expected value and PolicyEngine agrees** → done.
- **Spec states only `Expected: Eligible` / `Not eligible` with no dollar amount** (the common case) → assert the eligibility the spec states, take the recorded value as the expected value, and **write it back into `spec.md`** for that scenario. Note the back-fill on the Linear ticket so a reviewer can sanity-check the amounts.
- **PolicyEngine contradicts the spec's stated expectation** → **halt.** Do not re-point the assertion at whatever PolicyEngine returned. Report the scenario, the spec's expectation, and PolicyEngine's answer, and let the user decide whether the spec, the wiring, or PolicyEngine is wrong. This disagreement is the whole reason the tests exist.

Before blaming PolicyEngine, check whether the failure is one of these two — both look like a PE bug and neither is:

**Cent-scale boundary scenarios can't reach PolicyEngine.** `IncomeDependency.value()` sends `int(annual income)`, so a one-cent-per-month difference — 12¢ a year — is truncated away and a "one cent above the boundary" scenario arrives *identical to the boundary case it is meant to differ from*, returning the boundary's answer. Confirm by printing what the dependency actually sends:

```python
from programs.framework.pe_dependencies.member import EmploymentIncomeDependency
print(EmploymentIncomeDependency(screen, member, {}).value())
```

If two scenarios send the same integer, that's the cause. Report it, and expect to amend those scenarios to step **$1/month** (the smallest step that survives) rather than re-pointing assertions. Don't fix the `int()` inside a program ticket — it changes the request body for every PE program and invalidates every committed cassette.

**A monthly variable read at the annual period.** It returns the twelve months summed, so a rate that changes mid-year comes back as a blend matching neither half. If a premium or benefit amount is off by roughly a half-year's difference, add it to `pe_monthly_outputs` (Phase 4) rather than adjusting the expected value.

### 5.4 Commit tests, cassettes, and any spec edits together

```bash
git add benefits-api/{PROGRAM_DIR}/tests/
git add benefits-api/{PROGRAM_DIR}/specs/{state}.md   # if values were back-filled
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

2. **Should it confer eligibility on any program we already have — even if our code doesn't reflect that yet?** Because this program is new, check #1 can only find dependencies written ahead of it — usually none. Verify with the program's spec **and an up-to-date web search of its official eligibility policy** (don't rely on training data — rules change), then compare against the programs we offer (`programs/programs/cross_white_label/`, `programs/programs/white_labels/{state}/`, and the program config). If receipt of this program *should* gate one of ours but no calculator reads it, that's a missing dependency: flag it so the existing calculator is updated to read `has_benefit("<this program>")` **and** this program gets `show_in_has_benefits_step: true` — don't silently leave it off.

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

1. Read the program's spec (`{PROGRAM_DIR}/specs/{state}.md`, or `spec.md` for a state-only program)
2. Extract the **Test Scenarios** section verbatim — everything from the `## Test Scenarios` heading to the end of the file (or the next top-level `##` heading, whichever comes first). Include any values back-filled in Phase 5.3.
3. Post it as a comment on the Linear ticket:
   ```text
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
