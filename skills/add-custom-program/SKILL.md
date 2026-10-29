---
name: add-custom-program
description: Implements a custom ProgramCalculator in benefits-api from the program-ops spec and program record written by Discovery, including a federal program that replaces per-state rows (calculator PR, then a separate switch-over migration PR across weekly releases). Use this skill whenever the user wants to implement a new benefit program with a custom calculator, add a program from a Linear ticket, move a program to the federal white label, or mentions implementing a program from research/discovery artifacts. Also use when the user says "add program", "implement calculator", or references a ticket with program research files.
---

<command-name>add-custom-program</command-name>

# Add Custom Program Calculator

<!-- Editing note: never put a dollar sign directly before a digit in this file. When the skill loads, a dollar sign followed by a number is replaced by that argument (the first argument for zero, the second for one, and so on), so an amount like one thousand dollars written with the sign loads as "staging,000". Write amounts as plain numbers or "N dollars". -->

Implements a custom `ProgramCalculator` in `benefits-api` from the two artifacts Discovery writes in **program-ops**. Both stay in program-ops. Read them there, link to them, and never copy them into benefits-api:

- `{key}_spec.md`: eligibility criteria, benefit value, test scenarios. It's the source of truth for the calculator and its tests.
- `{key}_program_record.json`: the program row, documents, navigators and warnings. It's imported from program-ops in Phase 4.

Both sit in one directory:
- `program-ops/programs/white_labels/{wl}/{program}/` for a state-only or federal program, e.g. `federal/wic/federal_wic_spec.md`.
- `program-ops/programs/cross_white_label/{family}/{state|base}/` for a shared family, e.g. `head_start/nj/head_start_nj_spec.md`.

Beside them, `decisions.md` logs every settlement Discovery made, including ones that supersede earlier ones. Read it before questioning a rule, and log any new settlement there (in the program-ops PR).

A fix to any of these files is a program-ops PR, never a benefits-api edit.

## Where things live

**Read `benefits-api/programs/framework/README.md` first.** It's the maintained source of truth for the code layout; this is a summary, and the README wins any disagreement. Verify a path exists before relying on it, since this tree has been restructured before.

| | State-only program | Shared across white labels | Federal (every white label sees it) |
|---|---|---|---|
| Calculator | `programs/programs/white_labels/{state}/{program}/calculator.py` | `programs/programs/cross_white_label/{family}/{state}.py` | `programs/programs/white_labels/federal/{program}/calculator.py` |
| Tests | `white_labels/{state}/{program}/tests/` | `cross_white_label/{family}/tests/test_{state}.py` | `white_labels/federal/{program}/tests/` |
| `program_code` | `{state}_{program}` | per state | `federal_{program}` |

A family's base is `cross_white_label/{family}/base.py`. When a new MFB base replaces a PolicyEngine one that other states still use, put it in `{family}/mfb_base.py` beside it (precedent: `head_start/mfb_base.py`).

| What | Where |
|---|---|
| Base classes | `programs/framework/base.py`: `ProgramCalculator`, `Eligibility`, `MemberEligibility` |
| Condition messages | `programs/framework/eligibility_messages.py` (imported as `import programs.framework.eligibility_messages as messages`) |
| Registry | `programs/framework/registry.py`, which walks the package; **not a file you edit** (see 2.4) |
| Federal helpers | `programs/federal.py`: `visible_to`, `is_federal`, `visible_program` |
| External clients | `integrations/clients/`, e.g. `from integrations.clients.hud_income_limits import hud_client, HudIncomeClientError` |
| Import script | program-ops `scripts/import_programs.py`, run with `python3` (it isn't executable) |

## Phase 1: Gather Inputs

1. Fetch the Linear ticket (`get_issue` with `includeRelations`). Take the **branch name** (`gitBranchName`) and the **program key** (the record's `program.name_abbreviated`, e.g. `mo_sab` or `federal_wic`).
2. **Read the comments** (`list_comments`) on the ticket, its Discovery sub-issue and its related tickets. They carry what landed after Discovery: a proposed spec change, a follow-up someone owes. A comment that changes the spec is settled in a program-ops PR before you write code, and you implement against that PR's spec. A follow-up goes in the Phase 7 summary.
3. **Check open benefits-api PRs** for the same white label or shared code the calculator will touch (`gh pr list --search "{wl}"`, plus the program's family or base). Build on `main`, not on an unmerged PR, and say in your PR which ones overlap.
4. Find the record and spec in program-ops: `git -C program-ops ls-tree -r --name-only origin/main programs | grep {key}`. For a family, list the whole family directory (`grep cross_white_label/{family}/`): the base spec has its own key (`nslp`) and no record, so a grep for the state key misses it. If they aren't on program-ops `main` yet, ask which branch or open PR has them, and read them from there. Don't copy them.
5. Derive the white label (`white_label.code`) and program name from the record.
6. **Classify the program.** This decides whether Phase 6 applies:
   - **State-only** or **shared across white labels**: Phases 2–5 and 7.
   - **New family base plus its first state:** a base spec (`{family}/base/`, no record) and a state spec plus record. The base is `abstract=True` and backs no row; the state subclass is the program. Phases 2–5 and 7, testing the base through a stand-in subclass (Phase 3).
   - **Federal, new:** the record's white label is `federal` and no state rows carry the same `base_program`. Phases 2–5 and 7, plus the federal notes in 2.3.
   - **Federal, replacing state rows:** the record's white label is `federal`, and state programs with the same `base_program` already exist, e.g. `co_wic`, `il_wic`, `tx_wic`. **Phase 6 applies**, and the work ships as two benefits-api PRs over two weekly releases. To check, grep for the base program and query a database you can read (local or staging, never prod):
     ```bash
     git grep -nE "program_code = \"[a-z_]*{program}\"" -- programs/programs
     venv/bin/python manage.py shell -c "from programs.models import Program; print(list(Program.objects.filter(base_program='{program}').values_list('white_label__code', 'name_abbreviated', 'active')))"
     ```
7. In `benefits-api/`, create or switch to the feature branch from up-to-date `main`.

## Phase 2: Implement the Calculator

Read the spec carefully. Its eligibility criteria, benefit value and data gaps drive every decision here.

If a rule looks too broad or too narrow (e.g. no lower age, so a newborn qualifies), read the source the spec cites before raising it, and quote that text to David along with your concern.

### 2.1 Study existing patterns

Read 2–3 existing calculators first. Good references by complexity:

- **Simple** (fixed value, one income-band condition): `programs/programs/white_labels/co/erc/calculator.py`
- **Medium** (FPL income test, member + household conditions): `programs/programs/white_labels/tx/ccad/calculator.py`
- **Complex** (categorical eligibility, date ranges, pregnancy): `programs/programs/white_labels/federal/trump_account/calculator.py`
- **Federal replacing state rows** (per-member value, adjunctive eligibility, base-group reads): `programs/programs/white_labels/federal/wic/calculator.py`

Also read `programs/framework/base.py`, `programs/framework/eligibility_messages.py`, `programs/framework/registry.py`, and a sibling's `tests/` directory.

**Reuse a sibling's rule; don't copy it.** Read the other calculators in the same white label and family. If one already computes a rule this spec states the same way (which income counts, who the filers are, a tax schedule), share it rather than writing a second copy. Put it where the framework README's placement rule says: in the white label's directory when every user is in that white label. Refactoring the sibling to import it must not change its behavior, so its tests pass unchanged.

### 2.2 Create the calculator directory

```bash
mkdir -p programs/programs/white_labels/{state}/{program}/tests
touch programs/programs/white_labels/{state}/{program}/__init__.py programs/programs/white_labels/{state}/{program}/tests/__init__.py
```

### 2.3 Write the calculator

The calculator subclasses `ProgramCalculator`. Map spec criteria to overrides:

| Spec says | Override | Pattern |
|-----------|----------|---------|
| Household-level condition (income, location, assets) | `household_eligible(self, e: Eligibility)` | `e.condition(bool_expr, messages.xxx())` |
| Per-member condition (age, disability, pregnancy) | `member_eligible(self, e: MemberEligibility)` | `e.condition(bool_expr)` |
| Fixed benefit for the whole household | Class attribute `amount = N` (**annual**) | Or override `household_value()`, returning an annual value |
| Per-member benefit amount | Class attribute `member_amount = N` (**annual**) | Or override `member_value(member)`, returning an annual value |
| Variable benefit (depends on member attributes) | Override `member_value(member)` or `household_value()` | Return different amounts based on conditions |
| Custom value assignment (e.g. per eligible member) | Override `value(self, e: Eligibility)` | Iterate `e.eligible_members` and set `.value` |

**Federal programs.** Every white label sees a federal row, including `_default` and `co_tax_calculator`. So:
- **Residency** is the white label's job; never check the state.
- **Declare only the fields every white label sends.** A missing dependency drops the program from that screen with `missing_programs` set. The Get Ahead apps (`co_tax_calculator`) don't send `pregnant`, for example. Read a field that can be missing as a safe default (`member.pregnant is True`) rather than declaring it, and test both answers.
- **Location dependencies:** a program that needs `county` or `zipcode` drops out of `federal` test screens, which have no location.

**Tax programs** (claimed on a return for a tax year):
- **Year:** read `self.tax_year` (`programs/framework/base.py`), which follows the record's `year`. Don't hardcode it. Key yearly figures by tax year, and fall back to the latest year with a Sentry message rather than raising (`CTC_YEARS` in `federal/ctc/calculator.py`).
- **Tax Table:** where the source sends filers below a ceiling to a Tax Table, reproduce it. Price each row at its midpoint and round to the dollar (`tax_table_row` and `income_tax` in `federal/ctc/calculator.py`). The table is exact arithmetic, so the rate schedule applied to the exact figure is not an acceptable approximation.
- **Prior-tax-year warning:** if the white label has no `_prior_tax_year` warning row, name that in the Phase 7 summary. The January 1 tax-year rollover has its own process; don't flag it per program.

### Available APIs

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
self.screen.has_benefit("tx_snap")                      # bool — ONE exact name_abbreviated
self.screen.has_base_benefit("snap")                    # bool — any program in the base_program group
self.screen.has_benefit_from_list(["leap", "wic"])      # bool — each entry an exact name or a base group
```

**Reading another benefit:** `has_benefit` matches one exact `name_abbreviated`, and real-world names (`snap`, `section_8`) rarely exist as one. Use `has_base_benefit(...)` for "receives any variant of X". That's also the only form that survives a program moving to `federal_{program}`.

**HouseholdMember attributes:**
```python
member.age                          # int or None — always check for None before comparisons
member.age_at_end_of_year(2025)     # age on December 31 of that year (birth year only) — for rules
                                    #   judged over a benefit or tax year, not on the screening date
member.relationship                 # str: "headOfHousehold", or a key of relationship_options
                                    #   (configuration/white_labels/base.py): "spouse",
                                    #   "domesticPartner", "boyfriendOrGirlfriend", "child",
                                    #   "stepChild", "fosterChild", "grandChild", "parent",
                                    #   "stepParent", "fosterParent", "grandParent",
                                    #   "sisterOrBrother", "stepSisterOrBrother", "relatedOther",
                                    #   "roommate". Not validated: compare against these exactly
member.pregnant                     # bool or None — None when the screener never asked
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

**`self.data` (cross-program eligibility):** results of programs already calculated. Prefer `self.program_eligible("code")` and declare the program in `gates_on` / `gates_on_any` (`programs/framework/gates.py`).

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
gross_income = self.screen.calc_gross_income("yearly", ["all"], exclude=["cashAssistance"])
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

**Categorical eligibility — household-level (SNAP/TANF bypass).** Read receipt through `programs/framework/pe_dependencies/receipt.py`: `screen_reports_snap(screen)`, and `screen_reports_tanf(screen)`, which counts the TANF tile **or** reported `cashAssistance` income (despite the module path, these are plain screen reads, not PolicyEngine calls). If the spec's Logic reads the tile only, ask, and amend the spec to match. The bare form:
```python
categorically_eligible = self.screen.has_base_benefit("snap") or self.screen.has_base_benefit("tanf")

if categorically_eligible:
    e.condition(True, messages.presumed_eligibility())
else:
    gross_income = self.screen.calc_gross_income("yearly", ["all"])
    income_limit = int(self.fpl_percent * self.program.year.get_limit(self.screen.household_size))
    e.condition(gross_income <= income_limit, messages.income(gross_income, income_limit))
```

**Categorical eligibility — member-level (SSI/Medicaid bypass).** When only the member's **own** SSI or Medicaid counts, check that member, not the household:

```python
for member_e in e.eligible_members:
    if not member_e.eligible:
        continue
    member = member_e.member
    has_ssi = member.calc_gross_income("yearly", ["sSI"]) > 0
    has_medicaid = member.insurance.has_insurance_types(["medicaid"])
    if has_ssi or has_medicaid:
        presumed_eligible = True
        break
```

A 35-year-old's Medicaid should not bypass the income test for a 68-year-old's CCAD eligibility. MA's screener offers only MassHealth (`ma_mass_health`), so a Medicaid check that every white label sees reads both (see `federal/wic/calculator.py`).

**Expense checks:**
```python
e.condition(self.screen.has_expense(["mortgage"]))
e.condition(self.screen.has_expense(["rent", "mortgage"]))  # either qualifies
```

**Location / county / sub-state geography.** State residency is handled by white label routing. Add a location check only for sub-state restrictions:
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

When the spec judges age at the end of a benefit or tax year ("65 or older by December 31, 2025"), use `member.age_at_end_of_year(year)`, not `member.age`. For a tax program `year` is `self.tax_year`; for a benefit year the record doesn't carry, keep it as a class attribute (`benefit_year`). Test with a birth year that makes today's age and the year-end age differ (see `white_labels/nj/anchor/calculator.py`).

**Tiered member_value based on age or income:**
```python
# All returned values must be annual — multiply monthly spec amounts by 12
def member_value(self, member: HouseholdMember) -> int:
    if member.age <= self.max_age_preschool:
        return self.preschool_value   # e.g. preschool_value = 300 * 12
    elif member.age < self.max_age_afterschool:
        return self.afterschool_value  # e.g. afterschool_value = 200 * 12
    return 0
```

**Spouse income aggregation (tax credit programs):**
```python
def member_value(self, member: HouseholdMember) -> int:
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

`calc_gross_income(frequency, types)` takes these exact tokens; don't invent your own:

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

`"sSI"`, `"sSDisability"` and `"sSRetirement"` start with a lowercase `s`. A wrong token (e.g. `"socialSecurity"`) silently returns 0.

### Never let a computed value land on zero

A value of zero fails two filters: the API reports the program **not eligible**, and the frontend drops it on `programValue(program) > 0` (`benefits-calculator/src/Components/Results/Filter/filterPrograms.ts`). If the spec's value formula can reach zero or go negative for an eligible household, floor it at `1`, and amend the spec scenario to match in program-ops. Floor at `0` only when zero genuinely means "not eligible".

### Benefit value units — ALWAYS annual

Every value (`amount`, `member_amount`, and anything returned from `household_value()`, `member_value()` or `value()`) is **annual**. The frontend divides by 12 for display. Multiply a monthly spec amount by 12 (`member_amount = 50 * 12`). A raw monthly value shows 12× too low.

Rounding: the API serializes `estimated_value` as an integer (`screener/serializers.py`), so cents are cut before the frontend sees them. Compute in `Decimal` and round each annual value half-up to whole dollars (`federal/wic/calculator.py`). Tests then assert the rounded figure (spec 871.20 → 871); say so in the PR.

### Dependencies

List every screener field the calculator reads, by the names the screens' `missing_fields()` reports (`screener/models.py`):
- screen: `household_size`, `household_assets`, `county`, `zipcode`
- member: `age`, `relationship`, `student`, `pregnant`, `visually_impaired`, `disabled`, `long_term_disability`, `insurance`
- income: `income_type`, `income_amount`, `income_frequency`
- expense: `expense_type`, `expense_amount`, `expense_frequency`

A name not on these lists (e.g. `health_insurance`, `veteran`) is never reported missing, so declaring it protects nothing. A declared field that's null drops the program and sets `missing_programs`. For a federal program, re-read 2.3's federal notes before declaring one.

### Messages

Every `e.condition()` in `household_eligible` takes a message from `programs.framework.eligibility_messages`; member-level conditions usually don't. Available: `income`, `income_range`, `income_limit_unknown`, `location`, `older_than`, `child`, `adult`, `assets`, `must_have_benefit`, `must_not_have_benefit`, `has_disability`, `has_no_insurance`, `is_pregnant`, `presumed_eligibility`.

### Null safety

Guard `member.age`, `member.birth_year`, `member.pregnant` and `self.screen.household_assets` against `None`.

### Docstring and type hints

Give the class a concise docstring: what the program is, who it serves, and the spec's data gaps and deviations, with the spec's program-ops path. Type-hint every parameter and return value.

### 2.4 Registration is automatic — declare `program_code`

**Don't hand-edit any registry.** `programs/framework/registry.py` walks `programs.programs` and reads the key off each class. Every calculator declares exactly one of these. Declaring neither raises `UnregisteredCalculator` at import:

```python
class MyProgram(ProgramCalculator):
    program_code = "{name_abbreviated}"   # the Program.name_abbreviated row this backs

class MyBase(ProgramCalculator, abstract=True):
    ...                                   # exists to be subclassed, backs no row
```

Two classes claiming one key raise `DuplicateRegistryKey` at import. A federal replacement's `federal_{program}` doesn't collide with the state calculators it replaces, so both coexist until the cleanup (6.4).

### 2.5 Commit

Stage the specific paths (not `git add -A`) and commit.

## Phase 3: Write Unit Tests

The spec's Test Scenarios section is the source of truth. **Every scenario, eligibility criterion, value path and edge case gets a unit test**, and no branch in the calculator goes untested. If a scenario can't be expressed as a unit test, say why in a comment rather than dropping it.

References:
- `programs/programs/white_labels/tx/hse/tests/test_tx_hse.py`: mock-based, household eligibility and value tiers.
- `programs/programs/white_labels/tx/ccad/tests/test_ccad.py`: mock-based, member eligibility and categorical bypass.
- `programs/programs/white_labels/federal/wic/tests/test_federal_wic.py`: DB-based on `CustomCalculatorTestCase` (`programs/programs/testing_fixtures/custom_calculator.py`), one test per spec scenario. Tests receipt of another benefit via `seed_program` + `_write_current_benefits`, and a missing field via `calculate(screen, missing=("pregnant",))`.

What to test:
1. **Registration**: `program_code` matches the record's `name_abbreviated`, and the class constants.
2. **Member eligibility**: each age, disability or pregnancy condition.
3. **Household eligibility**: income at the limit and one step over, location, expenses, categorical bypasses.
4. **Benefit value**: each tier or path, in annual dollars.
5. **Missing answers**: each field a white label may not send behaves as the spec intends (federal programs especially).

For an abstract base, test each base rule through a test-only subclass that sets the values a state sets (`cross_white_label/sunbucks/tests/test_base.py`); run the state's spec scenarios end to end in `test_{state}.py`. Report a current benefit with `seed_program` + `_write_current_benefits`, using a stand-in row with the right `base_program` when the white label has none.

Once green, mutate one boundary (flip a `<=`, disable a branch) and confirm a test fails, then restore it.

Run the tests with the venv (add `-n0` to run one file without xdist; `-p no:xdist` errors because `pytest.ini` passes `-n`):
```bash
venv/bin/pytest programs/programs/white_labels/{state}/{program}
```

Every test passes before you go on.

## Phase 4: Import and Activate Locally

From `program-ops/`, with `benefits-api/` beside it on this branch. The import only creates a program whose calculator is registered in the running code:

```bash
python3 scripts/import_programs.py --env local --dry-run-only --program {key}
python3 scripts/import_programs.py --env local --program {key}
```

The real run asks `Apply the changes above to local? [y/N]` and fails with `EOFError` without a terminal; locally, pipe the answer: `echo y | python3 scripts/import_programs.py --env local --program {key}`.

A record problem the dry run reports is a program-ops PR. The import never sets `active`: a new program is created switched off. Switch it on **locally only** to test:

```bash
venv/bin/python manage.py shell -c "from programs.models import Program; Program.objects.filter(white_label__code='{wl}', name_abbreviated='{key}').update(active=True)"
```

For a federal replacement, also run the switch-over migration locally (6.2) and QA with both the state rows off and `federal_wic`-style row on, as production will be.

**Staging and production:** a program's import waits for its calculator to be deployed there ("Waiting for a calculator, not created" in the dry run). No flag skips this. So **a program can't be imported in an environment until the release carrying its calculator is live there.** Plan the PR's Deployment section around that.

## Phase 5: "Already Have" Screener Step (Conditional)

The tile on the "I already have this benefit" step comes from the `Program` row's `show_in_has_benefits_step`, set from the record. Nothing else to wire up.

**The criterion is functional.** A program belongs on the step only if receiving it changes another program's result, through categorical or presumed eligibility or as a disqualifier. Verify:

1. **Does the code already key off it?**
   ```bash
   grep -rnE "has_benefit(_from_list)?\(|has_base_benefit\(|presumptive_eligibility|categorically_eligible" programs/programs/ \
     | grep -vE "/tests/|test_" \
     | grep -iE "<name_abbreviated>|<base_program>"
   ```
2. **Should it gate any program we have, even if no code reads it yet?** Check the spec and an up-to-date web search of the official policy against our programs. A missing dependency gets flagged: the existing calculator should read `has_base_benefit("<base_program>")`, and this program gets the tile.

Run this check even when the record already sets the flag. Discovery's answer can go stale when a program that reads this one merges later (NJ SUN Bucks started reading `nslp` after `nj_nslp`'s record said false).

If either is yes, set `"show_in_has_benefits_step": true` in the record (a program-ops PR) and re-run the Phase 4 import. A federal replacement inherits the state rows' tile, so set it whenever the state rows had it.

## Phase 6: Federal Program Replacing State Rows (Conditional)

Applies when Phase 1 classified the program as **federal, replacing state rows**. The goal is a seamless switch: households that already receive the benefit keep showing it as held, the state rows stop showing, and the federal row is on, all at the same moment. Never a window where the program shows twice or not at all.

benefits-api ships on a **weekly release** that bundles everything merged to `main`. Staging deploys on every merge, and production on the published release. A deploy pushes code and then runs `migrate`, with no release phase in between. With the import waiting for a deployed calculator, the work splits into **two PRs in two releases**. Reference implementation: WIC, MFB-2073 (benefits-api #1853, then #1858).

### 6.1 PR 1, the calculator (release N)

- The federal calculator and tests (Phases 2–3).
- **Repoint exact-name reads** of the state rows to the base group, so they match both the state rows now and the federal row after the switch. Find them with `git grep -nE "\b({wl1}|{wl2}|...)_{program}\b" -- programs/programs ':!**/tests/**'`. Then `has_benefit("tx_wic")` becomes `has_base_benefit("wic")`, and `"co_wic"` in a `has_benefit_from_list` list becomes `"wic"`. First confirm every state row carries the `base_program` (query staging).
- **Keep the state calculators, specs, configs and their PolicyEngine inputs.** A deploy pushes code before it migrates, so deleting them in the release that switches their rows off leaves live rows with no calculator in between: `UnregisteredCalculatorError`, the program drops out, and Sentry logs it on every screen. They're deleted in the cleanup (6.4).
- **No migration.** Nothing changes for users: the state rows keep serving the program.
- The program-ops record lists the federal program's own navigators and documents. State navigators go on as **references** (`{"external_name": ...}` only), because a full entry would own the row on `federal` and show it in every state. They also need navigators on federal programs filtered by white label: check that `screener/navigators.py` on `main` has `filter_by_white_label` (MFB-2375). Until it does, leave the state navigators for the cleanup. State warnings need a gate on `screen.white_label`.

### 6.2 PR 2, the switch-over migration (release N+1)

One data migration. Copy `programs/migrations/0201_move_state_wic_current_benefits.py`; #1851's `0200_retire_state_federal_program_rows.py` is the multi-program version. It must:

1. **List every state row it replaces** as `(white_label_code, name_abbreviated)` pairs, including inactive legacy rows (WIC had an unprefixed CO `wic`). Get the list from a staging query, not memory.
2. **Fail closed before changing anything.** Raise when the federal row isn't imported while any state row is live (switched on or holding a `CurrentBenefit`), and name the import command in the message. A database with neither does nothing and says so.
3. **Move `CurrentBenefit` rows** from the state rows to the federal row. `already_has` on results is an exact-name match, so without this, households that said they receive it see it as new. Delete the state row on screens that already hold the federal row (`(screen, program)` is unique). Keep one row per screen (`Min("id")`) and move the rest in **one bulk `UPDATE`**, not a per-row loop.
4. **Switch the state rows off** and clear their `show_in_has_benefits_step`. Never delete them: `CurrentBenefit.program` cascades, and their snapshots keep history.
5. **Switch the federal row on**, but only where a state row was live, so an environment that had the program off everywhere keeps it off. This is the one place a migration sets `active`: doing it in the same migration is what makes the switch seamless. Don't switch it on by hand on staging or prod beforehand, or the program shows twice until this deploys.
6. **Be irreversible:** `migrations.RunPython(forwards)`, with no reverse. Unapplying it can't put households back or restore the duplicates it removed. Explain the manual rollback (state rows on, federal off) in a comment.
7. **Depend on `main`'s current leaf** migration for `programs`, plus the latest `screener` migration (it touches `CurrentBenefit`).

Test it against your local database **in a rolled-back transaction** (`scratch/`, piped to `manage.py shell`). Set up the pre-release state: state rows on, federal row imported and off, seeded current benefits including a screen with two state rows and one already on the federal row. Then check four cases: not imported raises and changes nothing; the switch-over; a re-run does nothing; and unapplying it raises `IrreversibleError`.

Known gap: a browser tab loaded before the switch can save a retired state name back. That's tracked on MFB-2247 for every federal move.

### 6.3 Release sequence

Per environment, in this order (production commands are handed to David):

1. **Merge PR 1.** Staging deploys it. It reaches prod in the next weekly release (N).
2. **Import the federal row, switched off,** once PR 1 is live in that environment: `python3 scripts/import_programs.py --env staging --program {key}`, and later `--env prod`. Leave it off.
3. **Merge PR 2 only once PR 1 is in a published prod release and the federal row is imported in both staging and prod.** Merging earlier puts both PRs in one weekly release. Prod then can't import before its `migrate` runs, so `migrate` stops at the switch-over. That's safe, since it changes nothing and the state rows keep serving, but it leaves the release half-applied until someone imports, re-runs `migrate`, and runs `add_config --all`. If both are already on `main`, recommend cutting the release at PR 1's merge commit.
4. **Verify after each deploy:** state rows off, federal row on, no `CurrentBenefit` left on a state row, and a state screen shows the program once.

### 6.4 Cleanup ticket (after PR 2 is live in prod)

Create it when PR 1 opens, blocked by the program's ticket (model: MFB-2376). It covers:
- deleting the state calculators, their tests, old benefits-api specs, `_initial_config.json` files and `readd_programs.py` entries, plus the PolicyEngine inputs only they used;
- repointing tests that use a state fixture;
- restoring state navigators and warnings on the federal row (6.1).

Its "before merging" check: in every environment, the federal row is active and every state row is inactive.

## Phase 7: PR and Summary

Before opening or updating a PR, and again before saying it's ready to merge:

1. **Check migrations against the latest `main`.** `git fetch`, then merge `origin/main` into the branch. Merge is the default because it keeps review comments anchored; a rebase is fine on your own branch if you push with `--force-with-lease`. Confirm each new migration depends on `main`'s current leaf, and that `venv/bin/python manage.py makemigrations --check --dry-run` is clean (it also catches "Conflicting migrations"). Renumber if `main` moved.
2. Run the program's tests and anything touching the repointed reads.
3. Open the PR ready, not draft, with the body structure from team-claude-config `docs/PR_TEMPLATE.md`. Its **Deployment** section gives the exact commands per environment:
   - **A standalone program:** the 6.3 step 2 import after deploy, then switching it on in the admin.
   - **A federal replacement:** the 6.3 sequence, with PR 1 and PR 2 each describing their place in it.

   A program-ops PR (spec, record or decisions.md changes) uses program-ops' own `.github/pull_request_template.md`, title shape included (`spec(nslp): … — MFB-1234`). First run, on each changed spec directory: `check_spec.py <dir> [<base_dir>]`, `check_fields.py <dir>`, `check_citations.py <dir>` and `render_structure.py <dir> --check`. `check_fields.py` writes `reference/screener-fields/<today>.md`; don't commit it.
4. Push, say CI is running, and don't watch it. **Never merge unless David explicitly asks.**

Summarize:
- the files created or changed;
- test results;
- the spec's data gaps and deviations;
- for a federal replacement, which release each PR belongs to and the cleanup ticket;
- follow-ups from the ticket comments (Phase 1) still open, and for a tax program a missing prior-tax-year warning (2.3);
- the ticket's "Done when" items outside the code (other tickets to rescope, the spec's `Calculator` and `Calculator added` fields to fill after merge).

Suggest QA with `/api-qa-execution {ticket} local`. Federal programs run as `federal` test screens with no location. A scenario whose current benefit exists only as a state program runs on that state's white label.
