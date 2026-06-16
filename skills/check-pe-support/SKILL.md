---
name: check-pe-support
description: Discover whether PolicyEngine exposes a variable for a program under consideration. Searches PE's full variable catalog (fuzzy or exact) and reports the entity, base class, period, and module — used as a pre-flight gate before implementing a PE calculator.
usage: /check-pe-support [pe_variable_name] [--state XX]
example: /check-pe-support co_ccad --state co
---

<command-name>check-pe-support</command-name>

# Check PolicyEngine Support

Determines whether PolicyEngine exposes a variable for a program we're considering implementing. This is a **discovery command**, not a check against calculators already in our system. It searches PE's variable catalog and tells you whether a PE-based calculator is even an option — and, when it is, which base class to subclass and what the variable looks like.

The command downloads PE's full metadata blob (~66 MB) once and caches it on disk for 24 hours. Subsequent runs within a work session reuse the cache.

---

## Step 1: Gather Inputs

You need at least one of:

- **Exact PE variable name** — from the ticket description, spec, or initial config (e.g. `co_ccad`, `hse`, `co_tanf`)
- **Search terms** — free-text concepts (e.g. `childcare colorado`, `liheap`, `snap`)
- **State abbreviation** — two-letter code (e.g. `co`, `ma`, `tx`) to narrow the search

If you have an exact variable name, prefer the exact lookup — it's unambiguous. If you only have a program concept, use fuzzy search scoped to the state.

---

## Step 2: Run the Command

Run from `benefits-api/`. Use `venv/bin/python` — `python` may not resolve in non-interactive shells.

### Exact variable-name lookup (preferred when name is known)
```bash
venv/bin/python manage.py check_pe_support --exact {pe_variable_name}
```

### Fuzzy search by concept, scoped to state
```bash
venv/bin/python manage.py check_pe_support {term1} {term2} --state {state_abbrev}
```

### Additional flags

| Flag | Purpose |
|---|---|
| `--state XX` | Narrow to variables under `gov.states.XX.*` |
| `--computed-only` | Hide raw input variables; show benefit outputs only |
| `--entity {entity}` | Filter by PE entity (`spm_unit`, `tax_unit`, `person`, etc.) |
| `--limit N` | Max results to display (default 40) |
| `--refresh` | Force a fresh metadata download (bypasses the 24h cache) |

### Example invocations
```bash
# Exact lookup
venv/bin/python manage.py check_pe_support --exact co_ccad

# Concept search scoped to Colorado
venv/bin/python manage.py check_pe_support childcare colorado

# Narrow to computed outputs for Colorado tax units
venv/bin/python manage.py check_pe_support credit --state co --entity tax_unit --computed-only

# Force refresh if metadata may be stale
venv/bin/python manage.py check_pe_support --refresh liheap --state ma
```

---

## Step 3: Interpret the Output

Each matched variable prints a block like:

```
  co_ccad  —  Colorado Child Care Assistance Program
       entity=spm_unit  ->  subclass PolicyEngineSpmCalulator
       period=year   unit=currency(USD)   computed output
       module=gov.states.co.ccad
```

Key fields:

| Field | What it tells you |
|---|---|
| `entity` → `subclass` | The base class to subclass in `policyengine/calculators/base.py` |
| `period` | Calculation period — `year`, `month`, `week`, etc. |
| `computed output` vs `INPUT` | Output = a benefit value PE computes; INPUT = a raw value you'd supply |
| `module` | Jurisdiction sanity-check — confirms the variable is under the right state |

**Entity → base class mapping:**

| PE entity | Base class |
|---|---|
| `spm_unit` | `PolicyEngineSpmCalulator` |
| `tax_unit` | `PolicyEngineTaxUnitCalulator` |
| `person` | `PolicyEngineMembersCalculator` |
| `household` / `family` / `marital_unit` | `PolicyEngineCalulator` (no dedicated subclass) |

---

## Step 4: Gate Decision

**Variable found** — PE supports this program → proceed with implementation.

**Variable NOT found** — the exact lookup exits non-zero with `NOT in PolicyEngine`, or the fuzzy search returns no match for that state. **Stop and alert the user.** Show them the command output and ask whether to continue.

Before halting, try to rule out false negatives:
1. Try a broader/single search term (drop `--state`, drop `--computed-only`)
2. Run `--refresh` in case the cached metadata is stale
3. Check whether the variable might live under a different name (e.g. federal vs. state variant)

If the user confirms it's OK to proceed despite no match (e.g. they know the variable name changed, or they intend to handle this differently), continue as instructed. Otherwise, halt.
