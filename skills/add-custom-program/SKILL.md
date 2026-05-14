---
name: add-custom-program
description: Implements a new custom ProgramCalculator in benefits-api from three research artifacts (initial_config.json, spec.md, validation .json). Use this skill whenever the user wants to implement a new benefit program with a custom calculator, add a program from a Linear ticket, or mentions implementing a program from research/discovery artifacts. Also use when the user says "add program", "implement calculator", or references a ticket with program research files.
---

<command-name>add-custom-program</command-name>

# Add Custom Program Calculator

Implements a new custom `ProgramCalculator` in `benefits-api` from three research artifacts produced during Discovery. Takes either a Linear ticket ID or local file paths as input.

The three artifacts are:
- `[name_abbreviated]_initial_config.json` — program metadata, documents, navigators, warning messages
- `[name_abbreviated]_spec.md` — eligibility criteria, benefit value methodology, test scenarios
- `[name_abbreviated].json` — validation scenarios (household JSON + expected results)

## Phase 1: Gather Inputs

Ask the user how they want to provide the artifacts:

> How would you like to provide the program files?
> 1. **Linear ticket** — I'll fetch the attachments from a ticket ID
> 2. **Local files** — Point me to the three files on disk

### Option 1: Linear Ticket

1. Fetch the ticket with `mcp__Linear__get_issue`
2. Extract:
   - **Branch name** — from the `branchName` field on the issue object
   - **Spec markdown**, **initial config JSON**, and **validation scenarios JSON** — from ticket attachments
     - If the MCP response includes attachment URLs, fetch them. Write all three files exactly as-is — do not summarize, paraphrase, or reformat.
     - If attachments can't be fetched automatically, ask the user to paste the file contents
3. If any piece is missing, prompt the user before continuing

### Option 2: Local Files

Ask the user for the paths to the three files. Read each one and confirm you have all three before proceeding.

### After gathering inputs

1. Derive the **state code** (e.g. `tx`, `co`, `il`) and **program name** in snake_case (e.g. `hse`, `ccad`) from the config's `white_label.code` and `program.name_abbreviated`.
2. In `benefits-api/`, create or switch to a feature branch:
   ```bash
   git checkout -b {username}/mfb-{ticket}-implement-{program_name}
   # or if the branch already exists:
   git checkout {branch-name}
   ```

## Phase 2: Place Research Files

Write (or move) the three artifacts to their canonical locations in the repo:

**Initial config:**
```
programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
```

**Spec:**
```
programs/programs/{state}/{program}/spec.md
```

**Validation scenarios:**
```
validations/management/commands/import_validations/data/{state}_{program}.json
```

Commit (stage specific files, not `git add .` or `git add -A`, to avoid picking up unrelated changes from auto-formatters):
```
git add programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
git add programs/programs/{state}/{program}/spec.md
git add validations/management/commands/import_validations/data/{state}_{program}.json
git commit -m "Add {state} {program} research files"
```

## Phase 3: Implement the Calculator

This is the core implementation step. Read the spec.md carefully — it contains the eligibility criteria, benefit value methodology, and data gaps that drive every decision in the calculator.

### 3.1 Study existing patterns

Before writing any code, read 2–3 existing calculators to absorb the project's conventions. Good references by complexity:

- **Simple** (fixed value, 1–2 conditions): `programs/programs/co/cash_back/calculator.py`
- **Medium** (FPL income test, member + household conditions): `programs/programs/tx/ccad/calculator.py`
- **Complex** (categorical eligibility, date ranges, pregnancy): `programs/programs/federal/trump_account/calculator.py`

Also read:
- `programs/programs/calc.py` — the base `ProgramCalculator` class, `Eligibility`, `MemberEligibility`
- `programs/programs/messages.py` — message helpers for conditions (income, location, age, etc.)
- The state's existing `__init__.py` to see how calculators are registered

### 3.2 Create the calculator directory

```bash
mkdir -p programs/programs/{state}/{program}
touch programs/programs/{state}/{program}/__init__.py
```

### 3.3 Write the calculator

Create `programs/programs/{state}/{program}/calculator.py`.

The calculator is a subclass of `ProgramCalculator`. Map spec criteria to overrides:

| Spec says | Override | Pattern |
|-----------|----------|---------|
| Household-level condition (income, location, assets) | `household_eligible(self, e: Eligibility)` | `e.condition(bool_expr, messages.xxx())` |
| Per-member condition (age, disability, pregnancy) | `member_eligible(self, e: MemberEligibility)` | `e.condition(bool_expr)` |
| Fixed benefit for the whole household | Class attribute `amount = N` (**annual**) | Or override `household_value()` — return annual value |
| Per-member benefit amount | Class attribute `member_amount = N` (**annual**) | Or override `member_value(member)` — return annual value |
| Variable benefit (depends on member attributes) | Override `member_value(member)` or `household_value()` | Return different amounts based on conditions |
| Custom value assignment (e.g. per eligible member) | Override `value(self, e: Eligibility)` | Iterate `e.eligible_members` and set `.value` |

### Available APIs

Before writing the calculator, understand the objects you have access to:

**`self.screen` (Screen object):**
```python
self.screen.household_size                              # int
self.screen.county                                      # str (or city name in MA)
self.screen.zipcode                                     # str
self.screen.household_assets                            # int or None — always guard against None
self.screen.household_members.all()                     # QuerySet of HouseholdMember
self.screen.num_children(age_max=18, child_relationship=["child", ...])  # int
self.screen.get_head()                                  # HouseholdMember (head of household)
self.screen.calc_gross_income(frequency, types, exclude=[])  # float — screen-level (all members)
self.screen.calc_expenses(frequency, types)             # float
self.screen.has_expense(["rent", "mortgage"])            # bool
self.screen.has_benefit("snap")                         # bool — canonical way to check benefits
```

**HouseholdMember attributes:**
```python
member.age                          # int or None — always check for None before comparisons
member.relationship                 # str: "headOfHousehold", "spouse", "domesticPartner",
                                    #       "child", "stepChild", "fosterChild", "grandChild",
                                    #       "parent", "sibling", "other"
member.pregnant                     # bool
member.disabled                     # bool (general disability flag)
member.visually_impaired            # bool
member.long_term_disability         # bool (12+ months expected duration — distinct from disabled)
member.student                      # bool
member.has_disability()             # method — True if disabled OR visually_impaired OR long_term_disability
member.has_benefit("medicaid")      # method — check individual member's current benefits
member.is_married()                 # returns {"is_married": bool, "married_to": HouseholdMember|None}
member.calc_gross_income(freq, types, exclude=[])  # float — member-level income only
member.calc_expenses(freq, types)   # float
member.insurance.has_insurance_types(["none", "private", "va", "medicaid", ...])  # bool
member.birth_year                   # int or None
member.fraction_age()               # float — precise age as decimal (e.g. 66.5)
```

**`self.program.year` (FPL context):**
```python
self.program.year.get_limit(household_size)  # int — FPL amount for given size
self.program.year.as_dict()                  # dict[int, int] — {household_size: fpl_amount}
self.program.year.period                     # str — time period for external service lookups (AMI/SMI)
```

**`self.data` (cross-program eligibility):**
```python
# Dict of previously-calculated program eligibilities
if "snap" in self.data and self.data["snap"].eligible:
    # household was found eligible for SNAP
```

### Key implementation patterns

**Income checks — FPL-based (most common):**
```python
gross_income = int(self.screen.calc_gross_income("yearly", ["all"]))
income_limit = int(self.fpl_percent * self.program.year.get_limit(self.screen.household_size))
e.condition(gross_income <= income_limit, messages.income(gross_income, income_limit))
```

**Income checks — AMI-based (housing programs):**
```python
from integrations.services.hud_client import hud_client, HudIncomeClientError
try:
    ami_limit = hud_client.get_screen_il_ami(self.screen, "80%")
    e.condition(gross_income <= ami_limit, messages.income(gross_income, ami_limit))
except HudIncomeClientError:
    e.condition(False, messages.income_limit_unknown())
```

**Income checks — SMI-based (child care, energy programs):**
```python
from integrations.services.income_limits import smi
income_limit = smi.get_screen_smi(self.screen, self.program.year.period) * self.smi_percent
e.condition(gross_income <= income_limit, messages.income(gross_income, income_limit))
```

**Income with deductions or exclusions:**
```python
# Exclude certain income types from gross calculation
gross_income = self.screen.calc_gross_income("yearly", ["all"], exclude=["cashAssistance"])

# Subtract expenses for net income tests
deductions = self.screen.calc_expenses("yearly", ["childSupport"])
net_income = gross_income - deductions
e.condition(net_income <= income_limit, messages.income(net_income, income_limit))
```

**Earned vs. unearned income split (Medicaid-style):**
```python
earned = int(self.screen.calc_gross_income("yearly", ["earned"]))
unearned = int(self.screen.calc_gross_income("yearly", ["unearned"]))
earned_after = max(0, (earned - self.earned_deduction) * self.earned_percent)
unearned_after = unearned - self.unearned_deduction
e.condition(earned_after + unearned_after <= income_limit)
```

**Asset checks:**
```python
assets = self.screen.household_assets if self.screen.household_assets is not None else 0
e.condition(assets < self.asset_limit, messages.assets(self.asset_limit))
```

**Categorical eligibility — household-level (SNAP/TANF bypass):**

SNAP and TANF are household-level benefits. If the household already has one of these, it bypasses the income test for everyone. Always use `self.screen.has_benefit()` (not direct boolean fields like `self.screen.has_snap`) because `has_benefit()` handles cross-state aliases correctly.

```python
categorically_eligible = self.screen.has_benefit("snap") or self.screen.has_benefit("tanf")

if categorically_eligible:
    e.condition(True, messages.presumed_eligibility())
else:
    gross_income = self.screen.calc_gross_income("yearly", ["all"])
    income_limit = int(self.fpl_percent * self.program.year.get_limit(self.screen.household_size))
    e.condition(gross_income <= income_limit, messages.income(gross_income, income_limit))
```

**Categorical eligibility — member-level (SSI/Medicaid bypass):**

SSI and Medicaid are individual-level — only the age-eligible member's own benefits count. For SSI, check the member's SSI income stream (not `screen.has_ssi`). For Medicaid, check the member's insurance.

```python
for member_e in e.eligible_members:
    if not member_e.eligible:
        continue
    member = member_e.member
    has_ssi = member.calc_gross_income("yearly", ["sSI"]) > 0
    has_medicaid = member.has_benefit("medicaid")
    if has_ssi or has_medicaid:
        presumed_eligible = True
        break
```

This distinction matters: a 35-year-old's Medicaid should not bypass the income test for a 68-year-old's CCAD eligibility.

**Cross-program eligibility via `self.data`:**
```python
if "snap" in self.data and self.data["snap"].eligible:
    e.condition(True, messages.presumed_eligibility())
    return
```

**Expense checks:**
```python
e.condition(self.screen.has_expense(["mortgage"]))
e.condition(self.screen.has_expense(["rent", "mortgage"]))  # either qualifies
```

**Location / county / sub-state geography:**

State residency is handled by white label routing — don't add location checks unless the spec requires sub-state restrictions (specific counties or cities):
```python
e.condition(self.screen.county in self.eligible_counties, messages.location())
```

**Insurance checks:**
```python
e.condition(member.insurance.has_insurance_types(["none"]), messages.has_no_insurance())
e.condition(not member.insurance.has_insurance_types(["va"]))
```

**Relationship checks:**
```python
e.condition(member.relationship in ["child", "stepChild", "fosterChild", "grandChild"])
e.condition(member.relationship not in self.ineligible_relationships)
```

**Age checks — always guard against None:**
```python
e.condition(member.age is not None and member.age >= 65)
e.condition(member.age is not None and self.min_age <= member.age <= self.max_age)
```

**Checking existing benefits:** Always use `self.screen.has_benefit("program_name")` rather than accessing boolean fields directly (e.g. `self.screen.has_snap`). The `has_benefit()` method handles state-specific aliases and is the canonical way to check whether a household already receives a benefit.

**Tiered member_value based on age or income:**
```python
# All returned values must be annual — multiply monthly spec amounts by 12
def member_value(self, member):
    if member.age <= self.max_age_preschool:
        return self.preschool_value   # e.g. preschool_value = 300 * 12
    elif member.age < self.max_age_afterschool:
        return self.afterschool_value  # e.g. afterschool_value = 200 * 12
    return 0
```

**Spouse income aggregation (tax credit programs):**
```python
# income_limits values must be annual amounts (monthly spec values × 12)
def member_value(self, member):
    income = member.calc_gross_income("yearly", ["all"])
    if member.is_married()["is_married"]:
        spouse = member.is_married()["married_to"]
        income += spouse.calc_gross_income("yearly", ["all"])
    for threshold, value in self.income_limits.items():
        if income <= threshold:
            return value  # annual value
    return 0
```

### Income stream type tokens

When calling `calc_gross_income(frequency, types)`, the `types` list uses these exact string tokens — do not invent your own:

| Token | What it matches |
|-------|----------------|
| `"all"` | Every income stream (special aggregation keyword) |
| `"earned"` | Shorthand for `"wages"` + `"selfEmployment"` |
| `"unearned"` | Shorthand for everything except `"wages"` and `"selfEmployment"` |
| `"wages"` | Employment wages |
| `"selfEmployment"` | Self-employment income |
| `"sSI"` | Supplemental Security Income |
| `"sSDisability"` | Social Security Disability Insurance (SSDI) payments |
| `"sSRetirement"` | Social Security retirement benefits |
| `"pension"` | Pension income |
| `"unemployment"` | Unemployment benefits |
| `"cashAssistance"` | TANF / cash assistance |
| `"alimony"` | Alimony payments |
| `"childSupport"` | Child support payments |
| `"investment"` | Investment income |

Note the camelCase conventions — `"sSI"`, `"sSDisability"`, and `"sSRetirement"` all start with lowercase `s`. These are the actual database values, not display names. Using the wrong token (e.g. `"socialSecurity"` instead of `"sSRetirement"`) will silently return 0 and produce incorrect eligibility results.

### Benefit value units — ALWAYS annual

**All benefit amounts stored in the calculator must be annual (yearly) values, not monthly.**

The frontend is responsible for dividing by 12 to display monthly estimates — the backend only stores and returns annual figures. This applies to every value field: `amount`, `member_amount`, and any value returned from `household_value()`, `member_value()`, or `value()`.

When the spec describes a monthly benefit, multiply by 12 before assigning it:

```python
# Spec says "$50/month per eligible member" → store as annual
member_amount = 50 * 12   # $600/year

# Spec says "$60/month household benefit" → store as annual
amount = 60 * 12          # $720/year

# Spec says "$1,634/month average payment" → store as annual
member_amount = 1_634 * 12  # $19,608/year
```

Never assign a raw monthly value (e.g. `member_amount = 50`) — this will cause the displayed amount to appear 12× too low.

### Common class attributes

```python
# Income thresholds
fpl_percent = 1.85           # FPL multiplier (observed range: 1.3–4.0)
ami_percent = "80%"          # String, passed to HUD client
smi_percent = 0.6            # SMI multiplier
income_limit = 1_620         # Fixed monthly threshold
asset_limit = 1_000_000      # Resource limit

# Benefit amounts — always annual values (multiply monthly specs by 12)
amount = 12_000              # Household-level fixed annual amount ($1,000/month × 12)
member_amount = 1_800        # Per-eligible-member fixed annual amount ($150/month × 12)

# Age thresholds
min_age = 3
max_age = 65

# Location
eligible_counties = ["Cook", "DuPage"]

# Relationships
child_relationships = ["child", "stepChild", "fosterChild", "grandChild"]
```

### Dependencies

List every screener field the calculator reads. Common values: `"age"`, `"income_amount"`, `"income_frequency"`, `"household_size"`, `"county"`, `"zipcode"`, `"pregnant"`, `"health_insurance"`, `"household_assets"`, `"relationship"`.

### Messages

Every `e.condition()` call in `household_eligible` should include a message from `programs.programs.messages`. Member-level conditions typically omit the message.

Available helpers: `income(income, max_income)`, `income_range(income, min_income, max_income)`, `income_limit_unknown()`, `location()`, `older_than(min_age)`, `child(min_age, max_age)`, `adult(min_age, max_age)`, `assets(asset_limit)`, `must_have_benefit(name)`, `must_not_have_benefit(name)`, `has_disability()`, `has_no_insurance()`, `is_pregnant()`, `presumed_eligibility()`.

### Null safety

Always guard against `None` for optional fields before using them in comparisons:
- `member.age` — can be None
- `self.screen.household_assets` — can be None
- `member.birth_year` — can be None

### Docstring

Write a concise docstring on the calculator class — what the program is, who it serves, any data gaps or nuances from the spec.

### 3.4 Register the calculator

Add the import and registry entry to `programs/programs/{state}/__init__.py`:

```python
from .{program}.calculator import {ClassName}

{state}_calculators: dict[str, type[ProgramCalculator]] = {
    # ... existing entries ...
    "{name_abbreviated}": {ClassName},  # key must match name_abbreviated exactly
}
```

If this is the first calculator for a new state, also add the state's calculator dict to `programs/programs/__init__.py`.

### 3.5 Commit

```
git add programs/programs/{state}/{program}/
git add programs/programs/{state}/__init__.py
git commit -m "Implement {ClassName} custom calculator"
```

## Phase 4: Write Unit Tests

Create `programs/programs/{state}/{program}/tests/__init__.py` and `programs/programs/{state}/{program}/tests/test_{program}.py`.

### Test structure

Study the test patterns from existing calculators before writing tests. Good references:
- `programs/programs/tx/hse/tests/test_tx_hse.py` — mock-based, tests household eligibility + value tiers
- `programs/programs/tx/ccad/tests/test_ccad.py` — mock-based, tests member eligibility + categorical bypass

The project uses two testing styles — pick the one that matches the calculator's complexity:

**Mock-based (preferred for most calculators):**
```python
from django.test import TestCase
from unittest.mock import Mock
from programs.programs.calc import ProgramCalculator, Eligibility, MemberEligibility

def make_member(age=40, disabled=False, ...):
    member = Mock()
    member.age = age
    member.has_disability = Mock(return_value=disabled)
    return member

def make_calculator(has_mortgage=True, members=None, ...):
    mock_screen = Mock()
    mock_screen.has_expense = Mock(return_value=has_mortgage)
    mock_screen.household_members.all = Mock(return_value=members or [make_member()])
    mock_program = Mock()
    mock_missing_deps = Mock()
    mock_missing_deps.has.return_value = False
    return MyCalculator(mock_screen, mock_program, {}, mock_missing_deps)
```

**DB-based (when you need real model interactions):**
```python
from django.test import TestCase
from screener.models import Screen, HouseholdMember, IncomeStream, WhiteLabel
from programs.models import Program, FederalPoveryLimit
from programs.util import Dependencies

class TestMyProgram(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.wl = WhiteLabel.objects.create(name="Texas", code="tx", state_code="TX")
        cls.fpl_year = FederalPoveryLimit.objects.create(year="2026", period="2026")
        cls.program = Program.objects.new_program(white_label="tx", name_abbreviated="tx_my_program")
        cls.program.year = cls.fpl_year
        cls.program.save()
```

### What to test

Map your tests to the spec's eligibility criteria and benefit value section:

1. **Class attributes** — verify registration in state calculators dict, correct class constants
2. **Member eligibility** — each age/disability/pregnancy condition from the spec
3. **Household eligibility** — income thresholds, location, expense checks, categorical bypasses
4. **Benefit value** — each value tier or calculation path
5. **Integration** — call `calc()` end-to-end for the main eligible/ineligible paths

Use the spec's test scenarios as a guide for which cases to cover, but test at the unit level (individual methods), not as full household JSON scenarios.

### Run the tests

Use the virtualenv python — `python` may not resolve in non-interactive shells:
```bash
venv/bin/python manage.py test programs.programs.{state}.{program} --no-input
```

Fix any failures before proceeding.

### Commit

```
git add programs/programs/{state}/{program}/tests/
git commit -m "Add unit tests for {ClassName}"
```

## Phase 5: Import and Validate

Run all commands from the `benefits-api/` directory. Use `venv/bin/python` for all manage.py commands.

### 5.1 Import the initial config

Read `programs/management/commands/import_program_config.py` to understand the command interface, then run it for the new config file.

Fix any import errors and commit fixes before continuing.

### 5.2 Import the validations

Read `validations/management/commands/import_validations.py` to understand the command interface, then run it for the new validation file.

Fix any import errors and commit fixes before continuing.

### 5.3 Run validations (program inactive)

Run validations for the program's white label. Verify:
- The new program's validations appear as **skipped** (expected — program is inactive)
- Note any other programs that are currently failing as a baseline

### 5.4 Activate the program

Set `Program.active = True` for the new program.

### 5.5 Re-run validations (program active)

Run validations again. Verify and fix:
- The new program's validations are **no longer skipped**
- If any of the new program's validations are **failing** — fix the calculator and commit
- If any **other** programs' validations are newly failing (compare to 5.3 baseline) — fix and commit

## Phase 6: "Already Have" Checkbox (Conditional)

> This phase is being deprecated once MFB-862 and MFB-720 ship. Only complete it if the program needs to appear in the "I already have this benefit" screener step — typically only for large federal/state programs (SNAP, TANF, Medicaid, etc.) or programs that confer automatic eligibility on other programs.

Ask the user: "Does this program need an 'already have' checkbox on the screener? This is typically only for major programs like SNAP, TANF, or Medicaid."

If yes, proceed with these sub-steps. If no, skip to Phase 7.

### 6.1 Add to white label category benefits

Edit `configuration/white_labels/{state_code}.py` and add the program to the appropriate category in `category_benefits`. Use the canonical name (no state prefix) for programs that exist in multiple states.

### 6.2 Check for existing database field

Look for `has_{canonical_name}` in `screener/models.py`. If it exists, skip to 6.4.

### 6.3 Add database field + migration (if new)

Add `has_{name} = models.BooleanField(default=False, blank=True, null=True)` to the `Screen` model, then:
```bash
venv/bin/python manage.py makemigrations screener
venv/bin/python manage.py migrate screener
```

Also add the mapping in the `has_benefit()` method in `screener/models.py`.

### 6.4 Update serializer (if new field)

Add the field to `ScreenSerializer` in `screener/serializers.py`.

### 6.5 Frontend changes (if new field)

Check if the canonical name already exists in the frontend (`FormData.ts`). If not, update these 5 files:
1. `src/Types/FormData.ts` — add to `Benefits` type
2. `src/Types/ApiFormData.ts` — add `has_{name}` to `ApiFormData`
3. `src/Assets/updateScreen.ts` — map `formData.benefits.{name}` to API field
4. `src/Assets/updateFormData.tsx` — map API response back to form data
5. `src/Components/Wrapper/Wrapper.tsx` — initialize default value to `false`

### 6.6 Commit

```
git add .
git commit -m "Add {program} to 'already have' screener step"
```

## Phase 7: Summary

Summarize what was implemented:
- Files created/modified
- Test results (unit tests + validations)
- Any data gaps or assumptions called out in the spec

Suggest next steps:
1. Review the code changes and address any issues
2. Run the full test suite to check for regressions
3. Run `/playwright-qa-execution` locally to QA the program end-to-end
4. Open a PR when ready
