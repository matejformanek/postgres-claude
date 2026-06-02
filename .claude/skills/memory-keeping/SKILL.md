---
name: memory-keeping
description: End-of-session bookkeeping for the pg-claude meta repo — sync progress/STATE.md, progress/coverage.md, progress/files-examined.md, and append a sessions/ log entry whenever a session produced durable output (new knowledge/idioms or knowledge/subsystems doc, verified-by-code fact, discovered gotcha, file-by-file deep read, or a locked decision from pg-claude-plan.md §14). Use proactively when the user says "wrap up", "close out", "sync memory files", "record this gotcha", or "we're done for the day". Do NOT trigger for PG MemoryContext/palloc questions, LangChain agent memory, app memory leaks, or finding old Claude sessions.
---

# memory-keeping

The pg-claude system is only as useful as its memory. STATE.md, coverage.md, and
the sessions/ log are how a future Claude (or future you) picks up cold without
re-reading the whole repo.

## Invariants

1. **STATE.md is the front page.** It must answer in under a minute: what phase
   are we in, what's the last thing that got finished, what's the next concrete
   step. Keep it short — link to detail elsewhere.
2. **coverage.md is a table.** One row per documented artifact (subsystem,
   idiom, data-structure). Columns: `name | path | last-verified-commit | confidence-summary | open-questions`.
3. **sessions/ is append-only.** One file per significant session,
   `YYYY-MM-DD-<topic>.md` (use **today's** date, the day you're writing —
   not the date of the work if it spanned multiple days). Never edit old
   session logs; if a later session invalidates a claim, write a new session
   log that supersedes it and update STATE.md to point at the newer one.
4. **files-examined.md is the per-file ledger.** Append-only. One row per
   source file read in non-trivial depth, columns:
   `path | depth (skim/read/deep-read) | date | last-verified-commit | produced-doc`.
   Append whenever a file becomes load-bearing for any claim in `knowledge/`,
   including pure file-by-file deep reads that don't yet have a synthesis doc.
   (See CLAUDE.md rule 6: "Track what you read.")

## When to update what

| Trigger | STATE.md | coverage.md | files-examined.md | sessions/ |
|---|---|---|---|---|
| New subsystem doc landed | yes (move forward) | new row | append one row per file cited | new file |
| Existing doc re-verified at a newer commit | bump phase if relevant | update `last-verified-commit` | append re-verify rows for re-read files | new file |
| Decision from `pg-claude-plan.md §14` locked | record decision + date | — | — | new file noting rationale |
| Discovered a wrong claim in an existing doc | note correction in STATE | adjust `confidence-summary` | append re-verify row for the file you re-read | new file describing the discovery |
| File-by-file deep read with no new synthesis | — | — | append rows | optional |
| Pure exploration with no durable output | — | — | — | optional, only if worth re-finding |

When you discover a wrong claim, **fix the claim in the knowledge/ doc itself**
(the artifact) in the same session. The session log records the discovery; the
coverage.md row gets its confidence-summary adjusted; STATE.md gets a one-line
note pointing at the new session log. The old session log is never touched.

## How to write a session log

≤ 50 lines is the target. Headings:

```markdown
# <date> — <topic>

## What I did
Bullets, terse.

## What I learned
The 2–5 non-obvious things. Cite source files where applicable.

## What I'm unsure about
Honest list. Future sessions can pick these up.

## Pointers left for next time
Concrete next steps, in priority order.
```

## How to update STATE.md

Edit, don't append. STATE.md has a fixed shape:

```markdown
# pg-claude — current state

**Phase:** <Phase 0 / 0.5 / 1a / …>
**Last activity:** <date> — <one-line summary>
**Source commit at last verification:** <sha>

## Done
- bullets

## In progress
- bullets (usually one)

## Next
- 1–3 concrete next steps, in order

## Recent session logs
- `sessions/<file>` — one-line tag
- (keep ~5 most recent; older ones live only in the dir)
```

## How to extend coverage.md

It is a markdown table. New rows go at the bottom unless you're reordering by
priority. Don't delete rows — if a doc is retired, mark its row with
`status: retired` and link to the replacement.

## Things you must not do

- Don't write into STATE.md decisions that aren't actually decided (don't
  speculate forward).
- Don't conflate sessions/ entries with knowledge/ docs. sessions/ records the
  *act of producing*; knowledge/ is the produced artifact.
- Don't try to compact session logs by deleting old ones — they are the
  audit trail.
