---
name: playwright-qa-execution
description: Execute automated QA test scenarios from Linear ticket using Playwright MCP for benefits screener testing. Use in a separate session with Playwright MCP enabled.
disable-model-invocation: true
---

# Playwright MCP QA Testing Skill

Automates browser testing of benefits screener using Playwright MCP. Fetches test scenarios from Linear ticket, systematically executes them against specified environment, and documents results locally.

**Related:** This is typically used as Step 6 in the AI_PROGRAM_QA_PROCESS.md workflow.

---

## Overview

This skill:
1. Fetches a Linear ticket containing QA test scenarios
2. Extracts test scenarios and program details from ticket
3. Executes each scenario against specified environment (staging/production/local)
4. Documents results in local `qa/` directory

---

## Prerequisites

**CRITICAL:** Before starting, verify:
- [ ] Playwright MCP server is enabled in THIS session
- [ ] Linear MCP server is enabled for ticket fetching
- [ ] You have access to launch a browser (not headless-only environment)
- [ ] Linear ticket contains test scenarios section (see format below)
- [ ] Target environment is accessible

If Playwright MCP or Linear MCP is not available, STOP and notify the user.

---

## Expected Linear Ticket Format

The Linear ticket must contain a structured description with the following sections:

```markdown
## Program Details
- Program: [Program Name]
- State: [State Code]
- White Label: [White Label ID]

## Test Scenarios

### Scenario 1: [Description]
**Household:**
- Member 1: [Head/Spouse/Child], Age [X], Income: $[amount]/[frequency] ([type])
- Member 2: [Relation], Age [Y], No income, Student

**Expected Outcome:** [Program Name] [shown as eligible / NOT shown]

### Scenario 2: [Description]
**Household:**
- Member 1: [Details]

**Expected Outcome:** [Expected result]
```

**Required fields for each scenario:**
- Scenario number and description
- Household member details (relation, age, income, conditions)
- Expected eligibility outcome (shown/not shown, eligible/ineligible)

**Optional fields:**
- Expenses (rent, childcare, etc.)
- Assets
- Existing benefits
- ZIP code (defaults to first ZIP in state)

---

## Required Arguments

1. **Linear Ticket ID**: The ticket containing test scenarios (e.g., `MFB-1234`, `LIN-567`)
2. **Environment** (optional): Target environment - `staging` (default), `production`, or `local`
3. **Output Directory** (optional): Directory for results, defaults to `qa/`

**Example invocations:**
```
/playwright-qa-execution MFB-1234                    # Staging, qa/ directory
/playwright-qa-execution MFB-1234 staging            # Explicit staging
/playwright-qa-execution MFB-1234 production         # Production environment
/playwright-qa-execution MFB-1234 local              # Local development
/playwright-qa-execution MFB-1234 staging qa-results # Custom directory
```

---

## Environment Configuration

The skill supports three environments with different base URLs:

**Staging (default):**
```
Base URL: https://benefits-calculator-staging.herokuapp.com/{state}
Use case: Standard QA testing, safe for experimentation
```

**Production:**
```
Base URL: https://screener.myfriendben.org/{state}
Use case: Final verification before release, smoke testing
WARNING: Use with caution, affects live users
```

**Local:**
```
Base URL: http://localhost:3000/{state}
Use case: Development testing, debugging
Requires: Local dev server running
```

**IMPORTANT:** If environment is `production`, display a warning and ask for confirmation before proceeding:
```
WARNING: Running tests against PRODUCTION environment

This will create real data in the production system.
Are you sure you want to proceed? (yes/no)
```

Only proceed if user explicitly confirms with "yes".

---

## Workflow

### Phase 1: Fetch Test Scenarios from Linear

**CRITICAL: Use Linear API to fetch ticket and extract test scenarios.**

1. **Parse Arguments**
   - Required: Linear ticket ID (e.g., `MFB-1234`)
   - Optional: Environment (default: `staging`)
   - Optional: Output directory (default: `qa`)

   ```javascript
   const ticketId = args[0];  // Required
   const environment = args[1] || 'staging';  // Default: staging
   const outputDir = args[2] || 'qa';  // Default: qa
   ```

2. **Determine Base URL from Environment**
   ```javascript
   const baseUrls = {
     staging: 'https://benefits-calculator-staging.herokuapp.com',
     production: 'https://screener.myfriendben.org',
     local: 'http://localhost:3000'
   };

   const baseURL = baseUrls[environment];
   ```

   **If environment is `production`, show warning:**
   ```
   WARNING: Running tests against PRODUCTION environment

   This will create real data in the production system.
   Are you sure you want to proceed? (yes/no)
   ```

   Wait for user confirmation. Only proceed if user types "yes".

3. **Fetch Linear Ticket**
   - Use Linear MCP tool to fetch ticket:
     ```
     mcp__Linear__get_issue with ticket ID
     ```
   - Verify ticket exists and contains test scenarios

4. **Parse Ticket for Required Information**

   The ticket description should contain sections like:
   ```markdown
   ## Program Details
   - Program: CSFP
   - State: CO
   - White Label: co

   ## Test Scenarios

   ### Scenario 1: Eligible - Single Senior
   **Household:**
   - Member 1: Head, Age 65, Income: $1,500/month (wages)

   **Expected Outcome:** CSFP shown as eligible

   ### Scenario 2: Ineligible - Too Young
   **Household:**
   - Member 1: Head, Age 45, Income: $1,200/month (wages)

   **Expected Outcome:** CSFP NOT shown
   ```

   Extract:
   - Program name
   - State code / white label
   - Each test scenario with:
     - Scenario number and description
     - Household member details (age, income, relation, conditions)
     - Expected eligibility outcome

5. **Present Summary to User**
   ```
   Linear Ticket: MFB-1234
   Title: QA Test Scenarios for CSFP - Colorado

   Program: CSFP (Commodity Supplemental Food Program)
   State: CO
   White Label: co
   Environment: STAGING
   Test Scenarios Found: 14

   Scenarios will be executed against:
   https://benefits-calculator-staging.herokuapp.com/co

   Results will be saved to: qa/MFB-1234-csfp-results.md

   Ready to proceed with execution? (y/n)
   ```

   **If user confirms, continue. If not, stop and await further instructions.**

4. **Create Output Directory Structure**
   ```bash
   mkdir -p qa
   ```

5. **Initialize Results File**
   - Create file: `{outputDir}/{TICKET-ID}-{program-name}-results.md`
   - Add header with ticket metadata:
   ```markdown
   # QA Test Results - [Program Name] - [State]

   **Linear Ticket:** [{TICKET-ID}](linear-ticket-url)
   **Test Date:** [Current Date]
   **Environment:** [STAGING/PRODUCTION/LOCAL]
   **Screener URL:** [baseURL]/[state]
   **Tester:** Playwright MCP Automation

   ## Test Scenarios

   | Scenario | Description | Expected | Actual | Result | URL |
   |----------|-------------|----------|--------|--------|-----|
   ```

6. **Create Todo List**
   - Create task for each test scenario extracted from Linear
   - Track progress through execution
   - Mark scenarios complete as you go

---

### Phase 2: Setup & Validation

1. **Verify Environment**
   ```javascript
   // Check that Playwright MCP tools are available
   // Confirm browser can be launched
   ```

2. **Validate Parsed Data**
   - Ensure all scenarios have complete household data
   - Verify state code is valid
   - Confirm expected outcomes are clearly defined
   - If any data is missing or unclear, report to user and stop

---

### Phase 3: Execute Test Scenarios

For each scenario parsed from Linear ticket, follow this systematic process:

#### 1. Navigate to Screener

```javascript
// Use state from Linear ticket and baseURL from environment config
const state = "co"; // Extracted from Linear ticket Program Details
const screenerURL = `${baseURL}/${state}`; // baseURL determined in Phase 1
await page.goto(screenerURL);
```

#### 2. Complete 12-Step Form Flow

**Step 1: Language Selection**
```javascript
await page.getByRole("button", { name: "English" }).click();
// Or for Spanish: await page.getByRole("button", { name: "Español" }).click();
await page.waitForTimeout(2000);
```

**Step 2: Legal/Privacy**
```javascript
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
```

**Step 3: ZIP Code**
```javascript
await page.getByRole("textbox", { name: "ZIP Code" }).fill("80202");
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
```

**Step 4: Household Size**
```javascript
await page.getByRole("button", { name: "Household Size" }).click();
await page.waitForTimeout(500);
await page.getByRole("option", { name: "2" }).click();
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
```

**Step 5: Household Members** (Loop for each member)

For the head of household:
```javascript
// Name
await page.getByRole("textbox", { name: "First Name" }).fill("John");
await page.getByRole("textbox", { name: "Last Name" }).fill("Doe");

// Birth date
await page.getByRole("button", { name: "Birth Month" }).click();
await page.getByRole("option", { name: "January" }).click();
await page.getByRole("combobox", { name: "Birth Year" }).fill("1990");

// Relation (only for non-head members)
// await page.getByRole("button", { name: "Relation" }).click();
// await page.getByRole("option", { name: "Child", exact: true }).click();

// Income
await page.getByText("Yes", { exact: true }).click(); // Has income
await page.getByRole("button", { name: "Income Type" }).click();
await page.getByRole("option", { name: /Wages, salaries, tips/i }).click();
await page.getByRole("button", { name: "Frequency" }).click();
await page.getByRole("option", { name: "every month" }).click();
await page.getByRole("textbox", { name: "Amount" }).fill("2500");

// Conditions (if applicable)
await page.getByRole("button", { name: "Student" }).click(); // Toggle on
await page.getByRole("button", { name: "Disabled" }).click(); // Toggle on

// Continue to next member or next step
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
```

**GOTCHA:** After clicking Student/Disabled buttons, income may auto-switch to "Yes". If member has no income, explicitly set it:
```javascript
await page.locator("label").filter({ hasText: /^No$/ }).click();
```

**Step 6: Expenses**
```javascript
// If no expenses
await page.getByText("None of these").click();
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);

// If has expenses (example: rent)
// await page.getByRole("button", { name: "Rent" }).click();
// await page.getByRole("textbox", { name: "Amount" }).fill("1200");
// await page.getByRole("button", { name: "Frequency" }).click();
// await page.getByRole("option", { name: "every month" }).click();
```

**Step 7: Assets**
```javascript
await page.getByRole("textbox", { name: "Total Assets" }).fill("5000");
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
```

**Step 8: Existing Benefits**
```javascript
// Check any current benefits or leave unchecked
// await page.getByRole("checkbox", { name: "SNAP" }).check();
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
```

**Step 9: Near-Term Help**
```javascript
await page.getByText("None of these").click();
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
```

**Step 10: Referral Source**
```javascript
await page.locator("#referral-source-select").click();
await page.getByRole("option", { name: "Test / Prospective Partner" }).click();
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
```

**Step 11: Optional Signup**
```javascript
await page.getByRole("button", { name: "Continue Without an Account" }).click();
await page.waitForTimeout(2000);
```

**Step 12: Confirmation**
```javascript
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(5000); // Wait for results to load
```

#### 3. Verify Results

```javascript
// Get current URL (contains UUID for permanent link)
const resultsURL = page.url();

// Verify total programs count
const programsCountText = await page.locator("text=/\\d+ Programs Found/").textContent();

// Check for specific program presence
const programVisible = await page.getByText("Program Name", { exact: true }).isVisible();

// Take screenshot if needed for documentation
// await page.screenshot({ path: 'scenario-1-results.png' });
```

#### 4. Document Results

Update the results file with findings:
```markdown
| 1 | Single adult, age 65+, low income | Yes | Yes | PASS | [Results](https://benefits-calculator-staging.herokuapp.com/results/abc-123) |
```

For failures, document:
```markdown
| 2 | Single adult, age 45, low income | No | Yes (BUG) | FAIL | [Results](https://benefits-calculator-staging.herokuapp.com/results/def-456) |

**Failure Details:**
- Expected: Program NOT shown (age requirement not met)
- Actual: Program shown as eligible
- Issue: Age validation not working correctly
```

#### 5. Update Task Progress

Mark scenario complete in todo list and move to next scenario.

---

## Common Patterns & Solutions

### Dropdown Selections

**Standard dropdowns:**
```javascript
await page.getByRole("button", { name: "Dropdown Label" }).click();
await page.waitForTimeout(500);
await page.getByRole("option", { name: "Option Value" }).click();
```

**Relation dropdown (avoid partial matches):**
```javascript
await page.getByRole("button", { name: "Relation" }).click();
await page.getByRole("option", { name: "Child", exact: true }).click();
```

**Referral dropdown (requires ID selector):**
```javascript
await page.locator("#referral-source-select").click();
await page.getByRole("option", { name: "Option Text" }).click();
```

### Multiple Household Members

Loop through each member configuration from test scenario:
```javascript
for (const member of scenario.householdMembers) {
  // Fill member form fields
  // Click Continue
  await page.waitForTimeout(2000);
}
```

### Income Entry Patterns

**No income:**
```javascript
await page.getByText("No", { exact: true }).click();
```

**Has income:**
```javascript
await page.getByText("Yes", { exact: true }).click();
await page.getByRole("button", { name: "Income Type" }).click();
await page.getByRole("option", { name: "Wages, salaries, tips" }).click();
await page.getByRole("button", { name: "Frequency" }).click();
await page.getByRole("option", { name: "every month" }).click();
await page.getByRole("textbox", { name: "Amount" }).fill("2500");
```

### Condition Toggles

Student, Disabled, Pregnant, etc. are toggle buttons:
```javascript
await page.getByRole("button", { name: "Student" }).click(); // On
await page.getByRole("button", { name: "Student" }).click(); // Off (if clicked again)
```

### Debugging & Snapshots

When encountering issues:
```javascript
// Take snapshot to see current page state
await page.screenshot({ path: 'debug-snapshot.png', fullPage: true });

// Log current URL
console.log('Current URL:', page.url());

// Check for validation errors
const errorText = await page.locator('[role="alert"]').textContent();
```

---

## Results Documentation

### Pass Result Format
```markdown
| 1 | Description | Expected | Actual | PASS | [Link](url) |
```

### Fail Result Format
```markdown
| 2 | Description | Expected | Actual (BUG) | FAIL | [Link](url) |

**Bug Details:**
- Expected behavior: Program should not appear (income too high)
- Actual behavior: Program shown as eligible
- Possible cause: Income threshold validation not applied
- Screenshot: scenario-2-failure.png
```

### Results Summary

After all scenarios, add summary section:
```markdown
## Summary

- **Total Scenarios:** 14
- **Passed:** 12
- **Failed:** 2
- **Pass Rate:** 85.7%

## Failed Scenarios

1. **Scenario 2** - Income threshold not validated correctly
2. **Scenario 7** - Age requirement bypassed for disabled applicants

## Recommendations

- Fix income validation in eligibility calculator
- Review age requirement logic for disabled applicants
- Add unit tests for edge cases
- Re-run failed scenarios after fixes
```

---

## Tips for Efficiency

1. **Use `browser_run_code` for multi-step actions** on a single page (filling entire member form)
2. **Batch related field entries** before clicking Continue
3. **Take snapshots sparingly** - only when debugging or documenting failures
4. **Update results incrementally** - don't wait until all scenarios complete
5. **Mark todos complete immediately** after each scenario
6. **Parallelize when possible** - if running multiple programs, use separate browser contexts

---

## Error Handling

### Form Validation Errors
If Continue button doesn't advance:
1. Take snapshot to identify missing fields
2. Check for validation error messages
3. Verify all required fields are filled
4. Document as test execution issue vs. bug

### Page Load Issues
If results don't load:
1. Wait longer (up to 10 seconds)
2. Check for error messages on page
3. Verify URL changed to results page
4. Document as infrastructure issue

### Element Not Found
If selector fails:
1. Take snapshot to see page state
2. Check if form step changed
3. Verify element text/role matches expected
4. Update selector if UI changed

---

## Phase 4: Final Reporting

After all scenarios executed:

1. **Calculate Pass Rate**
   - Count passed vs. failed scenarios
   - Add summary section to results file

2. **Identify Patterns**
   - Group similar failures
   - Note any systematic issues

3. **Generate Recommendations**
   - Suggest fixes for failed scenarios
   - Recommend additional test coverage
   - Note any UI/UX issues discovered

4. **Add Summary to Results File**
   Append to `qa/{TICKET-ID}-{program}-results.md`:
   ```markdown
   ## Summary

   - **Total Scenarios:** 14
   - **Passed:** 12
   - **Failed:** 2
   - **Pass Rate:** 85.7%

   ## Failed Scenarios

   1. **Scenario 2** - Income threshold not validated correctly
   2. **Scenario 7** - Age requirement bypassed for disabled applicants

   ## Recommendations

   - Fix income validation in eligibility calculator
   - Review age requirement logic for disabled applicants
   - Add unit tests for edge cases identified
   - Re-run failed scenarios after fixes
   ```

5. **Provide Results Summary to User**
   ```
   QA Execution Complete

   Linear Ticket: MFB-1234
   Program: CSFP
   State: CO
   Environment: STAGING
   Screener URL: https://benefits-calculator-staging.herokuapp.com/co

   Results: 12/14 scenarios passed (85.7%)
   Failed scenarios: 2, 7
   Results file: qa/MFB-1234-csfp-results.md

   Key findings:
   - Income validation bug affects 1 scenario
   - Age requirement logic needs review for disabled applicants

   Next steps:
   1. Review results file: qa/MFB-1234-csfp-results.md
   2. File bugs for failed scenarios
   3. Re-run this command after fixes are deployed:
      /playwright-qa-execution MFB-1234 staging
   ```

---

## Quality Gates

- All scenarios must be executed systematically
- Results must be documented in consistent format
- Screenshots required for ALL failed scenarios
- Results URLs must be captured for reproducibility
- Summary section required with pass rate and recommendations

---

## Integration with QA Process

This skill is typically invoked as **Step 6** in the AI_PROGRAM_QA_PROCESS:

1. Program research and implementation
2. Test scenario generation in Linear ticket
3. Manual review of scenarios
4. **Automated execution (THIS SKILL)**
5. Review results in local `qa/` directory
6. Bug filing for failures
7. Re-testing after fixes (re-run this skill)
8. Final QA approval

---

## Troubleshooting

### Playwright MCP Not Available
If tools not available:
- Verify MCP server is enabled in session settings
- Check that Playwright MCP is installed
- Restart session and try again

### Browser Launch Fails
If cannot launch browser:
- Check environment supports headed browser
- Try headless mode if available
- Verify Playwright dependencies installed

### Selectors Not Working
If elements not found:
- UI may have changed - take snapshot
- Check element roles/labels
- Verify correct form step
- Update selectors in this guide

### Test Data Issues
If scenarios incomplete:
- Verify test scenarios file has all required fields
- Check household member configurations
- Ensure expected outcomes are clearly defined

---

## Notes

- This skill REQUIRES Playwright MCP enabled in the session
- Use SEPARATE session from main development work
- Staging environment recommended (avoid production testing)
- Results are saved for traceability and bug reporting
- Screenshots provide evidence for QA sign-off
