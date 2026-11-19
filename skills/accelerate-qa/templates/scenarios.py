"""QA scenario runner. Standard library only.

    API_BASE=https://cobenefits-api-staging.herokuapp.com API_KEY=... python3 scenarios.py <TICKET>

Posts each scenario as a test screen (`is_test: true`), reads `/api/eligibility/<uuid>`, and grades
the program under test. Payload and grading rules follow the api-qa-execution skill (Phase 2 and
Phase 3); when they disagree, that skill wins.

Prints one line per scenario, then a summary:
  PASS / FAIL  outcome and value judged
  ERROR        not judged: a non-201 POST, a failed eligibility GET, or the program absent with
               missing_programs=true (on staging, why_dropped() in preflight.py names the reason)
  BLOCKED      a current benefit sent in the payload didn't save
  SKIP         the scenario needs a current benefit the white label doesn't offer here

Never prints the API key. Households are invented test data; keep them that way.
"""

import json
import os
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

API_BASE = os.environ.get("API_BASE", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("API_KEY", "")
TODAY = date.today()

FLAGS = ("disabled", "long_term_disability", "visually_impaired", "pregnant", "student", "student_full_time")
INSURANCE = (
    "none", "employer", "private", "medicaid", "medicare", "chp", "va",
    "mass_health", "emergency_medicaid", "family_planning", "dont_know",
)
DISABLED = {"disabled": True, "long_term_disability": True}
STUDENT = {"student": True, "student_full_time": True}


# --- household building


def age_now(age: int) -> tuple[int, int]:
    """Birth (year, month) for someone `age` today: January of (this year - age)."""
    return TODAY.year - age, 1


def age_at_year_end(age: int, year: int) -> tuple[int, int]:
    """Birth (year, month) for someone `age` on December 31 of `year` (tax and benefit years).

    January, so the person is a year older today: that also catches a calculator reading today's age.
    """
    return year - age, 1


def current_age(birth: tuple[int, int]) -> int:
    year, month = birth
    return TODAY.year - year - (1 if month > TODAY.month else 0)


Income = tuple[str, float, str]  # (type, amount, frequency), e.g. ("wages", 20000, "yearly")


@dataclass
class M:
    relationship: str
    birth: tuple[int, int]
    income: list[Income] = field(default_factory=list)
    insurance: str = "none"
    flags: dict[str, bool] = field(default_factory=dict)


@dataclass
class S:
    number: int
    title: str
    members: list[M]
    program: str
    eligible: bool
    value: Optional[int] = None  # annual whole dollars, as estimated_value reports it
    units: int = 1  # counted payment units: the value tolerance is 1 dollar per unit
    member_expect: dict[int, tuple[bool, Optional[int]]] = field(default_factory=dict)  # person (1-based) -> (eligible, annual value)
    benefits: list[str] = field(default_factory=list)  # resolved against has-benefits, or "=name" sent as is
    expenses: list[Income] = field(default_factory=list)
    assets: int = 0


@dataclass
class Ticket:
    white_label: str
    zipcode: Optional[str]  # None on `federal`
    county: Optional[str]
    scenarios: list[S]


def head(birth: tuple[int, int], *income: Income, **flags: bool) -> M:
    return M("headOfHousehold", birth, list(income), flags=flags)


def wages_y(amount: float) -> Income:
    return ("wages", amount, "yearly")


def wages_m(amount: float) -> Income:
    return ("wages", amount, "monthly")


# --- Example ticket: replace with the batch's tickets. Households are invented; expected values
# come from the program's spec and are illustrative here.

EXAMPLE = Ticket("federal", None, None, [
    S(1, "Disabled worker under the earnings limit", [head(age_now(45), wages_m(1000), **DISABLED)], "federal_ssdi", True),
    S(2, "No disability", [head(age_now(45))], "federal_ssdi", False),
])

TICKETS: dict[str, list[Ticket]] = {"EXAMPLE-1": [EXAMPLE]}


# --- HTTP (curl: Python's urllib can fail Heroku's certificates)


def request(method: str, path: str, body: Optional[dict[str, Any]] = None) -> tuple[int, Any]:
    """Call the API. The auth header goes to curl on stdin, never on the command line."""
    cmd = ["curl", "-sS", "-X", method, "-H", "@-", "-H", "Accept: application/json", "-w", "\n%{http_code}", "--max-time", "180"]
    body_file = None
    if body is not None:
        body_file = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(body, body_file)
        body_file.close()
        cmd += ["-H", "Content-Type: application/json", "--data-binary", f"@{body_file.name}"]
    cmd.append(f"{API_BASE}{path}")
    try:
        out = subprocess.run(cmd, input=f"Authorization: Token {API_KEY}\n", capture_output=True, text=True).stdout
    finally:
        if body_file:
            os.unlink(body_file.name)
    text, _, code = out.rpartition("\n")
    status = int(code) if code.isdigit() else 0
    try:
        return status, json.loads(text or "null")
    except json.JSONDecodeError:
        return status, text[:500]


def eligibility(screen_uuid: str) -> tuple[int, Any]:
    """GET eligibility, retrying once on an empty or non-JSON reply."""
    status, results = request("GET", f"/api/eligibility/{screen_uuid}")
    if status != 200 or not isinstance(results, dict) or "programs" not in results:
        status, results = request("GET", f"/api/eligibility/{screen_uuid}")
    return status, results


def benefit_names(white_label: str) -> list[str]:
    status, body = request("GET", f"/api/screener-options/{white_label}/has-benefits-programs/")
    if status != 200:
        sys.exit(f"has-benefits list for {white_label} returned {status}: {body}")
    return [p["name_abbreviated"] for p in body]


def resolve(kind: str, offered: list[str]) -> Optional[str]:
    return next((n for n in offered if n == kind or n.endswith("_" + kind)), None)


# --- payloads (api-qa-execution Phase 2)


def member_payload(m: M, frontend_id: str) -> dict[str, Any]:
    insurance = {k: False for k in INSURANCE}
    insurance[m.insurance] = True
    return {
        "frontend_id": frontend_id,
        "relationship": m.relationship,
        "birth_year": m.birth[0],
        "birth_month": m.birth[1],
        "age": current_age(m.birth),
        "has_income": bool(m.income),
        "income_streams": [{"type": t, "amount": a, "frequency": f} for t, a, f in m.income],
        "insurance": insurance,
        # The screener answers every yes/no question; null reads as unanswered and drops the program.
        **{k: False for k in FLAGS},
        **m.flags,
    }


def screen_payload(t: Ticket, s: S, benefits: list[str], ids: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "white_label": t.white_label,
        "is_test": True,
        "agree_to_tos": True,
        "is_13_or_older": True,
        "household_size": len(s.members),
        "household_assets": s.assets,
        "request_language_code": "en-us",
        "start_date": datetime.now(timezone.utc).isoformat(),
        "referral_source": "test",
        "household_members": [member_payload(m, i) for m, i in zip(s.members, ids)],
        "expenses": [{"type": t_, "amount": a, "frequency": f} for t_, a, f in s.expenses],
        "current_benefits": benefits,
        "has_benefits": "true" if benefits else "false",
    }
    if t.zipcode:
        payload["zipcode"], payload["county"] = t.zipcode, t.county
    return payload


# --- grading (api-qa-execution Phase 3)


def run_scenario(t: Ticket, s: S, offered: list[str]) -> tuple[str, str]:
    benefits = []
    for kind in s.benefits:
        name = kind[1:] if kind.startswith("=") else resolve(kind, offered)
        if name is None:
            return "SKIP", f"{t.white_label} offers no '{kind}' current benefit here"
        benefits.append(name)

    ids = [str(uuid.uuid4()) for _ in s.members]
    status, screen = request("POST", "/api/screens/", screen_payload(t, s, benefits, ids))
    if status in (401, 403):
        sys.exit(f"POST /api/screens/ returned {status}: check API_KEY")
    if status != 201:
        return "ERROR", f"POST /api/screens/ returned {status}: {str(screen)[:300]}"
    if not isinstance(screen, dict) or not screen.get("uuid"):
        # Don't re-POST: the first request may have created the screen.
        return "ERROR", f"POST /api/screens/ returned 201 with an unusable body: {str(screen)[:300]}"
    saved = {b if isinstance(b, str) else b.get("name_abbreviated") for b in screen.get("current_benefits") or []}
    unsaved = [b for b in benefits if b not in saved]
    if unsaved and screen.get("current_benefits") is not None:
        return "BLOCKED", f"current benefits not saved: {unsaved} screen={screen['uuid']}"

    status, results = eligibility(screen["uuid"])
    if status != 200 or not isinstance(results, dict) or "programs" not in results:
        return "ERROR", f"GET /api/eligibility returned {status}: {str(results)[:300]} screen={screen['uuid']}"

    missing = bool(results.get("missing_programs"))
    notes = [f"external_api_failures={results['external_api_failures']}"] if results.get("external_api_failures") else []
    notes += [f"{n} sent directly (not in the has-benefits step)" for n in benefits if n not in offered]
    program = next((p for p in results["programs"] if p["name_abbreviated"] == s.program), None)

    if program is None:
        if missing:
            return "ERROR", f"{s.program} absent with missing_programs=true (dropped; see why_dropped) screen={screen['uuid']}"
        got, eligible, value, by_id = "not found", False, None, {}
    else:
        eligible = bool(program["eligible"]) and not program.get("already_has")
        value = program["estimated_value"]
        got = f"eligible={program['eligible']} already_has={program.get('already_has', False)} value={value}"
        by_id = {m["frontend_id"]: m for m in program.get("members", [])}

    problems = []
    if eligible != s.eligible:
        problems.append(f"expected eligible={s.eligible}")
    if s.eligible and s.value is not None and program is not None:
        if not isinstance(value, (int, float)):
            problems.append(f"expected value={s.value}, got no numeric value")
        elif abs(value - s.value) > s.units:
            problems.append(f"expected value={s.value} (±{s.units})")
    for person, (m_eligible, m_value) in s.member_expect.items():
        m = by_id.get(ids[person - 1])
        if m is None:
            problems.append(f"person {person} not evaluated")
            continue
        got_value = m["value"] if m["eligible"] else 0
        got += f" p{person}=({m['eligible']}, {got_value})"
        if m["eligible"] != m_eligible or (m_value is not None and abs(got_value - m_value) > 1):
            problems.append(f"person {person} expected ({m_eligible}, {m_value})")
    if missing:
        notes.append("missing_programs=true (another program dropped)")
    detail = got + "".join(f" | {x}" for x in problems + notes) + f" | screen={screen['uuid']}"
    return ("FAIL" if problems else "PASS"), detail


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in TICKETS:
        sys.exit(f"usage: python3 scenarios.py {{{'|'.join(TICKETS)}}}")
    if not API_KEY:
        sys.exit("set API_KEY")
    ticket_id = sys.argv[1]
    print(f"{ticket_id} against {API_BASE}, {TODAY}")
    counts = {"PASS": 0, "FAIL": 0, "ERROR": 0, "BLOCKED": 0, "SKIP": 0}
    for t in TICKETS[ticket_id]:
        offered = benefit_names(t.white_label)
        print(f"\n== white label {t.white_label}; has-benefits names: {sorted(offered)}")
        for s in t.scenarios:
            status, detail = run_scenario(t, s, offered)
            counts[status] += 1
            print(f"{status} [{t.white_label}] scenario {s.number}: {s.title} -- {detail}", flush=True)
    print(f"\nSUMMARY {ticket_id}: " + ", ".join(f"{n} {k}" for k, n in counts.items()))


if __name__ == "__main__":
    main()
