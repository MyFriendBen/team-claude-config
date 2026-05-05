---
name: linear-to-files
description: Pull a Linear ticket and its comments, synthesize the initial drafts and all subsequent reviewer updates, and generate the three program files ready for dev implementation — [program]_spec.md, [program]_initial_config.json, and [program].json (validation scenarios).
---

# Linear → Program Files Workflow

Reads a Linear ticket produced by the Program Researcher, synthesizes all comments (initial drafts + reviewer corrections) into their final merged state, and writes three output files: a spec, a config JSON, and a validation scenarios JSON.

## Usage

```
/linear-to-files MFB-778
```

If no ticket ID is provided, ask the user for one before proceeding.

---

## Workflow

### Phase 1: Fetch Ticket and Comments

1. **Fetch the issue** using the Linear MCP tool with the provided ticket ID.
2. **Fetch all comments** ordered by `createdAt` ascending (oldest first). Use limit 250 to ensure you get them all; paginate if `hasNextPage` is true.
3. **Extract the `name_abbreviated`** — this is the file prefix. Look for it in:
   - A JSON block in any comment that contains an `initial_config` draft (the `program.name_abbreviated` field, e.g. `wa_wsos`)
   - If not found, derive it from the ticket title (e.g. "WA: Washington State Opportunity Scholarship" → `wa_wsos`)
4. **Announce what you found:**
   ```
   Ticket: MFB-778 — WA: Washington State Opportunity Scholarship
   Program prefix: wa_wsos
   Comments found: 14
   
   Reading comments to identify drafts and updates...
   ```

---

### Phase 2: Parse Comments

Read each comment body carefully and categorize it. Comments fall into several types:

**Initial draft comments** — typically posted by an AI researcher or program researcher. These contain the raw first-pass content for one or more of the three files. Look for:
- Large JSON blocks → this is the `initial_config.json` or `validation_scenarios.json` draft
- Numbered eligibility criteria lists with sub-bullets → this is the `spec.md` draft
- Numbered test scenario descriptions with "Steps," "Expected," "Why this matters" → these are spec test scenario narratives
- Household JSON objects with `notes`, `household`, `expected_results` keys → these are validation scenario JSON objects

**Reviewer update comments** — posted by human reviewers (typically after the initial drafts). These contain corrections, feedback, and amendments. Look for:
- Numbered lists reviewing the initial criteria one by one
- Specific field-by-field corrections (e.g. "Year: Update from 2025 to 2026")
- Notes like "REMOVE," "KEEP," "KEEP BUT REVISE," "INCORRECT," "CORRECT"
- Income threshold corrections
- Scenario-level decisions (KEEP / KEEP BUT REVISE / REMOVE)

**Important — scenario prioritization comments:** Reviewers sometimes follow up with a comment calling out 2–3 scenarios as the "core" or "most representative" ones. **Ignore this prioritization entirely.** All scenarios marked KEEP or KEEP BUT REVISE (across all reviewer comments) must be included in both the spec.md and the .json file. Prioritization comments are personal preference notes — they do not override the KEEP/REMOVE decisions made in the main review comment.

**Action/instruction comments** — short comments like "@elliott generate files" — ignore these for content purposes.

Build a mental model of the **final state** of each file by applying all reviewer updates on top of the initial drafts.

---

### Phase 3: Synthesize the Three Files

Using the initial drafts and all reviewer amendments, generate the final versions of each file. Apply ALL corrections from reviewer comments — later comments take precedence over earlier ones.

#### 3.0 — Pre-flight: Compile existing categories and documents from fixture files

Before generating the config, read all existing program config fixture files to get the full list of `program_category` and `document` `external_name` values already in the database. This prevents the skill from inventing new names for things that already exist.

**Find the fixture directory:**
```
programs/management/commands/import_program_config_data/data/
```
Use Glob to find all `.json` files in that directory, then read each one.

---

**Step A — Program categories**

From each fixture file, extract the `program_category` object. Collect all unique `external_name` values. Note which ones have a full definition (with `name`, `icon`, etc.) vs. which appear with `external_name` only (meaning they already exist in the DB and don't need re-defining).

When writing the `program_category` block in the config:
- If an existing category is the right fit (same domain — food, cash, health care, housing, transportation, child care, tax credits, education, etc. — for the same state or a reusable generic one), use `external_name` only. Do NOT re-specify `name`, `icon`, or other fields for a category that already exists.
- Only include `name`, `icon`, and optionally `description` and `tax_category` if this is a genuinely new category with no existing match.
- Follow the naming convention `{state}_{category_type}` (e.g. `wa_education`, `wa_housing`).
- In the generation summary, note whether the category was reused or newly created, and if new, flag that the icon value should be confirmed with a dev (valid icons seen in the codebase: `cash`, `food`, `health_care`, `housing`, `transportation`, `child_care`, `tax_credit` — an education or other new icon may need to be added).

---

**Step B — Documents**

From each fixture file, extract any entries in the `documents` array. Collect all unique `external_name` values into a reference list.

When writing the `documents` array in the config:
- First check whether an existing `external_name` is a close enough match (same document type, same intended use). If yes, reuse it — keep the existing `external_name` and write appropriate `text` for this program.
- Only invent a new `external_name` (following the `{program}_{doc_type}` convention) if no existing entry is a reasonable fit.
- In the generation summary, note which document names were reused vs. newly created.

#### 3.1 — `[name_abbreviated]_initial_config.json`

Generate valid JSON matching the schema below. Apply any reviewer corrections to fields (year, description, legal_status_required, estimated values, etc.).

**Complete schema and field reference:**

```json
{
  "white_label": {
    "code": "<2-letter state code or 'cesn'>"
  },
  "program_category": {
    "external_name": "<state>_<category>"
    // IMPORTANT: check existing categories (step 3.0A) first.
    // If this category already exists in the DB, use external_name ONLY.
    // Only add name/icon/description/tax_category if this is a genuinely new category.
  },
  "program": {
    "name_abbreviated": "<snake_case program ID>",
    "external_name": "<state>_<name_abbreviated>",  // omit if fine to auto-generate
    "year": 2026,  // ONLY include if program uses FPL-based income tests
    "legal_status_required": [
      "citizen", "non_citizen", "refugee", "gc_5plus", "gc_5less", "otherWithWorkPermission"
      // Include all 6 if no immigration restriction. Subset if restricted.
    ],
    "name": "<Official Program Name (ACRONYM if commonly used)>",
    "description_short": "<One-line teaser, ~120 chars max, no period>",
    "description": "<Full description, ~4 paragraphs, \\n\\n for breaks. Middle school reading level. NEVER describe eligibility criteria — not income limits, not age requirements, not residency rules, not enrollment requirements, nothing. The screener handles eligibility checks; the description should explain what the program is, how the benefit works, any helpful context about administration or application, and next steps.>",
    "learn_more_link": "https://...",
    "apply_button_link": "https://...",
    "apply_button_description": "",  // "" defaults to "Apply Now"
    "estimated_application_time": "<plain language, e.g. '30 to 60 minutes'>",
    "estimated_delivery_time": "",  // "" if unknown
    "estimated_value": "",  // "" for programs with a calculator
    "value_format": null,  // null=monthly, "lump_sum", or "estimated_annual"
    "website_description": "<same as description_short>",
    "base_program": null,  // see valid values list below
    "show_on_current_benefits": true,
    "has_calculator": true,
    "show_in_has_benefits_step": false
  },
  "documents": [
    // Omit this key entirely if no documents. Do NOT include empty array.
    // IMPORTANT: Always check existing external_name values (step 3.0) before inventing a new one.
    {
      "external_name": "<reuse existing name if applicable, else {program}_{doc_type}>",
      "text": "<user-facing label, specific and actionable>",
      "link_url": "",  // "" if no link
      "link_text": ""  // "" if no link
    }
  ],
  "navigators": [
    // Omit this key entirely if no navigators. Do NOT include empty array.
    {
      "external_name": "<org_identifier>",
      "name": "<Official org name>",
      "email": "<contact email>",
      "description": "<1-2 sentences about who they help>",
      "assistance_link": "https://...",
      "phone_number": "+1XXXXXXXXXX",  // E.164 format, omit if unknown
      "counties": ["County Name"],  // omit if statewide
      "languages": ["en", "es"]  // omit if English only
    }
  ]
  // "warning_message": omit entirely if not needed
  // If needed:
  // "warning_message": {
  //   "external_name": "<program>_notice",
  //   "calculator": "_show",
  //   "message": "<text shown to users>"
  // }
}
```

**Valid `base_program` values:** `"aca"`, `"ccap"`, `"chp"`, `"csfp"`, `"ctc"`, `"early_head_start"`, `"eitc"`, `"head_start"`, `"liheap"`, `"lifeline"`, `"medicaid"`, `"medicare_savings"`, `"nfp"`, `"nslp"`, `"oap"`, `"section_8"`, `"snap"`, `"ssi"`, `"ssdi"`, `"tanf"`, `"wap"`, `"wic"`. Use `null` for novel programs.

**Key rules to follow:**
- Omit `documents`, `navigators`, and `warning_message` keys entirely when empty — do NOT use empty arrays or objects
- `estimated_value` should almost always be `""` for programs with a calculator
- `value_format`: use `null` for monthly recurring, `"lump_sum"` for one-time, `"estimated_annual"` for annual
- The `description` should NOT include specific dollar thresholds or eligibility numbers — those belong in the spec
- `apply_button_description`: use `""` (defaults to "Apply Now"), `"Learn More"` if informational only, or something specific like `"Find Provider"` if warranted

---

#### 3.2 — `[name_abbreviated]_spec.md`

Generate a markdown document structured as follows. Incorporate all reviewer corrections to criteria, sources, benefit value, and test scenarios.

```markdown
# [Program Full Name] — Implementation Spec

**Program:** `[name_abbreviated]`
**State:** [State]
**White Label:** [code]
**Research Date:** [date from comments]

---

## Eligibility Criteria

[Numbered list. Each criterion formatted as:]

1. **[Criterion name]**
   - Screener fields: `[field1]`, `[field2]` (or `none` if data gap)
   - Note: [Any relevant context, assumptions, or data gap handling]
   - Source: [Citation with specific section, e.g. "10 CFR 440.22(a)(3)"; must be .gov or legal site]

[For data gaps, mark with ⚠️ *data gap* after the criterion name]

---

## Priority Criteria

[If applicable — criteria that affect who gets served first, not eligibility itself]

---

## Benefit Value

[Explain the benefit value methodology:]
- Fixed amounts: state the value and cite source
- Variable amounts: explain the calculation methodology
- Insurance: how value is estimated
- In-kind: reasoning and estimate with citations
- State whether values are citable or informed estimates

---

## Test Scenarios

Include ALL scenarios that reviewers marked KEEP or KEEP BUT REVISE, with revisions applied. Do not omit any approved scenario. Do not prioritize some over others. For each scenario:

**Scenario [N]: [Scenario name]**
- What's being tested: [brief description]
- Expected result: eligible / ineligible
- Key household details: [income, size, relevant member attributes]
- Revisions applied: [list any reviewer corrections made to this scenario, or "none"]
```

**Rules for eligibility criteria:**
- Include ONLY real eligibility requirements — not administrative requirements (ID, interviews, proof of X — those go in `documents`), not priority criteria (those get their own section), not application deadlines
- Every criterion needs a source that is a `.gov` or legal site (e.g. `law.cornell.edu`) — NOT third-party summary sites
- Data gaps must explain the assumption being made (inclusivity assumption = we assume all households pass that check)
- Apply ALL reviewer corrections: removed criteria, corrected thresholds, added sources, etc.

---

#### 3.3 — `[name_abbreviated].json`

Generate a JSON array containing **all scenarios that reviewers marked KEEP or KEEP BUT REVISE**, with all requested revisions applied. Remove only those explicitly marked REMOVE. Do not artificially reduce the count — the goal is to encode every approved scenario.

The initial draft comments typically contain the full list of scenarios (often 10–15). Reviewer comments then sort them into three buckets:
- **KEEP** — encode as-is (applying any other numeric/threshold corrections from earlier reviewer comments)
- **KEEP BUT REVISE** — encode with the specific changes the reviewer described
- **REMOVE** — omit entirely

If a later reviewer comment calls out 3 specific scenarios as the "core" or "representative" set, that is guidance for the **spec.md test scenarios section only** — it is not a signal to delete the other approved scenarios from the .json file.

```json
[
  {
    "notes": "<Clear description of what's being tested>",
    "household": {
      "white_label": "<state_code>",
      "is_test": true,
      "agree_to_tos": true,
      "is_13_or_older": true,
      "zipcode": "<valid in-state ZIP>",
      "county": "<County name only — no 'County' suffix, e.g. 'King' not 'King County'>",
      "household_size": <number — MUST match number of household_members>,
      "household_assets": <number>,
      "household_members": [
        {
          "relationship": "headOfHousehold",
          "age": <number>,
          "birth_year": <year — must be consistent with age>,
          "birth_month": <1-12>,
          "has_income": <true|false>,
          "income_streams": [
            {
              "type": "wages",
              "amount": <number>,
              "frequency": "monthly"
            }
          ],
          "insurance": { "none": true }
        }
      ],
      "expenses": []
    },
    "expected_results": {
      "program_name": "<name_abbreviated — must exactly match config>",
      "eligible": <true|false>
      // "value": <number> — ONLY include for eligible scenarios, omit for ineligible
    }
  }
]
```

**Field rules:**
- `household_size` MUST exactly equal the number of entries in `household_members`
- `birth_year` and `age` must be internally consistent (use today's year to compute)
- `value` in `expected_results`: include ONLY for eligible scenarios — omit entirely for ineligible (do not set to 0)
- `expenses` must always be present as `[]`
- Every household member must have an `insurance` object
- `program_name` must exactly match `name_abbreviated` in the config — case-sensitive
- `is_test`, `agree_to_tos`, `is_13_or_older` are always `true`
- Every household must have a `"relationship": "headOfHousehold"` member

**Across all scenarios, the full set should NOT:**
- Contain duplicate scenarios or ones with variation irrelevant to the program's eligibility rules
- Use FPL/AMI/MFI values from the wrong year (use the `year` from the config, or current year if not set)

**The spec.md test scenarios section** (distinct from the .json) is where you describe 3 representative scenarios in prose — the "golden path" eligible, the primary ineligible, and the key edge case. Those 3 are for human readability and quick orientation. The .json file is the full validation suite and should be larger.

---

### Phase 4: Write and Present Files

1. **Save all four files** to the current project directory:
   - `[name_abbreviated]_spec.md`
   - `[name_abbreviated]_initial_config.json`
   - `[name_abbreviated].json`
   - `[name_abbreviated]_changelog.md`

2. **The changelog** (`[white_label]_[name_abbreviated]_changelog.md`) is a record of everything the skill did. Structure it as:

```markdown
# [Program Name] — Generation Changelog

**Ticket:** [ticket ID]
**Program:** `[name_abbreviated]`
**Generated:** [date]

---

## Pre-flight: Existing Categories

- `[external_name]` — [REUSED / NEW: reason]

---

## Pre-flight: Existing Documents

- `[external_name]` — [REUSED / NEW: reason]

---

## Reviewer Corrections Applied

[For each correction from reviewer comments:]
- **[Field or criterion]:** [what changed and which comment it came from]

[If no reviewer corrections:]
> ⚠️ No reviewer corrections found on this ticket. Files are based on initial draft only and may need additional human review.

---

## Skill Rule Fixes Applied

[Issues caught and fixed by the skill's own rules, independent of reviewer comments:]
- **[Field or issue]:** [what was wrong and what was changed]
```

3. **Present a summary:**
   ```
   Files generated for wa_wsos (MFB-778):

   ✓ wa_wsos_spec.md
   ✓ wa_wsos_initial_config.json
   ✓ wa_wsos.json
   ✓ wa_wsos_changelog.md
   ```

4. **Provide download links** to each file so the user can open them directly.

---

## Handling Ambiguity

**Multiple conflicting updates:** Later comments override earlier ones. If two reviewer comments contradict each other, use the most recent one and note the conflict in your summary.

**Partial updates:** If a reviewer comment says "fix criterion 3 but keep the rest," apply only that fix and leave others as-is from the initial draft.

**Unclear content:** If a comment's intent is unclear (e.g. it's a general question rather than a correction), skip it for synthesis purposes but note it in your summary.

**Missing initial draft:** If a comment thread has no initial draft for one of the three files (e.g. no config JSON was posted), generate that file as best you can from the spec and other context, and note that it was inferred rather than extracted.

**No reviewer updates:** If there are only initial drafts and no reviewer corrections, use the initial drafts as-is but note this in the summary — the files may need additional human review.

---

## Error Handling

**Ticket not found:**
```
Error: Ticket MFB-XXX not found in Linear.
Please check the ticket ID and try again.
```

**No comments with file content:**
```
Warning: No initial drafts found in comments for MFB-XXX.
Comments found: [N]
The ticket description or comments don't appear to contain program research output.
Is this the right ticket?
```

---

## Notes

- The `name_abbreviated` from the config is the canonical file prefix — use it exactly
- Reviewer comments often number their feedback to match criteria numbers — use these to precisely apply corrections
- Comments marked "REMOVE" for a criterion mean remove it from the output entirely
- Comments marked "DATA GAP" mean add ⚠️ *data gap* and handle as described above
- The three output files are what a dev will pick up to implement the program — they must be complete and accurate
