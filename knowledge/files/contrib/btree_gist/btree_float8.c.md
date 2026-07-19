# btree_float8.c

## One-line summary

GiST opclass for `double precision` (float8). 16-byte key
`[lower:float8|upper:float8]`. Structurally identical to `btree_float4.c` —
same NaN-handling caveats apply, plus `inet` reuses the float8 framework via
`gbtree_ninfo`.

## Public API

Standard 8 GiST + sortsupport + KNN distance:
`gbt_float8_{compress,fetch,union,picksplit,consistent,distance,penalty,
same,sortsupport}` `source/contrib/btree_gist/btree_float8.c:19-27`. Plus
exported `float8_dist` at `:102`.

## Key invariants

- **Key:** `typedef struct { float8 lower, upper; } float8KEY` — 16 bytes
  (`gbtreekey16`).
- **Comparators are raw C `>` `==` etc.** — IEEE 754 semantics, NaN unordered
  `source/contrib/btree_gist/btree_float8.c:30-54`.
- **`gbt_float8key_cmp` does not handle NaN specially**
  `source/contrib/btree_gist/btree_float8.c:56-71`.
- **Sortsupport uses `float8_cmp_internal`** (the NaN-aware comparator from
  `utils/float.c`) — same inconsistency with the index-time comparator as
  in float4 `source/contrib/btree_gist/btree_float8.c:228`.

## Trust boundary / Phase D surface

Same as `btree_float4.c.md`:

- NaN insert may not update internal-node bounds (both `>` and `<` return
  false for NaN).
- EXCLUDE `WITH =` permits duplicate NaNs because `NaN == NaN` is false.
- `penalty_num` on NaN returns 0, biasing all NaN inserts into one subtree.
- Picksplit sort `gbt_float8key_cmp` orders NaN inconsistently vs the
  sortsupport `float8_cmp_internal`.
- KNN `float8_dist` checks subtraction overflow at `:111`.

## Cross-references

- `source/src/backend/utils/adt/float.c` — `float8_cmp_internal`.
- `knowledge/files/contrib/btree_gist/btree_float4.c.md` — same issues at
  smaller precision.

## Issues spotted

- [ISSUE-CORRECTNESS-NAN: Same as btree_float4.c — IEEE comparators diverge
  from the nbtree opclass for NaN. EXCLUDE constraints permit duplicate NaNs.
  (HIGH)]
- [ISSUE-CONSISTENCY: `gbt_float8key_cmp` vs `gbt_float8_ssup_cmp` use
  different comparator semantics for NaN. (MED)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
