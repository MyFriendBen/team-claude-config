---
name: add-custom-program
description: Implements a new custom ProgramCalculator in benefits-api from two research artifacts (initial_config.json, spec.md). Use this skill whenever the user wants to implement a new benefit program with a custom calculator, add a program from a Linear ticket, or mentions implementing a program from research/discovery artifacts. Also use when the user says "add program", "implement calculator", or references a ticket with program research files.
---

<command-name>add-custom-program</command-name>

# Add Custom Program Calculator

Implements a new custom `ProgramCalculator` in `benefits-api` from two research artifacts produced during Discovery. Takes either a Linear ticket ID or local file paths as input.

The two artifacts are:
- `[name_abbreviated]_initial_config.json` — program metadata, documents, navigators, warning messages
- `[name_abbreviated]_spec.md` — eligibility criteria, benefit value methodology, test scenarios

## Where things live

**Read `benefits-api/programs/framework/README.md` first.** It is the maintained source of truth for this layout;
what follows is a summary and the README wins any disagreement. Do not trust remembered paths — this tree has been
restructured before, and the paths in this skill were wrong for months because of it. Verify a concrete path exists before relying on it: the README has drifted at least once (it lists a `framework/helpers.py` that is not in the tree).

A custom calculator goes in one of two places, chosen by whether other white labels have the same program:

| | State-only program (the usual case here) | Program shared across white labels |
|---|---|---|
| Calculator | `programs/programs/white_labels/{state}/{program}/calculator.py` | `programs/programs/cross_white_label/{family}/{state}.py` |
| Spec | `white_labels/{state}/{program}/spec.md` | `cross_white_label/{family}/specs/{state}.md` |
| Tests | `white_labels/{state}/{program}/tests/` | `cross_white_label/{family}/tests/test_{state}.py` |

Everything else:

| What | Where |
|---|---|
| Base classes | `programs/framework/base.py` — `ProgramCalculator`, `Eligibility`, `MemberEligibility` |
| Condition messages | `programs/framework/eligibility_messages.py` (imported as `import programs.framework.eligibility_messages as messages`) |
| Registry | `programs/framework/registry.py` — walks the package; **not a file you edit** (see 3.4) |
| External clients | `integrations/clients/` — e.g. `from integrations.clients.hud_income_limits import hud_client, HudIncomeClientError` |
| Initial config | `programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json` |

## Phase 1: Gather Inputs

Ask the user how they want to provide the artifacts:

> How would you like to provide the program files?
> 1. **Linear ticket** — I'll fetch the attachments from a ticket ID
> 2. **Local files** — Point me to the two files on disk

### Option 1: Linear Ticket

1. Fetch the ticket with `mcp__Linear__get_issue`
2. Extract:
   - **Branch name** — from the `branchName` field on the issue object
   - **Spec markdown** and **initial config JSON** — from ticket attachments
     - If the MCP response includes attachment URLs, fetch them. Write both files exactly as-is — do not summarize, paraphrase, or reformat.
     - If attachments can't be fetched automatically, ask the user to paste the file contents
3. If any piece is missing, prompt the user before continuing

### Option 2: Local Files

Ask the user for the paths to the two files. Read each one and confirm you have both before proceeding.

### After gathering inputs

1. Derive the **state code** (e.g. `tx`, `co`, `il`) and **program name** in snake_case (e.g. `hse`, `ccad`) from the config's `white_label.code` and `program.name_abbreviated`.
2. In `benefits-api/`, create or switch to a feature branch:
   ```bash
   git checkout -b {username}/mfb-{ticket}-implement-{program_name}
   # or if the branch already exists:
   git checkout {branch-name}
   ```

## Phase 2: Place Research Files

Write (or move) the two artifacts to their canonical locations in the repo:

**Initial config:**
```
programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
```

**Spec:**
```
programs/programs/white_labels/{state}/{program}/spec.md
```

Commit (stage specific files, not `git add .` or `git add -A`, to avoid picking up unrelated changes from auto-formatters):
```
git add programs/management/commands/import_program_config_data/data/{state}_{program}_initial_config.json
git add programs/programs/white_labels/{state}/{program}/spec.md
git commit -m "Add {state} {program} research files"
```

## Phase 3: Implement the Calculator

This is the core implementation step. Read the spec.md carefully — it contains the eligibility criteria, benefit value methodology, and data gaps that drive every decision in the calculator.

### 3.1 Study existing patterns

Before writing any code, read 2–3 existing calculators to absorb the project's conventions. Good references by complexity:

- **Simple** (fixed value, one income-band condition): `programs/programs/white_labels/co/erc/calculator.py`
- **Medium** (FPL income test, member + household conditions): `programs/programs/white_labels/tx/ccad/calculator.py`
- **Complex** (categorical eligibility, date ranges, pregnancy): `programs/programs/white_labels/federal/trump_account/calculator.py`

Also read:
- `programs/framework/base.py` — the base `ProgramCalculator` class, `Eligibility`, `MemberEligibility`
- `programs/framework/eligibility_messages.py` — message helpers for conditions (income, location, age, etc.)
- `programs/framework/registry.py` — how a calculator gets registered (it isn't a file you edit; see 3.4)
- A sibling's `tests/` directory, for the test conventions Phase 4 expects

### 3.2 Create the calculator directory

```bash
mkdir -p programs/programs/white_labels/{state}/{program}
touch programs/programs/white_labels/{state}/{program}/__init__.py
```

### 3.3 Write the calculator

Create `programs/programs/white_labels/{state}/{program}/calculator.py`.

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
from integrations.clients.hud_income_limits import hud_client, HudIncomeClientError
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

SNAP and TANF are household-level benefits. If the household already has one of these, it bypasses the income test for everyone. Use `self.screen.has_benefit("snap")` / `self.screen.has_base_benefit("snap")` — these handle cross-state aliases correctly.

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

When a rule is *individual-level* — only the age-eligible member's **own** SSI/Medicaid should count — don't use a household-level check, which would also count another member's SSI/Medicaid. For SSI, check that member's own SSI income stream; for Medicaid, check that member's insurance. (A household-level `screen.has_benefit("ssi")` is still the right tool for the other kind of rule — "does *anyone* in the household receive SSI." Match the check to what the spec actually asks.)

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

**Checking existing benefits:** Use `self.screen.has_benefit("program_name")` — it reads the `CurrentBenefit` join table, handles state-specific aliases, and is the canonical way to check whether a household already receives a benefit.

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

### Never let a computed value land on $0

`Eligibility.value` drives two independent filters, and `$0` fails both: the API reports the program **not eligible**,
and the frontend drops it again on `programValue(program) > 0`
(`benefits-calculator/src/Components/Results/Filter/filterPrograms.ts`). A household that genuinely qualifies but
whose net value works out to zero — a benefit fully offset by a premium or copay, say — would be hidden from exactly
the people it applies to.

So if the spec's value formula can reach zero or go negative for an eligible household, floor it at `1` rather than
`0`, and amend the spec scenario to match. Only floor at `0` when reaching zero genuinely means "not eligible".

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

Every `e.condition()` call in `household_eligible` should include a message from `programs.framework.eligibility_messages`. Member-level conditions typically omit the message.

Available helpers: `income(income, max_income)`, `income_range(income, min_income, max_income)`, `income_limit_unknown()`, `location()`, `older_than(min_age)`, `child(min_age, max_age)`, `adult(min_age, max_age)`, `assets(asset_limit)`, `must_have_benefit(name)`, `must_not_have_benefit(name)`, `has_disability()`, `has_no_insurance()`, `is_pregnant()`, `presumed_eligibility()`.

### Null safety

Always guard against `None` for optional fields before using them in comparisons:
- `member.age` — can be None
- `self.screen.household_assets` — can be None
- `member.birth_year` — can be None

### Docstring

Write a concise docstring on the calculator class — what the program is, who it serves, any data gaps or nuances from the spec.

### 3.4 Registration is automatic — declare `program_code`

**Do not hand-edit any registry.** `programs/framework/registry.py` walks `programs.programs` and reads the key
off each class it finds, so writing the file registers the calculator. The per-state `{state}_calculators` dicts
are gone — `programs/programs/white_labels/{state}/__init__.py` is empty by design.

Every calculator must declare exactly one of the following. **Declaring neither raises `UnregisteredCalculator`
at import**, which takes the app down rather than quietly leaving the calculator unreachable — silence would read
the same whether the class is a base or whether someone forgot the key, so it is rejected instead of guessed at:

```python
class MyProgram(ProgramCalculator):
    program_code = "{name_abbreviated}"   # the Program.name_abbreviated row this backs

class MyBase(ProgramCalculator, abstract=True):
    ...                                   # exists to be subclassed, backs no row
```

`abstract=True` is a class keyword read by `__init_subclass__` at class creation rather than an attribute, so it
cannot drift from the class it describes. Subclassing an abstract base does **not** make the subclass abstract, and
a class may both declare a code and be subclassed. Two classes claiming the same key raise `DuplicateRegistryKey`
at import rather than resolving to whichever is found second.

### 3.5 Commit

```
git add programs/programs/white_labels/{state}/{program}/
git commit -m "Implement {ClassName} custom calculator"
```

## Phase 4: Write Unit Tests

The `spec.md` is the source of truth for test coverage. **Every scenario it describes — each eligibility criterion, benefit-value path, edge case, and every entry in its Test Scenarios section — must be captured by a unit test.** Aim for full coverage of the calculator: no branch in the code and no scenario in the spec should go untested. This is not optional polish; the tests are how we guarantee the calculator matches the spec now that per-program validations no longer run.

Create `programs/programs/white_labels/{state}/{program}/tests/__init__.py` and `programs/programs/white_labels/{state}/{program}/tests/test_{program}.py`.

### Test structure

Study the test patterns from existing calculators before writing tests. Good references:
- `programs/programs/white_labels/tx/hse/tests/test_tx_hse.py` — mock-based, tests household eligibility + value tiers
- `programs/programs/white_labels/tx/ccad/tests/test_ccad.py` — mock-based, tests member eligibility + categorical bypass

The project uses two testing styles — pick the one that matches the calculator's complexity:

**Mock-based (preferred for most calculators):**
```python
from django.test import TestCase
from unittest.mock import Mock
from programs.framework.base import ProgramCalculator, Eligibility, MemberEligibility

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

**DB-based (when the calculator walks `household_members`, income streams, or insurance):**
```python
from programs.programs.testing_fixtures.custom_calculator import CustomCalculatorTestCase
from programs.programs.white_labels.tx.my_program.calculator import MyProgram

class TestMyProgram(CustomCalculatorTestCase):
    calculator_class = MyProgram
    white_label_code = "tx"
    state_code = "TX"
    default_county = "Harris County"

    def test_eligible_household(self):
        screen = self.make_screen(household_size=2)
        self.add_member(screen, "headOfHousehold", 36, monthly_income=2_000)

        e = self.calculate(screen)

        self.assertTrue(e.eligible)
        self.assertEqual(e.value, 1_200)
```

The base class creates the white label, the `Program` row and its FPL year, then runs the
calculator. A scenario states only what makes it distinct.

**Do not write your own `make_screen` / `add_member` / `_calc` helper.** If the fixture is
missing something your program needs, add it to the fixture — a per-file helper is the
duplication this exists to remove.

#### Class attributes

| attribute | when to set it |
| -- | -- |
| `calculator_class` | always — `program_code` is taken from it, so do not restate it |
| `white_label_code`, `state_code` | always |
| `default_zipcode`, `default_county` | when the program is local to one place, so scenarios name a location only to move away from it. Note MA stores a city in `county` |
| `needs_program_row = False` | when the calculator never reads `self.program` — no FPL or SMI lookup. Skips the Translation rows a real `Program` writes, and is the common case |
| `fpl_year` | when the program is tested against a year other than the default |
| `reference_date` | only when a scenario is pinned to a calendar window — a program start date, an enrollment window, a birth month copied from the spec |

#### Building a household

| call | notes |
| -- | -- |
| `self.make_screen(household_size=2, county=...)` | white label, state and default location come from the class |
| `self.add_member(screen, "child", 3, monthly_income=...)` | also takes `yearly_income`, `pregnant`, `student`, `disabled`, any `HouseholdMember` field |
| `add_income(member, amount, income_type=..., frequency=...)` | for a second stream, or a frequency other than monthly/yearly |
| `add_expense(member, amount, expense_type="rent")` | |
| `add_insurance(member, medicaid=True, none=False)` | a member already comes with an uninsured record |

`age` may be fractional — `3.5` is three years six months — for calculators reading
`fraction_age()`. `add_member` writes a matching `birth_year_month`, so a calculator reading
either field sees the same person; pass `birth_year_month` yourself only when the scenario
turns on an absolute date. State a `yearly_income` as yearly rather than dividing it down:
a limit tested at the boundary rarely survives the rounding.

#### Running it

| call | returns |
| -- | -- |
| `self.calculate(screen)` | the final `Eligibility` |
| `self.make_calculator(screen)` | the calculator unrun, to assert on `eligible()` or one method |
| `self.calculate(screen, data={"tx_medicaid": eligible_result()})` | for a calculator gating on another program via `program_eligible()` |
| `self.calculate(screen, missing=("income_amount",))` | to assert the program is skipped rather than valued wrongly |

#### If the calculator reads HUD

Wrap the call in `hud_ami` rather than patching `hud_client` — it is bound per calculator
module, so a hand-written patch target is easy to get wrong:

```python
with self.hud_ami(50_000) as hud:
    e = self.calculate(screen)

hud.get_screen_il_ami.assert_called_once_with(screen, "80%", "2025")
```

`limit` may be a scalar, a dict keyed by AMI band (`{"60%": 60_000, "80%": 80_000}`), or a
callable when what HUD was *asked* is the thing under test. Add `payment_standard=` for the
voucher lookup, and `unavailable=True` / `payment_standard_unavailable=True` for the outage
paths. HUD's own behaviour is covered by its tests in
`integrations/clients/hud_income_limits/tests` — do not re-test it here.

See `benefits-api/docs/TESTING.md` for the fuller reference. The mock form above stays
correct for calculators that only read a few scalars off the screen.

### What to test

Map your tests to the spec's eligibility criteria and benefit value section:

1. **Class attributes** — the class constants the spec fixes (amounts, age bounds, FPL percentages). `program_code` needs no test: the base class takes it from the calculator and rejects a subclass that contradicts it
2. **Member eligibility** — each age/disability/pregnancy condition from the spec
3. **Household eligibility** — income thresholds, location, expense checks, categorical bypasses
4. **Benefit value** — each value tier or calculation path
5. **Integration** — call `calc()` end-to-end for the main eligible/ineligible paths

Work through the spec's Test Scenarios section item by item and add a test for each one — every scenario must have a corresponding test. Test at the unit level (individual methods), not as full household JSON scenarios. If a scenario can't be expressed as a unit test, note why in a comment rather than silently dropping it.

### Run the tests

Use the virtualenv python — `python` may not resolve in non-interactive shells:
```bash
venv/bin/python manage.py test programs.programs.{state}.{program} --no-input
```

**Every unit test must pass before proceeding** — this step is not complete until the full suite for the new program is green. Fix the calculator (or the test, if the test is wrong) and re-run until there are zero failures.

### Commit

```
git add programs/programs/white_labels/{state}/{program}/tests/
git commit -m "Add unit tests for {ClassName}"
```

## Phase 5: Import and Activate

Run all commands from the `benefits-api/` directory. Use `venv/bin/python` for all manage.py commands.

### 5.1 Import the initial config

Read `programs/management/commands/import_program_config.py` to understand the command interface, then run it for the new config file.

Fix any import errors and commit fixes before continuing.

### 5.2 Activate the program

Set `Program.active = True` for the new program.

## Phase 6: "Already Have" Screener Step (Conditional)

Whether a program appears as a tile on the "I already have this benefit" screener step is driven entirely by its `Program` row — specifically `show_in_has_benefits_step` — which is set from the program's `initial_config.json` at import time. There is nothing else to wire up: no white-label config edit, no database/serializer/frontend changes. (A household's declared benefits are stored in the `CurrentBenefit` join table and read via `screen.has_benefit(...)` / `screen.has_base_benefit(...)`.)

There is nothing to *build* here — only a decision to make and confirm in the config you're importing.

**The criterion is functional, not size-based.** A program belongs on this step only if knowing a household already receives it changes the eligibility result of *another* program — i.e. it confers categorical/presumed eligibility (or is a disqualifier) elsewhere. It does **not** have to be a "major" program; conversely, a large program that nothing else keys off of does not belong here. Don't guess from the program's prominence — verify:

1. **Does our code base already key off this benefit?** Grep the calculators for the program's `name_abbreviated` and its `base_program`:
   ```bash
   grep -rnE "has_benefit(_from_list)?\(|has_base_benefit\(|presumptive_eligibility|categorically_eligible" programs/programs/ \
     | grep -vE "/tests/|test_" \
     | grep -iE "<name_abbreviated>|<base_program>"
   ```
   A hit means another calculator reads this benefit's state (directly, via `has_base_benefit`, or through a `presumptive_eligibility` / `categorically_eligible` list) → it needs `show_in_has_benefits_step: true`. **But no hit is not proof it's unneeded** — the program is new, so nothing could have referenced it yet. Always also do check #2.

2. **Should it confer eligibility on any program we already have — even if our code doesn't reflect that yet?** Because this program is new, check #1 can only find dependencies that were somehow written ahead of it — usually none. This check looks for gaps: does receiving this new program categorically/presumptively qualify a household for one of our existing programs? Verify with the program's spec **and an up-to-date web search of its official eligibility policy** (don't rely on training data — rules change), then compare against the programs we offer (e.g. via `programs/programs/white_labels/{state}/`, `programs/programs/cross_white_label/`, and the program config). If receipt of this program *should* gate one of ours but no calculator reads it, that's a missing dependency: flag it so the existing calculator is updated to read `has_benefit("<this program>")` **and** this program gets `show_in_has_benefits_step: true` — don't silently leave it off.

Then:

- If either check says yes, set `"show_in_has_benefits_step": true` (and `"active": true`) in the program's `initial_config.json`. The tile's display name, description, and category grouping come from the program's own `name`, `website_description`, and `category` fields — nothing else to wire up.
- Otherwise (the common case), leave `show_in_has_benefits_step: false` — skip to Phase 7.

If you change this flag in the config, re-run the program config import so the `Program` row reflects it.

## Phase 7: Summary

Summarize what was implemented:
- Files created/modified
- Test results (unit tests)
- Any data gaps or assumptions called out in the spec

Suggest next steps:
1. Review the code changes and address any issues
2. Run the full test suite to check for regressions
3. Run `/playwright-qa-execution` locally to QA the program end-to-end
4. Open a PR when ready
