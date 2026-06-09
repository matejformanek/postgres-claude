# btree_float4.c

## One-line summary

GiST opclass for `real` (float4). 8-byte key `[lower:float4|upper:float4]`,
fixed-size framework. Comparators use raw C operators `>` `==` etc.;
IEEE 754 semantics directly leak through, including NaN unordered-ness.

## Public API

Standard 8 GiST + sortsupport + KNN distance:
`gbt_float4_{compress,fetch,union,picksplit,consistent,distance,penalty,
same,sortsupport}` `source/contrib/btree_gist/btree_float4.c:19-27`. Plus
`float4_dist` (`a - b` with overflow check) for KNN
`source/contrib/btree_gist/btree_float4.c:94`.

## Key invariants

- **Key:** `typedef struct { float4 lower, upper; } float4KEY` — 8 bytes
  (`gbtreekey8`).
- **Comparators are raw C `<`/`>`/`==`** — IEEE 754: NaN is unordered
  (`NaN < x`, `NaN > x`, `NaN == x` all false; `NaN <= x` also false).
  `source/contrib/btree_gist/btree_float4.c:29-53`.
- **Key compare for sort** uses `(ia->lower > ib->lower) ? 1 : -1` (and same
  for upper) — note the lack of an `==` fallback in the lower path; it relies
  on the earlier `if (ia->lower == ib->lower)` to catch it. Since NaN
  comparisons fail this check, NaN entries fall to the "lower > ..." branch
  → all NaN keys get sort key `-1` (since `NaN > X` is false). This means a
  vector of NaN keys is "sorted" consistently but at the bottom.
  `source/contrib/btree_gist/btree_float4.c:55-70`.
- **KNN dist** uses `fabsf(a - b)` with overflow check
  `source/contrib/btree_gist/btree_float4.c:95-107`.

## Notable internals

The `float4_dist` exported function (used by KNN-Gist's `<->` operator)
checks for inf produced from finite operands via `isinf(r) && !isinf(a) &&
!isinf(b)` — that pattern catches subtraction overflow without flagging
genuine infinity in the inputs.

## Trust boundary / Phase D surface

- **NaN handling — known corner case:**
  - Insert `NaN` into a `float4` GiST index: `gbt_float4_compress` copies
    the NaN bits verbatim into `[NaN, NaN]`. Subsequent `union` calls
    propagate NaN: `f_gt(o.lower, NaN, ...)` → false because `NaN > X` is
    false, so the existing lower bound is not overwritten by NaN. But
    `f_lt(o.upper, NaN, ...)` is also false, so the upper bound is never
    widened either. **Result: a NaN insert may not update the union** —
    the internal-node range stays as-is, and the NaN leaf is reachable only
    by full-table scan via GiST's per-page scan. Queries for `WHERE x = 'NaN'`
    on the index could miss the NaN row.
  - **Compare with PG's built-in float btree opclass:** in
    `source/src/backend/utils/adt/float.c` `float4_cmp_internal` explicitly
    handles NaN by ordering it greater than everything (so NaNs sort last,
    are findable, and EXCLUDE works). `btree_gist`'s `float4` opclass does
    NOT follow this convention in its raw-C comparators — only the
    sortsupport path at `:220` uses `float4_cmp_internal`. This is a
    correctness divergence.
  - See ISSUE-CORRECTNESS-NAN below.
- **Penalty with NaN:** `penalty_num` macro on NaN entries: `NaN > X` and
  `X > NaN` are both false, so `tmp` stays 0 and penalty is 0 — meaning
  inserting a NaN always picks the first scanned subtree, biasing all NaN
  inserts into one page.
- **EXCLUDE constraint on float4:** `EXCLUDE (val WITH =)` with NaN inserts
  may permit duplicate NaNs: `gbt_float4eq(NaN, NaN)` is `NaN == NaN` →
  false, so two `NaN` rows both pass the EXCLUDE check. **This is
  potentially a CORRECTNESS bug** depending on whether the user expects
  IEEE semantics or SQL semantics. (SQL `numeric` says `NaN = NaN` is true,
  IEEE says false; PG follows IEEE for float4/float8 at the SQL level too,
  so this might be intentional. But it definitely diverges from the nbtree
  opclass which deduplicates NaN.) Worth a Phase D test.
- **No bytes-out-of-bound risk:** float4 is a fixed-width by-value type;
  `DatumGetFloat4` is a bit-cast. No detoast surface.

## Cross-references

- `source/src/backend/utils/adt/float.c` — `float4_cmp_internal` (the NaN-
  aware comparator that the built-in nbtree opclass uses).
- `source/src/include/utils/float.h` — `float_overflow_error`.
- `knowledge/files/contrib/btree_gist/btree_utils_num.c.md`.

## Issues spotted

- [ISSUE-CORRECTNESS-NAN: `gbt_float4gt/ge/eq/le/lt` use raw IEEE comparisons
  (NaN is unordered), but the nbtree opclass that EXCLUDE-translation expects
  to mirror (`btfloat4cmp`) orders NaN as greater than all finite values.
  Consequence: `EXCLUDE USING gist (val WITH =)` permits multiple NaN rows
  (because `NaN == NaN` is false in IEEE), whereas the equivalent btree
  constraint would reject. Also: range queries `WHERE val > 1` may miss NaN
  rows that ARE matches in the nbtree semantics (where NaN > finite). This
  is a long-standing divergence; the sortsupport path at `:220` correctly
  uses `float4_cmp_internal` so post-IOS sorts are NaN-correct, but the GiST
  index structure itself is not. (HIGH — divergent semantics between gist
  and btree opclass for the same SQL type)]
- [ISSUE-PERF-NAN: `penalty_num` on a NaN insert returns 0, so all NaN
  inserts cluster into whichever subtree GiST happens to evaluate first.
  Pathological page splits in NaN-heavy workloads. (LOW)]
- [ISSUE-CONSISTENCY: `gbt_float4key_cmp` at `:55-70` does not use
  `float4_cmp_internal` even though `gbt_float4_ssup_cmp` does. The picksplit
  sort thus orders NaN entries inconsistently with sortsupport. (MED —
  could produce non-deterministic split decisions for NaN-bearing pages)]
