---
name: scan-database-fixtures-to-sheet
description: Read program_category, documents, navigators, and category icons directly from the production benefits-api database (via the GRAY read replica) and write them to a shared Google Sheet. Captures live values including post-hoc edits made through the Django admin, not just what's declared in fixture JSON.
---

# Live Database → Google Sheet Reference

Connects to the production benefits-api database (via the read-only `HEROKU_POSTGRESQL_GRAY_URL` follower), runs four queries against `programs_programcategory`, `programs_document`, `programs_navigator`, and `programs_categoryiconname` (joined to `translations_translation_translation` for human-readable text), and writes the results to a hardcoded Google Sheet — one tab per table.

This is the database-backed successor to the earlier fixture-scanning skill. The fixture files only show what was declared at import time; the database holds the current state, including any edits made through the Django admin afterward. **Use this skill when you want the live truth.**

## Usage

```
/scan-database-fixtures-to-sheet
```

No arguments. The sheet URL, Heroku app name, and DB env var are all hardcoded in `scan_database.py`. To preview without writing, pass `--dry-run` (see Phase 3).

---

## Prerequisites (one-time setup)

The skill needs three things in place. If all three verification commands below succeed, you're set up.

### 1. Google Sheets service account

The same setup as the previous skill — a service-account JSON at `~/.config/gspread/service_account.json` with editor access to the target spreadsheet. Verify:

```bash
python3 -c "import gspread; gc = gspread.service_account(); sh = gc.open_by_url('https://docs.google.com/spreadsheets/d/1yjmrktlCdQNRTERdiBiElz0fsc4skqzsuf1vCCBF0X4/edit'); print('OK:', sh.title)"
```

### 2. Heroku CLI logged in with access to `cobenefits-api`

```bash
heroku auth:whoami
heroku config:get HEROKU_POSTGRESQL_GRAY_URL -a cobenefits-api | head -c 30
```

The first should print your email. The second should print `postgres://` followed by 20+ chars (a real connection string). If it errors with a permission message, your Heroku account doesn't have access to the production app — escalate.

### 3. psycopg2-binary installed

```bash
python3 -m pip install psycopg2-binary
python3 -c "import psycopg2; print(psycopg2.__version__)"
```

If any of the three verifications fail, walk the user through the missing piece before proceeding.

---

## Workflow

### Phase 1: Confirm prerequisites

Run the three verification commands above quickly and surface results. Do not proceed to query the DB if any are missing.

### Phase 2: Dry-run

```bash
python3 team-claude-config/skills/scan-database-fixtures-to-sheet/scan_database.py --dry-run
```

This pulls the data from the read replica, prints row counts, and exits without touching the sheet. Surface the output to the user so they can sanity-check counts before any sheet write.

Sample output:

```
Fetching HEROKU_POSTGRESQL_GRAY_URL from Heroku app 'cobenefits-api'...
Connecting to read replica (GRAY)...
Querying program_category...
  27 rows
Querying documents...
  102 rows
Querying navigators...
  41 rows
Querying icons...
  8 rows

Dry-run - not writing to the sheet.
```

### Phase 3: Live write

Unless the user objects to the dry-run numbers, run the live write:

```bash
python3 team-claude-config/skills/scan-database-fixtures-to-sheet/scan_database.py
```

### Phase 4: Report and link

Report back:

- Four tabs were written: `program_category`, `documents`, `navigators`, `icons`
- How many rows in each
- The sheet URL: https://docs.google.com/spreadsheets/d/1yjmrktlCdQNRTERdiBiElz0fsc4skqzsuf1vCCBF0X4/edit

---

## Output structure

Each tab has these columns. The first row is bold headers. `external_name` is `UNIQUE` at the database level, so each row in the source data appears exactly once — no dedup or conflict resolution is needed.

### `program_category` tab
| white_label | external_name | name | icon |

### `documents` tab
| white_label | external_name | text | link_url | link_text |

### `navigators` tab
| white_label | external_name | name | email | description | assistance_link | phone_number | counties | languages |

`counties` and `languages` are M2M relations in the database; they are aggregated to a comma-separated string per navigator in the cell, sorted alphabetically.

### `icons` tab
| icon |

Flat, sorted list of every value in `programs_categoryiconname.name`. Treat this as the canonical inventory of allowed icon strings.

---

## How the queries work

All human-readable text (`name`, `description`, `text`, `link_url`, `link_text`, `email`, `assistance_link`) is stored on the `translations_translation_translation` table, not directly on the program/document/navigator tables. Each query JOINs through:

```
<table>.<field>_id  →  translations_translation_translation.master_id
                       (filtered to language_code = 'en-us')
```

This is the same pattern dbt uses in [data-queries/dbt/models/postgres/staging/stg_programs_value_types.sql](data-queries/dbt/models/postgres/staging/stg_programs_value_types.sql). Only the English (`en-us`) text is pulled — non-English translations exist but are out of scope.

The navigator query also aggregates two M2M relations:
- `programs_navigator_counties` → `programs_county.name`
- `programs_navigator_languages` → `programs_navigatorlanguage.code`

---

## Safety model

**Why hitting prod directly is acceptable here:**

1. **Read replica, not primary.** The script targets `HEROKU_POSTGRESQL_GRAY_URL`, which is a Postgres follower. Followers physically reject any write — even `INSERT INTO` against a read replica errors at the server level.
2. **Read-only session.** As a second guardrail, the script calls `conn.set_session(readonly=True, autocommit=True)` so any write attempt errors at the client level too.
3. **No persistent credentials.** The connection URL is fetched fresh from Heroku on every run via `heroku config:get` — nothing is cached on disk. If you lose Heroku access, the skill stops working immediately; if Heroku rotates the password, the next run picks it up automatically.
4. **Replica lag is minimal.** Typically a handful of commits behind (a few seconds), not material for a reference spreadsheet.

---

## Re-running

The skill is idempotent. Each run:

1. Clears each of the four tabs
2. Re-writes them from the current state of the production database

Tabs other than the four named ones are untouched, so any manual annotation tabs (e.g. a `notes` or `review` tab) the user adds to the sheet survive across runs.

---

## Troubleshooting

**`heroku CLI not found`:**
Install it: `brew install heroku/brew/heroku`, then `heroku login`.

**`Failed to fetch HEROKU_POSTGRESQL_GRAY_URL`:**
Likely either not logged in (`heroku login`) or no access to the `cobenefits-api` app. The error message will say which.

**`psycopg2.OperationalError: SSL ...`:**
The script normalizes the SSL params on the URL (`sslmode=verify-full` → `sslmode=require`, drops the Linux-only `sslrootcert` path). If you still see SSL issues, your local OpenSSL may be misconfigured — try `python3 -m pip install --upgrade certifi`.

**`SpreadsheetNotFound` or `403 PERMISSION_DENIED`:**
The sheet isn't shared with the gspread service account, or the service account JSON has been rotated. Open the JSON, copy the `client_email`, and share the sheet with that address as Editor.

**Empty `name` / `text` / etc. in the output:**
The translation row may not have an `en-us` entry. Check the `Translation` admin in Django for that program — it will have entries for other languages but no English.

**Replica is way behind (e.g. >100 commits):**
Run `heroku pg:info -a cobenefits-api` and look at the `Behind By:` line under the GRAY entry. If it's unusually high, Heroku may be doing maintenance — wait and retry. The data we're pulling rarely changes by the minute, so a short wait is fine.

---

## Notes

- The sheet URL, Heroku app name (`cobenefits-api`), and DB env var (`HEROKU_POSTGRESQL_GRAY_URL`) are intentionally hardcoded as constants in `scan_database.py`. To point this skill at staging or a different app, edit those constants directly.
- Only English (`en-us`) translations are pulled. Other languages exist in the DB but are out of scope for this reference sheet.
- This skill writes only — it never reads existing rows back. Hand-edits to the four managed tabs are overwritten on the next run. Annotations belong in a separate tab.
- The script does not write to or modify the database in any way. It uses a read replica + a read-only session, so writes are physically and procedurally impossible.
