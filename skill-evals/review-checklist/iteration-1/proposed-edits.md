# Proposed edits to SKILL.md after iteration-1

Score: with_skill 23/23 vs baseline 12/23 (+11). Skill is doing its job;
edits below are sharpening, not rewriting.

## Edit 1 — Cross-reference sibling skills (biggest gap)

The skill currently lives in isolation. A reviewer hitting WAL,
locking, error-message style, memory contexts, or test placement should
be pointed at the specialist skill instead of re-deriving it from the
seven-phase summary.

Add a `## Companion skills` section near the top (after the intro,
before Phase 1) that lists, with one-line "use when" pointers:

- `wal-and-xlog` — when the patch touches WAL records, redo functions, or RM registration
- `locking` — when reviewing lock acquisition order / deadlock risk
- `error-handling` — when judging ereport/elog/SQLSTATE choices
- `memory-contexts` — when judging palloc placement / context lifetime
- `coding-style` — for pgindent-survival / include order / C99 subset
- `catalog-conventions` — for pg_proc / catalog column / OID work
- `testing` — for picking regress vs isolation vs TAP vs module
- `commit-message-style` — when judging the committer-readiness of the message
- `patch-submission` — when the review is pre-submission of our own change

## Edit 2 — Add ABI-in-headers reminder in Phase 6

Phase 6 covers ABI for back-branches but only for exported function
signatures. Add an explicit bullet for headers in src/include/:

> Inline functions, macros, and struct layouts added in `src/include/`
> become part of the extension-visible ABI. For back-branch patches:
> new struct members at the end only, no signature changes to inline
> helpers that extensions might already pin against.

## Edit 3 — Add "revert just the code" sanity-test bullet in Phase 3

The skill mentions this once; make it more prominent because it
catches the common failure mode of "test passes because it's a
tautology, not because the code is right":

Already present — leave as-is. (No edit needed.)

## Edit 4 — Add the O(N²)-at-scale reminder in Phase 4

Current Phase 4 mentions O(N²) but doesn't flag the specific pattern
of "hot-loop micro-optimization that hides quadratic growth at larger
N." Add a bullet:

> If the patch is a hot-loop micro-optimization, test at significantly
> larger N than the author's benchmark. A faster constant factor that
> conceals a quadratic term is a footgun.

## Edit 5 — Tighten Phase 7 with explicit "post numbers as a table"

For performance reviews specifically, the wiki and -hackers convention
is to post a small table of master-vs-patched tps with hardware and
flags. Add to Phase 7 (or to "Posting the review"):

> For performance reviews, include a small table: master tps, patched
> tps, run count, hardware, build flags, exact repro recipe. Numerical
> claims without a recipe get bounced.

## Edit 6 — Add hint-bit / MarkBufferDirtyHint reminder in Phase 6

Already implied under "Storage / WAL: backwards-compatibility" but
worth surfacing as its own bullet — it's a recurring storage-review
flag:

> Hint-bit handling in redo: `MarkBufferDirtyHint` vs
> `MarkBufferDirty` — using the wrong one corrupts recovery.

## Non-edits (considered, rejected)

- Adding a Phase 0 "scope check" — overkill, the description already
  scopes the skill.
- Expanding the message-style guide inline — that's what
  `error-handling` and `coding-style` exist for; better to cross-link
  (Edit 1) than to duplicate.
- Adding a logical-decoding bullet under Phase 6 — already covered by
  "interact with other features sensibly" in Phase 2; making it
  WAL-specific risks duplicating wal-and-xlog.
