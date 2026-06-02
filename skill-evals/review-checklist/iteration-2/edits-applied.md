# Edits applied for iteration-2

Applied to `.claude/skills/review-checklist/SKILL.md`. Each edit
matches a proposal from `iteration-1/proposed-edits.md` and is
verified consistent with `knowledge/community/review-patterns.md`
and the wiki sources cited there.

## Edit 1 — Companion skills cross-reference (NEW section)

Inserted between the intro paragraph and Phase 1. Lists nine sibling
skills with one-line "use when" pointers. Verified each named skill
exists in `.claude/skills/` via the available-skills listing in this
session.

## Edit 2 — O(N²)-at-scale reminder in Phase 4

Added bullet between the existing O(N²) bullet and the Memory bullet:
"Hot-loop micro-optimization? Re-run at significantly larger N than
the author's benchmark — a faster constant factor that conceals a
quadratic term is a footgun."

## Edit 3 — Hint-bit reminder + wal-and-xlog handoff in Phase 6

Extended the Storage/WAL bullet with "Deep checklist: hand off to the
`wal-and-xlog` skill." Added a fresh bullet on
`MarkBufferDirtyHint` vs `MarkBufferDirty` correctness in redo.

## Edit 4 — Inline/macros ABI in Phase 6

Extended the existing back-branch ABI bullet to call out that inline
functions and macros in `src/include/` share the ABI surface.

## Edit 5 — Performance numbers as a table in "Posting the review"

Added a bullet under the CF-flip block: small table of master tps,
patched tps, run count, hardware, build flags, exact repro recipe;
numerical claims without a recipe get bounced.

## Non-applied (intentionally skipped from proposal)

- Proposal "Edit 3" (revert-just-the-code sanity test) was already
  present in Phase 3 — no change needed.
- No restructuring of phases — eval showed structure was the key win
  on E1; preserved as-is.
