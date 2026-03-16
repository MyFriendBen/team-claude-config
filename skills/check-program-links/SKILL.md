---
name: check-program-links
description: Audit program learn_more_link URLs, find replacements for broken links, and generate SQL updates with human validation checkpoints.
---

# Check Program Links - Link Audit Workflow

Audits all program `learn_more_link` URLs in the database, identifies broken links, searches for working replacements, and generates SQL UPDATE statements for human review and manual execution.

## Core Principle

**NEVER automatically execute SQL.** All database changes require:
1. Human review of proposed changes
2. Manual execution by the user

## Workflow Phases

### Phase 1: Export Programs (Automated)

1. **Check project location**
   ```bash
   cd /Users/jm/code/mfb
   ```

2. **Present SQL query for user execution**
   - Read the query from `${CLAUDE_SKILL_DIR}/templates/export_programs.sql`
   - Provide the user with the command to execute:
     ```bash
     psql "$DATABASE_URL" -f ${CLAUDE_SKILL_DIR}/templates/export_programs.sql --csv -o programs_export.csv
     ```
   - Wait for user to run the command and confirm CSV is generated
   - Filter for `language_code = 'en-us'`
   - Column order:
     1. program_id
     2. program_name
     3. learn_more_link
     4. name_abbreviated
     5. white_label_code
     6. white_label_name
     7. name_language
     8. active
   - Save to `programs_export.csv`

   **Note:** Column order will change in Phase 2 when link_status is added as column 4 (right after learn_more_link)

3. **Verify export with user**
   - Ask user to confirm CSV file was created
   - Read and display CSV sample (first 5 rows)
   - Count rows to confirm data exported

### Phase 2: Check Link Status (Automated)

1. **Check HTTP status of each link**
   - Use the existing `${CLAUDE_SKILL_DIR}/templates/check_link_status.py` script OR
   - Implement inline using requests library
   - For each URL:
     - **Skip if URL is empty or blank** - leave link_status empty
     - **Skip if URL is malformed/invalid** - leave link_status empty
     - Try HEAD request first (faster)
     - Fall back to GET if HEAD returns 405
     - Timeout: 10 seconds
     - Record numeric status code (200, 404, 403, etc.)

2. **Status codes to track**
   - `200` - Working (verified by automated check)
   - `404` - Not found (may be false positive - requires manual verification)
   - `403` - Forbidden (may be blocking bots - requires manual verification)
   - `(blank)` - Empty or invalid URL (no check performed)

   **IMPORTANT:** Automated checks have limitations:
   - Sites with bot protection may return 404/403 but work in browsers
   - User MUST manually click and verify all non-200 links before proceeding
   - Update CSV with "200 (manual)" for links that work when clicked

   **Note:** Only numeric HTTP status codes are recorded. Empty/invalid URLs have blank link_status for better readability (numeric codes are right-aligned).

3. **Save results**
   - Add `link_status` column as column 4 (right after `learn_more_link`)
   - Updated column order:
     1. program_id
     2. program_name
     3. learn_more_link
     4. **link_status** (NEW)
     5. name_abbreviated
     6. white_label_code
     7. white_label_name
     8. name_language
     9. active
   - Save as `programs_export_with_status.csv`

4. **Generate summary report**
   ```
   Link Status Summary:
   - Working (200): X links
   - Broken (404): Y links
   - Forbidden (403): Z links
   - Empty: N links
   ```

5. **Manual validation of non-200 links**
   - **IMPORTANT**: Automated HTTP checks may incorrectly flag working URLs as 404/403
   - Many sites have bot protection that blocks automated requests but work fine in browsers
   - Instruct user: "Please manually click through all non-200 links to verify"
   - User should update CSV to mark actually-working links as "200 (manual)" in link_status column
   - This manual verification step prevents unnecessary replacement searches

6. **CHECKPOINT 1: Present summary**
   - Show the summary report
   - Remind user to manually validate non-200 links before proceeding
   - Ask: "Have you manually validated non-200 links and updated the CSV? Continue to find replacements for remaining broken links? (y/n)"
   - If no, stop here

### Phase 3: Find Replacement URLs (Semi-automated)

**Note:** Only proceed after user has manually validated non-200 links in Phase 2

1. **Identify broken links**
   - Filter for status `404` and `403` (excluding any marked "200 (manual)")
   - Extract program info: name_abbreviated, program_name, white_label_code

2. **For each broken link:**
   - Announce: "Searching for: {program_name} ({white_label_code})..."

   - Use WebSearch to find official replacement:
     - Search query: "{program_name} {white_label} official site 2026"
     - Look for: Government sites, official program pages
     - Prioritize: .gov, .org, official state sites

   - Extract best URL from search results

   - Verify replacement works:
     - Check HTTP status of new URL
     - Should return 200

   - Show result: "Found: {new_url}" or "No replacement found"

3. **Update CSV**
   - Add `replacement_link` column
   - Populate with found URLs
   - Save updated `programs_export_with_status.csv`

4. **CHECKPOINT 2: Present replacements for review**
   - Show table of all replacements:
     ```
     Program         Old URL (Status)    New URL
     co_snap         peak...com (404)    cdhs.colorado.gov/snap
     ```
   - Say: "Please review programs_export_with_status.csv"
   - Say: "Verify the replacement_link column has appropriate URLs"
   - Ask: "Are these replacements acceptable? (y/n)"
   - If no, offer to:
     - Regenerate specific replacements
     - Let user manually edit CSV
     - Stop here

### Phase 4: Generate SQL (Automated)

1. **Read CSV with replacements**
   - Filter rows where `replacement_link` is not empty

2. **For each replacement:**
   - Generate UPDATE statement (see `${CLAUDE_SKILL_DIR}/templates/example_update_links.sql` for reference):
     ```sql
     UPDATE translations_translation_translation
     SET text = '{new_url}'
     WHERE master_id = (
       SELECT learn_more_link_id
       FROM programs_program
       WHERE name_abbreviated = '{name_abbrev}'
       LIMIT 1
     );
     ```

   - Handle duplicates (e.g., `nslp` in multiple states):
     ```sql
     WHERE master_id IN (
       SELECT learn_more_link_id
       FROM programs_program
       WHERE name_abbreviated = '{name_abbrev}'
     );
     ```

3. **Add summary query**
   - Include SELECT at end to show updated programs:
     ```sql
     SELECT
       p.name_abbreviated,
       wl.name as white_label,
       tt.text as updated_link
     FROM programs_program p
     JOIN screener_whitelabel wl ON p.white_label_id = wl.id
     JOIN translations_translation t ON p.learn_more_link_id = t.id
     JOIN translations_translation_translation tt ON t.id = tt.master_id
     WHERE p.name_abbreviated IN ('co_snap', 'co_tanf', ...)
     ORDER BY wl.name, p.name_abbreviated;
     ```

4. **Save SQL file**
   - Write to `update_links.sql`
   - Include header comments with:
     - Date generated
     - Number of updates
     - Warning about manual execution

5. **CHECKPOINT 3: Present SQL for review**
   - Show file path and summary:
     ```
     Generated: update_links.sql
     Contains: 24 UPDATE statements
     ```
   - Show first few UPDATE statements
   - Provide execution options:
     ```bash
     # Test on staging:
     psql "$STAGING_DATABASE_URL" -f update_links.sql

     # Execute on production:
     psql "$DATABASE_URL" -f update_links.sql

     # Dry-run (rollback after):
     psql "$DATABASE_URL" << 'EOF'
     BEGIN;
     \i update_links.sql
     ROLLBACK;
     EOF
     ```
   - Say: "Please review update_links.sql before executing"
   - Say: "When ready, run the SQL manually using one of the options above"

### Phase 5: Summary

Present final summary:
```
Link Audit Complete!

Files generated:
  - programs_export.csv (original export)
  - programs_export_with_status.csv (with status and replacements)
  - update_links.sql (for manual execution)

Summary:
  - Total programs: 179
  - Working links: 112
  - Broken links fixed: 24
  - SQL statements: 24

Next steps:
  1. Review update_links.sql
  2. Test on staging (recommended)
  3. Execute on production when ready
```

## Important Notes

### Database Connection
- User must have `DATABASE_URL` environment variable set
- Claude never accesses database directly
- User runs all psql commands manually
- Claude only reads/writes CSV files

### Language Filter
- Always use `language_code = 'en-us'`
- This is the primary language in production

### Safety
- Claude never executes ANY SQL (including SELECT queries)
- All database queries are run manually by the user
- Never use Django ORM to update translations
- Never execute SQL automatically
- Always generate SQL file for manual review
- Recommend staging test before production

### Column Order (Always maintain)
1. program_id
2. program_name
3. learn_more_link
4. name_abbreviated
5. white_label_code
6. white_label_name
7. name_language
8. active

### Error Handling
- If CSV export fails: Check database connection
- If link checks timeout: Continue with remaining links
- If web search fails: Mark as "No replacement found"
- If SQL generation fails: Show error and stop

## Supporting Files

### Templates (in this skill directory)
Read from `${CLAUDE_SKILL_DIR}/templates/`:
- `export_programs.sql` - SQL query for exporting programs
- `check_link_status.py` - Python script to check HTTP status
- `example_update_links.sql` - Example SQL UPDATE statements with real data

### Output Files (generated in project directory)
- `programs_export.csv` - Exported programs
- `programs_export_with_status.csv` - With HTTP status and replacement URLs
- `update_links.sql` - Final SQL UPDATE statements (for manual execution)

## Example Session

```
User: /check-program-links

You: Starting link audit workflow...

Phase 1: Exporting programs from database...
Exported 179 programs to programs_export.csv

Phase 2: Checking HTTP status of all links...
Checked 179 links in 2m 15s

Link Status Summary:
  200 (Working):     112 links
  404 (Not Found):    20 links
  403 (Forbidden):     4 links
  EMPTY:              43 links

CHECKPOINT: Continue to find replacements? (y/n)

User: y

Phase 3: Finding replacement URLs for 24 broken links...

Searching for: Colorado SNAP (co)...
Found: https://cdhs.colorado.gov/snap (200 OK)

Searching for: Colorado TANF (co)...
Found: https://cdhs.colorado.gov/colorado-works-tanf (200 OK)

[...continues for each broken link...]

Found working replacements for 23 of 24 broken links

CHECKPOINT: Please review programs_export_with_status.csv
The replacement_link column contains the new URLs.

Are these replacements acceptable? (y/n)

User: y

Phase 4: Generating SQL UPDATE statements...
Generated update_links.sql with 23 UPDATE statements

CHECKPOINT: Please review update_links.sql before executing.

To execute:
  # Test on staging first (recommended):
  psql "$STAGING_DATABASE_URL" -f update_links.sql

  # Or on production:
  psql "$DATABASE_URL" -f update_links.sql

Please review SQL before running on production!

---

Link Audit Complete!

Next steps:
  1. Review update_links.sql
  2. Test on staging
  3. Execute when ready
```

## Troubleshooting

**"No programs exported"**
- Check DATABASE_URL environment variable
- Verify connection: `psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM programs_program;"`

**"Too many 403 errors"**
- These sites may block bots but work for users
- Review manually in browser
- 403 often means site is working but blocking automated checks

**"WebSearch failing"**
- Try alternative search terms
- Fall back to manual URL finding
- Ask user for help: "I couldn't find a replacement for X. Do you know the official site?"

**"Want to re-run a phase"**
- Delete output file and re-run command
- CSV files can be manually edited
- SQL can be regenerated from CSV
