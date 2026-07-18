# btree_bytea.c

## One-line summary

GiST opclass for `bytea` — variable-length, `tinfo.trnc = true` so internal-
node keys are truncated to common-prefix + 1 byte. Uses raw memcmp via
`byteacmp` (no collation).

## Public API

Standard 7-function GiST set: `gbt_bytea_{compress,union,picksplit,
consistent,penalty,same,sortsupport}`
`source/contrib/btree_gist/btree_bytea.c:12-18`. No `gbt_bytea_fetch` —
index-only scan returns truncated keys, so IOS is implicitly disabled by the
opclass not advertising fetch support.

## Key invariants

- **Truncation enabled** `tinfo.trnc = true` at
  `source/contrib/btree_gist/btree_bytea.c:75`. Internal-node `lower`/`upper`
  bounds are cut to `common-prefix + 1 byte` after each union/picksplit.
- **No collation** — all six comparators call `DirectFunctionCall2` (not
  `Coll`) `source/contrib/btree_gist/btree_bytea.c:26`. Bytea is binary; raw
  memcmp ordering is correct and stable.
- **Leaf entries are full-width**; only node keys are truncated. Range query
  matching against truncated nodes uses `gbt_var_node_pf_match` (prefix match)
  inside `gbt_var_consistent`.
- **`*recheck = false`** in `gbt_bytea_consistent`
  `source/contrib/btree_gist/btree_bytea.c:113`. Correctness relies on:
  - Truncation preserves memcmp ordering (true: truncating both sides at
    the same length preserves byte-lexicographic order).
  - Prefix-match logic in `gbt_var_consistent` covers all
    inequality/range strategies on truncated nodes.

## Trust boundary / Phase D surface

- **Corrupt bytea in compress:** `gbt_var_compress` calls `PG_DETOAST_DATUM`
  on the incoming `entry->key`. If the bytea's TOAST pointer is corrupt or
  truncated, `detoast_attr` raises `ERRCODE_DATA_CORRUPTED`. No untrusted-
  input crash path here — bytea data is always varlena-validated by the
  TOAST layer before reaching us.
- **EXCLUDE constraint on bytea:** `gbt_bytea_same`'s equality goes through
  `byteacmp` which is exact byte-level equality. EXCLUDE `WITH =` is sound.
- **Truncation + EXCLUDE `<>`:** the not-equal strategy at internal nodes uses
  `gbt_var_consistent`'s last branch
  `source/contrib/btree_gist/btree_utils_var.c:613-616`:
  `!(eq(query, lower) && eq(query, upper))`. On a truncated node, `lower` and
  `upper` are prefixes — `byteaeq(query, "prefix")` is false for any query
  longer than the prefix, so `<>` is true → recurse into subtree. Sound but
  inefficient: many subtree descents won't actually contain a `<>` match.
- **`gbt_bytea_penalty` on truncated keys** treats the byte distance with
  beyond-length positions as 0 (from `gbt_var_penalty`). For bytea this
  means short keys get artificially low penalty, biasing splits toward
  short-key clusters. Operational, not correctness.
- **No IOS fetch:** if anyone added a `gbt_bytea_fetch` later, they'd need
  to disable it for non-leaf entries (truncated) or risk returning prefixes
  as if they were full values — a data-corruption-class bug for queries that
  trust IOS results.

## Cross-references

- `source/src/backend/utils/adt/varlena.c` — `byteacmp`, `byteaeq/gt/ge/le/lt`.
- `knowledge/files/contrib/btree_gist/btree_utils_var.c.md`.

## Issues spotted

- [ISSUE-CONSISTENCY: `gbt_bytea_consistent` line 102 casts the query to
  `void *` via `DatumGetByteaP` which may detoast. The detoasted copy is
  never freed; consistent with peers, but combined with `*recheck = false`
  on truncated nodes the function relies entirely on `gbt_var_consistent`'s
  prefix-match correctness. If `gbt_bytea_pf_match` (a static helper in
  `btree_utils_var.c`) ever returned a wrong answer for a query of size 0,
  EXCLUDE constraints could miss conflicts. Empty-bytea probes are an edge
  case to test. (LOW — defensive)]
- [ISSUE-PERF: For bytea columns with high-entropy data (e.g. SHA hashes),
  the truncated common-prefix is 1-2 bytes and `+1 byte` after the prefix is
  effectively random — internal-node ranges overlap heavily and the GiST
  index degenerates. nbtree handles this much better via its sophisticated
  split logic. Operational, not bug. (LOW)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
