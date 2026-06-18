---
name: discovery-review
description: Review the two program researcher artifacts (initial_config.json, spec.md) attached to a Linear ticket for accuracy, format, and completeness. Produces corrected files and a changelog in ./discovery-reviews/{ticket-id}/.
---

# Discovery Review Workflow

Reviews the two program research artifacts attached to a Linear ticket — `[program]_initial_config.json` and `[program]_spec.md` — for accuracy, format, and completeness. Produces corrected versions of each file plus a changelog documenting every change.

The deliverables are now two artifacts: the config and the spec.md. There is no separate validation `.json` artifact — the spec.md **Test Scenarios** are the single source of truth for correctness and are reviewed here for coverage and for committed expected values (no unresolved placeholders).

## Usage

```
/discovery-review MFB-1234
```

If no ticket ID is provided, ask the user for one before proceeding.

---

## Workflow

### Phase 1: Fetch Ticket and Attachments

1. **Fetch the issue** using the Linear MCP tool (`get_issue`) with the provided ticket ID.
2. **Identify the two artifact files** from the ticket description or attachments. The two files are:
   - `[program]_initial_config.json` — program config for DB import
   - `[program]_spec.md` — eligibility criteria, benefit value, test scenarios
3. **Download each attachment** using `get_attachment` for each attachment ID found on the ticket. If attachments are embedded as text/code blocks in the ticket description or comments, extract them from there instead.
4. **Also fetch all comments** using `list_comments` (ordered by `createdAt`, limit 250) — reviewer corrections in comments must be accounted for. If a reviewer has already left corrections, apply those corrections as the baseline before running the review checks below.
5. **Extract `name_abbreviated`** from the config JSON's `program.name_abbreviated` field.
6. **Create the output directory:** `./discovery-reviews/{ticket-id}/` (e.g., `./discovery-reviews/MFB-1234/`).
7. **Save the original files** into the output directory with an `_original` suffix for reference (e.g., `co_snap_initial_config_original.json`).

**Announce what you found:**
```
Ticket: MFB-1234 — CO: Supplemental Nutrition Assistance Program
Program: co_snap
Attachments found: 2
Comments found: N

Saving originals and beginning review...
```

If either of the two files is missing, warn the user and proceed with what's available.

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

#### 2.3 — Household field/enum reference

Reference the test case schema at:
```
benefits-api/validations/management/commands/import_validations/test_case_schema.json
```

This defines valid household field names, enum values (relationships, income stream types, frequencies), and county naming conventions. Even though there is no longer a separate validation `.json` artifact, the spec.md test scenarios describe households using these same conventions — use this reference to sanity-check that the scenarios' member/income/county details are internally valid.

#### 2.4 — County naming conventions

County naming varies by state. From the schema:
- **CO, NC:** Include "County" suffix (e.g., `"Denver County"`, `"Wake County"`)
- **TX, IL:** County name only, no suffix (e.g., `"Travis"`, `"Cook"`)
- **MA:** City names instead of counties (e.g., `"Boston"`, `"Cambridge"`)
- **WA:** Include "County" suffix (e.g., `"King County"`)

Verify all county values in the config and the spec's test scenarios follow the correct convention for their state.

---

### Phase 3: Review `[program]_initial_config.json`

Check each section of the config systematically. For every issue found, record it in the changelog with a concise justification.

#### 3.1 — JSON validity
- Parse the JSON. If it fails, identify the exact error (trailing comma, mismatched brackets, curly quotes, etc.).
- Check for curly/smart quotes that may have come from a word processor.

#### 3.2 — `white_label`
- `code` must be a valid 2-letter state abbreviation or `cesn`. Verify it matches the program's state.

#### 3.3 — `program_category`
- **Confirm-or-define (critical — this fails loudly at import, not silently):** every category referenced by `external_name` must *either* already exist *or* be fully defined in this config. Check the `external_name` against the existing categories from Phase 2.1:
  - If it **already exists** → reference by `external_name` only; flag if it unnecessarily re-specifies `name`, `icon`, `description`, or `tax_category`.
  - If it does **not** exist → the config **must** include `name` + `icon` (and optionally `description`, `tax_category`) so the import creates it. A config that references a non-existent category by `external_name` alone **fails the import outright** (`"Program category '{x}' does not exist. To create a new category, provide: icon, name."`). Discovery review never runs the import, so this looks fine on paper and breaks at implementation/deploy.
  - *Real-world example:* the KS MSP config referenced `program_category: {external_name: "ks_healthcare"}` with no `name`/`icon`, assuming the category existed. It didn't, and the import failed. Do not assume "another program creates it" — either it already exists in Phase 2.1's data, or this config defines it.
  - **State-launch corollary:** when several programs in a batch share a brand-new category, exactly one config should define it (name+icon) and the rest reference it; flag if none of them define it, or if two define the same one with conflicting name/icon.
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
- **Confirm-or-define** (same rule as categories in 3.3): check each `external_name` against Phase 2.1. If it already exists → reference it (reuse). If it does **not** → the config must fully define it (`external_name` + `text`). Don't reference a document by `external_name` alone unless it's confirmed to already exist.
- `link_url` and `link_text` should both be `""` or both populated.

#### 3.6 — `navigators`
- Omit the key entirely if no navigators — flag empty arrays `[]`.
- **Confirm-or-define** (same rule as 3.3): check each `external_name` against Phase 2.1. If it already exists → reference it. If it does **not** → the config must fully define it with all required fields below. Don't reference a navigator by `external_name` alone unless confirmed to already exist.
- Every navigator needs `external_name`, `name`, `email`, `description`, `assistance_link`.
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
   - **Current AND faithful.** Two separate checks, both required:
     - *Recency* — is the cited source the current tax/program year's? (Catches stale links — e.g., a 2010 form cited for a 2025 rate.)
     - *Fidelity* — does the cited document actually **state** the number the spec claims? A correct, current citation is necessary but not sufficient: the number can still be a misread of the right document. For every rate/threshold/percentage, **quote the operative sentence from the source verbatim** next to the value so it can be confirmed at a glance. A paraphrase hides a misread; a quote exposes it.
     - *Real-world example to watch for:* the KS CDCC spec cited the correct, current source (Notice 24-09) but stated "25%" — it read the notice's "prior to amendment, 25%" sentence instead of the "as amended… 50%" sentence in the same document. The actual rate is 50%. A recency check alone would have passed it; only quoting the operative sentence catches this.

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
- **No unresolved placeholders in binding fields.** A scenario's expected result, an eligibility rule, or a benefit value must hold a single committed answer — never a deferral like `verify with PE`, `~$X (estimate)`, `TBD`, "Team to decide," `⚠️ PE verification needed`, or an "X (recommended)… or Y…" fork. These read as finished but aren't: a developer can't build from a fork, so they take the default and the real decision — value verification or a policy call — never happens. Raising the open question during discovery is correct; *leaving it in a binding field* is the failure. Resolve it (compute the value against PolicyEngine per Phase 4.4; make the policy call and write the single answer) or hold the ticket out of To Do until it's resolved.
  - *KS Launch: TANF shipped "⚠️ PE verification needed" scenarios (the disregard question was never resolved); EITC stated every value as "~$X, verify with PE" (all off 10–40%); HCBS Scenario 8 shipped a "Team to decide" fork the implementer silently defaulted.*
  - Checkable form: grep the spec/scenarios for `verify with PE`, `TBD`, `team to decide`, `~$`, `(recommended)`, "estimate," "PE verification needed," and "or … or" expected results — any hit in an eligibility, value, or expected-result field blocks sign-off.

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

6. **Run every scenario through PolicyEngine and diff against the spec (PE-backed programs only).** This is the highest-value check and the one most often skipped. For a PE Custom / PE Federal program you do **not** need our implementation to verify values — the program is `fraction × <PE variable>`, so each scenario's household can be run directly through PolicyEngine (live API or a pinned local install) and compared to the spec's stated expected value/eligibility.
   - Build each spec scenario's household, run the relevant PE variable(s), and record PE's output next to the spec's expected outcome.
   - **Flag every mismatch** — both value drift and eligibility flips. Real cases this catches: estimates off 10–40% (the value was guessed, not computed); an eligibility flip (a non-refundable credit that resolves to $0 because tax liability is fully absorbed); and cases PE *cannot* compute at all (a genuine PE bug — e.g. CDCC attributing $0 expenses to a disabled adult dependent), which become `mfb-policy-engine` fix requests.
   - This is the concrete form of the "PE delta report" acceptance criterion in the [Discovery doc](https://myfriendben.getoutline.com/doc/discovery-y7UDrfmYzN). The separate importable validation suite has been retired, so this scenario-level diff is the **primary** correctness gate — there is no later automated check to fall back on.
   - This applies to **all** spec scenarios (every scenario should be machine-checked against PE — the unchecked ones are exactly where errors hide).
   - Does **not** apply to MFB Custom programs: there is no pre-existing engine to diff against, so their values come from the cited policy data and are verified by the source-fidelity check (Phase 4.1.4) instead. (For MFB Custom programs the scenarios are instead realized as 1:1 unit tests at implementation time.)

---

### Phase 5: (Retired) Validation-Scenarios Review

> The separate `[program].json` validation-scenarios artifact and the importable validation suite have been retired. There is no longer a third file to review here. The spec.md **Test Scenarios** are the single source of truth and are reviewed in **Phase 4.4** for coverage, internal consistency, committed expected values (no placeholders), and — for PE-backed programs — a run-through-PE diff. Skip directly to Phase 6.

The household-level sanity checks that used to live in this phase still apply to the **spec.md scenarios** — fold them into the Phase 4.4 review rather than treating them as a separate file:

- **Internal consistency per scenario:** `household_size` matches the number of members described; each member's `age`/`birth_year`/`birth_month` are consistent (a child with `age: 0` and `birth_year: 2023` is wrong in 2026); one `headOfHousehold`; income amounts realistic; valid relationship/income-stream/frequency conventions (Phase 2.3).
- **Expected results committed:** every scenario states a single committed eligibility outcome and, for eligible scenarios, an **annual** value (no `0`-as-placeholder, no deferral — see Phase 4.3).
- **Cross-file consistency:** scenario households use the program's `white_label.code` (state), and county values follow the state's naming convention (Phase 2.4); expected values are consistent with the benefit-value methodology in the spec.

---

### Phase 6: Screener Field Mapping Check

Using the screener field inventory from `find-screener-fields` (Phase 2.2), perform a field mapping audit:

1. **For each eligibility criterion in the spec**, verify that the screener fields listed are:
   - Real fields that exist in the screener models
   - The best available fields for that check (not proxies when a direct field exists)
   - Using the correct method signatures (e.g., `calc_gross_income("monthly", ["all"])` not just `income`)

2. **Identify unmapped criteria** — any criterion that should reference screener fields but doesn't.

3. **Identify phantom fields** — any field cited in the spec that doesn't exist in the screener models.

4. **Check the spec's test scenarios** — do their household details use only fields/enums that exist (per the reference in Phase 2.3)? Flag any invalid field names.

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

Save corrected versions of both files to `./discovery-reviews/{ticket-id}/`:

- `{name_abbreviated}_initial_config.json` — corrected config
- `{name_abbreviated}_spec.md` — corrected spec

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

## Test Scenarios (in `_spec.md`)

### Auto-fixed
- **Scenario N ([name]):** [what was wrong] → [what it was changed to]. [Why.]

### Flagged for reviewer
- **Scenario N ([name]):** [concern — e.g. coverage gap, unresolved expected value, PE diff]. [Recommendation.]

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
  ✓ {name_abbreviated}_review_changelog.md

  Auto-fixed: N issues
  Flagged for reviewer: N issues

  All files saved to ./discovery-reviews/{ticket-id}/
```

Provide a brief summary of the most important findings. If there are critical issues (schema violations, missing required fields, inconsistent program names), highlight them explicitly.

---

## What to Auto-fix vs. Flag

**Auto-fix (change in the output file):**
- JSON syntax errors in the config (trailing commas, missing brackets)
- Curly/smart quotes → straight quotes
- `website_description` not matching `description_short` → sync them
- Empty `documents: []` or `navigators: []` → remove the key
- County naming convention wrong (in the config or in a spec scenario) → fix to match state convention
- Deprecated `age` field in screener field references → note `birth_year` + `birth_month`
- In a spec scenario: `household_size` not matching the number of members described → update to match
- In a spec scenario: `birth_year`/`age` inconsistency → fix `birth_year` to match `age`

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
Warning: Only found N of 2 expected files on {ticket-id}.
Missing: [list missing file types]
Proceeding with review of available files.
```

**Unparseable JSON:**
```
Warning: {filename} contains invalid JSON. Attempting to identify and fix syntax errors.
[Show the specific error and location]
```
