#!/usr/bin/env python3
"""
Scan the live benefits-api production database (via the GRAY read replica)
and write program_category, documents, navigators, and icons tables to a
shared Google Sheet.

Why the read replica: it physically rejects writes (it's a Postgres
follower). We additionally set the session to read-only as a second
guardrail. The replica typically lags the primary by a handful of
commits — effectively real-time for this use case.

Auth model: no credentials live on disk. The connection URL is fetched
at runtime via `heroku config:get HEROKU_POSTGRESQL_GRAY_URL -a cobenefits-api`.
The user must be logged in to the Heroku CLI with access to that app.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.parse

import gspread
import psycopg2

SHEET_URL = "https://docs.google.com/spreadsheets/d/1yjmrktlCdQNRTERdiBiElz0fsc4skqzsuf1vCCBF0X4/edit"
HEROKU_APP = "cobenefits-api"
HEROKU_DB_VAR = "HEROKU_POSTGRESQL_GRAY_URL"
LANGUAGE_CODE = "en-us"

QUERY_PROGRAM_CATEGORY = """
SELECT
    wl.code AS white_label,
    pc.external_name,
    name_t.text AS name,
    icon.name AS icon
FROM programs_programcategory pc
JOIN screener_whitelabel wl ON wl.id = pc.white_label_id
LEFT JOIN programs_categoryiconname icon ON icon.id = pc.icon_id
LEFT JOIN translations_translation_translation name_t
    ON name_t.master_id = pc.name_id AND name_t.language_code = %(lang)s
WHERE pc.external_name IS NOT NULL
ORDER BY pc.external_name;
"""

QUERY_DOCUMENTS = """
SELECT
    wl.code AS white_label,
    d.external_name,
    text_t.text AS text,
    url_t.text AS link_url,
    link_t.text AS link_text
FROM programs_document d
JOIN screener_whitelabel wl ON wl.id = d.white_label_id
LEFT JOIN translations_translation_translation text_t
    ON text_t.master_id = d.text_id AND text_t.language_code = %(lang)s
LEFT JOIN translations_translation_translation url_t
    ON url_t.master_id = d.link_url_id AND url_t.language_code = %(lang)s
LEFT JOIN translations_translation_translation link_t
    ON link_t.master_id = d.link_text_id AND link_t.language_code = %(lang)s
WHERE d.external_name IS NOT NULL
ORDER BY d.external_name;
"""

QUERY_NAVIGATORS = """
WITH counties AS (
    SELECT nc.navigator_id,
           STRING_AGG(c.name, ', ' ORDER BY c.name) AS names
    FROM programs_navigator_counties nc
    JOIN programs_county c ON c.id = nc.county_id
    GROUP BY nc.navigator_id
),
languages AS (
    SELECT nl.navigator_id,
           STRING_AGG(l.code, ', ' ORDER BY l.code) AS codes
    FROM programs_navigator_languages nl
    JOIN programs_navigatorlanguage l ON l.id = nl.navigatorlanguage_id
    GROUP BY nl.navigator_id
)
SELECT
    wl.code AS white_label,
    n.external_name,
    name_t.text AS name,
    email_t.text AS email,
    desc_t.text AS description,
    link_t.text AS assistance_link,
    n.phone_number,
    COALESCE(c.names, '') AS counties,
    COALESCE(l.codes, '') AS languages
FROM programs_navigator n
JOIN screener_whitelabel wl ON wl.id = n.white_label_id
LEFT JOIN translations_translation_translation name_t
    ON name_t.master_id = n.name_id AND name_t.language_code = %(lang)s
LEFT JOIN translations_translation_translation email_t
    ON email_t.master_id = n.email_id AND email_t.language_code = %(lang)s
LEFT JOIN translations_translation_translation desc_t
    ON desc_t.master_id = n.description_id AND desc_t.language_code = %(lang)s
LEFT JOIN translations_translation_translation link_t
    ON link_t.master_id = n.assistance_link_id AND link_t.language_code = %(lang)s
LEFT JOIN counties c ON c.navigator_id = n.id
LEFT JOIN languages l ON l.navigator_id = n.id
WHERE n.external_name IS NOT NULL
ORDER BY n.external_name;
"""

QUERY_ICONS = """
SELECT name FROM programs_categoryiconname ORDER BY name;
"""


def fetch_db_url() -> str:
    """Pull the GRAY read-replica URL from Heroku and normalize SSL params."""
    try:
        raw = subprocess.check_output(
            ["heroku", "config:get", HEROKU_DB_VAR, "-a", HEROKU_APP],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except FileNotFoundError:
        sys.exit("heroku CLI not found. Install it: brew install heroku/brew/heroku")
    except subprocess.CalledProcessError as e:
        sys.exit(
            f"Failed to fetch {HEROKU_DB_VAR} from Heroku app {HEROKU_APP}.\n"
            f"Are you logged in? Try: heroku login\n\n{e.stderr}"
        )
    if not raw:
        sys.exit(f"Heroku returned empty value for {HEROKU_DB_VAR}.")

    # Heroku ships the URL with sslmode=verify-full + a Linux-only
    # sslrootcert path. Swap for sslmode=require so it works on macOS.
    parts = urllib.parse.urlparse(raw)
    qs = dict(urllib.parse.parse_qsl(parts.query))
    qs.pop("sslrootcert", None)
    qs["sslmode"] = "require"
    return parts._replace(query=urllib.parse.urlencode(qs)).geturl()


def fetch_rows(conn, query: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute(query, {"lang": LANGUAGE_CODE})
    cols = [d[0] for d in cur.description]
    rows = []
    for raw_row in cur.fetchall():
        row = {}
        for col, val in zip(cols, raw_row):
            if val is None:
                row[col] = ""
            elif isinstance(val, str):
                row[col] = val
            else:
                row[col] = str(val)
        rows.append(row)
    cur.close()
    return rows


def write_tab(sheet, tab_name: str, headers: list[str], rows: list[dict]) -> None:
    try:
        ws = sheet.worksheet(tab_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(
            title=tab_name,
            rows=max(len(rows) + 10, 100),
            cols=len(headers),
        )

    values = [headers] + [[row.get(h, "") for h in headers] for row in rows]
    ws.update(values=values, range_name="A1")
    ws.format("A1:Z1", {"textFormat": {"bold": True}})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pull the data and print row counts, but do not write to the sheet.",
    )
    args = parser.parse_args()

    print(f"Fetching {HEROKU_DB_VAR} from Heroku app '{HEROKU_APP}'...")
    db_url = fetch_db_url()
    print("Connecting to read replica (GRAY)...")
    conn = psycopg2.connect(db_url)
    conn.set_session(readonly=True, autocommit=True)

    try:
        print("Querying program_category...")
        cat_rows = fetch_rows(conn, QUERY_PROGRAM_CATEGORY)
        print(f"  {len(cat_rows)} rows")

        print("Querying documents...")
        doc_rows = fetch_rows(conn, QUERY_DOCUMENTS)
        print(f"  {len(doc_rows)} rows")

        print("Querying navigators...")
        nav_rows = fetch_rows(conn, QUERY_NAVIGATORS)
        print(f"  {len(nav_rows)} rows")

        print("Querying icons...")
        icon_rows = fetch_rows(conn, QUERY_ICONS)
        print(f"  {len(icon_rows)} rows")
    finally:
        conn.close()

    if args.dry_run:
        print("\nDry-run - not writing to the sheet.")
        return

    print(f"\nConnecting to: {SHEET_URL}")
    gc = gspread.service_account()
    sheet = gc.open_by_url(SHEET_URL)
    print(f"Opened: {sheet.title}")

    write_tab(
        sheet,
        "program_category",
        ["white_label", "external_name", "name", "icon"],
        cat_rows,
    )
    write_tab(
        sheet,
        "documents",
        ["white_label", "external_name", "text", "link_url", "link_text"],
        doc_rows,
    )
    write_tab(
        sheet,
        "navigators",
        [
            "white_label",
            "external_name",
            "name",
            "email",
            "description",
            "assistance_link",
            "phone_number",
            "counties",
            "languages",
        ],
        nav_rows,
    )
    write_tab(sheet, "icons", ["icon"], [{"icon": r["name"]} for r in icon_rows])
    print("Done.")


if __name__ == "__main__":
    main()
