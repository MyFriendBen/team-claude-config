---
name: add-program
description: Implements a new benefit program from Linear ticket created by program-researcher. Follows Django best practices with automatic quality gates via hooks.
usage: /add-program <ticket-id>
example: /add-program LIN-1234
---

<command-name>add-program</command-name>

# Add Program - Implementation Skill

Implements a new benefit program following the MyFriendBen Django architecture patterns. This skill takes a Linear ticket created by the `program-researcher` tool and translates the research into production-ready code.

## Workflow

### Phase 1: Fetch Research from Linear Ticket

**CRITICAL: Use Linear API to fetch ticket and research data.**

1. **Fetch Linear Ticket**
   - User provides ticket ID like `LIN-1234` or `MFB-567`
   - Use Linear MCP tool to fetch ticket:
     ```
     mcp__Linear__get_issue with ticket ID
     ```
   - Verify ticket exists and is from program-researcher

2. **Extract Research Data from Ticket**

   The ticket description contains:
   - **Program name, state, white label** (in title or description)
   - **Eligibility criteria** (in acceptance criteria section)
   - **Test cases** (attached or in description)
   - **Data gaps** (noted in ticket body)
   - **Source URLs** (research documentation links)

   Parse the ticket description to extract:
   ```markdown
   ## Program Details
   - Program: CSFP
   - State: IL
   - White Label: il

   ## Eligibility Criteria
   1. Age: 60+ years
   2. Income: ≤130% FPL
   3. Residence: Illinois

   ## Data Gaps
   - Institutional care status (no screener field)
   - County verification (limited availability)

   ## Test Cases
   [14 test scenarios listed or attached as JSON]
   ```

3. **Present Summary to User**
   ```
   Linear Ticket: LIN-1234
   Title: Implement CSFP program for Illinois

   Research Summary:
   - Program: CSFP (Commodity Supplemental Food Program)
   - State: IL
   - 8 eligibility criteria identified
   - 2 data gaps identified (needs discussion)
   - 14 test cases available

   Data gaps to address:
   1. Institutional care status - No screener field available
   2. County residence - CSFP available in limited counties only

   Ready to proceed with implementation? (y/n)
   ```

### Phase 2: Planning (Use EnterPlanMode)

**CRITICAL: Enter plan mode BEFORE writing any code.**

1. **Research Existing Patterns**
   - Read `benefits-be/programs/models.py` to understand Program model
   - Read existing program calculators in `benefits-be/programs/calculators/`
   - Review translation patterns in `benefits-be/translations/`
   - Check test patterns in `benefits-be/programs/tests/`

2. **Identify Dependencies**
   - Which screener fields are needed?
   - Are any helper methods required?
   - Do any PolicyEngine calculations apply?
   - What translations are needed?
   - Does a `has_[program]` field need to be added to Screen? (see Step 3.4)

3. **Create Implementation Plan**
   - Map eligibility criteria to Django model fields
   - Design calculator logic with decision tree
   - Plan test coverage based on research test cases
   - Identify translation keys needed

4. **Present Plan to User** (use ExitPlanMode)
   - Show proposed model structure
   - Explain calculator approach
   - List test scenarios
   - Get approval before coding

### Phase 3: Implementation

**Work through plan systematically. Hooks will auto-run after each file change.**

#### Step 3.1: Create Program Model Entry

1. **Read existing program definitions** to understand the structure:
   ```bash
   # Look at existing programs to understand the pattern
   Read: benefits-be/programs/data/programs.json
   ```

2. **Follow the established pattern** found in existing programs
3. **Include all required fields**: name, state, white_label, eligibility_calculator, etc.
4. **Reference the calculator functions** you'll create in the next step

**After creating: Hooks run automatically**
- `file_created` hook → ruff check → auto-fix formatting
- `file_created` hook → mypy → verify types

#### Step 3.2: Create Eligibility Calculator

1. **Read existing calculators** to understand the established patterns:
   ```bash
   # Review 2-3 recent calculators for current conventions
   Glob: benefits-be/programs/calculators/*.py
   Read: benefits-be/programs/calculators/[recent_example].py
   ```

2. **Follow the patterns you observe**:
   - Return type structure (TypedDict or similar)
   - How eligibility criteria are checked
   - How missing data is tracked
   - How reasons are formatted
   - Error handling approaches
   - Use of Screen model methods

3. **Create calculator file** following the observed patterns:
   - File naming convention (e.g., `program_state.py`)
   - Function naming convention (e.g., `calculate_X_eligibility`)
   - Type hints (all functions must be typed)
   - Docstrings with eligibility criteria from Linear ticket
   - Import statements matching existing calculators

4. **Map Linear ticket criteria** to Screen model fields/methods

**After creating: Hooks run**
- `file_created` → ruff, mypy → auto-fix

#### Step 3.3: Create Value Calculator

1. **Follow value calculator patterns** from existing calculators
2. **Return type**: integer (benefit amount in cents)
3. **Check eligibility first**: Call eligibility calculator, return 0 if not eligible
4. **Calculate benefit value** based on Linear ticket research
5. **Document calculation logic** in docstring with source references

#### Step 3.4: Implement has_[benefit] (when applicable)

If this program needs to be tracked as a benefit a user may already hold:

**Backend (`benefits-be/`):**

1. Add field to Screen model (`screener/models.py`):
   ```python
   has_[program] = models.BooleanField(default=False, blank=True, null=True)
   ```
2. Add mapping in `Screen.has_benefit()` (same file):
   ```python
   "[program_name_abbreviated]": self.has_[program],
   ```
3. Add `"has_[program]"` to the `fields` tuple in `ScreenSerializer` (`screener/serializers.py`)
4. Generate migration:
   ```bash
   python manage.py makemigrations screener
   ```

5. Add to the white label config (`configuration/white_labels/[state].py`) `category_benefits` section — this is what makes the checkbox appear in the screener (follow the existing pattern for other benefits in the same category)

**Frontend (`benefits-fe/`):**

1. `src/Types/ApiFormData.ts` — add the field type:
   ```typescript
   has_[program]: boolean | null;
   ```
2. `src/Assets/updateScreen.ts` — add to the `benefits` mapping (sends form data → API):
   ```typescript
   has_[program]: formData.benefits.[program] ?? null,
   ```
3. `src/Assets/updateFormData.tsx` — add to the `benefits` object (maps API response → form state):
   ```typescript
   [program]: response.has_[program] ?? false,
   ```

#### Step 3.5: Create Translations

1. **Read existing translation files** to understand structure:
   ```bash
   Glob: benefits-be/translations/fixtures/*.json
   Read: benefits-be/translations/fixtures/[recent_example].json
   ```

2. **Follow the translation pattern**:
   - File naming convention
   - Required translation keys (program_name, description, etc.)
   - Language codes supported (en, es, etc.)
   - Text formatting and tone

3. **Create translations** for both English and Spanish:
   - Program name (full and abbreviated if applicable)
   - Program description (clear, concise)
   - Eligibility summary (user-friendly language)
   - Any program-specific fields

4. **Use clear, accessible language** - avoid jargon where possible

#### Step 3.6: Create Validation JSON File

The `import_validations` management command uses JSON files from `validations/management/commands/import_validations/data/` to create regression test scenarios. **Always create this file** from the test cases in the Linear ticket.

1. **Read the schema and example** to understand the required format:
   ```bash
   Read: benefits-be/validations/management/commands/import_validations/test_case_schema.json
   Read: benefits-be/validations/management/commands/import_validations/test_case_example.json
   ```

2. **Look at existing files** for similar programs to follow conventions:
   ```bash
   Glob: benefits-be/validations/management/commands/import_validations/data/*.json
   ```

3. **Create** `benefits-be/validations/management/commands/import_validations/data/[state]_[program].json`
   - One JSON object per test case from the Linear ticket (both eligible and ineligible scenarios)
   - Each object: `notes`, `household` (full household data per schema), `expected_results`
   - If `has_[program]` was added, include it in the `household` object (default `false` for eligible scenarios)

#### Step 3.7: Generate Tests

1. **Read existing test files** to understand testing patterns:
   ```bash
   Glob: benefits-be/programs/tests/test_*.py
   Read: benefits-be/programs/tests/test_[recent_example].py
   ```

2. **Follow the established test patterns**:
   - Test class structure and naming
   - Pytest decorators (@pytest.mark.django_db, etc.)
   - How Screen and HouseholdMember objects are created
   - Assertion patterns for eligibility results
   - How test data is structured
   - Test method naming conventions

3. **Generate comprehensive tests** based on Linear ticket test cases:
   - Cover all eligibility criteria (age, income, residence, etc.)
   - Test edge cases (boundary conditions, missing data)
   - Test value calculations
   - Test both eligible and ineligible scenarios
   - Include descriptive docstrings explaining what each test validates

4. **Aim for >90% coverage** of the calculator logic

**After creating tests: Hooks run**
- `file_created` → pytest runs on the new test file
- Coverage report generated

### Phase 4: Validation

**Run comprehensive validation checks:**

1. **Run Full Test Suite**
   ```bash
   pytest benefits-be/programs/tests/test_csfp_il.py -v --cov=programs.calculators.csfp_il
   ```
   - Should see all tests passing
   - Coverage should be >90%

2. **Run Integration Tests**
   ```bash
   pytest benefits-be/programs/tests/test_integration.py -k csfp
   ```

3. **Type Checking**
   ```bash
   mypy benefits-be/programs/calculators/csfp_il.py
   ```

4. **Lint Check** — run black against changed files following the same approach as `benefits-be/.github/workflows/format.yaml`

5. **Import and Run Validations Locally**

   Import the validation JSON file created in Step 3.6:
   ```bash
   cd benefits-be && python manage.py import_validations validations/management/commands/import_validations/data/[state]_[program].json
   ```

   Then run the validations to confirm they all pass:
   ```bash
   python manage.py validate --program [program_name_abbreviated]
   ```

   Use `--hide-skipped` to suppress programs not yet in the DB. Filter by white label if needed:
   ```bash
   python manage.py validate --program [program_name_abbreviated] --white-label [state_code] --hide-skipped
   ```

   - `Passed` count should match the number of test cases imported
   - `Failed` count must be 0
   - If you suspect a test case is failing because of an issue with the validation (and not the calculator), prompt the user before taking action

### Phase 5: Commit & Review

**Only commit after all validations pass:**

1. **Review Changes**
   ```bash
   git status
   git diff
   ```

2. **Stage Changes**
   - Add program definition
   - Add calculator
   - Add translations
   - Add tests

3. **Create Commit** (following CLAUDE.md git protocol)

   Write a clear commit message that:
   - References the Linear ticket ID
   - Summarizes the program and key eligibility criteria
   - Notes test coverage
   - Mentions translations

   **Note:** The git hook will automatically remove Claude co-author lines to ensure proper attribution to you.

4. **Push & Create PR**
   ```bash
   git push -u origin feature/add-[program]-[state]
   ```

   Create PR with:
   - **Title**: "Add [PROGRAM] program ([State])"
   - **Body**: Follow `benefits-be/.github/pull_request_template.md`

   Use `gh pr create` or GitHub UI to create the PR.

5. **Optional: Trigger CodeRabbit Review**
   - CodeRabbit will auto-review the PR
   - Address feedback using `/respond-to-coderabbit` skill (see CLAUDE.md)

## Error Handling

### If Linear Ticket Not Found
```
❌ Error: Could not find Linear ticket with ID: LIN-1234

Please verify:
- Ticket ID is correct (format: LIN-#### or MFB-###)
- You have access to the ticket
- Ticket was created by program-researcher

Usage: /add-program <ticket-id>
Example: /add-program LIN-1234
```

### If Ticket Missing Research Data
```
⚠️  Warning: Linear ticket found but missing research data.

Ticket LIN-1234: "Implement CSFP"

Missing information:
- Eligibility criteria details
- Test cases
- Data gap analysis

This may not be a program-researcher ticket.
Please verify ticket was created by the research workflow.
```

### If Data Gaps Block Implementation
```
⚠️  Warning: Research identified unresolvable data gaps:

1. County residence verification - No screener field available
2. USDA commodity calendar - External data source needed

Options:
A) Document limitations and implement with available data
B) Pause and request screener model updates
C) Consult with product team on data collection

Which approach? (A/B/C)
```

### If Tests Fail
```
❌ Test failures detected:

FAILED test_csfp_il.py::test_eligible_elderly_low_income
AssertionError: Income calculation incorrect

Review test output, fix calculator logic, and re-run tests.
Do NOT commit failing code.
```

## Quality Gates (Enforced by Hooks)

All these checks run automatically via hooks (see `.claude/hooks.json`):

- ✅ Black formatting
- ✅ MyPy type checking
- ✅ Django model validation
- ✅ Test coverage >90%
- ✅ No failing tests
- ✅ Translation keys present

## Best Practices

1. **ALWAYS enter plan mode first** - Don't write code without a plan
2. **Use research test cases** - They're designed for edge cases
3. **Handle missing data gracefully** - Return `missing_data` list
4. **Follow Django patterns** - Match existing calculator structure
5. **Write clear docstrings** - Include eligibility criteria and sources
6. **Test thoroughly** - All test cases from Linear ticket should become pytest tests
7. **Commit atomically** - One program per commit
8. **Reference Linear ticket** - Link to ticket in commit message

## Success Criteria

- ✅ All tests passing (pytest)
- ✅ Type checking clean (mypy)
- ✅ Linting clean (black)
- ✅ Coverage >90%
- ✅ Translations complete
- ✅ Validations imported and passing locally
- ✅ Clear commit message
- ✅ PR created with test plan

## Next Steps After Implementation

1. **QA Validation**: Product team tests with research scenarios
2. **Staging Deployment**: Deploy to staging environment
3. **Integration Testing**: Test with real PolicyEngine data
4. **Production Deployment**: Roll out to users

---

## Linear Ticket Format Expected

The Linear ticket should follow the program-researcher output format:

```markdown
# Title
Implement [PROGRAM] for [STATE]

# Description

## Program Details
- **Program**: CSFP (Commodity Supplemental Food Program)
- **State**: Illinois (IL)
- **White Label**: il
- **Agency**: USDA Food and Nutrition Service
- **Category**: Food assistance

## Eligibility Criteria

1. **Age**: 60 years or older
   - Screener field: `household_members.age`
   - Method: `get_elderly_members(age_threshold=60)`

2. **Income**: At or below 130% Federal Poverty Level
   - Screener field: `household_income_gross`
   - Method: `get_fpl_percentage_threshold(130)`

3. **Residence**: Illinois
   - Screener field: `state`

## Benefit Value
- **Amount**: $60/month in commodity foods
- **Calculation**: $60 × eligible_seniors × 12 months
- **Source**: USDA CSFP 2024 estimates

## Data Gaps

1. **Institutional care status**
   - Not captured in screener
   - Recommendation: Document as limitation

2. **County of residence**
   - CSFP available in limited counties only
   - Recommendation: Note in program description

## Test Cases

[Either embedded in ticket or attached as JSON file]

1. Eligible - 65yo single senior, 100% FPL ✅
2. Ineligible - 55yo (too young) ❌
... (12 more)

## Research Sources
- https://www.fns.usda.gov/csfp
- https://www.dhs.state.il.us/page.aspx?item=30513
```

## Workflow Integration

```
Step 1: Research (LangGraph)
  └─> program-researcher creates Linear ticket

Step 2: Implementation (Claude Code)
  └─> /add-program LIN-1234
      ├─> Fetch ticket via Linear API
      ├─> Extract research data from ticket
      └─> Generate Django code

Step 3: Review
  └─> CodeRabbit + Human review
```

**Remember**: This skill implements ONE program at a time. If you need to add multiple programs, run `/add-program` for each Linear ticket separately.
