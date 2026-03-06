# Check Program Links - Example Workflow

This document shows a complete example session of using `/check-program-links`.

## Prerequisites

```bash
# Set database connection
export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Navigate to MyFriendBen project
cd ~/code/mfb
```

## Session Start

```
User: /check-program-links
```

## Phase 1: Export Programs

```
Claude: Starting link audit workflow...

Phase 1: Exporting programs from database...

Reading SQL template from team-claude-config/commands/check-program-links/templates/export_programs.sql

Please run this command to export programs:

  psql "$DATABASE_URL" -f team-claude-config/commands/check-program-links/templates/export_programs.sql --csv -o programs_export.csv

User: [runs command]
Done! Created programs_export.csv

Claude: ✓ Reading programs_export.csv - found 179 programs

Sample (first 3 rows):
program_id | program_name                          | learn_more_link
1          | Supplemental Nutrition Assistance... | https://peak--coloradopeak.force.com/...
2          | Affordable Connectivity Program      | https://nv.fcc.gov/lifeline/...
3          | Lifeline                             | https://nv.fcc.gov/lifeline
```

## Phase 2: Check Link Status

```
Claude: Phase 2: Checking HTTP status of all links...

Checking 1: co_snap - https://peak--coloradopeak.force.com/...
  Status: 404

Checking 2: acp - https://nv.fcc.gov/lifeline/?id=nv_flow...
  Status: 200

[... continues for all 179 programs ...]

✓ Checked 179 links in 2m 15s

Link Status Summary:
  ✓ 200 (Working):     112 links
  ✗ 404 (Not Found):    20 links
  ✗ 403 (Forbidden):     4 links
  ⊘ EMPTY:              43 links

Saved results to: programs_export_with_status.csv

⚠️  IMPORTANT: Please manually validate non-200 links!

   Automated checks may incorrectly flag working URLs as 404/403 due to:
   - Bot protection
   - Anti-scraping measures
   - Server security policies

   Please:
   1. Open programs_export_with_status.csv
   2. Click through each 404/403 link in your browser
   3. Update link_status to "200" for links that actually work
   4. Save the CSV before continuing
```

## Checkpoint 1: Continue?

```
Claude: CHECKPOINT 1: Found 24 links with non-200 status.

Have you manually validated the non-200 links and updated the CSV?
Continue to find replacements for remaining broken links? (y/n)

User: [User manually checks links, updates CSV]

User: y
```

## Phase 3: Find Replacements

```
Claude: Phase 3: Finding replacement URLs for 24 broken links...

🔍 Searching for: Supplemental Nutrition Assistance Program (SNAP) (Colorado)...
   Query: "Colorado SNAP official site 2026"
   Checking: https://cdhs.colorado.gov/snap
   ✓ Found: https://cdhs.colorado.gov/snap (200 OK)

🔍 Searching for: Colorado Works (TANF) (Colorado)...
   Query: "Colorado TANF Colorado Works official site 2026"
   Checking: https://cdhs.colorado.gov/colorado-works-tanf
   ✓ Found: https://cdhs.colorado.gov/colorado-works-tanf (200 OK)

[... continues for each broken link ...]

✓ Found working replacements for 23 of 24 broken links
✗ No replacement found for: bca (Basic Cash Assistance for Families)

Updated programs_export_with_status.csv with replacement_link column
```

## Checkpoint 2: Review Replacements

```
Claude: CHECKPOINT 2: Review proposed replacement URLs

Found 23 replacement URLs:

Program      | Old URL (Status)           | New URL
-------------|----------------------------|----------------------------------
co_snap      | peak...com (404)          | cdhs.colorado.gov/snap
co_tanf      | peak...com (404)          | cdhs.colorado.gov/colorado-works-tanf
co_medicaid  | peak...com (404)          | healthfirstcolorado.com
rtdlive      | rtd-denver.com/... (404)  | rtd-denver.com/fares-passes/pass-programs/live
[... 19 more ...]

📝 Please review programs_export_with_status.csv
   Open the file and verify the replacement_link column.

Are these replacements acceptable? (y/n)

User: y
```

## Phase 4: Generate SQL

```
Claude: Phase 4: Generating SQL UPDATE statements...

Reading replacements from CSV...
Generating UPDATE statements...

✓ Generated update_links.sql with 23 UPDATE statements

Preview (first 3 statements):

-- Update broken learn_more_link URLs with replacement links
-- Generated: 2026-02-19
-- Total updates: 23

UPDATE translations_translation_translation
SET text = 'https://cdhs.colorado.gov/snap'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'co_snap');

UPDATE translations_translation_translation
SET text = 'https://cdhs.colorado.gov/colorado-works-tanf'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'co_tanf');

UPDATE translations_translation_translation
SET text = 'https://www.healthfirstcolorado.com/'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'co_medicaid');

[... 20 more statements ...]
```

## Checkpoint 3: Review SQL

```
Claude: CHECKPOINT 3: Please review update_links.sql before executing

File location: /Users/you/code/mfb/update_links.sql

To review:
  cat update_links.sql

To execute (choose one option):

  # Option 1: Test on staging first (RECOMMENDED)
  psql "$STAGING_DATABASE_URL" -f update_links.sql

  # Option 2: Execute on production
  psql "$DATABASE_URL" -f update_links.sql

  # Option 3: Dry-run (rollback after to see changes without committing)
  psql "$DATABASE_URL" << 'EOF'
  BEGIN;
  \i update_links.sql
  ROLLBACK;
  EOF

⚠️ Important: Always review SQL before running on production!
```

## Final Summary

```
Claude: ✓ Link Audit Complete!

Files generated:
  - programs_export.csv (original export)
  - programs_export_with_status.csv (with status and replacements)
  - update_links.sql (for manual execution)

Summary:
  - Total programs: 179
  - Working links: 112 (62.6%)
  - Broken links found: 24 (13.4%)
  - Broken links fixed: 23 (95.8%)
  - Empty links: 43 (24.0%)

Next steps:
  1. Review update_links.sql
  2. Test on staging database (recommended)
  3. Execute on production when ready

User: Thanks!
```

## Manual SQL Execution

```bash
# User reviews the SQL
cat update_links.sql

# User tests on staging
psql "$STAGING_DATABASE_URL" -f update_links.sql

# Output shows 23 rows updated
UPDATE 1
UPDATE 1
[... 21 more ...]

# Verify updates
psql "$STAGING_DATABASE_URL" -c "SELECT COUNT(*) FROM translations_translation_translation WHERE text LIKE 'https://cdhs.colorado.gov%';"

# If good, run on production
psql "$DATABASE_URL" -f update_links.sql
```

## Cleanup (Optional)

```bash
# Archive the output files
mkdir -p link-audits/2026-02-19
mv programs_export*.csv update_links.sql link-audits/2026-02-19/

# Or delete them
rm programs_export*.csv update_links.sql
```

## Notes

- Total time: ~5 minutes (mostly waiting for HTTP checks)
- Web searches: 24 searches
- Database queries: 2 (export + verify)
- Manual steps: 3 checkpoints + 1 SQL execution
- Safe: No automatic database modifications
