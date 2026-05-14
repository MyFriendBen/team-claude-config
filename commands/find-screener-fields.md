---
name: find-screener-fields
description: Takes a program spec.md file and maps each eligibility criterion to the relevant screener fields, flags data gaps, and recommends how to implement the check in the calculator.
usage: /find-screener-fields
example: /find-screener-fields
---

<command-name>find-screener-fields</command-name>

# Find Screener Fields — Spec Mapping Workflow

Given a program `spec.md`, this skill walks through each eligibility criterion and tells you exactly which screener fields to use, which criteria have data gaps, and what assumptions to document.

---

## Step 1: Get the Spec

Ask the user:

> Please provide the `spec.md` file for the program you want to map. You can either:
> - Paste the full content directly into the chat, or
> - Give me the file path (e.g. `benefits-api/programs/programs/co/leap/spec.md`) and I'll read it.

Read the file if a path is given. Confirm the program name, state, and white label before proceeding.

---

## Step 2: Parse the Eligibility Criteria

Extract every numbered criterion from the `## Eligibility Criteria` section of the spec. For each criterion record:

- The criterion number and plain-language summary
- Any screener fields already cited in the spec (look for `Screener fields:` lines)
- Whether the criterion is already flagged as a data gap (`⚠️ data gap`)
- Any notes or caveats the spec author included

Do not skip criteria that are already marked as data gaps — they still need a recommendation.

---

## Step 3: Map Each Criterion to Screener Fields

For each criterion, reason through the full screener field inventory below and recommend the best available fields. Apply the mapping rules that follow.

### Complete Screener Field Inventory

**Screen (household level)**

| Field | What it captures |
|---|---|
| `zipcode` | 5-digit ZIP code |
| `county` | County name |
| `household_size` | Number of people in household (max 8) |
| `housing_situation` | Housing type (renting, owning, homeless, shelter, etc.) |
| `household_assets` | Total household assets in dollars |
| `last_tax_filing_year` | Tax year most recently filed (currently unused in most calculators) |
| `has_benefits` | Whether household has any current benefits (`"true"` / `"false"` / `"preferNotToAnswer"`) |
| `has_snap` | Currently has SNAP |
| `has_wic` | Currently has WIC |
| `has_tanf` | Currently has TANF |
| `has_ssi` | Currently has SSI |
| `has_ssdi` | Currently has SSDI |
| `has_medicaid` | Currently has Medicaid |
| `has_aca` | Currently has ACA marketplace insurance |
| `has_chp` | Currently has CHP+ / CHIP |
| `has_nslp` | Currently has National School Lunch Program |
| `has_head_start` | Currently has Head Start |
| `has_early_head_start` | Currently has Early Head Start |
| `has_csfp` | Currently has Commodity Supplemental Food Program |
| `has_ccdf` | Currently has Child Care and Development Fund |
| `has_section_8` | Currently has Section 8 housing voucher |
| `has_pell_grant` | Currently has Pell Grant |
| `has_nfp` | Currently has Nurse-Family Partnership |
| `has_eitc` | Currently has federal EITC |
| `has_ctc` | Currently has federal Child Tax Credit |
| `has_lifeline` | Currently has Lifeline (phone/internet discount) |
| `has_acp` | Currently has Affordable Connectivity Program |
| `has_sunbucks` | Currently has Summer EBT / Sun Bucks |
| `has_employer_hi` | Has employer health insurance |
| `has_private_hi` | Has private health insurance |
| `has_medicaid_hi` | Has Medicaid (alternate insurance flag) |
| `has_medicare_hi` | Has Medicare |
| `has_chp_hi` | Has CHP+ insurance |
| `has_no_hi` | Has no health insurance |
| `has_va` | Has VA health benefits |
| *(state-specific `has_*` fields)* | See screener-fields-reference.md for the full list by state |
| `needs_food` | Self-reported need: food |
| `needs_baby_supplies` | Self-reported need: baby supplies |
| `needs_housing_help` | Self-reported need: housing |
| `needs_mental_health_help` | Self-reported need: mental health |
| `needs_child_dev_help` | Self-reported need: child development |
| `needs_funeral_help` | Self-reported need: funeral assistance |
| `needs_family_planning_help` | Self-reported need: family planning |
| `needs_job_resources` | Self-reported need: job resources |
| `needs_dental_care` | Self-reported need: dental care |
| `needs_legal_services` | Self-reported need: legal services |
| `needs_college_savings` | Self-reported need: college savings |
| `needs_veteran_services` | Self-reported need: veteran services |
| `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `utm_id` | Analytics tracking only — not used in eligibility |
| `referral_source`, `referrer_code`, `path` | Session metadata — not used in eligibility |

**HouseholdMember (per person)**

| Field | What it captures |
|---|---|
| `relationship` | Relationship to head of household: `headOfHousehold`, `spouse`, `domesticPartner`, `child`, `fosterChild`, `parent`, `fosterParent`, `stepParent`, `grandParent`, `grandChild`, `sibling`, `other` |
| `birth_year` + `birth_month` | Date of birth — use together to calculate precise age |
| `age` | Age in years — deprecated, present only on old screens |
| `pregnant` | Currently pregnant |
| `disabled` | Has a disability (general) |
| `visually_impaired` | Blind or visually impaired |
| `long_term_disability` | Has a long-term disability (12+ months) |
| `medicaid` | Receives Medicaid (per-member) |
| `disability_medicaid` | Receives Medicaid specifically due to disability |
| `veteran` | Is a U.S. military veteran |
| `unemployed` | Currently unemployed |
| `worked_in_last_18_mos` | Has worked in the last 18 months |
| `is_care_worker` | Is a paid care worker |
| `student` | Is a student |
| `student_full_time` | Is a full-time student |
| `student_job_training_program` | Is in a job training program |
| `student_has_work_study` | Has a work-study position |
| `student_works_20_plus_hrs` | Works 20+ hours/week while a student |
| `has_income` | Has any income (top-level flag) |
| `has_expenses` | Has any expenses (top-level flag) |

**IncomeStream (per income source per person)**

| Field | What it captures |
|---|---|
| `type` | Income type: `wages`, `selfEmployment`, `sSI`, `sSID` (SSDI), `unemployment`, `pension`, `veteran`, `childSupport`, `alimony`, `investment`, `rental`, `other` |
| `category` | Broad income category |
| `amount` | Dollar amount per pay period |
| `frequency` | Pay frequency: `monthly`, `weekly`, `biweekly`, `semimonthly`, `yearly`, `hourly` |
| `hours_worked` | Hours per week (for hourly income only) |
| `calc_gross_income(frequency, types)` | Computed method on Screen/HouseholdMember — sums income by type and converts to requested frequency |

**Expense (per expense per household)**

| Field | What it captures |
|---|---|
| `type` | Expense type: `rent`, `mortgage`, `childcare`, `medical`, `businessExpenses`, `propertyTax`, `utilities`, `homeInsurance` |
| `amount` | Dollar amount per pay period |
| `frequency` | Pay frequency |
| `calc_expenses(frequency, types)` | Computed method — sums expenses by type and converts to requested frequency |

**Insurance (per person)**

| Field | What it captures |
|---|---|
| `none` | Has no insurance |
| `dont_know` | Doesn't know their insurance status |
| `employer` | Employer-provided insurance |
| `private` | Privately purchased insurance |
| `medicaid` | Medicaid |
| `medicare` | Medicare |
| `chp` | CHIP / CHP+ |
| `emergency_medicaid` | Emergency Medicaid only |
| `family_planning` | Family planning coverage only |
| `va` | VA coverage |
| `mass_health` | MassHealth (MA combined Medicaid/CHIP) |

**EnergyCalculatorScreen (only present on energy calculator flows)**

| Field | What it captures |
|---|---|
| `is_home_owner` | Owns their home |
| `is_renter` | Rents their home |
| `electric_provider` | Electric utility code |
| `electric_provider_name` | Electric utility human-readable name |
| `gas_provider` | Gas utility code |
| `gas_provider_name` | Gas utility human-readable name |
| `electricity_is_disconnected` | Electricity shut off |
| `has_past_due_energy_bills` | Has overdue energy bills |
| `has_old_car` | Has a car made before 1996 |
| `needs_water_heater` | Needs water heater |
| `needs_hvac` | Needs HVAC |
| `needs_stove` | Needs stove |
| `needs_dryer` | Needs dryer |

**EnergyCalculatorMember (per person, only on energy calculator flows)**

| Field | What it captures |
|---|---|
| `surviving_spouse` | Is a surviving spouse of a veteran |
| `receives_ssi` | Receives SSI |
| `medical_equipment` | Requires electric medical equipment at home |

---

### Mapping Rules

Apply these rules when recommending fields for each criterion:

**Income tests**
- Use `calc_gross_income("monthly", ["all"])` or `calc_gross_income("yearly", ["all"])` for total gross income.
- Use `calc_gross_income(freq, ["wages", "selfEmployment"])` for earned income only.
- Use `calc_gross_income(freq, ["sSI", "sSID", "pension", ...])` to isolate unearned income types.
- Use `calc_net_income(freq, income_types, expense_types)` when the program deducts certain expense types.
- Always pair income checks with `household_size` when a Federal Poverty Level (FPL) threshold is involved.

**Asset tests**
- Use `household_assets`. Note: this is a household-level total and may include non-eligible members' assets — flag this as a potential data gap for programs that test assets per applicant or per couple only.

**Age checks**
- Use `birth_year` + `birth_month` (not `age`) for precise age calculation. `age` is deprecated.
- For programs with age ranges or cutoffs keyed to birth year (e.g., Social Security full retirement age), note that the calculator must use the birth-year schedule, not a fixed age.

**Disability**
- `disabled` = general disability
- `long_term_disability` = long-term / expected to last 12+ months — closer match for SSA definitions
- `visually_impaired` = blindness / visual impairment (relevant for programs with a separate blind threshold, e.g., SSDI SGA)
- `disability_medicaid` = specifically on Medicaid due to disability

**Current enrollment (categorical eligibility)**
- When a program grants automatic eligibility to recipients of another program, use the relevant `has_*` field on the Screen (e.g., `has_ssi`, `has_tanf`, `has_snap`).
- When enrollment in a program disqualifies a person, use the same `has_*` field to filter them out.

**Housing**
- Use `housing_situation` for general housing type.
- Use `EnergyCalculatorScreen.is_home_owner` / `is_renter` for energy programs.
- Use `has_section_8` if the criterion involves current housing voucher status.

**Children and family structure**
- Child presence: count `HouseholdMember` records where `relationship` is `child`, `fosterChild`, or `grandChild` and age is within the program's definition of qualifying child.
- Pregnancy: `pregnant` on HouseholdMember.
- Marriage / joint filing: check for a member with `relationship` of `spouse` or `domesticPartner`.
- Guardian count: use `screen.num_guardians()`.

**Student status**
- Use `student` for basic student presence.
- Use `student_full_time` for programs that require full-time enrollment.
- Use `student_job_training_program`, `student_has_work_study`, `student_works_20_plus_hrs` for SNAP student exemptions and similar rules.

**Veterans**
- `veteran` on HouseholdMember for general veteran status.
- `EnergyCalculatorMember.surviving_spouse` for surviving-spouse-specific rules.

**Work history**
- `unemployed` = currently unemployed.
- `worked_in_last_18_mos` = employment in recent 18-month window.
- No field captures lifetime work history or Social Security work credits — always flag this as a data gap for SSDI, SSI, and similar programs.

**Insurance**
- Use the `Insurance` model fields per member for per-person insurance status.
- Use Screen-level `has_*_hi` fields when asking about the household's existing insurance rather than per-person coverage.

**Geographic eligibility**
- Use `zipcode` and `county` to establish location. The calculator typically enforces white-label matching rather than re-checking the ZIP, but cite both fields for residency criteria.

---

## Step 4: Identify Data Gaps

For every criterion that cannot be fully evaluated with available fields, write a data gap entry containing:

1. **What's missing** — which real-world fact the screener doesn't capture
2. **Inclusivity assumption** — the safe default (almost always: assume the person meets this criterion unless proven otherwise)
3. **Suggested improvement** — a concrete screener question that would close the gap, if one exists

Common data gaps to watch for:
- Work history / Social Security credits (no field exists)
- Whether an applicant is claimed as a dependent on another tax return (no field)
- Criminal justice / incarceration status (no field — do not suggest adding one)
- Immigration/citizenship status (no field — do not suggest adding one; flag as a data gap only)
- Whether a disability began before a specific age (no field)
- Specific medical conditions or diagnoses (no field)
- Whether income is from a Social Security-covered job (no field)
- Marital history (no field beyond current relationship status)

---

## Step 5: Deliver the Mapping

Present your findings in this exact structure:

---

### Program: [Program Name] ([State])

#### Criterion-by-Criterion Field Map

For each criterion:

**Criterion N — [plain-language summary]**
- **Fields to use:** list the specific field names
- **How to use them:** one sentence explaining the check (e.g., "Sum `calc_gross_income('monthly', ['all'])` and compare to the FPL table for `household_size`")
- **Data gap:** Yes / No — and if Yes, state the assumption and any suggested improvement
- **Notes:** any spec caveats worth carrying into the implementation

#### Summary Table

| Criterion | Fields | Data Gap? |
|---|---|---|
| 1. [short label] | `field_a`, `field_b` | No |
| 2. [short label] | `field_c` | Yes — assume eligible |
| ... | ... | ... |

#### Fields Not in the Screener

List any fields cited in the original spec that do not exist in the screener model (e.g., `filing_status`, `medical_condition`). For each, note:
- Whether an existing field is a reasonable proxy
- Whether the spec's data gap note already handles it
- Whether a new screener field should be proposed

#### Already-Has Check

Identify the `has_*` field on the Screen that corresponds to this program (e.g., `has_snap` for SNAP). This field must be used to suppress the program from results for households that already have it. If no matching field exists, flag it so one can be added.

---

## Step 6: Offer Next Steps

After delivering the mapping, ask:

> Would you like me to:
> 1. Draft the eligibility calculator method stubs with these fields wired in?
> 2. Flag which of these fields are already in the screener reference doc vs. need to be added?
> 3. Move on to a different spec?
