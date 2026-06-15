---
path: src/port/bsearch_arg.c
anchor_sha: e18b0cb7344
loc: 78
depth: read
---

# src/port/bsearch_arg.c

## Purpose

Binary-search variant that passes a user-supplied closure pointer (`arg`)
to the comparator. POSIX `bsearch(3)` doesn't take such a parameter, so any
state the comparator needs must come through globals — incompatible with
reentrant code, and clumsy in general. This file ports a classical
4.4BSD bsearch implementation, adding the `arg` parameter to the comparator
signature: `int (*compar)(const void *, const void *, void *)`. There is
no libc equivalent on any platform, so this is unconditionally compiled
into `libpgport`. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void *bsearch_arg(const void *key, const void *base0, size_t nmemb, size_t size, int (*compar)(const void *, const void *, void *), void *arg)` | `bsearch_arg.c:55` | Returns matching element or NULL |

## Internal landmarks

- Iterative halving (`:65-76`) — classic loop: `lim` starts at `nmemb`,
  halves each iteration. `p = base + (lim >> 1) * size` picks the midpoint.
  On `cmp > 0` (key > p) advance base past p and shrink lim by one before
  the implicit halving. On `cmp < 0` just halve. On equality return p.
- The "sneaky" logic from the comment block (`:41-53`) — handles odd vs
  even `lim` correctly without an extra branch. The pre-decrement of
  `lim--` on the move-right path is what makes odd-length sub-ranges shrink
  properly. `[from-comment]`

## Invariants & gotchas

- **Array must be sorted by the same comparator** — same precondition as
  libc bsearch. Behavior on unsorted input is undefined.
- **Comparator must use the same semantics as qsort: negative / zero /
  positive return.** No tri-state struct or anything fancy.
- **`arg` is opaque to bsearch_arg itself** — just passed through to
  every comparator invocation. Comparator may modify it (though that's
  unusual), and may store keys derived from it.
- **No libc equivalent.** glibc has `qsort_r` and `bsearch` but no
  `bsearch_r`/`bsearch_arg`. C11 Annex K's `bsearch_s` adds error checks
  but no closure arg. So this file is the only way to get reentrant
  bsearch in C. Don't try to remove it on the theory that "libc must
  have this by now". `[verified-by-code]`
- Returns `void *` (not `const void *`) for caller convenience even though
  `base0` is `const`. Match POSIX bsearch's same cast-away convention.

## Cross-refs

- `source/src/backend/utils/adt/jsonb_util.c`, `formatting.c` and others —
  callers that want closure-based comparison.
- `source/src/include/port.h` — prototype.
- `source/src/port/qsort_arg.c` — analogous qsort variant (not in this
  file batch).
