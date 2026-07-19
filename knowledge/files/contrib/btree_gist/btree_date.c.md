# btree_date.c

## One-line summary

GiST opclass for `date` (DateADT = int32 day count). 8-byte key
`[DateADT|DateADT]`. Has its own `gbt_date_penalty` using `date_mi` rather
than the generic `penalty_num` macro.

## Public API

Standard 8 + sortsupport + KNN:
`gbt_date_{compress,fetch,union,picksplit,consistent,distance,penalty,same,
sortsupport}` `source/contrib/btree_gist/btree_date.c:20-28`. Plus
`date_dist`.

## Key invariants

- Key: `[lower:DateADT|upper:DateADT]`, size 8 (`gbtreekey8`)
  `source/contrib/btree_gist/btree_date.c:103-115`.
- Comparators via `DirectFunctionCall2(date_gt, ...)` etc. → proper
  infinity-aware date comparison.
- KNN dist uses `date_mi` (subtraction) and `abs()` `:91-100`.

## Notable internals

Custom penalty `:204-237`: computes growth via `date_mi`, scaled by
old-range size. Like `penalty_num` but written explicitly because `date_mi`
returns int32 and the macro expects scalar arithmetic.

## Trust boundary / Phase D surface

- **Date infinity:** `DateADT` has reserved values for `-infinity` and
  `+infinity`. `date_cmp`/`date_mi` handle these. `gbt_date_penalty` calls
  `date_mi` on bounds; if both bounds are `+infinity`, `date_mi` returns 0
  → penalty 0. If one is finite and one is infinity, `date_mi` may overflow
  or return a sentinel — the code doesn't check.
  See ISSUE.
- EXCLUDE on date: sound via `date_eq`.

## Issues spotted

- [ISSUE-INFINITY: `gbt_date_penalty` doesn't explicitly handle date
  infinity. `date_mi(infinity, finite)` overflow behaviour is whatever
  `date_mi` does (returns `INT32_MIN`/`MAX` in PG's date.c). Penalty
  arithmetic on that gets clamped via `Max(diff, 0)` which masks the
  overflow rather than detecting it. Practically: infinite dates cluster
  into pages with their finite neighbours, slightly suboptimally. (LOW)]
- [ISSUE-PERF: `date_dist` SQL function at `:120` comment "we assume the
  difference can't overflow" — int32 day distance can't overflow because
  DateADT is itself int32 (max diff ~4 billion days), but `abs(INT_MIN)`
  is UB. If `date_mi` ever returns `INT_MIN`, the `abs()` is undefined.
  (LOW)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
