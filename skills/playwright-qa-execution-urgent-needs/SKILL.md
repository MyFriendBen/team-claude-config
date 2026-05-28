---
name: playwright-qa-execution-urgent-needs
description: Execute automated QA test scenarios using Playwright MCP for urgent needs. Use in a separate session with Playwright MCP enabled.
disable-model-invocation: true
---

# Summary

Urgent Needs are defined in the `/main/benefits-api/programs/management/commands/import_urgent_need_config_data/data` directory. Each file contains a JSON with a `type_short` array — these are the option labels a user can select on the Urgent Needs step of the screener for a given white label. This skill verifies that when someone selects a given option on the Urgent Needs step, the correct number of programs appear on the Additional Resources tab at the end of the screener.

In most cases only one screener is needed. Once you reach the Urgent Needs step for the first time (which gives the screener its unique UUID), navigate back to it using the "this step" link to select each subsequent option without creating a new screener. The exception is when programs have mutually incompatible UrgentNeedFunction conditions — in that case, a separate screener must be created for each incompatible group (see Step 0d).

## Required Inputs

Before starting, collect the following from the user:
- `files` — one or more JSON filenames (or paths) in the urgent needs data directory

`white_label`, `county`, and `postal_code` are all derived from the JSON files during Phase 0. Only ask the user for any of these values if they cannot be determined automatically (see Steps 0a and 0b).

---

## Overview

This skill:
1. Collects `files` from the user.
2. Reads each specified JSON file, extracts `white_label` from `white_label.code`, and collects `type_short` values, county restrictions, and function references.
3. Derives the valid county and asks the user only for a ZIP code in that county (or asks for both if county cannot be determined from the data).
4. Checks whether any programs reference UrgentNeedFunction classes, reads those classes, and determines what screener conditions are required.
5. Detects whether program function conditions are mutually compatible or require separate screener sessions.
6. Plans the test scenarios (one per unique `type_short` per screener group) and computes the expected Additional Resources count for each.
7. Executes each scenario via Playwright, creating a new screener for each incompatible group if needed.
8. Documents results in a local `qa/` directory.

---

## Prerequisites

**CRITICAL:** Before starting, verify:
- [ ] Playwright MCP server is enabled in THIS session
- [ ] Target environment is accessible (ask user: local, staging, or production?)
- [ ] If target is local, confirm the local server is running before proceeding
- [ ] `files` has been provided by the user

If Playwright MCP is not available, STOP and notify the user.

---

## Phase 0: Discovery and Planning

Before opening a browser, perform all of the following in sequence.

### Step 0a — Read JSON files and determine white_label

Read each specified JSON file from `/main/benefits-api/programs/management/commands/import_urgent_need_config_data/data/`. For each file, extract:
- `white_label.code` — the white label slug for this program
- `need.type_short` — array of Urgent Needs step option labels this program appears under
- `need.functions` — array of UrgentNeedFunction keys (may be empty)
- `need.counties` — array of county names (empty = all counties eligible)
- `need.required_expense_types` — array of required expense type names (empty = no requirement)
- `need.active` — whether the program is active

**Determine `white_label`** from the extracted `white_label.code` values:

| Situation | Action |
|---|---|
| All files have the same `white_label.code` | Use that value as `white_label` — no user input needed |
| Files have different `white_label.code` values | Warn the user: "The specified files belong to multiple white labels: [list]. This skill tests one white label at a time. Please confirm which white label to test, or split the files into separate runs." Wait for the user to decide. |
| Any file is missing `white_label.code` | Ask the user: "Could not determine the white label from [filename]. Please provide the white label slug (e.g. `wa`, `co`, `tx`, `il`, `ma`)." |

### Step 0b — Determine county and ZIP code

Using the `need.counties` arrays collected in Step 0a, determine the valid county for the test screener:

1. **Separate programs** into two groups:
   - *County-restricted*: programs with a non-empty `counties` array
   - *Unrestricted*: programs with an empty `counties` array (valid everywhere)

2. **Compute the intersection** of all county-restricted programs' `counties` arrays. This is the set of counties where every county-restricted program would be eligible.

3. **Apply one of the following outcomes:**

   | Situation | Action |
   |---|---|
   | All programs have empty `counties` (no restrictions) | Inform the user any county works. Ask: "Please provide a valid ZIP code for the `[white_label]` state." |
   | Intersection is non-empty | Present the valid counties to the user: "All programs can be tested from any of these counties: [list]. Please provide a ZIP code in one of them." |
   | Intersection is empty (conflicting county requirements) | Warn the user: "The programs being tested have conflicting county requirements and cannot all be tested in a single screener session. [Program A] requires [County X]; [Program B] requires [County Y]. Would you like to (a) split into separate test sessions by county group, or (b) focus on one county and accept that out-of-county programs will not appear?" Wait for the user to decide before continuing. |

4. **Once a county is confirmed**, set `county` = that county name and ask the user for a `postal_code` (5-digit ZIP) within that county if one has not already been provided.

> Note: ZIP codes are not present in the JSON files and must always come from the user. The goal of this step is to narrow the county choice so the user only needs to supply one ZIP rather than guessing.

### Step 0c — Inspect UrgentNeedFunctions (if present)

**First, check whether any program has functions at all.** Look at each file's `need.functions` array:

- **All programs have empty `functions` arrays** → Skip the rest of this step. There are no code-level eligibility conditions to satisfy. The screener can be filled out with any valid data — just complete the required form fields. Proceed directly to Step 0d.
- **One or more programs have non-empty `functions`** → Continue below for those programs only.

For each function key listed in any `need.functions` array:
1. Open `/main/benefits-api/programs/programs/urgent_needs/[white_label]/__init__.py`.
2. Find the class mapped to that key (e.g. `"tx_diaper_bank": NationalDiaperBankNetwork`).
3. Read the source file for that class.
4. Note its `dependencies` list and its `eligible()` method to understand what screener conditions it requires.

Common patterns and what they mean for screener setup:

| Condition in `eligible()` | Required screener setup |
|---|---|
| `self.screen.county == "X County"` | Confirm this matches the county determined in Step 0b |
| `self.screen.num_children(age_max=N) > 0` | Add a household member with age ≤ N |
| `self.screen.num_children(age_min=M, age_max=N) > 0` | Add a household member aged M–N |
| `self.screen.has_expense(["rent", "mortgage"])` | Add rent or mortgage in Step 6 (Expenses) |
| Other `self.screen.*` checks | Adapt accordingly — read the method to understand the model field |

Programs with no `functions` impose no code-level eligibility conditions — they will appear in results for any screener that satisfies the JSON-level `counties` and `required_expense_types` restrictions (already handled in Steps 0b and the screener plan). Do not add screener complexity for these programs.

### Step 0d — Detect condition compatibility and plan screener group(s)

Using the function conditions gathered in Step 0c, determine whether all programs can be tested with a single screener configuration or whether separate screeners are required.

**Check for incompatible conditions** — conditions are incompatible when satisfying one makes another impossible. Common cases:

| Conflict example | Why incompatible |
|---|---|
| Program A needs a child aged 0–4; Program B's function returns `False` when any children are present | Cannot have and not have a child simultaneously |
| Program A needs `has_expense(["rent"])`; Program B's function explicitly checks that rent is absent | Cannot have and not have rent simultaneously |
| Program A requires County X via `eligible()`; Program B requires County Y via `eligible()` (distinct from JSON `counties` — that is handled in Step 0b) | Cannot be in two counties simultaneously |

**Outcome A — All conditions are compatible (the common case):**
Plan a single screener configuration that satisfies all conditions at once. Document the plan:
- Household size (default 1; increase only if a function requires children or additional members)
- Birth year(s) for each member to satisfy all age conditions (any valid year if no age condition exists)
- Expense types to add in the Expenses step (none if no expense condition exists)
- Confirm county from Step 0b matches any county checked in `eligible()`
- Programs with no `functions` are always compatible with any screener setup — they do not factor into this plan

**Outcome B — Incompatible conditions detected (edge case):**
Split programs into the minimum number of groups such that all conditions within each group are mutually satisfiable. For each group, document a separate screener configuration. Example:

```
Group 1 — Programs: [tx_diaper_bank]
  Requires: 1 adult + 1 child (age ≤ 4), no special expenses
  County: Dallas County
  ZIP: ask user for a Dallas County ZIP

Group 2 — Programs: [tx_snap_employment]
  Requires: 1 adult, no children
  County: Dallas County
  ZIP: same ZIP as Group 1 (if county matches)
```

Inform the user: "These programs require separate screener sessions due to incompatible eligibility conditions. I will run Phase 1 + Phase 2 once per group." Then proceed — each group will go through Phase 1 and Phase 2 independently, starting from Step 1 each time.

### Step 0e — Compute expected counts per type_short

Build a map of `type_short` → expected count. The expected count for a given `type_short` is the number of programs from the specified files that:
1. Include that `type_short` in their `type_short` array
2. Are `active: true`
3. Either have no `counties` restriction, or list the confirmed test county
4. Either have no `required_expense_types`, or have a type that matches the screener setup
5. Either have no `functions`, or have functions whose `eligible()` will return `true` given the screener setup planned in Step 0d

Document the expected count for each `type_short` before running any Playwright tests.

### Step 0f — Map type_short values to front-end labels

Look up how each `type_short` string maps to its display label in the front-end repo (`benefits-calculator`). The front-end option tile text is what you will click on the Urgent Needs step. If you cannot find the mapping, note it and ask the user.

---

## Phase 1: Screener Setup

> **If multiple screener groups were identified in Step 0d**, run Phase 1 + Phase 2 once per group, sequentially. Each group starts a fresh screener from Step 1 and gets its own UUID.

Navigate to `http://localhost:3000/[white_label]/step-1`. The base URL is `http://localhost:3000`. After navigating, a UUID is assigned and the URL becomes `/[white_label]/{uuid}/step-1`.

> **Step numbers vary by white label.** Do not rely on URL step numbers to identify pages — use page content instead (see detection rules in each row below).

| Step | What to do | How to detect this page |
|---|---|---|
| Language | Click Continue / leave as English | Page contains a language selector dropdown |
| Disclaimer | Check both checkboxes, click Continue | Page contains two checkboxes and disclaimer text |
| Zip code | Enter `[postal_code]`; if a county dropdown appears, select `[county]` | Page contains a ZIP code input field |
| Household size | Enter the count needed for the screener plan (default: 1), click Continue | Page asks "how many people are in your household" |
| Household members | Set birth month and any valid birth year. Only add special conditions (specific health insurance type, income amount, etc.) if an UrgentNeedFunction in Step 0c explicitly requires them. If no functions exist, just fill the required form fields with any valid values and leave income empty. Click Continue. | Page is titled "Tell us about yourself" with birth month/year fields |
| Expenses | Add expense types required by any UrgentNeedFunction (e.g. rent/mortgage); otherwise click Continue | Page contains expense category options |
| Assets | Enter 0, click Continue | Page asks about cash, savings, stocks |
| Intermediate steps (if any) | Some white labels include additional steps after Assets (e.g. a Public Benefits step). If a `.hb-loading` spinner is present, wait for it to disappear before clicking Continue. Keep clicking Continue on each intermediate step until the Urgent Needs step is detected. | **Not** the Urgent Needs step — no tiles matching the `type_short` labels from Step 0f are visible |
| **Urgent Needs step** | Click the tile matching the first `type_short`'s front-end label (from Step 0f), then click Continue | **Detection:** page contains button tiles matching at least one of the `type_short` display labels identified in Step 0f (e.g. "Family planning or birth control", "Food or groceries") |

The UUID is established on Step 1 navigation — do not create a new screener after this point.

---

## Phase 2: Test Loop

Run one scenario per unique `type_short` value in the **current screener group**. If multiple groups were defined in Step 0d, complete this entire loop for the current group before returning to Phase 1 to start the next group's screener.

**Scenario 1 (first run — post-Urgent-Needs steps traversed once):**

1. On the Urgent Needs step: click the tile for the first `type_short`'s display label.
2. Click Continue → lands on the referral source step (detected by: page asks "How did you hear about MyFriendBen?").
3. Select any referral source (e.g. "Test / Prospective Partner"), click Continue.
4. If a sign-up step appears (detected by: optional email/name fields), click Continue to skip it.
5. If a confirmation step appears, click Continue.
6. Verify URL contains `/results/`.
7. Click the `role=tab[name*="Additional Resources"]` tab to switch to Additional Resources.
8. Verify the tab label reads `Additional Resources (N)` where N equals the expected count for this `type_short`.

**Scenarios 2–N (subsequent runs — Urgent Needs step → results directly):**

1. From the Additional Resources tab, click the "this step" link inside `[data-testid="needs-section"]`.
   - Selector: `page.locator('[data-testid="needs-section"]').getByRole('link', { name: 'this step' })`
   - This navigates back to the Urgent Needs step (whatever step number it is for this white label) with `{ routeBackToResults: true }` as React Router location state, bypassing the referral/sign-up steps on Continue.
2. On the Urgent Needs step: click the previously selected tile to deselect it, then click the new scenario's tile.
3. Click Continue → skips referral/sign-up steps, lands directly on `/[white_label]/{uuid}/results/near-term-needs`.
4. Verify the tab label count matches the expected count for this `type_short`.

**After all scenarios in this group are complete:** If another screener group remains from Step 0d, return to Phase 1 and start a new screener for that group. Otherwise, proceed to Documentation.

---

## Key Selectors Reference

| Element | Selector |
|---|---|
| Urgent Needs option tile | `page.getByRole('button', { name: '<label text>' })` |
| Continue button | `page.getByRole('button', { name: 'Continue' })` |
| Near-term benefits tab | `page.getByTestId('near-term-benefits-tab')` |
| "this step" back-link | `page.locator('[data-testid="needs-section"]').getByRole('link', { name: 'this step' })` |
| Needs section container | `page.locator('[data-testid="needs-section"]')` |

**Verification approach:** The tab label text contains `Additional Resources (N)`. Extract N:

```js
const tabText = await page.getByTestId('near-term-benefits-tab').textContent();
const match = tabText.match(/\((\d+)\)/);
const count = parseInt(match[1]);
expect(count).toBe(expectedCount);
```

---

## URL Structure

```
Entry:         http://localhost:3000/[white_label]/step-1   (creates UUID)
Urgent Needs:  /[white_label]/{uuid}/step-N    (N varies by white label — detect by content)
Results:       /[white_label]/{uuid}/results/benefits        (default tab)
Needs:         /[white_label]/{uuid}/results/near-term-needs (Additional Resources tab)
```

> The step number for the Urgent Needs page differs across white labels (e.g. step 8 for `tx`, step 9 for `wa`). Never hardcode a step number — always detect the Urgent Needs step by looking for tile buttons matching the `type_short` labels from Step 0f.

---

## Critical Implementation Notes

1. **`routeBackToResults` state** — This state is only set when navigating to the Urgent Needs step via the "this step" link from the Additional Resources tab. Navigating directly to the Urgent Needs step URL (without this state) causes Continue to go to the referral step instead of results. Scenarios 2–N must use the "this step" link — never a direct URL.

2. **Toggle deselect on the Urgent Needs step** — Tiles are toggle buttons. On Scenarios 2–N, click the currently selected tile to deselect it before clicking the new scenario's tile.

3. **Household size = 1 by default** — A single-member household avoids the optional member overview step at `/step-5/0` (which only appears for households > 1). Only increase household size if a UrgentNeedFunction requires children or additional members.

4. **Wait for loading on intermediate steps** — Some white labels include a Public Benefits step between Assets and the Urgent Needs step. If a `.hb-loading` spinner appears, wait for it to fully disappear before clicking Continue.

5. **Detect the Urgent Needs step by content, not URL** — The step number differs by white label (`tx` = step 8, `wa` = step 9, others may differ). After completing Assets, click Continue on each page until one contains tile buttons matching the `type_short` display labels from Step 0f. That page is the Urgent Needs step.

6. **County restrictions** — If any program JSON lists `counties`, the screener's county must be one of them for that program to appear. The county is determined automatically in Step 0b; only ask the user if there is ambiguity or a conflict.

7. **Required expense types** — If any program JSON lists `required_expense_types`, add at least one matching expense type in the Expenses step. Common types: `rent`, `mortgage`, `childCare`, `childSupport`.

8. **UrgentNeedFunction `dependencies`** — A function with `dependencies = ["age"]` will return `False` (and be excluded from results) if no age data is on the screen. Always set at least one household member's birth year.

9. **Programs with no functions have no screener requirements** — A program whose `need.functions` array is empty will appear in results for any screener that satisfies the county and expense type restrictions defined in the JSON. Do not add household members, specific insurance types, income values, or expenses for these programs — the default minimal setup is sufficient and adding unnecessary data can interfere with programs that do have function conditions.

10. **Expected count accuracy** — The count verified in the UI reflects ALL currently active programs for the white label that match the `type_short` and pass eligibility — not just the newly added ones. If existing programs also match, they will be included in the count. If the count does not match expectations, check for other active programs in the database with the same `type_short`.

---

## Documentation

After all scenarios complete, write a result summary to `qa/urgent-needs-qa-[white_label]-[date].md` with:
- Inputs used (white_label, postal_code, county, files tested)
- Screener configuration used (household size, ages, expenses)
- For each `type_short`: expected count, actual count, pass/fail
- Any discrepancies and notes
