# `src/backend/utils/sort/qsort_interruptible.c`

- **File:** `source/src/backend/utils/sort/qsort_interruptible.c` (16 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

A single line of useful content: provide a `qsort_arg`-shaped sort
function that calls `CHECK_FOR_INTERRUPTS()` during partitioning, so
long-running sorts of bare `void *` arrays can be cancelled via SIGINT
without waiting for the qsort to finish.

## How it works

The whole file is configuration of `lib/sort_template.h`:

```c
#define ST_SORT qsort_interruptible
#define ST_ELEMENT_TYPE_VOID
#define ST_COMPARATOR_TYPE_NAME qsort_arg_comparator
#define ST_COMPARE_RUNTIME_POINTER
#define ST_COMPARE_ARG_TYPE void
#define ST_SCOPE
#define ST_DEFINE
#define ST_CHECK_FOR_INTERRUPTS
#include "lib/sort_template.h"
```

`sort_template.h` is a header that, when included with these `ST_*`
macros set, expands to a complete `qsort_interruptible(void *base,
size_t n, size_t elsize, qsort_arg_comparator cmp, void *arg)` function.
The `ST_CHECK_FOR_INTERRUPTS` switch inserts a `CHECK_FOR_INTERRUPTS()`
call inside the recursive partition step (and the iteration loops over
small partitions).

`ST_ELEMENT_TYPE_VOID` means the template operates on opaque byte ranges
(using `elsize`/`memcpy`/swap), as opposed to the typed-element variants
that `tuplesort.c` generates (`qsort_tuple` / `qsort_ssup`) where the
element type is `SortTuple`.

## Compare it to

- `tuplesort.c:489-508` — the **typed** variants for SortTuple.
- `qsort_arg` in `port/qsort_arg.c` — the libpgport non-interruptible
  baseline used outside the backend.
- `lib/sort_template.h` — the macro magic itself; same template
  generates `pg_qsort`, type-specialized sorts in nbtree/gist/etc., and
  the tuplesort variants.

## Callers

Used by code that needs an interruptible generic qsort on a backend-side
array of `void *` payloads. Greppable callers include array sort paths
and several catalog-related sorts. [unverified — not exhaustively
chased.]

## Confidence tag tally

- `[verified-by-code]` × 3
- `[from-comment]` × 1
- `[unverified]` × 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
