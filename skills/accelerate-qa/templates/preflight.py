# QA state check. READ-ONLY: no saves, no deletes.
#
#   cd <mfb-workspace>/benefits-api
#   heroku run --no-tty -a <heroku app> "python manage.py shell" < <batch folder>/preflight.py
#
# Locally: python manage.py shell < <batch folder>/preflight.py (local data can be stale; a
# local-only FAIL is unconfirmed).
#
# Prints one PASS/FAIL/INFO line per check, tagged with its ticket, then a summary.
# Keep the helpers; replace the example block at the bottom with one block per ticket.

import json
from typing import Any, Optional

from django.db.migrations.recorder import MigrationRecorder

from configuration.models import Configuration
from programs.framework.gates import all_calculator_classes
from programs.models import Program, Referrer, WarningMessage
from screener.models import EligibilitySnapshot

counts = {"PASS": 0, "FAIL": 0}
APPLIED = set(MigrationRecorder.Migration.objects.values_list("app", "name"))
CALCULATORS = all_calculator_classes()


def check(ticket: str, ok: bool, label: str, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    counts[status] += 1
    print(f"{status} [{ticket}] {label}" + (f" -- {detail}" if detail else ""))


def info(ticket: str, text: str) -> None:
    print(f"INFO [{ticket}] {text}")


def describe(p: Program) -> str:
    period = p.year.period if p.year else None
    registered = p.name_abbreviated in CALCULATORS
    return (
        f"{p.white_label.code}/{p.name_abbreviated} active={p.active} "
        f"has_calculator={p.has_calculator} registered={registered} year={period}"
    )


def program(white_label: str, name: str) -> Optional[Program]:
    return (
        Program.objects.filter(white_label__code=white_label, name_abbreviated=name)
        .select_related("year", "white_label")
        .first()
    )


def expect_migration(ticket: str, app: str, name: str) -> None:
    check(ticket, (app, name) in APPLIED, f"migration {app}.{name} applied")


def expect_active(ticket: str, white_label: str, name: str) -> Optional[Program]:
    """The row exists, is active, and has a registered calculator (unless it's a no-calculator program)."""
    p = program(white_label, name)
    ok = p is not None and p.active and (not p.has_calculator or p.name_abbreviated in CALCULATORS)
    check(ticket, ok, f"{white_label}/{name} exists, active, calculator registered", describe(p) if p else "missing")
    return p


def expect_inactive(ticket: str, rows: list[tuple[str, str]]) -> None:
    for white_label, name in rows:
        p = program(white_label, name)
        check(ticket, p is None or not p.active, f"{white_label}/{name} inactive", describe(p) if p else "no row")


def expect_year(ticket: str, p: Optional[Program], period: str) -> None:
    got = p.year.period if p and p.year else None
    check(ticket, got == period, f"{p.name_abbreviated if p else '?'} year is {period}", f"got {got}")


def expect_warning_links(ticket: str, calculator: str, white_label: str, names: set[str]) -> None:
    """A warning with this calculator exists for the white label and links at least `names`."""
    warnings = WarningMessage.objects.filter(calculator=calculator, white_label__code=white_label)
    check(ticket, warnings.exists(), f"{calculator} warning exists for {white_label}")
    for w in warnings:
        linked = set(w.programs.values_list("name_abbreviated", flat=True))
        check(ticket, linked >= names, f"warning {w.id} ({white_label}) links {sorted(names)}", f"links {sorted(linked)}")


def expect_referrer(ticket: str, white_label: str, code: str) -> None:
    r = Referrer.objects.filter(white_label__code=white_label, referrer_code=code).first()
    check(
        ticket,
        r is not None,
        f"{white_label} referrer {code} exists",
        f"name={r.name!r} is_partner={r.is_partner}" if r else "missing",
    )


def config_data(white_label: str, name: str) -> Any:
    cfg = Configuration.objects.filter(white_label__code=white_label, name=name).first()
    if cfg is None:
        return None
    return json.loads(cfg.data) if isinstance(cfg.data, str) else cfg.data


def navigators(p: Program) -> list[str]:
    """The program's navigators in display order. `navigators_ordered` is current; `navigator` is legacy."""
    return list(p.navigators_ordered.values_list("external_name", flat=True))


def why_dropped(uuid: str) -> None:
    """Print why programs were left out of a screen's latest results (`missing_programs: true`)."""
    snap = EligibilitySnapshot.objects.filter(screen__uuid=uuid).order_by("-submission_date").first()
    print(f"INFO dropped_programs for {uuid}: {snap.dropped_programs if snap else 'no snapshot'}")


# --- Example block: replace with one block per ticket. Names below are illustrative.

T = "EXAMPLE-1"
expect_migration(T, "programs", "0001_initial")
expect_active(T, "federal", "federal_eitc")
info(T, f"co rows named eitc: {[describe(p) for p in Program.objects.filter(name_abbreviated='eitc', white_label__code='co')]}")

print(f"\nSUMMARY: {counts['PASS']} PASS, {counts['FAIL']} FAIL")
