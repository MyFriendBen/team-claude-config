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
1. Fetches a Linear ticket and downloads its attached `{state}_{program}_spec.md` (if running in `local` environment) or finds the `{state}_{program}_spec.md` in the `benefits-api` repo (when running in `staging` or `production` environment)
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

4. **Locate and fetch the spec.md attachment** 

    a. *** If running in the `local` environment*** - find the file whose name matches `*_spec.md`. **Always download it with curl, not WebFetch** — WebFetch will summarize large spec files and drop test scenarios. Use:
   ```bash
   /usr/bin/curl -s -L -o /tmp/{ticket-id}/spec.md "{signed_url}"
   ```
   Then read the file with the Read tool. If the URL has expired (Linear signed URLs are short-lived), re-fetch the ticket to get a fresh URL. If it still can't be fetched, ask the user to paste the spec contents.

   b. *** If running in the `staging` or `production` environment*** - Ffind the spec in the local directory. These spec files should live in the `/programs/programs` directory and should follow this naming convention for the whitelabel and program name: `/{whitelabel}/{program_name_in_snake_case}/spec.md`. Determine the name of the program using the linear ticket name and determine the best match.
   
   Examples:
   - `programs/programs/co/collegeinvest_first_step/spec.md`
   - `programs/programs/wa/orca_lift/spec.md`

   If you cannot find the spec, ask the user if you want them to pull down the latest changes from git and try again. If you still cannot find the spec, use the instructions from step 4a and use the `spec.md` from the ticket.

5. **Parse the spec.md** — extract from `## Program Details`:
   - Program name, state code, white label

   Extract each `### Scenario N:` block under `## Test Scenarios` into structured data:
   - Scenario number and description
   - Expected outcome (Eligible / Not eligible)
   - Expected estimated value (if specified — see below)
   - Steps: Location (ZIP, county), Household size, Person details, Current Benefits

   **Extracting expected estimated value:** The `**Expected:**` line may include an expected dollar value in several formats. Parse these patterns (case-insensitive) and extract the numeric value:
   - `Estimated annual value: \`$828\`` → 828
   - `value: \`111\` (annual)` → 111
   - `estimated value \`$828\`` → 828
   - `estimated value \`$2,484\`` → 2484 (strip commas)
   
   If the Expected line contains no numeric value (e.g., just `Eligible` or `Not eligible` or `No value`), set expected_estimated_value to `null`. Only compare values when the spec explicitly provides one.

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
| Grandchild | `grandChild` |
| Sibling | `sibling` |
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

**County naming rules** (from test_case_schema.json and confirmed against validation JSON files):
- CO, NC: Include "County" suffix (e.g., "Denver County", "Wake County")
- TX, IL: No "County" suffix (e.g., "Travis", "Cook")
- MA: Use city names (e.g., "Boston", "Cambridge")
- WA: Include "County" suffix (e.g., "King County", "Pierce County") — confirmed against `wa_hcv.json`; the test_case_schema.json note saying no suffix is incorrect for WA

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

**Compare eligibility:**
- Expected "Eligible" vs Actual "Eligible" → **PASS** (eligibility)
- Expected "Not eligible" vs Actual "Not eligible" → **PASS** (eligibility)
- Expected "Not eligible" vs Actual "Not found" → **PASS** (program correctly excluded)
- Any mismatch → **FAIL**

**Compare estimated value (when spec provides one):**
If the scenario's `expected_estimated_value` is not null AND the eligibility result is "Eligible":
- Extract `estimated_value` from the matched program object in the API response (integer field)
- If `actual_estimated_value == expected_estimated_value` → value match: **PASS**
- If they differ → value match: **FAIL** — record both expected and actual values
- If expected_estimated_value is null (spec didn't specify), skip value comparison — value match: **N/A**
- If scenario is "Not eligible", skip value comparison — value match: **N/A**

**Overall scenario result:** A scenario is **PASS** only if BOTH eligibility and value match pass (or value match is N/A). If either fails, the scenario is **FAIL**.

**`already_has` note:** The API returns `eligible: true` alongside `already_has: true` when a household already has a benefit (e.g. `has_eitc: true`). The platform suppresses these on the frontend — they never appear as new results. Treat `already_has: true` as "Not eligible" for comparison purposes. For "Currently receiving" scenarios in the spec, this is the correct pass condition.

#### Step 4: Record Result

For each scenario, capture:
- Scenario number and description
- Expected vs actual eligibility outcome
- Expected vs actual estimated value (if spec provided one)
- PASS/FAIL status (considering both eligibility and value match)
- Screen UUID (for debugging: `${API_BASE}/api/screens/${UUID}`)
- Eligibility URL (for debugging: `${API_BASE}/api/eligibility/${UUID}`)
- If FAIL (eligibility): the `failed_tests` and `passed_tests` arrays from the program result
- If FAIL (value): both expected and actual estimated values
- If program found: `estimated_value` for informational purposes (even when spec doesn't specify one)

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

**⚠️ Four known pitfalls:**
1. **`curl` not on PATH in subprocess** — always use `/usr/bin/curl` explicitly; bare `curl` in a `for` loop or `subprocess.run(["curl", ...])` silently fails with "command not found".
2. **Python `urllib` SSL errors** — `urllib.request` fails with `[SSL: CERTIFICATE_VERIFY_FAILED]` against Heroku endpoints. Do not use `urllib`; use `/usr/bin/curl -k` instead.
3. **Missing `--max-time` causes silent empty responses** — staging eligibility calls routinely take 30–90 seconds. Without `--max-time 120`, curl may hang and eventually return an empty string; `json.loads("")` raises an exception, the fallback returns `{"error": "..."}`, and `programs` defaults to `[]` — making every scenario appear as "program not found." Always set `--max-time 120` on every curl call AND set `timeout=130` on `subprocess.run`.
4. **Staging 503s return HTML, not JSON** — when Heroku dynos are overloaded, curl returns an HTML error page. Detect this in `curl_get` by checking if the response starts with `<` before parsing JSON, then retry once before marking as ERROR.

**Recommended pattern — single Python script, all scenarios:**

```python
import json, os, subprocess, time

API_BASE = "https://cobenefits-api-staging.herokuapp.com"
API_KEY  = os.environ["STAGING_API_KEY"]  # loaded from skills/api-qa-execution/.env

def curl_post(url, payload_dict):
    result = subprocess.run(
        ["/usr/bin/curl", "-s", "-k", "--max-time", "120", "-w", "\n%{http_code}",
         "-X", "POST", url,
         "-H", "Content-Type: application/json",
         "-H", f"Authorization: Token {API_KEY}",
         "-d", json.dumps(payload_dict)],
        capture_output=True, text=True, timeout=130
    )
    lines = result.stdout.strip().rsplit("\n", 1)
    code = int(lines[-1]) if len(lines) > 1 else 0
    body = lines[0] if len(lines) > 1 else result.stdout
    return code, json.loads(body)

def curl_get(url, retries=1):
    for attempt in range(retries + 1):
        result = subprocess.run(
            ["/usr/bin/curl", "-s", "-k", "--max-time", "120", url,
             "-H", f"Authorization: Token {API_KEY}"],
            capture_output=True, text=True, timeout=130
        )
        raw = result.stdout.strip()
        if not raw:
            if attempt < retries:
                continue
            return None  # empty response — caller should treat as retry signal
        if raw.startswith("<"):
            # HTML response — Heroku 503 or error page
            if attempt < retries:
                continue  # retry once
            return {"error": "non-JSON response (likely 503)", "raw": raw[:200]}
        try:
            return json.loads(raw)
        except Exception as e:
            if attempt < retries:
                continue
            return {"error": str(e), "raw": raw[:200]}
    return None

def get_eligibility_with_retry(uuid, program, max_attempts=5, delay=4):
    """Retry until the target program appears or missing_programs clears.
    
    Custom-calculator programs (HCV, etc.) take 12–20s on staging to calculate.
    missing_programs=True means calculations are still running — the target program
    may be completely absent from the programs list until calculation finishes.
    """
    url = f"{API_BASE}/api/eligibility/{uuid}"
    elig = None
    for attempt in range(max_attempts):
        if attempt > 0:
            time.sleep(delay)
        elig = curl_get(url)
        if elig is None:
            continue  # empty/503 — retry
        prog = next((p for p in elig.get("programs", []) if p.get("name_abbreviated") == program), None)
        if prog is not None:
            return elig, prog
        if not elig.get("missing_programs"):
            return elig, None  # program definitively absent (not a timing issue)
        # missing_programs=True: target program still calculating — wait and retry
    return elig, None

# POST screen, extract UUID
code, screen = curl_post(f"{API_BASE}/api/screens/", payload)
uuid = screen["uuid"]

# GET eligibility with retry for slow calculations
elig, prog = get_eligibility_with_retry(uuid, PROGRAM)

# Evaluate eligibility
if prog and prog.get("already_has"):
    actual = "Not eligible"   # household already enrolled — frontend suppresses
elif prog and prog["eligible"]:
    actual = "Eligible"
else:
    actual = "Not eligible"

# Evaluate estimated value (when spec provides expected value)
actual_value = prog.get("estimated_value") if prog else None
expected_value = scenario.get("expected_estimated_value")  # parsed from spec, int or None

if expected_value is not None and actual == "Eligible":
    value_match = "PASS" if actual_value == expected_value else "FAIL"
else:
    value_match = "N/A"

# Overall result: PASS only if both eligibility and value match pass (or value is N/A)
eligibility_pass = (expected == actual) or (expected == "Not eligible" and actual == "Not found")
overall_pass = eligibility_pass and value_match != "FAIL"
result = "PASS" if overall_pass else "FAIL"
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

| # | Description | Expected | Actual | Exp. Value | Act. Value | Value Match | Result | Screen UUID |
|---|-------------|----------|--------|------------|------------|-------------|--------|-------------|
| 1 | Single parent, low income | Eligible | Eligible | $828 | $828 | PASS | PASS | abc-123 |
| 2 | Income boundary | Eligible | Eligible | $828 | $1,200 | FAIL | FAIL | def-456 |
| 3 | Child too young | Not eligible | Not eligible | — | — | N/A | PASS | ghi-789 |
| 4 | Income too high | Not eligible | Eligible | — | $10,517 | N/A | FAIL | jkl-012 |
| 5 | Basic eligible, no value in spec | Eligible | Eligible | N/A | $10,517 | N/A | PASS | mno-345 |
```

### Failure Details

For each FAIL, append detailed diagnostics:

```markdown
### Scenario 2: Income Boundary — FAIL (Value Mismatch)

**Expected:** Eligible (value: $828)
**Actual:** Eligible (value: $1,200)
**Value Match:** FAIL — expected $828, got $1,200
**Screen:** {API_BASE}/api/screens/{uuid}
**Eligibility:** {API_BASE}/api/eligibility/{uuid}

**Analysis:** Eligibility is correct, but calculator is returning $1,200 instead of expected $828. Check benefit value formula — spec expects $4.60/lunch × 180 days = $828 per child.

---

### Scenario 4: Income Too High — FAIL (Eligibility Mismatch)

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
- **Passed:** 8
- **Failed:** 3
  - Eligibility mismatches: 2
  - Value mismatches: 1
- **Errors:** 0 (API failures)
- **Pass Rate:** 72.7%

## Failed Scenarios

1. **Scenario 2** — Value mismatch: expected $828, got $1,200 (eligibility correct)
2. **Scenario 4** — Income too high but still shown as eligible
3. **Scenario 7** — Age boundary not enforced

## Recommendations

- Fix benefit value calculation — Scenario 2 returns $1,200 but spec expects $828
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

- **`missing_programs: true` means calculations are still in flight** — this flag indicates that one or more programs haven't finished computing yet. The target program may be completely absent from the `programs` array (not just returning `eligible: false` — literally not in the list). This is not an error; it means the calculation is async and hasn't finished. **Always retry with a delay** when the target program is absent and `missing_programs: true`. Use the retry pattern below. Programs requiring county-specific lookup tables (e.g. HCV, SNAP in large-HMFA counties) take longer — expect 12–20 seconds on staging before they appear.

- **Retry pattern for slow calculations**:
  ```python
  def get_eligibility_with_retry(uuid, program, max_attempts=5, delay=4):
      url = f"{API_BASE}/api/eligibility/{uuid}"
      elig = None
      for attempt in range(max_attempts):
          if attempt > 0:
              time.sleep(delay)
          elig = curl_get(url)
          if elig is None:
              continue
          prog = next((p for p in elig.get("programs", []) if p.get("name_abbreviated") == program), None)
          if prog is not None:
              return elig, prog
          if not elig.get("missing_programs"):
              return elig, None  # program definitively absent — not a timing issue
          # missing_programs=True: still calculating, retry
      return elig, None  # exhausted retries
  ```

- **If `missing_programs: false` and program absent**: the program is genuinely not in the result set — not a timing issue. Treat as "Not eligible" per the normal evaluation rules.

- If the response itself is empty/HTML (503), retry the curl call once. If it fails again, recreate the screen (new POST) and use the retry pattern above for the new UUID.
- Document as `ERROR` only if eligibility completely fails after retry.

### Program Not Found in Results
If the target program doesn't appear in the eligibility response at all:
- If expected "Not eligible" → treat as PASS
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
8. **FPL version mismatch** — SNAP and other income-tested programs update their FPL thresholds every October. Specs are sometimes written with projected future FPL values. If a boundary-income scenario (e.g., "$1 below 200% FPL") fails unexpectedly, check which FPL year the spec used versus the year PolicyEngine currently uses. If the spec income value exceeds PE's current threshold, this is a spec issue — not a calculator bug. Note it in the results and recommend updating the spec income to a value safely below the current threshold.
9. **SNAP student restriction age boundary** — 7 CFR 273.5 applies only to individuals aged 18–49. A spec scenario expecting a person under 18 to be ineligible due to student status is incorrect; the restriction doesn't apply below 18. PolicyEngine correctly returns Eligible for under-18 students. Flag this as a spec issue if encountered.
10. **`already_has: true` still has a non-zero `estimated_value`** — this is the benefit amount the household would receive if they didn't already have it. It does not affect result evaluation (still "Not eligible"), but confirms the program calculated correctly. Value comparison is skipped for `already_has` scenarios.
11. **Value comparison uses the raw integer from the API** — the `estimated_value` field is an integer (truncated from decimal). When parsing the spec's expected value, strip `$`, commas, and decimal portions to compare integers. For example, spec says `$2,484` → compare against API integer `2484`.

---

## Quality Gates

- All scenarios must be executed (no skipping)
- Results must include Screen UUID for every scenario (enables debugging)
- Failed scenarios must include the full payload sent and eligibility response diagnostics
- Summary section required with pass rate
- Results file must be written incrementally (don't lose progress on error)
