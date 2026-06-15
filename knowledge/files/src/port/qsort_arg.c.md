---
path: src/port/qsort_arg.c
anchor_sha: e18b0cb7344
loc: 14
depth: read
---

# src/port/qsort_arg.c

## Purpose

`qsort_arg()` — `qsort` variant that threads an opaque `void *arg`
through to the comparator. Used everywhere PG sorts data where the
comparator needs context (collation, sort-support state, tuple
descriptor, etc.) — most notably `tuplesort.c`. Like `pg_qsort`, the
body is generated from `lib/sort_template.h` rather than written out by
hand. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void qsort_arg(void *base, size_t nel, size_t elsize, qsort_arg_comparator cmp, void *arg)` | `qsort_arg.c:7` (via `ST_SORT qsort_arg`) | `arg` is passed unchanged to every comparator call |

## Internal landmarks

- Template knobs (`qsort_arg.c:7-13`):
  - `ST_SORT qsort_arg` — generated symbol name.
  - `ST_COMPARATOR_TYPE_NAME qsort_arg_comparator` — typedef for the
    `(const void *, const void *, void *)` comparator.
  - `ST_COMPARE_ARG_TYPE void` — the trailing arg's type.
  - `ST_COMPARE_RUNTIME_POINTER` — comparator is a runtime function
    pointer.

## Invariants & gotchas

- **Not the same shape as glibc `qsort_r`.** glibc's prototype is
  `qsort_r(base, nel, elsize, cmp, arg)` where the comparator is
  `int (*)(const void *, const void *, void *)` — same as PG. BSD's
  `qsort_r` puts the `arg` *before* the comparator, with a different
  comparator signature. Don't reach for libc's `qsort_r` as a drop-in;
  always use this PG version.
- The comparator's `arg` is **not** copied — it must remain valid for
  the duration of the sort, and callers must not rely on the
  comparator seeing any specific call order.
- Not stable, same as `pg_qsort`. Append a tiebreaker if you need
  stability.

## Cross-refs

- `knowledge/files/src/port/qsort.c.md` — context-free sibling.
- `source/src/backend/utils/sort/tuplesort.c` — primary consumer.
- `source/src/include/lib/sort_template.h` — underlying template.
