#!/usr/bin/env python3
"""Run a program's spec scenarios against the benefits screener API from a scenario file.

    python3 runner.py scenarios.json --env staging [--ticket MFB-1234] [--out-dir ~/main/qa]

The scenario file is JSON (see examples/ and SKILL.md, Phase 4). The runner creates one
test screen per scenario, fetches eligibility, compares it with the expected outcome and
annual value, and writes `{ticket}-{program}-{env}-results.json` and `.md` to the output
directory.

Environments:
- local: http://localhost:8000; the key is LOCAL_API_KEY, or the first DRF token in the
  local database (read through benefits-api's manage.py, never printed).
- staging: the staging API; the key is STAGING_API_KEY from ~/main/.env.
- production: run by David only. Asks for confirmation; the key is PRODUCTION_API_KEY.

A scenario is BLOCKED, not run or not judged, when the file gives it a `blocked` reason, or
when the API drops a `current_benefits` name the white label has no program for (the POST
response lists the names it saved). BLOCKED is reported and left out of the pass rate.

Exit status is 0 when every scenario and check that ran passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

API_BASES = {
    "local": "http://localhost:8000",
    "staging": "https://cobenefits-api-staging.herokuapp.com",
    "production": "https://cobenefits-api.herokuapp.com",
}
WORKSPACE = Path.home() / "main"
NOW = datetime.now(timezone.utc)

INSURANCE_TYPES = (
    "none", "employer", "private", "medicaid", "medicare", "chp", "va",
    "mass_health", "emergency_medicaid", "family_planning", "dont_know",
)
MEMBER_FLAGS = (
    "pregnant", "student", "student_full_time", "disabled", "long_term_disability",
    "unemployed", "veteran", "visually_impaired",
)
FILE_KEYS = {"program", "title", "spec", "white_label", "zipcode", "county", "scenarios", "checks"}
SCENARIO_KEYS = {
    "n", "title", "white_label", "zipcode", "county", "household_size", "household_assets",
    "members", "expenses", "current_benefits", "expect", "blocked", "age_only",
}
CHECK_KEYS = SCENARIO_KEYS - {"n"} | {"type", "match"}
MEMBER_KEYS = {"rel", "age", "age_end_of_year", "birth_month", "income", "insurance", *MEMBER_FLAGS}
EXPECT_KEYS = {"eligible", "annual", "units"}
CHECK_TYPES = {"result", "shows_once", "already_has"}


class ScenarioFileError(Exception):
    pass


# Scenario file


def _require_keys(obj: dict, allowed: set[str], where: str) -> None:
    unknown = set(obj) - allowed
    if unknown:
        raise ScenarioFileError(f"{where}: unknown keys {sorted(unknown)} (allowed: {sorted(allowed)})")


def load_scenario_file(path: Path) -> dict:
    data = json.loads(path.read_text())
    _require_keys(data, FILE_KEYS, path.name)
    for key in ("program", "white_label", "scenarios"):
        if key not in data:
            raise ScenarioFileError(f"{path.name}: missing '{key}'")
    for i, s in enumerate(data["scenarios"]):
        where = f"scenario {s.get('n', i + 1)}"
        _require_keys(s, SCENARIO_KEYS, where)
        if "expect" not in s or "eligible" not in s["expect"]:
            raise ScenarioFileError(f"{where}: needs expect.eligible")
        _require_keys(s["expect"], EXPECT_KEYS, f"{where} expect")
        for j, m in enumerate(s.get("members", [])):
            _require_keys(m, MEMBER_KEYS, f"{where} member {j + 1}")
    for i, c in enumerate(data.get("checks", [])):
        where = f"check {i + 1}"
        _require_keys(c, CHECK_KEYS, where)
        if c.get("type", "result") not in CHECK_TYPES:
            raise ScenarioFileError(f"{where}: type must be one of {sorted(CHECK_TYPES)}")
        if c.get("type", "result") == "result" and "eligible" not in c.get("expect", {}):
            raise ScenarioFileError(f"{where}: a result check needs expect.eligible")
        if c.get("type") == "shows_once" and "match" not in c:
            raise ScenarioFileError(f"{where}: shows_once needs 'match' (a substring of the program names to count)")
        for j, m in enumerate(c.get("members", [])):
            _require_keys(m, MEMBER_KEYS, f"{where} member {j + 1}")
    return data


# Payloads


def build_income(stream: list) -> dict:
    """`[type, amount, frequency]`, or `[type, amount, "hourly", hours_per_week]`."""
    if len(stream) not in (3, 4):
        raise ScenarioFileError(f"income {stream}: needs [type, amount, frequency] or [type, amount, frequency, hours]")
    income_type, amount, frequency, *hours = stream
    if (frequency == "hourly") != bool(hours):
        raise ScenarioFileError(f"income {stream}: hourly income takes hours worked per week as a 4th element, "
                                "and only hourly income takes one")
    income = {"type": income_type, "amount": amount, "frequency": frequency}
    if hours:
        income["hours_worked"] = hours[0]
    return income


def build_member(m: dict, age_only: bool = False) -> dict:
    """A household member from the scenario file's compact form.

    `age` is today's age; with `birth_month` the birth year is the one that gives that age
    today. `age_end_of_year` ({"year": 2025, "age": 64}) is an age on December 31 of that
    year, so the birth year is year - age; use it for rules judged at the end of a benefit or
    tax year. `age_only` sends today's age without a birth year or month, as the Get Ahead
    apps do.
    """
    birth_month = m.get("birth_month", 1)
    birthday_ahead = 1 if NOW.month < birth_month else 0
    if "age_end_of_year" in m:
        birth_year = m["age_end_of_year"]["year"] - m["age_end_of_year"]["age"]
    elif "age" in m:
        birth_year = NOW.year - m["age"] - birthday_ahead
    else:
        raise ScenarioFileError(f"member {m}: needs age or age_end_of_year")
    if (birth_year, birth_month) > (NOW.year, NOW.month):
        raise ScenarioFileError(f"member {m}: birth date {birth_year}-{birth_month:02} is in the future")
    age = NOW.year - birth_year - birthday_ahead

    streams = [build_income(s) for s in m.get("income", [])]
    covered = set(m.get("insurance", ["none"]))
    unknown = covered - set(INSURANCE_TYPES)
    if unknown:
        raise ScenarioFileError(f"member {m}: unknown insurance {sorted(unknown)}")
    insurance = {t: t in covered for t in INSURANCE_TYPES}

    member = {
        "relationship": m["rel"], "age": age,
        "has_income": bool(streams), "income_streams": streams, "insurance": insurance,
    }
    if not age_only:
        member.update(birth_year=birth_year, birth_month=birth_month)
    # The screener sends false for every unticked condition box. A flag left out would be null, and
    # any program declaring it is dropped as a missing field. Pass null explicitly to test that.
    member.update({flag: m.get(flag, False) for flag in MEMBER_FLAGS})
    return member


def build_payload(s: dict, defaults: dict) -> dict:
    white_label = s.get("white_label", defaults["white_label"]).lower()
    members = [build_member(m, s.get("age_only", False)) for m in s["members"]]
    payload = {
        "white_label": white_label, "is_test": True, "agree_to_tos": True, "is_13_or_older": True,
        "household_size": s.get("household_size", len(members)),
        "household_assets": s.get("household_assets", 0),
        "request_language_code": "en", "start_date": NOW.isoformat(), "referral_source": "test",
        "household_members": members,
        "expenses": [{"type": t, "amount": a, "frequency": f} for t, a, f in s.get("expenses", [])],
        "current_benefits": s.get("current_benefits", []),
    }
    # Federal screens take no location. Elsewhere it's sent when the file gives one; the API
    # only validates a location it receives, and `_default` has no ZIP map to validate against.
    if white_label != "federal":
        zipcode = s.get("zipcode", defaults.get("zipcode"))
        county = s.get("county", defaults.get("county"))
        if zipcode:
            payload["zipcode"] = zipcode
        if county:
            payload["county"] = county
    return payload


# API


@dataclass
class Api:
    base: str
    key: str

    def call(self, method: str, path: str, body: Optional[dict] = None, retries: int = 1) -> tuple[int, Any]:
        """curl, not urllib: urllib fails Heroku's certificates. Retries an empty or HTML (503) reply."""
        for attempt in range(retries + 1):
            cmd = ["/usr/bin/curl", "-s", "-k", "--max-time", "120", "-w", "\n%{http_code}", "-X", method,
                   f"{self.base}{path}", "-H", "Content-Type: application/json",
                   "-H", f"Authorization: Token {self.key}"]
            if body is not None:
                cmd += ["-d", json.dumps(body)]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=130).stdout
            raw, _, code = out.rpartition("\n")
            status = int(code) if code.isdigit() else 0
            if (not raw.strip() or raw.lstrip().startswith("<")) and attempt < retries:
                time.sleep(3)
                continue
            try:
                return status, json.loads(raw)
            except ValueError:
                return status, raw[:300]
        return 0, ""

    def eligibility(self, uuid: str, program: str) -> tuple[int, Any]:
        """Poll while the program is absent and `missing_programs` says calculations are pending.

        Returns the last status and body; the caller treats anything but a 200 with a
        `programs` list as a failed call.
        """
        status, elig = 0, None
        for attempt in range(5):
            if attempt:
                time.sleep(4)
            status, elig = self.call("GET", f"/api/eligibility/{uuid}")
            if status == 200 and isinstance(elig, dict) and (
                any(p.get("name_abbreviated") == program for p in elig.get("programs", []))
                or not elig.get("missing_programs")
            ):
                break
        return status, elig


def resolve_key(env: str, benefits_api: Path) -> str:
    if env == "staging":
        name = "STAGING_API_KEY"
        if os.environ.get(name):
            return os.environ[name]
        for line in (WORKSPACE / ".env").read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"')
        raise SystemExit(f"{name} not found in the environment or {WORKSPACE / '.env'}")
    if env == "production":
        if not os.environ.get("PRODUCTION_API_KEY"):
            raise SystemExit("Set PRODUCTION_API_KEY for this run.")
        return os.environ["PRODUCTION_API_KEY"]
    if os.environ.get("LOCAL_API_KEY"):
        return os.environ["LOCAL_API_KEY"]
    # REACT_APP_API_KEY 403s locally; the local database holds a working token.
    code = "from rest_framework.authtoken.models import Token; t = Token.objects.order_by('created').first(); print(t.key if t else '')"
    out = subprocess.run([str(benefits_api / "venv/bin/python"), "manage.py", "shell", "-c", code],
                         cwd=benefits_api, capture_output=True, text=True, timeout=120).stdout.strip().splitlines()
    if not out or not out[-1]:
        raise SystemExit("No DRF token in the local database; set LOCAL_API_KEY.")
    return out[-1]


# Evaluation


@dataclass
class Outcome:
    label: str
    title: str
    kind: str  # "scenario" or "check"
    white_label: str
    result: str  # PASS / FAIL / ERROR / BLOCKED
    expected: str = ""
    actual: str = ""
    exp_value: Optional[int] = None
    act_value: Optional[int] = None
    value_match: str = "N/A"
    uuid: Optional[str] = None
    detail: str = ""
    missing_programs: Optional[bool] = None
    diagnostics: dict = field(default_factory=dict)


def evaluate(program_row: Optional[dict], expect: dict) -> tuple[str, str, Optional[int], str, bool]:
    if program_row is None:
        actual = "Not found"
    elif program_row.get("already_has"):
        actual = "Not eligible"  # the frontend hides a benefit the household already has
    else:
        actual = "Eligible" if program_row.get("eligible") else "Not eligible"
    expected = "Eligible" if expect["eligible"] else "Not eligible"
    act_value = program_row.get("estimated_value") if program_row else None

    value_match = "N/A"
    if expect["eligible"] and expect.get("annual") is not None and actual == "Eligible":
        # Each payment unit's annual value is rounded to whole dollars: 1 either way per unit.
        tolerance = expect.get("units", 1)
        value_match = "PASS" if act_value is not None and abs(act_value - expect["annual"]) <= tolerance else "FAIL"
    ok = (expected == actual or (expected == "Not eligible" and actual == "Not found")) and value_match != "FAIL"
    return expected, actual, act_value, value_match, ok


def run_one(api: Api, item: dict, defaults: dict, program: str, label: str, kind: str) -> Outcome:
    title = item.get("title", "")
    check_type = item.get("type", "result")
    white_label = item.get("white_label", defaults["white_label"]).lower()
    if item.get("blocked"):
        return Outcome(label, title, kind, white_label, "BLOCKED", detail=item["blocked"])
    try:
        payload = build_payload(item, defaults)
    except ScenarioFileError as e:
        return Outcome(label, title, kind, white_label, "ERROR", detail=str(e))

    status, screen = api.call("POST", "/api/screens/", payload)
    if status in (401, 403):
        raise SystemExit(f"{status} from {api.base}: the API key was rejected")
    if status != 201 or not isinstance(screen, dict):
        return Outcome(label, title, kind, white_label, "ERROR", detail=f"POST {status}: {screen}")
    uuid = screen["uuid"]
    # The API silently drops a name the white label has no program for, which would make the
    # scenario test a household without that benefit.
    dropped = sorted(set(payload["current_benefits"]) - set(screen.get("current_benefits", [])))
    if dropped:
        return Outcome(label, title, kind, white_label, "BLOCKED", uuid=uuid,
                       detail=f"current_benefits {dropped} dropped: white label '{white_label}' has no program by "
                              f"that name, so the scenario can't be expressed here")
    status, elig = api.eligibility(uuid, program)
    if status != 200 or not isinstance(elig, dict) or not isinstance(elig.get("programs"), list):
        # A failed call returns no programs, which would otherwise read as "Not found" and
        # pass every "Not eligible" scenario.
        return Outcome(label, title, kind, white_label, "ERROR", uuid=uuid,
                       detail=f"eligibility GET {status}: {str(elig)[:300]}")
    programs = elig["programs"]
    row = next((p for p in programs if p.get("name_abbreviated") == program), None)

    if check_type == "shows_once":
        names = sorted(p["name_abbreviated"] for p in programs if item["match"] in p.get("name_abbreviated", ""))
        ok = names == [program]
        return Outcome(label, title, kind, white_label, "PASS" if ok else "FAIL", uuid=uuid,
                       detail=f"programs matching '{item['match']}': {names}",
                       missing_programs=elig.get("missing_programs"))
    if check_type == "already_has":
        ok = bool(row and row.get("already_has"))
        return Outcome(label, title, kind, white_label, "PASS" if ok else "FAIL", uuid=uuid,
                       detail=f"found={row is not None} already_has={row and row.get('already_has')}",
                       missing_programs=elig.get("missing_programs"))

    if row is None and elig.get("missing_programs"):
        # Some program on this screen was dropped (a missing screener field, no calculator, or an
        # upstream it gates on), and it may be this one, so absence proves nothing.
        expected = "Eligible" if item["expect"]["eligible"] else "Not eligible"
        return Outcome(
            label, title, kind, white_label, "ERROR", expected=expected, actual="Not found", uuid=uuid,
            missing_programs=True,
            detail="program absent and missing_programs is true: it may have been dropped, not judged",
            diagnostics={"payload": payload, "error": elig.get("error")},
        )
    expected, actual, act_value, value_match, ok = evaluate(row, item["expect"])
    outcome = Outcome(
        label, title, kind, white_label, "PASS" if ok else "FAIL", expected=expected, actual=actual,
        exp_value=item["expect"].get("annual") if item["expect"]["eligible"] else None,
        act_value=act_value, value_match=value_match, uuid=uuid, missing_programs=elig.get("missing_programs"),
    )
    if not ok:
        outcome.diagnostics = {
            "payload": payload,
            "failed_tests": row.get("failed_tests") if row else None,
            "passed_tests": row.get("passed_tests") if row else None,
            "error": elig.get("error"),
        }
    return outcome


# Reports


def never_found(outcomes: list[Outcome]) -> bool:
    """True when scenarios reached the API but none of them returned the program, so every
    'not eligible' pass was only the program's absence."""
    reached = [o for o in outcomes if o.kind == "scenario" and o.uuid and o.actual]
    return bool(reached) and all(o.actual == "Not found" for o in reached)


def money(value: Optional[int]) -> str:
    return "—" if value is None else f"{value:,}"


def write_reports(data: dict, outcomes: list[Outcome], env: str, base: str, ticket: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{ticket}-{data['program']}-{env}-results"
    (out_dir / f"{stem}.json").write_text(json.dumps([o.__dict__ for o in outcomes], indent=2))

    scenarios = [o for o in outcomes if o.kind == "scenario"]
    checks = [o for o in outcomes if o.kind == "check"]
    passed = sum(o.result == "PASS" for o in scenarios)
    errors = sum(o.result == "ERROR" for o in scenarios)
    blocked = [o for o in outcomes if o.result == "BLOCKED"]
    judged = sum(o.result != "BLOCKED" for o in scenarios)
    lines = [
        f"# API QA Test Results - {data.get('title', data['program'])} (`{data['program']}`)",
        "",
        f"**Linear Ticket:** {ticket}",
        f"**Test Date:** {NOW.date().isoformat()}",
        f"**Environment:** {env.upper()}",
        f"**API Base:** {base}",
        f"**Spec:** {data.get('spec', 'not recorded')}",
        "",
        "Values are annual, in dollars, compared within 1 per counted unit for rounding.",
        "",
        "## Test Scenarios",
        "",
        "| # | Description | White label | Expected | Actual | Exp. Value | Act. Value | Value Match | Result | Screen UUID |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for o in scenarios:
        lines.append(f"| {o.label} | {o.title} | {o.white_label} | {o.expected} | {o.actual} | "
                     f"{money(o.exp_value)} | {money(o.act_value)} | {o.value_match} | {o.result} | `{o.uuid}` |")
    if checks:
        lines += ["", "## Checks", "", "| Check | White label | Result | Detail | Screen UUID |", "|---|---|---|---|---|"]
        lines += [f"| {o.label} | {o.white_label} | {o.result} | {o.detail} | `{o.uuid}` |" for o in checks]
    lines += [
        "", "## Summary", "",
        f"- **Scenarios:** {len(scenarios)}",
        f"- **Passed:** {passed}",
        f"- **Failed:** {judged - passed - errors}",
        f"- **Errors:** {errors}",
        f"- **Blocked (not judged):** {sum(o.result == 'BLOCKED' for o in scenarios)}",
        f"- **Checks passed:** {sum(o.result == 'PASS' for o in checks)}/{sum(o.result != 'BLOCKED' for o in checks)}",
        f"- **Pass rate:** {passed / judged:.0%} ({passed}/{judged}, blocked excluded)" if judged else "",
    ]
    if never_found(outcomes):
        lines += ["", "## Program never returned", "",
                  f"`{data['program']}` was absent from every scenario's results, so no scenario judged it. "
                  "Check it's imported and active here, and that the payloads supply every field it declares."]
    if blocked:
        lines += ["", "## Blocked", "", "| # | Description | Reason |", "|---|---|---|"]
        lines += [f"| {o.label} | {o.title} | {o.detail} |" for o in blocked]
    failures = [o for o in outcomes if o.result not in ("PASS", "BLOCKED")]
    if failures:
        lines += ["", "## Failures", ""]
        for o in failures:
            lines += [f"### {o.label}: {o.title} — {o.result}", "",
                      f"- Expected: {o.expected} {money(o.exp_value)}; actual: {o.actual} {money(o.act_value)}",
                      f"- Detail: {o.detail}", f"- Eligibility: {base}/api/eligibility/{o.uuid}", "",
                      "```json", json.dumps(o.diagnostics, indent=2), "```", ""]
    path = out_dir / f"{stem}.md"
    path.write_text("\n".join(lines) + "\n")
    return path


# Main


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario_file", type=Path)
    parser.add_argument("--env", choices=sorted(API_BASES), default="staging")
    parser.add_argument("--ticket", default="QA")
    parser.add_argument("--out-dir", type=Path, default=WORKSPACE / "qa")
    parser.add_argument("--api-base", help="Override the environment's API base URL.")
    parser.add_argument("--benefits-api", type=Path, default=WORKSPACE / "benefits-api",
                        help="benefits-api checkout, for reading the local API token.")
    parser.add_argument("--only", help="Comma-separated scenario numbers to run (checks are skipped).")
    args = parser.parse_args(argv)

    try:
        data = load_scenario_file(args.scenario_file)
    except (ScenarioFileError, json.JSONDecodeError) as e:
        print(f"Scenario file error: {e}", file=sys.stderr)
        return 2

    if args.env == "production" and input("This sends test screens to production. Type prod to continue: ").strip() != "prod":
        return 2

    base = args.api_base or API_BASES[args.env]
    api = Api(base, resolve_key(args.env, args.benefits_api))
    defaults = {k: data[k] for k in ("white_label", "zipcode", "county") if k in data}
    only = {s.strip() for s in args.only.split(",")} if args.only else None

    outcomes: list[Outcome] = []
    for s in data["scenarios"]:
        if only and str(s["n"]) not in only:
            continue
        o = run_one(api, s, defaults, data["program"], str(s["n"]), "scenario")
        outcomes.append(o)
        print(f"{o.label:>3} {o.result:7} {o.actual or '':13} {money(o.act_value):>7}  {s.get('title', '')}"
              + (f"  [{o.detail}]" if o.result == "BLOCKED" else ""), flush=True)
    for i, c in enumerate([] if only else data.get("checks", [])):
        label = c.get("title", f"check {i + 1}")
        o = run_one(api, c, defaults, data["program"], label, "check")
        outcomes.append(o)
        print(f"CHECK {o.result:7} {label}: {o.detail or o.actual}", flush=True)

    report = write_reports(data, outcomes, args.env, base, args.ticket, args.out_dir)
    print(f"\nReport: {report}")
    if never_found(outcomes):
        print(f"\n{data['program']} was not returned for any scenario: it isn't being judged. Check it's "
              "imported and active, and that the payloads supply every field it declares.", file=sys.stderr)
        return 1
    return 0 if all(o.result in ("PASS", "BLOCKED") for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
