# `src/include/lib/integerset.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 24

## Role

Compact in-memory set of uint64 values. Originally introduced for
the vacuum dead-tid list before being **superseded by `tidstore`
backed by `radixtree.h`** in PG17. Still in tree but new vacuum
code path uses radixtree. [verified-by-code] `git log --oneline
src/backend/lib/integerset.c` shows shrinking caller set.

## Public API (header is just 24 lines)

- `intset_create(void)` → `IntegerSet *`
- `intset_add_member`, `intset_is_member`
- `intset_num_entries`, `intset_memory_usage`
- `intset_begin_iterate`, `intset_iterate_next`

## Invariants

- Iteration delivers values in sorted order. [from-comment]
- Insert must precede iteration (no random-add during walk).

## Trust boundary (Phase D)

None.

## Cross-refs

- `knowledge/files/src/include/lib/radixtree.h.md` — the
  modern replacement
- `knowledge/files/src/backend/access/common/tidstore.c.md` (if
  exists) — PG17 successor

## Issues

- ISSUE-DESIGN: `integerset` is approaching deletion-candidate
  status; new code should use radixtree/tidstore. No active
  cleanup PR last verified. (Low — tech debt.)
