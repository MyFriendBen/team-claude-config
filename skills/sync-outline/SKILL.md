---
name: sync-outline
description: Audit a mapped group of Outline docs for parity against their source SKILL.md files (the source of truth), surface logical discrepancies, and update the Outline docs only after explicit user approval. Use when SKILL.md files have changed and the corresponding Outline documentation may be stale, or when the user asks to "sync Outline", "check Outline docs against the skills", or verify documentation parity. Runs fully locally through the Outline MCP server — no API keys are stored or pushed anywhere.
---

# Sync Outline — SKILL.md → Outline Parity Audit

Keeps a set of Outline documents in parity with the SKILL.md files that define our workflows. **The SKILL.md files are the source of truth.** This skill reads a mapping of Outline docs to their source skills, compares each Outline doc against its source(s) for *logical* discrepancies (not verbatim diffs — the Outline docs are human-readable renderings, not copies), recommends changes, and updates Outline **only after the user approves each change**.

This is a read-first, ask-always workflow. It never writes to Outline without explicit confirmation.

## Usage

```
/sync-outline                # audit every doc in the mapping
/sync-outline <outline_title substring or doc id>   # audit only matching entries
```

## Core Principles

1. **SKILL.md is canonical.** When the source and the Outline doc disagree, the SKILL.md wins. Recommend bringing Outline into line with the skill — never the reverse.
2. **Logical parity, not byte parity.** Outline docs are summarized / reformatted prose. Only flag discrepancies that change meaning: missing steps, contradictory instructions, stale commands, removed/renamed phases, wrong prerequisites, outdated facts. Do not flag pure wording, ordering of prose, or formatting differences.
3. **Always ask before writing.** Present every proposed change and wait for explicit approval. Never batch-write silently.
4. **No mapping, no write.** Only operate on Outline docs that have a *valid mapping entry* — a present `outline_id` (not a placeholder) and a non-empty `sources` list whose files all exist on disk. Docs that are unmapped, have empty `sources`, or point at a missing source file are skipped entirely: never audited, never updated. Report them as skipped so it's clear they fell outside the sync.
5. **Prefer surgical patches.** Use `update_document` with `editMode: "patch"` so Outline's rich formatting (highlights, comments, table widths, manual annotations) is preserved. Only fall back to `replace` when the change is too structural to patch and the user agrees.
6. **Backtick fallback = full replace, with permission.** The patch matcher cannot match `findText` containing a backtick, so any change that lives inside inline code (`` `like_this` ``) is impossible to patch. When that happens, the **only** way to apply it is a full-document `replace`. Do not do that silently: **notify the user that this specific change requires a full-doc refresh, explain that `replace` overwrites the whole document and may drop Outline-only formatting, and get their explicit approval first.** If they don't approve, skip the change and report it as unaddressed. This permission is per-document and not implied by approval of the patches.

---

## Workflow

### Phase 0: Verify the Outline MCP server is running

Before anything else, confirm the Outline MCP server is connected and authenticated. Make one lightweight call:

- Call `mcp__outline__list_collections` with `limit: 1`.

**If it returns successfully**, the server is up — proceed.

**If it errors** (not connected, auth failure, tool unavailable), stop and tell the user:

> The Outline MCP server isn't responding. Authenticate it by running `/mcp` in this session (select `outline` → authenticate), then re-run `/sync-outline`.

Do not continue until the check passes.

### Phase 1: Load the mapping

Read `${CLAUDE_SKILL_DIR}/outline-map.json`. It defines every Outline doc under management and the source SKILL.md file(s) that inform it. The format:

```json
{
  "documents": [
    {
      "outline_id": "<doc id or full Outline URL>",
      "outline_title": "Human-friendly title (for display + filtering)",
      "combination_strategy": "sectioned | concat",
      "section_separator": "---",
      "sources": [
        { "path": "discovery-review/SKILL.md", "heading": "Discovery Review" }
      ]
    }
  ]
}
```

- `sources` paths are relative to the skills root (`team-claude-config/skills`).
- **Many-to-one is supported**: list multiple sources to have several skills inform one Outline doc.
- `combination_strategy`: `sectioned` mentally groups each source under its `heading`; `concat` treats them as one continuous body.

If the user passed an argument, filter `documents` to entries whose `outline_title` or `outline_id` matches it.

**Filter to valid mappings only.** An entry is valid when it has a real `outline_id` (not a `REPLACE-WITH-...` placeholder) **and** a non-empty `sources` list whose every `path` resolves to a file on disk. Drop any entry that fails this check and list it under a "Skipped (no valid mapping)" heading with the reason (placeholder id / empty sources / missing source file). These docs are never fetched, audited, or written. If *no* entries are valid, tell the user the mapping needs to be filled in first and stop.

### Phase 2: Gather sources and current Outline content

For each mapped document:

1. Read every source SKILL.md from disk (the canonical content).
2. Fetch the live Outline doc: `mcp__outline__fetch` with `resource: "document"` and `id: <outline_id>` (accepts an id or a full URL). Capture its current markdown.

### Phase 3: Audit for logical discrepancies

Compare the source(s) against the Outline doc. For each mapped doc, produce a short findings list. Classify each finding:

- **Stale** — Outline states something the skill has since changed (old command, renamed phase, dropped step).
- **Missing** — the skill covers something the Outline doc omits that matters for the workflow.
- **Contradiction** — Outline says something that conflicts with the skill.
- **Extra** — Outline contains workflow content with no basis in any source (may be intentional human annotation — flag, don't assume it's wrong).

If a doc is already in parity, say so plainly and move on — no busywork edits.

### Phase 4: Recommend changes (ASK FIRST)

For each doc with findings, present:

- The doc title and a one-line parity verdict.
- Each finding with the exact current Outline text and the proposed replacement (the `findText` / `text` you'd use for a patch).

Then **ask the user** which changes to apply — all, some, or none. Wait for their answer. Do not write yet.

If any proposed change targets text inside inline code (a backtick token), flag it here as **"requires full-doc refresh"**: it cannot be patched, so applying it means a full `replace` of that document. Call this out as its own approval decision — name the doc, warn that `replace` overwrites the whole document and may drop Outline-only formatting, and ask the user to approve the refresh or skip the change. Never assume approval of the other patches extends to a `replace`.

### Phase 5: Apply approved updates

Only docs that passed the Phase 1 valid-mapping filter are eligible to be written. For each approved change, call `mcp__outline__update_document`:

- Prefer `editMode: "patch"` with `findText` (verbatim from the current Outline markdown) and `text` (the replacement). This preserves rich formatting elsewhere in the doc.
- Use `editMode: "replace"` only for structural rewrites the user explicitly approves.
- Update `title` only if the user approves a title change.

### Patch-matching constraints

The Outline `patch` matcher is literal and brittle. Account for these before proposing a patch:

- **`findText` containing a backtick never matches.** Inline code (`` `like_this` ``) and code-fence lines can't be targeted by `patch`. If the text you need to change *is* a backtick token (a code path, command, field name, etc.), **patch cannot reach it.** In that case, propose a **full-document refresh** (`editMode: "replace"` with the whole corrected doc) — but **only after the user explicitly approves it.** Never run a `replace` without that approval, because it overwrites the entire document and can drop Outline-only formatting (table column widths, highlights, comments). Present it as a distinct choice: "this fix needs a full-doc refresh because the change is inside inline code — approve replace, or skip?"
- **Anchor on backtick-free spans.** When the surrounding prose is plain text, match a backtick-free phrase next to the target rather than the code token itself.
- **Identical strings = first-occurrence trap.** `patch` replaces only the first match. If the same line appears more than once (e.g. a command repeated in a "Step" and a "Testing" section), a second identical patch will re-hit the already-edited first line — often corrupting it. Disambiguate by including a leading/trailing newline (`\n…\n`) or other unique surrounding context so each call targets a distinct occurrence, and re-fetch/verify between writes.

After writing, confirm what changed per doc and note anything left unaddressed (e.g. "Extra" content the user chose to keep). Never re-run a write the user didn't approve.

---

## Adding a new doc to the sync

Edit `outline-map.json` and add an entry with the Outline `outline_id` (id or URL), a title, and its `sources`. New entries are picked up on the next run. Removing an entry takes a doc out of management without touching the live Outline content.

## Notes

- This skill only ever reads SKILL.md files and reads/writes the mapped Outline docs. It touches nothing else.
- No secrets are stored or transmitted — all Outline access goes through the already-authenticated Outline MCP server.
