---
name: discovery-review
description: Review the three program researcher artifacts (initial_config.json, spec.md, validation .json) attached to a Linear ticket for accuracy, format, and completeness. Produces corrected files and a changelog in ./discovery-reviews/{ticket-id}/.
---

# Discovery Review Workflow

Reviews the three program research artifacts attached to a Linear ticket — `[program]_initial_config.json`, `[program]_spec.md`, and `[program].json` (validation scenarios) — for accuracy, format, and completeness. Produces corrected versions of each file plus a changelog documenting every change.

## Usage

```
/discovery-review MFB-1234
```

If no ticket ID is provided, ask the user for one before proceeding.

---

## Workflow

### Phase 1: Fetch Ticket and Attachments

1. **Fetch the issue** using the Linear MCP tool (`get_issue`) with the provided ticket ID.
2. **Identify the three artifact files** from the ticket description or attachments. The three files are:
   - `[program]_initial_config.json` — program config for DB import
   - `[program]_spec.md` — eligibility criteria, benefit value, test scenarios
   - `[program].json` — validation scenario JSON array
3. **Download each attachment** using `get_attachment` for each attachment ID found on the ticket. If attachments are embedded as text/code blocks in the ticket description or comments, extract them from there instead.
4. **Also fetch all comments** using `list_comments` (ordered by `createdAt`, limit 250) — reviewer corrections in comments must be accounted for. If a reviewer has already left corrections, apply those corrections as the baseline before running the review checks below.
5. **Extract `name_abbreviated`** from the config JSON's `program.name_abbreviated` field.
6. **Create the output directory:** `./discovery-reviews/{ticket-id}/` (e.g., `./discovery-reviews/MFB-1234/`).
7. **Save the original files** into the output directory with an `_original` suffix for reference (e.g., `co_snap_initial_config_original.json`).

**Announce what you found:**
```
Ticket: MFB-1234 — CO: Supplemental Nutrition Assistance Program
Program: co_snap
Attachments found: 3
Comments found: N

Saving originals and beginning review...
```

If any of the three files are missing, warn the user and proceed with what's available.

---

### Phase 2: Pre-flight — Load Reference Data

Before reviewing, load reference data needed for cross-checking.

#### 2.1 — Existing program categories, documents, navigators, and icons

**Primary reference:** Fetch the database reference spreadsheet at:
```
https://docs.google.com/spreadsheets/d/1yjmrktlCdQNRTERdiBiElz0fsc4skqzsuf1vCCBF0X4/edit?usp=sharing
```

This spreadsheet contains all current `external_name` values and relevant metadata already in the database — program categories, documents, navigators, and category icons. Use it as the authoritative source to:
- Verify the config reuses existing `external_name` values correctly instead of inventing duplicates
- Check that naming conventions match what's already in the DB for the given state (or follow established patterns if it's a new state)
- Confirm valid category icons
- Identify existing navigators and documents that can be reused

**Secondary reference:** Also read fixture files in:
```
benefits-api/programs/management/commands/import_program_config_data/data/
```

Use Glob to find all `.json` files, then read each one. Compile:
- All unique `program_category.external_name` values
- All unique `document.external_name` values
- All unique `navigator.external_name` values

Cross-reference these with the spreadsheet. The spreadsheet reflects the live database and is the source of truth; the fixture files show what's been added via the import pipeline.

#### 2.2 — Screener field inventory

Reference the screener field inventory from `/find-screener-fields` (documented in `team-claude-config/commands/find-screener-fields.md`) to verify that:
- Every `Screener fields:` line in the spec references real fields
- No criteria use deprecated fields (e.g., `age` instead of `birth_year` + `birth_month`)
- Data gaps are correctly identified — criteria that reference information we don't capture should be marked with ⚠️ *data gap*
- No criteria are missing screener field mappings that should have them

#### 2.3 — Validation scenario schema

Reference the test case schema at:
```
benefits-api/validations/management/commands/import_validations/test_case_schema.json
```

This defines valid field names, enum values, and required fields for validation scenarios. Use it to catch invalid field names, enum values, or missing required fields.

#### 2.4 — County naming conventions

County naming varies by state. From the schema:
- **CO, NC:** Include "County" suffix (e.g., `"Denver County"`, `"Wake County"`)
- **TX, IL:** County name only, no suffix (e.g., `"Travis"`, `"Cook"`)
- **MA:** City names instead of counties (e.g., `"Boston"`, `"Cambridge"`)
- **WA:** Include "County" suffix (e.g., `"King County"`)

Verify all county values in the validation scenarios follow the correct convention for their state.

---

### Phase 3: Review `[program]_initial_config.json`

Check each section of the config systematically. For every issue found, record it in the changelog with a concise justification.

#### 3.1 — JSON validity
- Parse the JSON. If it fails, identify the exact error (trailing comma, mismatched brackets, curly quotes, etc.).
- Check for curly/smart quotes that may have come from a word processor.

#### 3.2 — `white_label`
- `code` must be a valid 2-letter state abbreviation or `cesn`. Verify it matches the program's state.

#### 3.3 — `program_category`
- If the category already exists in the fixture data (from Phase 2.1), the config should use `external_name` only — flag if it unnecessarily re-specifies `name`, `icon`, `description`, or `tax_category`.
- If this is a genuinely new category, verify it includes `name`, `icon`, and optionally `description` and `tax_category`.
- Verify naming convention: `{state}_{category_type}` (e.g., `co_food`, `tx_cash`).
- Valid icon values seen in the codebase: `cash`, `food`, `health_care`, `housing`, `transportation`, `child_care`, `tax_credit`. Flag any other value as needing dev confirmation.

#### 3.4 — `program` fields

Check every field against these rules:

| Field | Check |
|-------|-------|
| `name_abbreviated` | Must be snake_case, typically `{state}_{program}` |
| `external_name` | If present, must be globally unique. Usually fine to omit. |
| `year` | Only include if program uses FPL-based income tests. Flag if present but program has no income test. Flag if absent but program does use FPL. |
| `legal_status_required` | Must NOT be empty. If no restriction, must include all 6 base values: `citizen`, `non_citizen`, `refugee`, `gc_5plus`, `gc_5less`, `otherWithWorkPermission`. If restricted, verify the subset matches actual program rules. |
| `name` | Should match official program name. Flag informal/abbreviated names. Include acronym in parentheses if commonly used. |
| `description_short` | Under ~120 characters, no period at end. Should function as standalone teaser. |
| `description` | ~4 paragraphs with `\n\n` breaks. Middle school reading level. Must NOT include specific eligibility numbers/cutoffs (income limits, age requirements, FPL percentages). Must NOT repeat eligibility criteria the screener already checks. Should cover: what the program provides, how the benefit is administered, any priority or unverifiable criteria worth mentioning, application guidance. |
| `learn_more_link` | Must be a working URL. Prefer .gov pages. |
| `apply_button_link` | Must be a working URL that gets users as close to the application as possible. |
| `apply_button_description` | `""` defaults to "Apply Now". Use `"Learn More"` if URL is informational only. |
| `estimated_application_time` | Should be a realistic estimate, not an AI-generated guess. Flag obviously made-up values. |
| `estimated_delivery_time` | `""` if unknown. Flag AI-generated guesses. |
| `estimated_value` | Should be `""` for programs with a calculator. Flag if set to `"Varies"` unless justified. |
| `value_format` | `null` for monthly (default), `"lump_sum"` for one-time, `"estimated_annual"` for annual. Verify this matches the program's actual payment structure. |
| `value_type` | `"benefit"` or `"tax_credit"`. Verify correctness. |
| `website_description` | Should match `description_short`. |
| `base_program` | Must be one of the valid values or `null`/omitted. Flag if a cross-state program exists but `base_program` is missing. |
| `show_on_current_benefits` | Should be `true` for programs with a calculator. |
| `has_calculator` | Should be `true` for Discovery programs. |
| `show_in_has_benefits_step` | Usually `false` unless this is a major program (SNAP, TANF, etc.) that confers categorical eligibility on other programs. |

#### 3.5 — `documents`
- Omit the key entirely if no documents — flag empty arrays `[]`.
- Each document needs `external_name` and `text`. Check if the `external_name` already exists in the DB (Phase 2.1) — if so, reuse it.
- `link_url` and `link_text` should both be `""` or both populated.

#### 3.6 — `navigators`
- Omit the key entirely if no navigators — flag empty arrays `[]`.
- Every navigator needs `external_name`, `name`, `email`, `description`, `assistance_link`.
- Check if navigator already exists in DB fixtures.
- `phone_number` must be E.164 format (`+1XXXXXXXXXX`).
- `counties` array values must follow the state's naming convention.

#### 3.7 — `warning_message`
- Omit entirely if not needed — flag empty objects `{}`.
- If present, verify `calculator` is `"_show"` (the common case) and `message` contains accurate, time-sensitive info.

---

### Phase 4: Review `[program]_spec.md`

#### 4.1 — Eligibility criteria

For each numbered criterion:

1. **Is it a real eligibility requirement?** Flag if it's actually:
   - An administrative requirement (provide ID, complete interview, show proof) — belongs in `documents` or `description`
   - A priority criterion (lower income gets priority) — belongs in Priority Criteria section
   - An application requirement (deadline, waiting list) — belongs in `description`

2. **Are screener fields correct?** Cross-reference against the screener field inventory (Phase 2.2):
   - Every field cited must actually exist in the screener
   - No use of deprecated `age` field (should be `birth_year` + `birth_month`)
   - Fields must be appropriate for the check (e.g., income tests should reference `calc_gross_income`, not raw `amount`)

3. **Data gaps correctly identified?** Criteria we can't check should have ⚠️ *data gap* and a note explaining the assumption (typically inclusivity — assume eligible).

4. **Sources credible and specific?** Every source must be:
   - A .gov or legal site (e.g., `law.cornell.edu`) — NOT third-party summary sites
   - Specific enough to verify (include section numbers, e.g., `10 CFR 440.22(a)(3)`)
   - Flag any sources that look like AI-fabricated citations (common pattern: plausible-sounding section numbers that don't exist)

5. **Are any criteria missing?** Based on your understanding of the program type and the sources cited, flag if obvious eligibility criteria appear to be absent.

#### 4.2 — Priority criteria

- Check that priority criteria are separated from eligibility criteria (not mixed in).
- If the spec has no Priority Criteria section but eligibility criteria contain priority-type rules, flag them for extraction.

#### 4.3 — Benefit value

- **Fixed amounts:** Verify the cited value matches the source.
- **Variable amounts:** Verify the methodology is clear enough for a developer to implement.
- **Insurance/in-kind:** Verify the estimate is reasonable and the reasoning is documented.
- Verify whether it's presented as a citable value or an informed estimate.
- All values discussed here must be **annual** (this is critical — the frontend divides by 12 for monthly display).

#### 4.4 — Test scenarios

Check all test scenarios in the spec for:

1. **Coverage:** Do they cover all major branches of eligibility logic? At minimum:
   - One clearly eligible "golden path" case
   - One clearly ineligible case per major criterion
   - At least one edge case (boundary value, multi-member household, mixed eligibility)

2. **Consistency with eligibility criteria:**
   - Do scenario outcomes match the criteria? (e.g., if criterion says income must be below 200% FPL, does the ineligible scenario have income above that threshold?)
   - Do scenarios only use screener fields we actually have?

3. **No duplicates:** Flag scenarios that test the same eligibility dimension with irrelevant variation.

4. **Correct year-based values:** If scenarios use FPL, AMI, or other year-indexed values, verify they use the correct year (should match the `year` in the config, or current year if not set).

5. **Internal consistency:** For each scenario:
   - `household_size` matches number of members described
   - Ages and birth years are consistent
   - Income amounts are realistic for the scenario being tested

---

### Phase 5: Review `[program].json` (Validation Scenarios)

#### 5.1 — JSON validity
- Parse the JSON array. Top level must be `[...]`.
- Check for trailing commas, mismatched brackets, curly quotes.

#### 5.2 — Schema compliance

For each scenario object, validate against the test case schema:

| Field | Check |
|-------|-------|
| `notes` | Required. Should clearly describe what's being tested. |
| `household.white_label` | Must match the program's state code. Must be a valid enum value. |
| `household.is_test` | Must be `true`. |
| `household.agree_to_tos` | Must be `true`. |
| `household.is_13_or_older` | Must be `true`. |
| `household.zipcode` | Must be a valid 5-digit ZIP in the correct state. |
| `household.county` | Must follow the state's naming convention (Phase 2.4). |
| `household.household_size` | Must exactly equal the number of entries in `household_members`. |
| `household.household_members` | At least one member. Must include exactly one `headOfHousehold`. |
| `household.expenses` | Must be present (at least empty `[]`). |
| `expected_results.program_name` | Must exactly match `name_abbreviated` from the config (case-sensitive). |
| `expected_results.eligible` | Required boolean. |
| `expected_results.value` | Include ONLY for eligible scenarios. Omit entirely for ineligible (not `0`). Must be **annual** value. |

#### 5.3 — Per-member validation

For each household member:

| Field | Check |
|-------|-------|
| `relationship` | Must be a valid enum: `headOfHousehold`, `spouse`, `domesticPartner`, `child`, `fosterChild`, `parent`, `fosterParent`, `stepParent`, `grandParent`, `grandChild`, `sibling`, `other` |
| `age` | Required integer >= 0. |
| `birth_year` + `birth_month` | Must be consistent with `age`. A child with `age: 0` and `birth_year: 2023` is wrong in 2026. |
| `has_income` | Must be `true` if `income_streams` is non-empty, `false` if empty. |
| `income_streams` | If present, each needs `type` (valid enum), `amount` (number >= 0), `frequency` (valid enum). |
| `insurance` | Required on every member. At minimum `{"none": true}`. |

Valid income stream types (from schema): `wages`, `selfEmployment`, `sSDisability`, `sSRetirement`, `sSI`, `sSSurvivor`, `sSDependent`, `unemployment`, `cashAssistance`, `cOSDisability`, `workersComp`, `veteran`, `childSupport`, `alimony`, `gifts`, `boarder`, `pension`, `investment`, `rental`, `deferredComp`, `workersCompensation`, `veteransBenefits`, `rentalIncome`, `other`

Valid frequencies: `monthly`, `weekly`, `biweekly`, `semimonthly`, `yearly`, `hourly`

#### 5.4 — Scenario coverage

**Important:** The validation JSON intentionally contains only 3 scenarios, even though the spec may describe many more test scenarios. This is by design — the 3 scenarios in the JSON are deliberately selected as the most representative subset for the validation suite. Do NOT flag the mismatch in count between spec scenarios and JSON scenarios as an issue.

The 3 scenarios should cover different eligibility dimensions:

1. **Clearly eligible, standard case** — golden path hitting all criteria
2. **Clearly ineligible, primary exclusion** — most common disqualifying reason
3. **Edge case or nuance** — boundary condition, multi-member interaction, or program-specific wrinkle

Flag if:
- All 3 test the same dimension of eligibility
- There are duplicate scenarios (same logic branch with irrelevant variation)
- A major eligibility criterion has no corresponding ineligible scenario
- Scenarios use FPL/AMI values from the wrong year

#### 5.5 — Cross-file consistency

- `program_name` in every `expected_results` must exactly match `name_abbreviated` in the config
- `white_label` in every scenario must match `white_label.code` in the config
- Eligible scenario `value` amounts should be consistent with the benefit value methodology described in the spec
- County values must be valid for the state

---

### Phase 6: Screener Field Mapping Check

Using the screener field inventory from `find-screener-fields` (Phase 2.2), perform a field mapping audit:

1. **For each eligibility criterion in the spec**, verify that the screener fields listed are:
   - Real fields that exist in the screener models
   - The best available fields for that check (not proxies when a direct field exists)
   - Using the correct method signatures (e.g., `calc_gross_income("monthly", ["all"])` not just `income`)

2. **Identify unmapped criteria** — any criterion that should reference screener fields but doesn't.

3. **Identify phantom fields** — any field cited in the spec that doesn't exist in the screener models.

4. **Check the validation scenarios** — do they use only fields that exist in the test case schema? Flag any invalid field names.

Present a brief summary of findings (not the full mapping — just issues found).

---

### Phase 7: Link Verification

For key URLs in the config, attempt to verify they are reachable:

- `learn_more_link`
- `apply_button_link`
- `assistance_link` (on each navigator)
- Any `link_url` on documents

Use `WebFetch` to check each URL. Flag any that return errors (404, 500, connection refused). Note: some .gov sites block automated requests — if a fetch fails, note it as "unable to verify" rather than "broken."

---

### Phase 8: Write Corrected Files and Changelog

#### 8.1 — Write corrected files

Save corrected versions of all three files to `./discovery-reviews/{ticket-id}/`:

- `{name_abbreviated}_initial_config.json` — corrected config
- `{name_abbreviated}_spec.md` — corrected spec
- `{name_abbreviated}.json` — corrected validation scenarios

Only modify things that are clearly wrong (format errors, schema violations, field name typos, internal inconsistencies). For judgment calls (is this description good enough? is this source credible?), flag in the changelog but don't change the file — let the reviewer decide.

#### 8.2 — Write the changelog

Save `{name_abbreviated}_review_changelog.md` to the same directory:

```markdown
# [Program Name] — Discovery Review Changelog

**Ticket:** [ticket-id]
**Program:** `[name_abbreviated]`
**Reviewed:** [today's date]

---

## Summary

[2-3 sentence overview: how many issues found, severity breakdown, overall assessment]

---

## Config (`_initial_config.json`)

### Auto-fixed
[Issues that were corrected in the output file]
- **[field]:** [what was wrong] → [what it was changed to]. [Why.]

### Flagged for reviewer
[Issues that need human judgment]
- **[field]:** [concern]. [Recommendation.]

---

## Spec (`_spec.md`)

### Auto-fixed
- **[criterion/section]:** [what was wrong] → [what it was changed to]. [Why.]

### Flagged for reviewer
- **[criterion/section]:** [concern]. [Recommendation.]

---

## Validation Scenarios (`.json`)

### Auto-fixed
- **Scenario N ([notes]):** [what was wrong] → [what it was changed to]. [Why.]

### Flagged for reviewer
- **Scenario N ([notes]):** [concern]. [Recommendation.]

---

## Screener Field Mapping

[Summary of field mapping check results]
- Fields verified: N
- Issues found: N
- [List any phantom fields, unmapped criteria, or incorrect field references]

---

## Link Verification

| URL | Status | Notes |
|-----|--------|-------|
| [url] | ✓ OK / ✗ Error / ? Unable to verify | [details] |
```

#### 8.3 — Present results

```
Discovery review complete for {name_abbreviated} ({ticket-id}):

  ✓ {name_abbreviated}_initial_config.json
  ✓ {name_abbreviated}_spec.md
  ✓ {name_abbreviated}.json
  ✓ {name_abbreviated}_review_changelog.md

  Auto-fixed: N issues
  Flagged for reviewer: N issues

  All files saved to ./discovery-reviews/{ticket-id}/
```

Provide a brief summary of the most important findings. If there are critical issues (schema violations, missing required fields, inconsistent program names), highlight them explicitly.

---

## What to Auto-fix vs. Flag

**Auto-fix (change in the output file):**
- JSON syntax errors (trailing commas, missing brackets)
- Curly/smart quotes → straight quotes
- `household_size` not matching member count → update to match
- `birth_year`/`age` inconsistency → fix `birth_year` to match `age`
- Missing `expenses: []` → add it
- Missing `insurance` on a member → add `{"none": true}`
- `is_test`/`agree_to_tos`/`is_13_or_older` not `true` → fix
- `value: 0` on ineligible scenario → remove `value` key
- `value` present on ineligible scenario → remove `value` key
- `website_description` not matching `description_short` → sync them
- Empty `documents: []` or `navigators: []` → remove the key
- County naming convention wrong → fix to match state convention
- Deprecated `age` field in screener field references → note `birth_year` + `birth_month`
- `has_income: false` but `income_streams` is non-empty → fix `has_income` to `true`

**Flag for reviewer (note in changelog, don't change):**
- Description quality / reading level concerns
- Whether a source actually says what the spec claims
- Whether estimated_application_time is realistic
- Whether the benefit value estimate is reasonable
- Whether a category should be reused vs. new
- Whether priority criteria are correctly separated from eligibility
- Missing eligibility criteria (possible omissions)
- Navigator contact info that couldn't be verified
- Links that couldn't be reached (may be false positives)
- Whether `show_in_has_benefits_step` should be `true`
- Whether `base_program` should be set

---

## Error Handling

**Ticket not found:**
```
Error: Ticket {ticket-id} not found in Linear.
Please check the ticket ID and try again.
```

**Missing attachments:**
```
Warning: Only found N of 3 expected files on {ticket-id}.
Missing: [list missing file types]
Proceeding with review of available files.
```

**Unparseable JSON:**
```
Warning: {filename} contains invalid JSON. Attempting to identify and fix syntax errors.
[Show the specific error and location]
```
