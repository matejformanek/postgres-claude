# Proposed edits to .claude/skills/memory-keeping/SKILL.md (iter-1 → iter-2)

Baseline scored 0.20/1.00 (project-specific, expected). With-skill scored 1.00 but
relied on outside context (CLAUDE.md) for `progress/files-examined.md`. The skill
itself doesn't mention that ledger at all, and it's load-bearing for the most
common operation (deep-reading a file).

## Edit 1 — Add `progress/files-examined.md` as a first-class artifact

The skill currently lists STATE.md, coverage.md, sessions/ as the three artifacts.
Add files-examined.md as the fourth. Description-line, Invariants section, and
the "When to update what" table all need a mention.

### 1a. SKILL.md frontmatter `description`

Replace:
> sync progress/STATE.md, progress/coverage.md, and append a sessions/ log entry

With:
> sync progress/STATE.md, progress/coverage.md, progress/files-examined.md, and append a sessions/ log entry

### 1b. Add Invariant 4

After invariant 3 add:
```
4. **files-examined.md is the per-file ledger.** Append-only. One row per
   source file read in non-trivial depth, columns:
   `path | depth (skim/read/deep-read) | date | last-verified-commit | produced-doc`.
   Update whenever a file becomes load-bearing for any claim in `knowledge/`.
```

### 1c. Add a column to the "When to update what" table

```
| Trigger | STATE.md | coverage.md | files-examined.md | sessions/ |
|---|---|---|---|---|
| New subsystem doc landed | yes (move forward) | new row | append one row per file cited | new file |
| Existing doc re-verified at a newer commit | bump phase if relevant | update `last-verified-commit` | append re-verify rows for re-read files | new file |
| Decision from `pg-claude-plan.md §14` locked | record decision + date | — | — | new file noting rationale |
| Discovered a wrong claim in an existing doc | note correction in STATE | adjust `confidence-summary` | append re-verify row for the file you re-read | new file describing the discovery |
| File-by-file deep read with no new synthesis | — | — | append rows | optional |
| Pure exploration with no durable output | — | — | — | optional, only if worth re-finding |
```

(Adds a row for the file-by-file case, which is currently missing.)

## Edit 2 — Today's date for session log filenames

Add a one-liner to the "How to write a session log" section:
> Use **today's date** in the filename (not the date of the work being described
> if it spanned multiple days — use the day you're writing).

This prevents an LLM with a stale `currentDate` in its context from writing a
filename anchored to an old date and clobbering an existing log.

## Edit 3 — Cross-link to CLAUDE.md rule 6

In the Invariants section add a parenthetical to the new invariant 4:
> (see CLAUDE.md rule 6: "Track what you read.")

So the skill self-anchors to the project rule that motivates it.

## Edit 4 — Tighten correction workflow

Currently row "Discovered a wrong claim" doesn't explicitly say "fix the actual
claim in the knowledge/ doc". Add a sentence under the table:

> When you discover a wrong claim, **fix the claim in the knowledge/ doc itself**
> (the artifact) in the same session. The session log records the discovery; the
> coverage.md row gets its confidence-summary adjusted; STATE.md gets a one-line
> note pointing at the new session log. The old session log is never touched.

## Not changing

- The four session-log headings — they're clear and working.
- The STATE.md fixed shape — also clear.
- "Things you must not do" — still correct.
