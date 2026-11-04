---
name: pr-description
description: Write a pull request description in the MyFriendBen house format, with a mandatory Deployment section covering post-deployment responsibilities. Use whenever opening a PR, drafting or revising a PR body, running `gh pr create`, or when the user asks for "the PR description". Also use when reviewing an existing PR body for missing deployment steps.
usage: /pr-description [PR-number | branch | ticket-id]
example: /pr-description MFB-1638
---

<command-name>pr-description</command-name>

# MFB PR Description

Produces a pull request description in the format MyFriendBen actually uses in
`benefits-api`. The authority is [`.github/pull_request_template.md`](https://github.com/MyFriendBen/benefits-api/blob/main/.github/pull_request_template.md);
this skill records how the team fills it in, and the conventions that only exist in
merged PRs.

**The Deployment section is required on every PR, without exception** — including
pure refactors, test-only changes, and doc changes. "Nothing to do" is a finding
that reviewers and the on-call need stated, not an omission for them to infer.
Historically refactor PRs dropped the section entirely (benefits-api #1700, #1704,
#1709); do not copy that.

---

## Output rules

**Print the description in chat as markdown. Never write it to a file.** It gets
pasted into GitHub, so it has to be copy-pasteable straight out of the conversation.

Wrap it in a fence using **four** backticks, so fenced code blocks *inside* the
description survive. One block per PR.

The same applies to anything else destined for a web form: issue bodies, PR comment
replies, release notes, Slack posts, commit messages.

When creating the PR directly, pass the body via stdin or a heredoc:

```bash
gh pr create --title "MFB-1234: short imperative summary" --body "$(cat <<'EOF'
...description...
EOF
)" --assignee @me
```

Title convention: `MFB-1234: lowercase imperative summary`. Ticket-less work drops
the prefix (`fix: hash passwords saved through the user admin`).

---

## The shape

Five sections, in this order. Keep the template's headings — reviewers scan for them.

```markdown
## Context & Motivation
## Changes Made
## Testing
## Deployment          <-- always present
## Notes for Reviewers
```

The format is loose below the headings. Long PRs replace the flat bullet lists with
prose and sub-headings (`### Bug 1 — ...`), add tables of measured before/after
values, and split `## Changes Made` into several topical `##` sections. That is fine
and normal — the fixed points are the five headings and the Deployment content.

### Context & Motivation

Why the change is needed, not what it does. Link the Linear ticket by URL (a bare
`MFB-1234` is not clickable), plus related PRs across repos. If the change is
blocked by or blocking another ticket, say so here.

State the consequence of *not* shipping when there is a deadline or an active
incorrect behavior — that is what tells a reviewer how hard to look.

### Changes Made

Concrete and specific. Name the files, classes, and commands. Prefer a short lead
sentence per change over a bare filename list.

For bug fixes, give each bug its own sub-heading with the mechanism: what the code
did, why that was wrong, what it does now. Reviewers should be able to check the
reasoning without reconstructing it from the diff.

Call out anything deliberately **not** changed and why — a stale base class left
alone to avoid an unreviewed cross-state blast radius is a decision, and silence
reads as an oversight.

### Testing

What you ran and what it proved, with real numbers:

- Test counts and suites (`programs/`: 2710 passed).
- **Pre-existing failures identified as pre-existing**, with how you confirmed it
  (stash the change, re-run, name the test).
- For bug fixes: verify the new tests actually fail against the unfixed code, and
  report it (`with the fix reverted, 6 of the 16 fail`). A regression test that
  passes both ways is not a regression test.
- Migrations to run locally, config imports, env vars, and manual steps a reviewer
  needs to reproduce.
- `black -l 120` clean.

### Notes for Reviewers

Where to look and what you already know is imperfect. Common content: review
feedback addressed (and anything **declined**, with the reasoning); spec
corrections back-filled, verified against a live source rather than argued;
known limitations and data gaps; future considerations and follow-up tickets.

---

## Deployment

**Everything after merge.** The reader is whoever merges, deploys, or gets paged —
not the reviewer. Assume they have not read the diff.

### The deploy model

Confirm against [`docs/DEPLOYMENT.md`](https://github.com/MyFriendBen/benefits-api/blob/main/docs/DEPLOYMENT.md);
it is the source of truth and this summary can go stale.

| | Trigger | Heroku app |
|---|---|---|
| **Staging** | merge to `main` (automatic) | `cobenefits-api-staging` |
| **Production** | publishing a GitHub Release | `cobenefits-api` |

Both deploys already run, unconditionally:

- `python manage.py migrate`
- `python manage.py add_config --all`

So **migrations and white-label config changes need no manual step** — say that
explicitly rather than leaving it ambiguous:

> **Handled automatically** — per `docs/DEPLOYMENT.md`, both staging (on merge to
> `main`) and production (on publishing the release) already run `manage.py migrate`
> and `manage.py add_config --all`. The migration and the tile in all 8 white labels
> land with no intervention.

Rollback, worth stating when the change carries real risk:
`heroku rollback -a cobenefits-api`.

### Answer all four prompts, every time

Keep the template's labels. `none` is a valid and useful answer — never drop a line.

```markdown
- Post-deployment scripts needed:
- Production config updates:
- Admin updates needed:
- Notify team/users of:
```

Minimum acceptable form, for a code-only change:

```markdown
## Deployment

- Post-deployment scripts needed: none
- Production config updates: none
- Admin updates needed: none
- Notify team/users of: nothing user-facing — no migrations, no config, no behavior
  change outside the fixed dependency.
```

### Deriving the section

Walk the diff against this table. Anything that hits a **Manual** row belongs in
Deployment with a runnable command.

| In the diff | Deployment consequence |
|---|---|
| New migration | Automatic (`migrate`). Note it anyway; flag long-running or locking migrations. |
| `configuration/white_labels/**` | Automatic (`add_config --all`). Note that a Django admin edit to these rows is **overwritten** on the next deploy. |
| New `*_initial_config.json` | **Manual** — `import_program_config`. |
| New `Program` (calculator + config) | **Manual** — import, then **activate**. See the `active=False` hazard below. |
| New react-intl labels / copy | **Manual** — `add_translations` per environment. See the `add-pr-translations` skill. |
| Urgent needs / resources / navigator fixtures | **Manual** — the relevant import command, per environment. |
| Feature flag | **Manual** admin flip; state who flips it and when. |
| PolicyEngine version-gated inputs (`min_pe_version`) | Verify the deployed PE version clears the floor, with the command to check it. |
| Redis / addon / dyno settings | **Manual** `heroku` config, marked applied or not. |
| Cross-repo change (`ai-service`, `benefits-calculator`) | State deploy **order** and what breaks in the wrong one. |
| Benefit values or eligibility move | Notify + QA guidance, with measured before/after figures. |
| Code-only refactor / tests / docs | All four `none` — still write the section. |

### Recurring patterns to reuse

**Commands are copy-pasteable, per environment, in order.** Not prose describing a
command. Include the app flag and number the steps.

````markdown
*Staging, after the merge deploy completes:*

```bash
heroku run --app cobenefits-api-staging --no-tty -- \
  python manage.py import_program_config path/to/mo_pts_initial_config.json
```
````

**New programs ship `active=False` and must be activated on deploy.** Always give
the reason — it is a real outage mode, not bookkeeping:

> **`mo_ssdi` is intentionally left `active=False`.** An active `Program` row whose
> calculator is absent from the *running* server raises `KeyError` in
> `Program.eligibility()`, where `programs/models.py` resolves
> `calculators[self.name_abbreviated.lower()]` unguarded, and 500s eligibility for
> the entire MO white label. It must be activated as part of deploy, once the
> deployed code includes this calculator.

Cite that lookup by symbol, not by line number — older PRs say
`programs/models.py:782` and the refactors in #1702/#1704 have already moved it.

**Name hazards as instructions, before the commands.** If a natural way to run the
steps is wrong, say so first (benefits-api #1693, #1695):

> **Do not run these imports as a bare loop.** `--override` deletes and recreates
> each program: `new_program()` creates with `active=False`, so every currently
> active program goes inactive until restored.

**Assign an owner when it is not the merger's job.** Otherwise the steps fall to
whoever merges, or to nobody (#1688):

> **Owner: David.** These steps are not for the merger or the on-call to pick up.
> Please do not run the repair independently.

**Mark status on multi-environment rollouts**, so a re-reader knows what is left:

> **Status: staging ✅ done · production ⏸ blocked on a release**

**State deploy order for cross-repo work**, and the failure mode of getting it wrong
(#1670):

> **Deploy ai-service#9 first.** It ignores `current_programs` if this ships alone,
> so the already-receiving context would be silently dropped.

**Warn on blast radius under "notify" when user-visible numbers move.** Give the
measured figures — intended changes still need announcing (#1685):

> Benefit **values change** for a large share of households — intended, but not a
> silent refactor: SNAP rises in all 7 states for households not reporting SSI
> (measured `$62.50 → $298`/mo). WIC eligibility narrows in CO/IL/MA/NC/TX/MO.

**Idempotency and verification.** If a script is safe to re-run, say so. Give the
command that confirms it worked, not just the one that does the work.

---

## Checklist

- [ ] Five headings present, Deployment among them — no exceptions
- [ ] Ticket linked by full URL; related PRs across repos linked
- [ ] Bug fixes explain the mechanism, not just the symptom
- [ ] Deliberate non-changes stated as decisions
- [ ] Test counts real; pre-existing failures confirmed as pre-existing
- [ ] New regression tests verified to fail against the unfixed code
- [ ] All four Deployment prompts answered, `none` included
- [ ] Automatic vs. manual stated explicitly, citing `docs/DEPLOYMENT.md`
- [ ] Manual steps are runnable commands, per environment, correctly ordered
- [ ] New programs: `active=False` noted with the activation step and its reason
- [ ] Owner named where the steps are not the merger's
- [ ] User-visible value/eligibility changes announced with figures
- [ ] Printed in chat inside a four-backtick fence — never written to a file
