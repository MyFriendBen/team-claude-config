# Check Program Links - Templates and Dependencies

This directory contains templates and dependencies for the `/check-program-links` command.

## Structure

```
check-program-links/
├── README.md                           # This file
├── templates/                          # Reusable templates
│   ├── export_programs.sql            # SQL query to export programs
│   ├── check_link_status.py           # Python script to check HTTP status
│   └── update_links_template.sql      # Example SQL UPDATE statements
└── examples/                           # Example outputs
    └── example_workflow.md            # Example session walkthrough
```

## How the Workflow Uses These Files

When `/check-program-links` is invoked:

1. **SQL template for user execution** (`templates/export_programs.sql`)
   - Claude reads the template and provides it to the user
   - User runs: `psql "$DATABASE_URL" -f templates/export_programs.sql --csv -o programs_export.csv`
   - User confirms CSV file is created
   - Claude then reads the CSV file to proceed

2. **Python script for link checking** (`templates/check_link_status.py`)
   - Claude checks HTTP status of each URL (using requests library)
   - Can be run directly or used as reference for inline implementation

3. **SQL update template** (`templates/update_links_template.sql`)
   - Claude generates UPDATE statements for broken links
   - Saves to project directory as `update_links.sql`
   - User manually reviews and executes the SQL

## Database Connection

The user must have a `DATABASE_URL` environment variable set:

```bash
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
```

**Important:** Claude never accesses this variable or connects to the database. Only the user runs psql commands. Claude only reads/writes CSV files in the project directory.

For MyFriendBen projects, this is typically already set.

## Column Order

All exports use this column order:
1. program_id
2. program_name
3. learn_more_link
4. name_abbreviated
5. white_label_code
6. white_label_name
7. name_language
8. active

## Language Filter

Templates filter for `language_code = 'en-us'` by default.

## Output Files

The workflow generates files in the **project directory** (not here):
- `programs_export.csv` - Created by user running SQL template
- `programs_export_with_status.csv` - Created by Claude adding link status
- `update_links.sql` - Created by Claude, executed manually by user

## Customization

To customize for your project:

1. **Different language**: Edit `export_programs.sql` to change `'en-us'` to your language code
2. **Different columns**: Modify the SELECT statement
3. **Different timeout**: Edit `check_link_status.py` timeout value

## For Team Members

When you clone `team-claude-config`, these templates are included automatically.
No additional setup required - just run `/check-program-links` in your MyFriendBen project.

## Version Control

These templates are checked into git, so improvements benefit the whole team.

## Related Files

- Main skill definition: `../check-program-links.md`
- Working directory: Project root (e.g., `/Users/you/code/mfb/`)
- Output location: Project root
