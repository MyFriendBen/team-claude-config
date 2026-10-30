---
name: api-qa-execution
description: Execute a program's spec test scenarios against the benefits screener API (local or staging; production is handed over as a script). Reads the spec from program-ops, translates each scenario into a Screen API payload, and compares eligibility and value with the spec. Use when the user wants to QA a program via API, run screener test scenarios without a browser, or validate eligibility results programmatically.
---

# API-Based QA Testing Skill

<!-- Editing note: never put a dollar sign directly before a digit in this file. When the skill loads, a dollar sign followed by a number is replaced by that argument (the first argument for zero, the second for one, and so on), so an amount like one thousand dollars written with the sign loads as "staging,000". Write amounts as plain numbers or "N dollars". -->

Tests a program's eligibility logic by sending API calls instead of driving a browser. Reads the program's spec from **program-ops**, turns each test scenario into a Screen API payload, POSTs it, fetches eligibility, and compares the result with the spec's expected outcome and value.

Use it for eligibility and value. What the results page shows (copy, warnings, navigators, display rounding) needs a manual browser check.

---

## Overview

1. Finds the program's `*_spec.md` in program-ops (any environment) from the Linear ticket's program.
2. Extracts the program key, white label, benefit value format and test scenarios.
3. Classifies each scenario as API-testable or frontend-only.
4. For each API-testable scenario, POSTs `/api/screens/`, then GETs `/api/eligibility/{uuid}`.
5. Compares the actual eligibility and value with the spec.
6. Writes results to the local `qa/` directory, including the frontend-only scenarios that need a browser check.

**Production is never called from here.** `production` writes the script and expected results for David to run (see Environment Configuration).

---

## Prerequisites

- [ ] Linear MCP server is enabled for ticket fetching
- [ ] The program's spec is in program-ops (on `main`, or a named branch or open PR)
- [ ] Target environment API is accessible, with an API key (see Environment Configuration)
- [ ] The program is imported and active in the target environment
- [ ] **Local only:** benefits-api is on the branch under test, the program is imported from program-ops (`echo y | python3 scripts/import_programs.py --env local --program {key}`) and switched on, and the server is running: `venv/bin/python manage.py runserver 8000` in the background. `curl -s -o /dev/null -w "%{http_code}" localhost:8000/api/screens/` returns 403 once it's up. Stop it after the run.

If Linear MCP is not available, STOP and notify the user.

---

## Required Arguments

1. **Linear Ticket ID** (required): The ticket containing test scenarios (e.g., `MFB-1234`)
2. **Environment** (optional): `staging` (default), `production`, or `local`
3. **Output Directory** (optional): Directory for results, defaults to `qa/`

**Example invocations:**
```
/api-qa-execution MFB-1234
/api-qa-execution MFB-1234 staging
/api-qa-execution MFB-1234 production    # writes the script; David runs it
/api-qa-execution MFB-1234 local qa-results
```

---

## Environment Configuration

| Environment | API Base URL | API Key |
|---|---|---|
| **staging** (default) | `https://cobenefits-api-staging.herokuapp.com` | `STAGING_API_KEY` from the workspace `.env` (`~/main/.env`) |
| **local** | `http://localhost:8000` | The DRF auth token in the local database (below) |
| **production** | Handed over, never called | David supplies it when he runs the script |

**⚠️ The frontend and backend are separate Heroku apps.** `benefits-calculator-staging.herokuapp.com` is the React SPA, and every path there returns `index.html`. The API is `cobenefits-api-staging.herokuapp.com`.

**API keys: read them in-process and never echo, log or write them.**
- **Staging:** parse `STAGING_API_KEY` from `~/main/.env` inside the script, or export it from that file in the same shell command that runs the script. There's no skill-local `.env`. Never edit any `.env` file.
- **Local:** `REACT_APP_API_KEY` from `benefits-calculator/.env` returns 403 locally. Pull a token from the local database into an environment variable without printing it:
  ```bash
  export LOCAL_API_KEY=$(venv/bin/python manage.py shell -c "from rest_framework.authtoken.models import Token; t = Token.objects.order_by('created').first(); print(t.key if t else '')" 2>/dev/null | tail -1)
  [ -n "$LOCAL_API_KEY" ] && echo "key loaded"
  ```
- If no key resolves, ask the user.

**Production: hand over, never run.** Don't send any request to production (`cobenefits-api`), read-only or not. For `production`:
1. Write the script (Phase 3) with the expected results in it, reading the key from `PRODUCTION_API_KEY` and asking him to type `prod` before it sends anything.
2. Hand David the script and the command to run it. He runs it and shares the report.

---

## Workflow

### Phase 1: Fetch and Parse Spec

1. **Parse arguments** — ticket ID (required), environment (default: staging), output dir (default: qa)

2. **Determine API base URL and resolve API key** from environment config above.

3. **Fetch the Linear ticket** (`get_issue`) and identify the program: its key (e.g. `federal_wic`, `co_nf`) from the title, description or linked program-ops PR.

4. **Find the spec in program-ops.** It's the source of truth in every environment; don't use a Linear attachment or a copy in benefits-api.
   ```bash
   git -C ~/main/program-ops fetch -q origin
   git -C ~/main/program-ops grep -l "Program Key\*\*: \`{key}\`" origin/main -- 'programs/**/*_spec.md'
   ```
   - Specs sit beside their program record: `programs/white_labels/{wl}/{program}/` or `programs/cross_white_label/{family}/{state|base}/`.
   - **Search by the Program Key line, not the file name.** File names don't always match the key: `head_start_nj_spec.md` has the key `nj_head_start`.
   - If the latest spec is in an open program-ops PR (e.g. one changing the scenarios), read it from that branch with `git show origin/{branch}:{path}`, and say which version you used.
   - Copy it to `/tmp/{ticket-id}/spec.md` and read it whole.
   - **Fallback, older programs only:** a program not yet migrated to program-ops may only have a spec in benefits-api (`programs/programs/white_labels/{wl}/{program}/spec.md` or `cross_white_label/{family}/specs/{wl}.md`). Use it only if program-ops has none, and say so in the results.

5. **Parse the spec.**
   - **`## 1. Header`:** `Program Key` (the `name_abbreviated` to match in results) and `White Label`. Lowercase the white label for the API (`NJ` → `nj`). **A federal spec (`White Label: federal`) runs on the `federal` white label;** see Federal programs in Phase 2.
   - **`## 7. Benefit Value`:** `value_format` (`monthly`, `estimated_annual`, …) and `Payment unit` (`household` or `member`).
   - **`## 8. Test Scenarios`:** each `### Scenario N: {title}` block holds:
     - `**Checking**:` what it tests;
     - `**Expected**:` the outcome and value, e.g. `Eligible — 129.78/month (64.89 × 2 eligible members)`, `Eligible — 9,938.20/year estimated`, or `Ineligible — \`income_limit\` fails`. (Specs put a dollar sign before each amount; it's left out of the examples here, see the note at the top.)
     - `**Steps**:` bullets:
       - `Location: ZIP \`80301\`, county \`Boulder County\``
       - `Person N: age 28, head of household, pregnant, wages 20,000/year, on Medicaid`
       - `Person N: age 64 on December 31, 2025, …`: an age at the end of a benefit or tax year. Set `birth_year` to that year minus the age (2025 − 64 = 1961) and `birth_month` to 1. Calculators judging age at year end read `age_at_end_of_year(year)`, which uses the birth year only, so deriving the birth year from today's age tests the wrong boundary. With a January birth month the person is a year older today, which also checks the calculator ignores today's age.
       - `Household assets: 1,000`
       - `Expenses: property tax 9,000/year, rent 1,500/month, mortgage 2,000/month`: one `expenses` entry each (type, amount, frequency); see the Expenses mapping in Phase 2.
       - `Current benefits: SNAP`

   **Expected value, as an annual figure** (the API returns `estimated_value` in annual whole dollars):
   - `$X/month` → `X × 12`; `$X/year` → `X`. Strip `$` and commas.
   - A calculator may round each payment unit's annual value, and the API then truncates the total to whole dollars, so allow **1 dollar either way per counted unit** (`× 2 eligible members` → 2 dollars). Report both figures. (64.89 × 12 = 778.68 shows as 779 per member, so the spec's 129.78/month is 1,557.36 a year and the API returns 1,558.)
   - `Ineligible`, `Not eligible` or no dollar figure → no value comparison.

6. **Classify each scenario as API-testable or frontend-only.**

   Some spec scenarios describe conditions that can only be verified in the browser. After parsing all scenarios, check each one against the frontend-only detection rules below and mark it accordingly.

   #### Frontend-Only Detection Rules

   A scenario is **frontend-only** (skip from API execution) if ANY of these conditions are true:

   **a. Expected outcome references display behavior:**
   The `**Expected:**` line (or surrounding description) contains phrases indicating the test is about what the UI shows, not what the API calculates:
   - "warning message", "action item", "info message", "information message"
   - "displayed", "should display", "should show", "should appear", "visible", "hidden"
   - "category", "grouped under", "appears under", "section"
   - "learn more link", "apply button", "apply link", "button text"
   - "navigator", "resource referral", "referral displayed"
   - "document required", "documentation", "required documents"
   - "translation", "in Spanish", "in English", "language display"
   - "estimated value override" (the text override, not the numeric value)
   - "description", "program card", "card text", "program description should"

   **b. Expected outcome cannot be parsed as eligibility + optional value:**
   If the `**Expected:**` line does not contain "Eligible" or "Not eligible" (case-insensitive, including variants like "Ineligible") AND does not match a recognizable eligibility pattern, it is likely a frontend-specific check. Examples:
   - "Expected: Warning about citizenship requirement is shown"
   - "Expected: Program appears in Healthcare category"
   - "Expected: Apply link opens in new tab"

   **c. Scenario explicitly states it requires browser/frontend testing:**
   The scenario description or "What this checks" line mentions:
   - "frontend", "browser", "UI", "visual", "rendering"
   - "form field", "wizard step", "form validation"
   - "conditional display", "field visibility"

   **d. Scenario tests data the API payload cannot express:**
   The scenario steps reference input fields that don't exist in the Screen/HouseholdMember API:
   - Specific screener question visibility ("When user selects X, field Y appears")
   - Form validation behavior ("Entering negative income shows error")
   - Navigation flow ("User returns to step 2 and changes answer")

   #### What is NOT frontend-only

   These are common spec patterns that ARE testable via API — do not skip them:
   - `Citizenship: U.S. Citizen` in steps — The API ignores citizenship (it's config-level via `legal_status_required`). The eligibility result is still correct without it.
   - `already_has` / display suppression scenarios — The API returns `already_has: true`, which the skill already handles.
   - Scenarios mentioning "should not be shown" when referring to eligibility suppression — This means "Not eligible" via the `already_has` flag, which is API-testable.
   - Expected lines with just "Eligible" or "Not eligible" plus optional value — These are standard API scenarios.
   - `housing_situation` mentioned in spec context but not in scenario steps — Only skip if the scenario steps require setting `housing_situation` AND the expected outcome depends on it.

7. **Present summary to user:**
   ```
   Linear Ticket: MFB-1234
   Program: Head Start (nj_head_start)
   Spec: program-ops programs/cross_white_label/head_start/nj/head_start_nj_spec.md (main)
   White Label: nj
   Environment: STAGING
   API Base: https://cobenefits-api-staging.herokuapp.com
   Test Scenarios: 11 (9 API-testable, 2 frontend-only)

   Frontend-only scenarios (will be skipped):
   - Scenario 5: "Warning message about citizenship" — tests display behavior
   - Scenario 9: "Program card category placement" — tests UI rendering

   Ready to execute? (y/n)
   ```

   If there are frontend-only scenarios, list them with the reason they were classified as frontend-only. The user can override if they believe a scenario was misclassified.

   Skip the `Ready to execute?` question when the request already asks for the run (for example "run it on staging and update the ticket"). Show the summary and go on.

8. **Create output directory and initialize results file.**

---

### Phase 2: Build API Payloads

For each **API-testable** scenario (skip frontend-only scenarios), construct a Screen API payload. The payload is a Screen create request: `benefits-api/screener/serializers.py::ScreenSerializer` defines the valid fields.

#### Payload Template

```json
{
  "white_label": "{spec Header → White Label}",
  "is_test": true,
  "agree_to_tos": true,
  "is_13_or_older": true,
  "zipcode": "{Steps → Location ZIP; omit on federal}",
  "county": "{Steps → Location county; omit on federal}",
  "household_size": "{number of Person lines, unless Steps says otherwise}",
  "household_assets": 0,
  "request_language_code": "en",
  "start_date": "{current ISO 8601 timestamp}",
  "referral_source": "test",
  "household_members": [
    {
      "relationship": "{mapped from scenario}",
      "birth_year": "{calculated from scenario age}",
      "birth_month": "{from scenario or default 1}",
      "age": "{from scenario}",
      "has_income": "{from scenario}",
      "income_streams": [],
      "insurance": {
        "none": true,
        "employer": false,
        "private": false,
        "medicaid": false,
        "medicare": false,
        "chp": false,
        "va": false,
        "mass_health": false,
        "emergency_medicaid": false,
        "family_planning": false,
        "dont_know": false
      }
    }
  ],
  "expenses": [],
  "current_benefits": ["{program name_abbreviated for each benefit the scenario household currently receives, e.g. \"snap\", \"tanf\"}"]
}
```

#### Federal programs

A federal program's scenarios run as test screens on the `federal` white label, with no location:

- **`"white_label": "federal"` and `"is_test": true`.** The API accepts `federal` only for test screens; without `is_test` it returns `400` ("'federal' only takes test screens").
- **Omit `zipcode` and `county`.** Leave the keys out, even when the scenario names a location: `federal` has no ZIP map.
- **The response lists federal programs only,** so other programs can't crowd the result.
- **`current_benefits` resolves against federal programs only,** and a state program's name is silently dropped. A scenario whose current benefit exists only as a state program (SNAP, TANF) runs on a state white label where the federal program is also visible. Use that state's names (`co_snap`, `co_tanf`) and a ZIP and county, and note the white label in the results.
- **A federal program that needs a location** drops out with `missing_programs: true`. Report it as an ERROR naming the dependency; don't add a location to work around it.
- **The program must be imported and active.** An inactive program comes back "Not found" with `missing_programs: false`.
- **For a federal program replacing state rows,** QA after the switch-over migration has run (state rows off, federal row on). Add three checks:
  - a state white-label screen shows the program **once**, under its federal key, with no state row;
  - a household holding the federal key in `current_benefits` comes back `already_has: true`;
  - a `co_tax_calculator` screen (the Get Ahead apps send no `pregnant`, no birth dates and few other fields) still calculates the program, if the program applies there. Send each member's `age` with no `birth_year` or `birth_month`, and `pregnant: null`; with birth dates or `pregnant: false` the check proves nothing.

**Current benefits:** a list of `name_abbreviated` values for the white label the screen uses; `[]` when the household has none.

#### Field Mapping from Spec Scenarios

**Relationship mapping** (spec text → API value). The API doesn't validate `relationship`: a value not in this table saves without error, but the member then never counts as a dependent (`DEPENDENT_ELIGIBLE_RELATIONSHIPS` in `screener/models.py`), which can change a result without any warning. The source of truth is `relationship_options` in benefits-api `configuration/white_labels/base.py`, plus `headOfHousehold` for person 1.
| Spec Text | API Value |
|---|---|
| Head of Household | `headOfHousehold` |
| Spouse | `spouse` |
| Domestic Partner | `domesticPartner` |
| Boyfriend / Girlfriend | `boyfriendOrGirlfriend` |
| Child | `child` |
| Step-child | `stepChild` |
| Foster Child / Kinship Care | `fosterChild` |
| Grandchild | `grandChild` |
| Parent | `parent` |
| Step-parent | `stepParent` |
| Foster Parent | `fosterParent` |
| Grandparent | `grandParent` |
| Sibling / Sister / Brother | `sisterOrBrother` |
| Step-sibling | `stepSisterOrBrother` |
| Other relative (aunt, uncle, cousin, in-law) | `relatedOther` |
| Roommate / unrelated | `roommate` |

**Income type mapping** (spec text → API enum):
| Spec Text | API Value |
|---|---|
| Wages, Salaries, Tips / Wages/Salaries | `wages` |
| Self-Employment | `selfEmployment` |
| Social Security Disability / SSD / SSDI | `sSDisability` |
| Social Security Retirement / SS Retirement | `sSRetirement` |
| SSI / Supplemental Security Income | `sSI` |
| SS Survivor | `sSSurvivor` |
| SS Dependent | `sSDependent` |
| Unemployment | `unemployment` |
| Cash Assistance / TANF | `cashAssistance` |
| Child Support | `childSupport` |
| Alimony | `alimony` |
| Pension | `pension` |
| Investment | `investment` |
| Rental Income | `rental` |
| Veterans Benefits | `veteran` |
| Workers Compensation | `workersComp` |
| Other | `other` |

**Income frequency mapping** (spec text → API enum):
| Spec Text | API Value |
|---|---|
| per month / monthly / every month | `monthly` |
| per year / yearly / annually | `yearly` |
| per week / weekly / every week | `weekly` |
| biweekly / every two weeks | `biweekly` |
| hourly | `hourly`, plus `hours_worked` (per week) on the stream; without it the API treats the income as malformed and drops programs |

**Insurance mapping** (spec text → insurance object field):
| Spec Text | Field to set `true` |
|---|---|
| None / No insurance | `none` |
| Employer | `employer` |
| Private | `private` |
| Medicaid | `medicaid` |
| Medicare | `medicare` |
| CHP+ / CHIP | `chp` |
| VA | `va` |
| MassHealth (MA) | `mass_health` |
| Emergency Medicaid | `emergency_medicaid` |
| Family planning coverage | `family_planning` |
| Don't know | `dont_know` |

Set `none` to `false` whenever another type is `true`.

**Current benefits mapping** (spec text → `current_benefits` list entry):

Each current benefit the household receives is an entry in the `current_benefits` array, identified by the program's `name_abbreviated`. **Use the exact `name_abbreviated` that white label uses** — for a given benefit it may be the bare name (e.g. `snap`) or state-prefixed (e.g. `{state}_snap`, like `tx_snap`), and some are neither (e.g. `wa_apple_health_medicaid` for Medicaid in WA). The form varies per white label and isn't predictable from the benefit type, so **don't assume — look it up** (see the note below). The table below lists the bare/canonical name as a starting point only; the real value is whatever that white label's `Program` row has.

| Spec Text | Canonical `name_abbreviated` (may be `{state}_`-prefixed per white label) |
|---|---|
| SNAP | `snap` |
| TANF | `tanf` |
| WIC | `federal_wic` (federal) |
| SSI | `federal_ssi` (federal, where active) |
| SSDI | `federal_ssdi` (federal) |
| Medicaid | `medicaid` |
| Section 8 | `section_8` |
| CSFP | `csfp` |
| ACA | `aca` |
| EITC | `federal_eitc` (federal) |
| None | `[]` (empty array) |

A state screen resolves names among its own programs **and** the federal ones (the federal row wins a shared name), so a state scenario sends `federal_wic`, not a state WIC name. The federal programs have moved one at a time, so check `Program.objects.filter(white_label__code="federal")` rather than trusting this table.

**Note:** For the exact `name_abbreviated` a given white label uses, check the program's record in program-ops (`program.name_abbreviated` in `programs/**/*_program_record.json`) or query the `programs_program` table. The serializer resolves each entry against `(white_label, name_abbreviated)` and **silently drops** any name that white label has no `Program` for — so a typo or a name from the wrong white label just vanishes with no error. Any benefit the white label has a program for can be set here; it does not have to be one that renders as a visible tile on the current-benefits step.

**A benefit the white label doesn't have can't be tested there.** A new white label often lacks SNAP or TANF (NJ at launch). Compare the names you sent with the `current_benefits` the POST returns, and mark a scenario **BLOCKED** when one was dropped, so it never reads as a calculator failure (Phase 3). Where another input expresses the same route (TANF as `cashAssistance` income), add it as a `checks` entry so the route is still exercised.

**Expenses mapping** (spec text → expense object in `expenses` array):

The `expenses` field is a **required** top-level array in the Screen payload. It cannot be omitted — use `"expenses": []` when the scenario has no expenses. Each expense object has three required fields: `type`, `amount`, and `frequency`.

| Spec Text | API `type` Value | Category |
|---|---|---|
| Rent | `rent` | housing |
| Mortgage | `mortgage` | housing |
| Property Taxes | `propertyTax` | housing |
| HOA / Condo Association Fees | `hoa` | housing |
| Homeowners Insurance | `homeownersInsurance` | housing |
| Heating | `heating` | utilities |
| Cooling | `cooling` | utilities |
| Telephone | `telephone` | utilities |
| Internet | `internet` | utilities |
| Other Utilities | `otherUtilities` | utilities |
| Medical Insurance / Medical Bills | `medical` | healthcare |
| Child Care | `childCare` | dependentCare |
| Child Support (Paid) | `childSupport` | dependentCare |
| Dependent Care | `dependentCare` | dependentCare |

Expense `frequency` uses the same values as income: `monthly`, `weekly`, `biweekly`, `semimonthly`, `yearly`.

**Example expense object:**
```json
{"type": "rent", "amount": 1200.00, "frequency": "monthly"}
```

**When to include expenses:** Most spec scenarios don't mention expenses — use `"expenses": []`. If a scenario's steps mention housing costs, rent, utilities, medical expenses, or child care costs, map them to the appropriate expense type. Some program calculators (e.g., Emergency Rental Assistance, Energy Assistance, SNAP shelter deductions) use expenses in eligibility checks, so including them when specified in the scenario is important for accurate results.

**Condition flags** (spec text → API field on household member):
| Spec Text | API Field |
|---|---|
| Student | `student: true` |
| Full-time student | `student: true, student_full_time: true` |
| Disabled | `disabled: true` |
| Long-term disability | `long_term_disability: true` |
| Pregnant | `pregnant: true` |
| Unemployed | `unemployed: true` |
| Veteran | `veteran: true` |
| Visually impaired | `visually_impaired: true` |

Send every flag on every member, `false` where the scenario doesn't set it: the screener sends `false` for an unticked box. A flag left out is null, and a program declaring it is dropped as a missing field. Send `null` only to test a missing answer.

**Age → birth_year/birth_month calculation:**
```
birth_month = 1  (default, unless spec provides explicit month)
birth_year = current_year - age, minus 1 more if birth_month is later than the current month
```
This is for an ordinary age. An age on a given date ("64 on December 31, 2025") sets the birth year from that year instead (Phase 1 step 5). Send `age` as today's age either way. A birth month later than the current month otherwise lands a year off, and an infant's birth date in the future (400).
If the spec says "Birth month/year: June 2022", use `birth_month: 6, birth_year: 2022` directly and calculate age from that.

**County naming rules:**
- CO, NC: Include "County" suffix (e.g., "Denver County", "Wake County")
- TX, IL: No "County" suffix (e.g., "Travis", "Cook")
- MA: Use city names (e.g., "Boston", "Cambridge")
- WA: Include "County" suffix (e.g., "King County", "Pierce County")
- NJ: Include "County" suffix (e.g., "Mercer County", "Essex County")

---

### Phase 3: Run the scenarios

Write one Python script for the run, in `{output-dir}/{TICKET-ID}-{program_key}-qa.py` (`~/main/qa` unless the output-directory argument names another). Call the API with `curl` through `subprocess` (urllib fails Heroku's certificates). Follow these rules:

**Payloads**
- One screen per scenario, sequentially: `POST /api/screens/` with `Content-Type: application/json` (curl's `-d` otherwise sends form encoding), then `GET /api/eligibility/{uuid}`.
- Build each payload by the Phase 2 rules: every condition flag `false` unless set, `age` as today's age, `expenses: []` when there are none, a full insurance map, no location on `federal`.
- Keep each scenario's expected outcome and annual value beside its payload, so the script carries its own expectations when it's handed over.

**Keys**
- Read the key in-process (Environment Configuration). Never print, log or write it.
- Pass the auth header to curl on stdin (`-H @-`), not as an argument, and don't use `-k`.
- A 401 or 403 stops the run.

**Results**
- Match `name_abbreviated` against the spec's Program Key. `already_has: true` → Not eligible; `eligible: true` → Eligible; otherwise Not eligible; absent → Not found.
- **PASS:** the outcome matches, and for an expected Eligible with a value, the value is within the rounding tolerance (Phase 1 step 5). Not found passes an expected Not eligible only when `missing_programs` is false.
- **ERROR** (not judged): the POST isn't `201`; the eligibility GET isn't a `200` with a `programs` list after one retry of an empty or HTML reply; or the target is absent with `missing_programs: true`. A failed eligibility call is never read as Not found.
- **BLOCKED** (outside the pass rate): a name sent in `current_benefits` is missing from the POST response's `current_benefits`, or the environment can't express the scenario yet. Name the reason, and the ticket that unblocks it.
- **Never returned:** if the target is Not found in every scenario that reached the API, the run fails. Check the program is imported and active, and that the payloads supply every field it declares.
- Write results after each scenario, so an error mid-run loses nothing.

**Failures:** check the payload before blaming the calculator; a wrong birth year, frequency or insurance type is the usual cause. Locally, `Screen.objects.get(uuid=...).current_benefits.values_list("program__name_abbreviated", flat=True)` shows what was saved.

---

## Results Documentation

Write `{output-dir}/{TICKET-ID}-{program}-{env}-results.md` (add a suffix when a second run would overwrite one). It holds:

- **Header:** program name and key, ticket, date, environment, API base, and the spec's path and branch.
- **Scenarios table:** `| # | Description | White label | Expected | Actual | Exp. Value | Act. Value | Value Match | Result | Screen UUID |`. Values are annual whole dollars. Frontend-only scenarios appear as `SKIPPED`, keeping the spec's numbering.
- **Checks table**, when there are checks (federal replacements): check, white label, result, detail, screen UUID.
- **Summary:** passed, failed, errors, blocked and skipped counts, and the pass rate over judged scenarios (blocked and skipped excluded).
- **Program never returned**, when it applies.
- **Blocked:** each scenario with its reason and unblocking ticket.
- **Failures:** per FAIL or ERROR, expected vs actual with values, the eligibility URL, the payload, `failed_tests` / `passed_tests`, and a one-line analysis.
- **Frontend-Only Scenarios:** always present ("None" if every scenario was API-testable), each with the reason it needs a browser. Values display as annual/12 rounded to whole dollars, so a spec's 129.78/month shows as 130.

---

## Error Handling

### API Key Missing
If no API key can be resolved:
```
ERROR: No API key found for [environment] environment.
Set the [ENV_VAR] environment variable in your own shell and rerun.
Don't paste the key into the conversation.
```

### Screen Creation Fails (400)
Log the validation error from the response body. Common causes:
- Invalid ZIP code format
- Missing required fields (especially `expenses` — must be `[]` even if empty)
- Birth date in future
Document as `ERROR` (not FAIL) and continue.

### Screen Creation Fails (500)
Log the error. Document as `ERROR` and continue.

### Eligibility Endpoint Fails
If eligibility returns error or empty programs array:

- **`missing_programs: true` means a program on the screen was dropped**, not that it is still computing. The eligibility endpoint calculates within the request; a program is dropped for a missing screener field, no calculator, or a missing program it gates on (`screener/views.py::eligibility_results`). The flag covers the whole screen, so another program's drop sets it too.

- **An absent target with `missing_programs: true` is ERROR.** Locally, the screen's latest `EligibilitySnapshot.dropped_programs` names each dropped program and why.

- **If `missing_programs: false` and program absent**: the program is genuinely not in the result set — not a timing issue. Treat as "Not eligible" per the normal evaluation rules.

- If the response itself is empty/HTML (503), retry the curl call once. If it fails again, recreate the screen (new POST) and fetch eligibility for the new UUID.
- Document as `ERROR` only if eligibility completely fails after retry.

### Program Not Found in Results
If the target program doesn't appear in the eligibility response at all:
- If expected "Not eligible" → PASS only when `missing_programs` is false; otherwise ERROR (see above)
- If expected "Eligible" → treat as FAIL, note "Program missing from results entirely"
- Check: is the program active for this white label? Is the `name_abbreviated` correct?
- **Before concluding program is missing**: verify by directly querying the UUID in a separate curl call and checking the raw programs list. Silent curl failures (timeout/503) can make a program appear absent when it was actually returned.

---

## Tips for Efficiency

1. **Run curl calls sequentially** — each scenario needs its own screen and eligibility check
2. **Use python3 for JSON parsing** — safer than bash string manipulation
3. **Write all payloads first, then execute** — easier to debug if something goes wrong
4. **Capture full responses** — save response JSON for failed scenarios
5. **Mark todos as you go** — don't batch updates
6. **Check API key first** — do a quick `GET /api/screens/` (expect 405, not 401/403) before running all scenarios
7. **PolicyEngine programs have empty `passed_tests`/`failed_tests`** — unlike custom calculators, PE-based programs (e.g. `wa_eitc`, `wa_wftc`) return empty arrays for both fields. Don't rely on them for failure diagnosis; instead inspect the payload and re-check the spec thresholds manually.
8. **FPL version mismatch** — SNAP and other income-tested programs update their FPL thresholds every October. Specs are sometimes written with projected future FPL values. If a boundary-income scenario (e.g., "1 below 200% FPL") fails unexpectedly, check which FPL year the spec used versus the year PolicyEngine currently uses. If the spec income value exceeds PE's current threshold, this is a spec issue — not a calculator bug. Note it in the results and recommend updating the spec income to a value safely below the current threshold.
9. **SNAP student restriction age boundary** — 7 CFR 273.5 applies only to individuals aged 18–49. A spec scenario expecting a person under 18 to be ineligible due to student status is incorrect; the restriction doesn't apply below 18. PolicyEngine correctly returns Eligible for under-18 students. Flag this as a spec issue if encountered.
10. **`already_has: true` still has a non-zero `estimated_value`** — this is the benefit amount the household would receive if they didn't already have it. It does not affect result evaluation (still "Not eligible"), but confirms the program calculated correctly. Value comparison is skipped for `already_has` scenarios.
11. **Value comparison uses the API's whole-dollar integer** — `estimated_value` is annual whole dollars: the API truncates the fraction (`math.trunc` in `screener/views.py`), after any per-unit rounding the calculator does. Convert the spec's figure to annual (Phase 1 step 5), strip the dollar sign and commas, and compare within the rounding tolerance. Spec `2,484/year` → API `2484`.
12. **`expenses` is a required field** — The Screen serializer requires `"expenses"` in every POST payload. Omitting it returns `400 Bad Request` with `{"expenses": ["This field is required."]}`. Always include `"expenses": []` even when the scenario has no expenses. See the Expenses mapping table in Phase 2 for available expense types.

---

## Quality Gates

- All API-testable scenarios must be executed (no skipping except frontend-only)
- Frontend-only scenarios must be listed in the "Frontend-Only Scenarios" section with the reason they were skipped
- Results must include Screen UUID for every API-tested scenario (enables debugging)
- Failed scenarios must include the full payload sent and eligibility response diagnostics
- Summary section required with pass rate (calculated from API-tested scenarios only, excluding frontend-only)
- Results file must be written incrementally (don't lose progress on error)
