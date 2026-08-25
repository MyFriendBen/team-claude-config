---
name: check-pe-support
description: Discover whether PolicyEngine exposes a variable for a program under consideration. Probes the private household API and reports whether the variable exists, which entity owns it, which base class to subclass, and whether it is annual or monthly — the pre-flight gate before implementing a PE calculator.
usage: /check-pe-support [pe_variable_name] [--state XX]
example: /check-pe-support mo_chip_premium --state mo
---

<command-name>check-pe-support</command-name>

# Check PolicyEngine Support

Determines whether PolicyEngine exposes a variable for a program we're considering implementing, and if so what shape it has. This is a **discovery command**, not a check against calculators already in our system. It tells you whether a PE-based calculator is even an option — and, when it is, which base class to subclass, which entity to read from, and which period to read at.

Run from `benefits-api/`. Use `venv/bin/python` — `python` may not resolve in non-interactive shells.

> This skill used to describe a `manage.py check_pe_support` command that searched a downloaded metadata blob. **That command does not exist**, and `household.api` has no metadata endpoint. Asking PolicyEngine to compute the variable is the check.

---

## Step 1: Gather Inputs

You need the **exact PE variable name** — from the ticket description, the spec, or the initial config (e.g. `mo_chip_premium`, `chip_gross`, `co_ccad`). A two-letter **state code** if the variable is state-scoped.

If you only have a program concept and no variable name, there is no catalog to search. Get the name from Discovery, or read PolicyEngine's source on GitHub (`policyengine_us/variables/gov/…`) and come back with a candidate.

---

## Step 2: Find Out What PolicyEngine Currently Serves

```bash
curl -s https://household.api.policyengine.org/versions/us
# {"current":"1.794.2","frontier":"1.815.1"}
```

`household.api` serves **only** what `current` and `frontier` resolve to right now, and returns `422 unsupported_version` for any other exact version. Probe at the version you'd actually ship against — usually `current`, or `frontier` if the variable or a fix you need is new.

**Only ever use the private API.** Never probe `api.policyengine.org`: it ignores the request's `version` field, so its answers aren't comparable to ours.

---

## Step 3: Probe the Variable

Ask PolicyEngine to compute it for a minimal household. Requesting a variable means adding `{period: None}` under the entity you think owns it.

```python
# venv/bin/python manage.py shell < probe.py
# Prefix PE_RECORD=1 to permit the live auth call; the repo's own helper reads the
# credentials, so nothing is ever printed or copied out of .env.
import requests
from integrations.clients.policyengine.engines import _fetch_pe_bearer_token

TOK = _fetch_pe_bearer_token()
VARIABLE, ENTITY, PERIOD, VERSION = "mo_chip_premium", "tax_units", "2026-07", "1.815.1"

ids = ["1", "2"]
household = {
    "people": {"1": {"age": {"2026": 35}, "employment_income": {"2026": 30000}},
               "2": {"age": {"2026": 7},  "employment_income": {"2026": 0}}},
    "tax_units": {"tax_unit": {"members": ids}},
    "families": {"family": {"members": ids}},
    "households": {"household": {"members": ids, "state_code": {"2026": "MO"}}},
    "spm_units": {"spm_unit": {"members": ids}},
    "marital_units": {},
}

if ENTITY == "people":
    for m in ids:
        household["people"][m][VARIABLE] = {PERIOD: None}
else:
    sub = {"tax_units": "tax_unit", "spm_units": "spm_unit", "households": "household",
           "families": "family"}[ENTITY]
    household[ENTITY][sub][VARIABLE] = {PERIOD: None}

r = requests.post("https://household.api.policyengine.org/us/calculate",
                  json={"household": household, "version": VERSION},
                  headers={"Authorization": f"Bearer {TOK}"}, timeout=60)
print(r.status_code, r.text[:500])
```

Adjust the household to something the variable would plausibly fire for — a program for children needs a child, a pregnancy variable needs `is_pregnant`. A `200` returning `0.0` may mean "variable exists, this household doesn't qualify" rather than "no such variable".

---

## Step 4: Interpret the Result

| Response | Meaning |
|---|---|
| `200` with a number | Variable exists on that entity. Note the value — it's also your first real data point for the spec's scenarios |
| `500` … `"You tried to compute the variable 'X' for the entity 'people'; however the variable is defined for 'tax_units'"` | Variable exists, **wrong entity** — the message names the right one. Retry there |
| `500` … variable not found at all | No such variable at this version |
| `422 unsupported_version` | The version isn't `current` or `frontier` right now. Re-read `/versions/us` |

**Entity → base class** (`programs/framework/pe_base.py`):

| PE entity | Payload key | Base class |
|---|---|---|
| `person` | `people` | `PolicyEngineMembersCalculator` |
| `spm_unit` | `spm_units` | `PolicyEngineSpmCalulator` |
| `tax_unit` | `tax_units` | `PolicyEngineTaxUnitCalulator` |
| `household` / `family` | `households` / `families` | `PolicyEngineCalulator` |

---

## Step 5: Determine the Period

**Do this every time — it is not optional.** A variable PolicyEngine defines per month returns its twelve months *summed* at the annual period, which silently blends a schedule that changes mid-year into a figure matching neither half.

Re-run Step 3 twice, at `"2026"` and at a `"2026-MM"` inside the window your expected values are stated against, and compare:

- **Equal, or annual ≈ 12 × monthly** → annual variable. Read it at the annual period.
- **Annual is the twelve months added up, and months differ from each other** → monthly variable. Read it at a month period and multiply by 12. In the calculator that means `pe_monthly_outputs` + `pe_period_month` (see `/add-pe-program` Phase 4).

Worked example: `mo_chip_premium` for a household of three in tier 1 returns `$102` at `2026-01`, `$32` at `2026-07`, and `$804` at `2026` — six months of each Appendix E schedule, matching neither.

---

## Step 6: Gate Decision

**Variable found** — PolicyEngine supports this program. Record the variable, entity, base class and period; hand them to `/add-pe-program`.

**Variable NOT found** — before halting, rule out false negatives:

1. Try the federal name as well as the state-prefixed one (`chip` vs `mo_chip`), and the reverse.
2. Try the other entities — the 500 message names the right one, but only if the variable exists at all.
3. Try `frontier` as well as `current`; the variable may be newer than the served default.
4. Check PolicyEngine's source for a rename: `policyengine_us/variables/gov/…` on GitHub.
5. Build a household the variable would actually fire for. `0.0` is not the same as "missing".

Still nothing → **stop and alert the user.** Show the request and response, and ask whether to continue. PolicyEngine having no variable means there is no data source for a PE calculator, and the program belongs in `/add-custom-program` instead.
