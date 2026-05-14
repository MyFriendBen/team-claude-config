---
name: api-qa-execution
description: Execute automated QA test scenarios from a spec.md attached to a Linear ticket by sending API calls directly to the benefits screener API. Faster and more reliable than browser-based testing. Use when the user wants to QA a program via API, run screener test scenarios without a browser, or validate eligibility results programmatically.
---

# API-Based QA Testing Skill

Automates benefits screener testing by sending direct API calls instead of driving a browser. Fetches the `{state}_{program}_spec.md` file attached to a Linear ticket, translates each test scenario into a Screen API payload, POSTs it, fetches eligibility results, and compares against expected outcomes.

**Compared to `playwright-qa-execution`:** This skill is faster, more reliable (no DOM selectors to break), and works in headless environments. Use this for eligibility logic validation. Use Playwright when you need to test the UI itself.

---

## Overview

This skill:
1. Fetches a Linear ticket and downloads its attached `{state}_{program}_spec.md`
2. Extracts program details and test scenarios from the spec
3. For each scenario: builds a Screen API payload, POSTs to `/api/screens/`, GETs `/api/eligibility/{uuid}`
4. Compares actual eligibility results against expected outcomes
5. Documents results in local `qa/` directory

---

## Prerequisites

- [ ] Linear MCP server is enabled for ticket fetching
- [ ] Target environment API is accessible
- [ ] API key is available (see Environment Configuration)
- [ ] Linear ticket has a `{state}_{program}_spec.md` file attached

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
/api-qa-execution MFB-1234 production
/api-qa-execution MFB-1234 local qa-results
```

---

## Environment Configuration

Each environment has a different API base URL and requires an API key:

| Environment | API Base URL | API Key |
|---|---|---|
| **staging** (default) | `https://cobenefits-api-staging.herokuapp.com` | `STAGING_API_KEY` env var (see `.env`) |
| **production** | `https://screener.myfriendben.org` | `PRODUCTION_API_KEY` env var, or ask user |
| **local** | `http://localhost:8000` | `LOCAL_API_KEY` env var, or ask user |

**⚠️ The frontend and backend are separate Heroku apps.** `benefits-calculator-staging.herokuapp.com` is the React SPA — every path there returns `index.html`. The Django API backend is `cobenefits-api-staging.herokuapp.com`. If the staging backend URL ever needs to be re-discovered, fetch the staging frontend's main JS bundle and grep it for `herokuapp.com`.

**API Key Resolution Order:**
1. Read `skills/api-qa-execution/.env` and use `STAGING_API_KEY` for staging
2. Check environment variable (`STAGING_API_KEY`, `PRODUCTION_API_KEY`, `LOCAL_API_KEY`)
3. Check `benefits-calculator/.env` for `REACT_APP_API_KEY` (local dev key — works against local server only)
4. Ask user to provide

**IMPORTANT:** If environment is `production`, display a warning and ask for confirmation:
```
WARNING: Running tests against PRODUCTION environment.
This will create real screen records in the production database (marked as is_test=true).
Are you sure you want to proceed? (yes/no)
```

---

## Workflow

### Phase 1: Fetch and Parse Spec

1. **Parse arguments** — ticket ID (required), environment (default: staging), output dir (default: qa)

2. **Determine API base URL and resolve API key** from environment config above.

3. **Fetch Linear ticket** using `mcp__Linear__get_issue` (or the available Linear MCP tool).

4. **Locate and fetch the spec.md attachment** — find the file whose name matches `*_spec.md`. If it can't be fetched automatically, ask the user to paste the spec contents.

5. **Parse the spec.md** — extract from `## Program Details`:
   - Program name, state code, white label

   Extract each `### Scenario N:` block under `## Test Scenarios` into structured data:
   - Scenario number and description
   - Expected outcome (Eligible / Not eligible)
   - Steps: Location (ZIP, county), Household size, Person details, Current Benefits

6. **Present summary to user:**
   ```
   Linear Ticket: MFB-1234
   Program: Head Start
   State: TX
   White Label: tx
   Environment: STAGING
   API Base: https://benefits-calculator-staging.herokuapp.com
   Test Scenarios: 11

   Ready to execute? (y/n)
   ```

7. **Create output directory and initialize results file.**

---

### Phase 2: Build API Payloads

For each test scenario, construct a Screen API payload. The payload format matches the validation JSON schema at `validations/management/commands/import_validations/test_case_schema.json`.

#### Payload Template

```json
{
  "white_label": "{from Program Details}",
  "is_test": true,
  "agree_to_tos": true,
  "is_13_or_older": true,
  "zipcode": "{from scenario Steps → Location}",
  "county": "{from scenario Steps → Location}",
  "household_size": "{from scenario Steps → Household}",
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
        "va": false
      }
    }
  ],
  "expenses": [],
  "has_tanf": false,
  "has_wic": false,
  "has_snap": false,
  "has_ssi": false,
  "has_ssdi": false,
  "has_medicaid": false
}
```

#### Field Mapping from Spec Scenarios

**Relationship mapping** (spec text → API enum):
| Spec Text | API Value |
|---|---|
| Head of Household | `headOfHousehold` |
| Spouse | `spouse` |
| Child | `child` |
| Parent | `parent` |
| Foster Child | `fosterChild` |
| Foster Parent | `fosterParent` |
| Step Parent | `stepParent` |
| Grandparent | `grandParent` |
| Domestic Partner | `domesticPartner` |
| Other | `other` |

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
| hourly | `hourly` |

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

**Current benefits mapping** (spec text → API field):
| Spec Text | API Field |
|---|---|
| SNAP | `has_snap` |
| TANF | `has_tanf` |
| WIC | `has_wic` |
| SSI | `has_ssi` |
| SSDI | `has_ssdi` |
| Medicaid | `has_medicaid` |
| Section 8 | `has_section_8` |
| CSFP | `has_csfp` |
| ACA | `has_aca` |
| EITC | `has_eitc` |
| None | (all false) |

**Note:** For any program not in this table, check `screener/models.py` — search for the `name_abbreviated` in the `current_benefits` property (e.g. `"wa_eitc": self.has_eitc`). The screener model maps each program name to its `has_*` boolean field.

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

**Age → birth_year/birth_month calculation:**
```
birth_year = current_year - age
birth_month = 1  (default, unless spec provides explicit month)
```
If the spec says "Birth month/year: June 2022", use `birth_month: 6, birth_year: 2022` directly and calculate age from that.

**County naming rules** (from test_case_schema.json):
- CO, NC: Include "County" suffix (e.g., "Denver County", "Wake County")
- TX, IL: No "County" suffix (e.g., "Travis", "Cook")
- MA: Use city names (e.g., "Boston", "Cambridge")
- WA: No "County" suffix (e.g., "King")

---

### Phase 3: Execute API Calls

For each scenario, execute this two-step API flow:

#### Step 1: Create Screen

```bash
curl -s -X POST "${API_BASE}/api/screens/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token ${API_KEY}" \
  -d '${PAYLOAD_JSON}'
```

**Expected response:** `201 Created` with JSON body containing `uuid` field.

**Error handling:**
- `400 Bad Request` → Log validation errors, mark scenario as ERROR, continue to next
- `401 Unauthorized` → STOP all execution, API key is invalid
- `500 Server Error` → Log error, mark scenario as ERROR, continue to next

Extract `uuid` from response.

#### Step 2: Fetch Eligibility Results

```bash
curl -s -X GET "${API_BASE}/api/eligibility/${UUID}" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token ${API_KEY}"
```

**Expected response:** `200 OK` with JSON body containing `programs` array.

#### Step 3: Evaluate Results

From the eligibility response, find the target program in `programs` array by matching `name_abbreviated` against the program name from the spec (e.g., `tx_head_start`).

```
program_name = "{state}_{program}"  (from spec, e.g., "tx_head_start")

Match: response.programs[].name_abbreviated == program_name
```

**Determine result:**
- If program found and `already_has == true` → Actual = "Not eligible" (frontend suppresses it; household already enrolled)
- If program found and `eligible == true` and `already_has == false` → Actual = "Eligible"
- If program found and `eligible == false` → Actual = "Not eligible"
- If program NOT found in response → Actual = "Not found" (this is a FAIL unless expected was "Not eligible")

**Compare:**
- Expected "Eligible" vs Actual "Eligible" → **PASS**
- Expected "Not eligible" vs Actual "Not eligible" → **PASS**
- Expected "Not eligible" vs Actual "Not found" → **PASS** (program correctly excluded)
- Any mismatch → **FAIL**

**`already_has` note:** The API returns `eligible: true` alongside `already_has: true` when a household already has a benefit (e.g. `has_eitc: true`). The platform suppresses these on the frontend — they never appear as new results. Treat `already_has: true` as "Not eligible" for comparison purposes. For "Currently receiving" scenarios in the spec, this is the correct pass condition.

#### Step 4: Record Result

For each scenario, capture:
- Scenario number and description
- Expected vs actual outcome
- PASS/FAIL status
- Screen UUID (for debugging: `${API_BASE}/api/screens/${UUID}`)
- Eligibility URL (for debugging: `${API_BASE}/api/eligibility/${UUID}`)
- If FAIL: the `failed_tests` and `passed_tests` arrays from the program result
- If program found: `estimated_value` for informational purposes

#### Step 5: Update Progress

Mark scenario complete in todo list and move to next.

---

### Phase 4: Execute with curl

Use the Bash tool to run all scenarios inside a single Python script using `subprocess` to call `/usr/bin/curl`. This is the **only reliably working approach** — see caveats below.

**Loading the API key from `.env`:** Before running the script, source the `.env` file to populate `STAGING_API_KEY` in the environment:

```bash
set -a && source "$(dirname "$0")/../../.claude/skills/api-qa-execution/.env" && set +a
```

Or in the Python script, load it explicitly:

```python
from pathlib import Path
import dotenv  # if available, or parse manually
env_path = Path(__file__).parent / ".env"  # adjust path as needed
# Manual parse (no dependencies):
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
```

**⚠️ Two known pitfalls:**
1. **`curl` not on PATH in subprocess** — always use `/usr/bin/curl` explicitly; bare `curl` in a `for` loop or `subprocess.run(["curl", ...])` silently fails with "command not found".
2. **Python `urllib` SSL errors** — `urllib.request` fails with `[SSL: CERTIFICATE_VERIFY_FAILED]` against Heroku endpoints. Do not use `urllib`; use `/usr/bin/curl -k` instead.

**Recommended pattern — single Python script, all scenarios:**

```python
import json, os, subprocess

API_BASE = "https://cobenefits-api-staging.herokuapp.com"
API_KEY  = os.environ["STAGING_API_KEY"]  # loaded from skills/api-qa-execution/.env

def curl_post(url, payload_dict):
    result = subprocess.run(
        ["/usr/bin/curl", "-s", "-k", "-w", "\n%{http_code}",
         "-X", "POST", url,
         "-H", "Content-Type: application/json",
         "-H", f"Authorization: Token {API_KEY}",
         "-d", json.dumps(payload_dict)],
        capture_output=True, text=True
    )
    lines = result.stdout.strip().rsplit("\n", 1)
    code = int(lines[-1]) if len(lines) > 1 else 0
    body = lines[0] if len(lines) > 1 else result.stdout
    return code, json.loads(body)

def curl_get(url):
    result = subprocess.run(
        ["/usr/bin/curl", "-s", "-k", "-X", "GET", url,
         "-H", f"Authorization: Token {API_KEY}"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

# POST screen, extract UUID
code, screen = curl_post(f"{API_BASE}/api/screens/", payload)
uuid = screen["uuid"]

# GET eligibility
elig = curl_get(f"{API_BASE}/api/eligibility/{uuid}")

# Find program and evaluate
prog = next((p for p in elig.get("programs", []) if p["name_abbreviated"] == PROGRAM), None)
if prog and prog.get("already_has"):
    actual = "Not eligible"   # household already enrolled — frontend suppresses
elif prog and prog["eligible"]:
    actual = "Eligible"
else:
    actual = "Not eligible"
```

---

## Results Documentation

### Results File Format

Create: `{outputDir}/{TICKET-ID}-{program}-api-results.md`

```markdown
# API QA Test Results - [Program Name] - [State]

**Linear Ticket:** [{TICKET-ID}](linear-ticket-url)
**Test Date:** [Current Date]
**Environment:** [STAGING/PRODUCTION/LOCAL]
**API Base:** [API base URL]
**Tester:** API QA Automation

## Test Scenarios

| # | Description | Expected | Actual | Result | Est. Value | Screen UUID |
|---|-------------|----------|--------|--------|------------|-------------|
| 1 | Single parent, low income | Eligible | Eligible | PASS | $10,517 | abc-123 |
| 2 | Child too young | Not eligible | Not eligible | PASS | — | def-456 |
| 3 | Income too high | Not eligible | Eligible | FAIL | $10,517 | ghi-789 |
```

### Failure Details

For each FAIL, append detailed diagnostics:

```markdown
### Scenario 3: Income Too High — FAIL

**Expected:** Not eligible
**Actual:** Eligible (estimated value: $10,517)
**Screen:** {API_BASE}/api/screens/{uuid}
**Eligibility:** {API_BASE}/api/eligibility/{uuid}

**Passed tests:** age_eligible, household_size_valid
**Failed tests:** (none — all passed, but shouldn't have)

**Payload sent:**
```json
{ ... the exact JSON payload ... }
```

**Analysis:** Income threshold check may not be working. Household monthly income $5,000 exceeds 100% FPL for household of 2.
```

### Summary Section

```markdown
## Summary

- **Total Scenarios:** 11
- **Passed:** 9
- **Failed:** 2
- **Errors:** 0 (API failures)
- **Pass Rate:** 81.8%

## Failed Scenarios

1. **Scenario 3** — Income too high but still shown as eligible
2. **Scenario 7** — Age boundary not enforced

## Recommendations

- Fix income threshold validation in calculator
- Review age boundary logic
- Re-run after fixes: `/api-qa-execution MFB-1234 staging`
```

---

## Comparison with Existing Validation JSON

After running all scenarios, if a corresponding validation JSON file exists at `validations/management/commands/import_validations/data/{state}_{program}.json`, note this in the results:

```markdown
## Cross-Reference

Validation file exists: `validations/.../data/tx_head_start.json`
The validation JSON contains [N] test cases that can be imported via `import_validations` management command.
Spec scenarios and validation JSON should produce consistent results.
```

This is informational only — do not modify the validation JSON.

---

## Error Handling

### API Key Missing
If no API key can be resolved:
```
ERROR: No API key found for [environment] environment.
Please provide an API key:
- Set the [ENV_VAR] environment variable, OR
- Add it to .env file as [ENV_VAR]=your_key, OR
- Paste it here
```

### Screen Creation Fails (400)
Log the validation error from the response body. Common causes:
- Invalid ZIP code format
- Missing required fields
- Birth date in future
Document as `ERROR` (not FAIL) and continue.

### Screen Creation Fails (500)
Log the error. Document as `ERROR` and continue.

### Eligibility Endpoint Fails
If eligibility returns error or empty programs array:
- Check if `missing_programs: true` in response (calculation error)
- Document as `ERROR` with response details

### Program Not Found in Results
If the target program doesn't appear in the eligibility response at all:
- If expected "Not eligible" → treat as PASS
- If expected "Eligible" → treat as FAIL, note "Program missing from results entirely"
- Check: is the program active for this white label? Is the `name_abbreviated` correct?

---

## Tips for Efficiency

1. **Run curl calls sequentially** — each scenario needs its own screen and eligibility check
2. **Use python3 for JSON parsing** — safer than bash string manipulation
3. **Write all payloads first, then execute** — easier to debug if something goes wrong
4. **Capture full responses** — save response JSON for failed scenarios
5. **Mark todos as you go** — don't batch updates
6. **Check API key first** — do a quick `GET /api/screens/` (expect 405, not 401/403) before running all scenarios
7. **PolicyEngine programs have empty `passed_tests`/`failed_tests`** — unlike custom calculators, PE-based programs (e.g. `wa_eitc`, `wa_wftc`) return empty arrays for both fields. Don't rely on them for failure diagnosis; instead inspect the payload and re-check the spec thresholds manually.

---

## Quality Gates

- All scenarios must be executed (no skipping)
- Results must include Screen UUID for every scenario (enables debugging)
- Failed scenarios must include the full payload sent and eligibility response diagnostics
- Summary section required with pass rate
- Results file must be written incrementally (don't lose progress on error)
