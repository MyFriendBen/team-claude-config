---
name: pe-cassette-refresh
description: Weekly PolicyEngine drift check for benefits-api. Re-records every PolicyEngine spec-scenario cassette at PE `frontier` (early warning) and `current` (adoption), opens a PR adopting the programs whose values didn't change, and files one Linear rollup ticket for value changes plus a separate Urgent ticket per screener-breaking change. Run by the on-call dev on Thursdays, or whenever PolicyEngine promotes a release.
usage: /pe-cassette-refresh [--dry-run]
example: /pe-cassette-refresh
---

<command-name>pe-cassette-refresh</command-name>

# PolicyEngine Cassette Refresh

PolicyEngine (PE) serves only what `current` and `frontier` resolve to, and staging and prod ride `current` with no pin. So a PE release changes what households see the day PE promotes it. This skill measures that change against our spec scenarios and turns it into a PR and tickets.

- **Who:** the on-call dev, every Thursday. PE releases usually land Tuesday–Wednesday.
- **Triage SLA:** the rollup is triaged by the following Monday and fixed in that week's release. Urgent tickets are hotfixes.
- **`--dry-run`:** do everything except push, open the PR, and write to Linear. Print the PR body and ticket drafts instead.

The mechanics live in benefits-api: `manage.py record_and_diff` (`programs/management/commands/record_and_diff.py`) and the suite pin `PE_TEST_VERSION` (`programs/programs/testing_fixtures/pe_integration.py`). See `docs/TESTING.md` there. This skill runs them and does the judgment.

## Rules

- Only call the private `household.api.policyengine.org`. Never the public API.
- Never print, copy, link or edit any `.env` file. Recording reads PE credentials from `benefits-api/.env` through `decouple`, which finds it by walking up from the worktree.
- Never edit a `spec.md` expected value, and never merge. The PR and tickets go to people.
- If a stage fails, stop. Say which stage failed and why, and keep the run directory so triage can be finished by hand. Don't retry a recording blindly: PE limits tokens per month.

---

## Step 1: Preflight

Run from the root of the dev's benefits-api checkout. Stop at the first failure and tell the dev what to fix.

```bash
API=$(git rev-parse --show-toplevel)             # the dev's benefits-api checkout
git fetch -q origin
redis-cli ping                                   # PONG; else: redis-server --daemonize yes
grep -c -E '^POLICY_ENGINE_CLIENT_(ID|SECRET)=.' .env   # must print 2; never print the values
gh auth status
```

Confirm Linear works by listing teams through the Linear MCP; tickets go to team **MFB General**.

Set the run's values. Resolve PE once: it can promote mid-run.

```bash
DATE=$(date +%F)
VERSIONS=$(curl -sf https://household.api.policyengine.org/versions/us)   # -f: an HTTP error fails here
CURRENT=$(echo "$VERSIONS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["current"])')
FRONTIER=$(echo "$VERSIONS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["frontier"])')
PIN=$(git show origin/main:programs/programs/testing_fixtures/pe_integration.py | sed -n 's/^PE_TEST_VERSION = "\(.*\)"$/\1/p')
echo "DATE=$DATE CURRENT=$CURRENT FRONTIER=$FRONTIER PIN=$PIN"
```

Stop unless `CURRENT`, `FRONTIER` and `PIN` are all exact versions (`2.53.1`, not empty or an alias). Shell variables don't carry between commands, so set these values again (or substitute them) in every later command.

## Step 2: Worktree

Work in a fresh worktree off `origin/main`, inside `.claude/` (gitignored), so the dev's checkout is untouched and `.env` is found by walking up.

```bash
cd "$API"
WT="$API/.claude/worktrees/pe-drift-$DATE"
git worktree add -b "pe-drift/$DATE" "$WT" origin/main
ln -s "$API/venv" "$WT/venv"                     # the pre-commit hook runs venv/bin/python; gitignored
RUN=/tmp/pe-drift/$DATE
PY="$WT/venv/bin/python"
```

Run every later command from `$WT` with `$PY`.

## Step 3: Frontier pass (warning only)

Skip if `FRONTIER == CURRENT`.

```bash
cd "$WT" && "$PY" manage.py record_and_diff --target "$FRONTIER" --out "$RUN/frontier"
```

Takes several minutes: a baseline replay, then a serial live recording of every PE scenario. Writes `$RUN/frontier/diff.json`. Nothing in the worktree changes. If `baseline.log` shows failures, `main` itself is broken: stop and report them.

## Step 4: Current pass (adoption)

Always run it. Even when `CURRENT == PIN`, modules still pinned below `CURRENT` get re-recorded.

```bash
cd "$WT"
# Step 3 ran: reuse its baseline.
"$PY" manage.py record_and_diff --target "$CURRENT" --out "$RUN/current" --baseline "$RUN/frontier/baseline" --adopt
# Step 3 was skipped:
"$PY" manage.py record_and_diff --target "$CURRENT" --out "$RUN/current" --adopt
```

`--adopt` moves `PE_TEST_VERSION` to `CURRENT`, copies in the new cassettes of every unchanged module and removes its pin, and pins every changed module at its old version with a reason. `diff.json` lists both under `adopt`.

**Current-pass changes are already live:** staging and prod serve `CURRENT` today. Frontier changes are coming.

## Step 5: Verify and open the PR

Skip if `git -C "$WT" status --porcelain` is empty.

```bash
cd "$WT" && VCR_MODE=none "$PY" -m pytest -q -p no:cacheprovider -m integration
```

It must pass. A failure means adoption left a module inconsistent; stop and report it.

Commit. If the black hook reformats a file, `git add` it and commit again. Unless `--dry-run`, push `pe-drift/$DATE` and open a PR titled `PE drift: adopt PolicyEngine $CURRENT ($DATE)`. Write the body to `$RUN/pr-body.md` (never a shared `/tmp` name), following `.github/pull_request_template.md`:
- **Context & Motivation:** the weekly refresh; `PIN` → `CURRENT`; link the rollup ticket (Step 7).
- **Changes Made:** adopted modules; held modules and why, linking the rollup.
- **Testing:** "Strict replay (`VCR_MODE=none pytest -m integration`) passes." No migrations, config or env changes.
- **Deployment:** none. Test-only change.
- **Notes for Reviewers:** anything surprising from triage.

Unless `--dry-run`, fill in the rollup link after Step 7 with `gh pr edit --body-file "$RUN/pr-body.md"`.

## Step 6: Triage

For every module in either `diff.json` whose `status` isn't `unchanged`, and each scenario under it:

1. Read the scenario's test (its docstring states the expected outcome) and the program's spec: `spec.md` beside the tests' parent, or `specs/<state>.md` in a family directory.
2. Read the spec's cited source for the rule that moved.
3. Find the PE change: the `CHANGELOG.md` sections of `PolicyEngine/policyengine-us` between the baseline version and the target:
   `gh api repos/PolicyEngine/policyengine-us/contents/CHANGELOG.md -H 'Accept: application/vnd.github.raw'`
4. Classify:

| Class | Test | Goes to |
|--|--|--|
| **PE fix** | The new value or eligibility matches the spec's cited source | Rollup: update the spec value and the assertion |
| **Divergence** | The new value or eligibility moves away from the cited source | Rollup: investigate; report upstream to PE if PE is wrong |
| **Screener-breaking** | `error` status: a request error (e.g. 422), a renamed or removed PE variable, or anything that would 500 the eligibility endpoint or drop programs from results | **Urgent** ticket |

Give the reason in one sentence, with the citation. When unsure between fix and divergence, say so; a person decides.

Group scenarios that move for one root cause (one changelog entry) into one finding.

## Step 7: Tickets

Skip writes under `--dry-run`; print the drafts.

**Label.** Use `PE Drift`. If it doesn't exist, create it (workspace label, description: "Found by the weekly PolicyEngine cassette refresh").

**Previous rollup.** Find the latest open issue labelled `PE Drift` titled `PE drift rollup — …`. Findings in it that this run still shows are carried forward, marked "Carried forward from <issue>", not filed again. Comment on the previous rollup linking the new one.

**Rollup** (one per run; skip only if there are no findings and nothing carried forward):
- Team **MFB General**, label `PE Drift`, priority High, title `PE drift rollup — week of <Monday of DATE>`.
- Body:
  - Header: run date, who ran it, `PIN` / `CURRENT` / `FRONTIER`, link to the PR.
  - **Live now (`CURRENT`)** and **Coming (`FRONTIER`)** sections. One subsection per program: a table of scenario / before / after, the class and its one-line reason, the spec citation, the PE changelog entry.
  - **Held modules:** the modules `--adopt` pinned at their old version. Fixing one means reconciling its spec, then deleting its `PE_VERSION` / `PE_VERSION_REASON` and re-recording.

**Urgent** (one per screener-breaking finding; never folded into the rollup):
- Team **MFB General**, labels `PE Drift` and `Bug`, priority Urgent, title `PE drift: <program> breaks at PolicyEngine <version>`.
- Body: the error, the scenarios hitting it, the changelog entry, and whether it's **live now** (`CURRENT`, so prod is broken today, hotfix) or **coming** (`FRONTIER`, fix before PE promotes it).
- Link it from the rollup.

## Step 8: Wrap up

Report to the dev: the versions, counts per class, links to the PR, rollup and any Urgent tickets, and anything triage couldn't decide.

Remove the worktree only once its branch is pushed (or under `--dry-run`): `rm "$WT/venv" && git worktree remove "$WT"`. Keep `$RUN` until the rollup is triaged.

## First run

Modules recorded before the suite pin existed still carry `PE_VERSION` overrides at old versions. The first run re-records them all at `CURRENT`, so expect a large rollup. That rollup is the catch-up backlog.
