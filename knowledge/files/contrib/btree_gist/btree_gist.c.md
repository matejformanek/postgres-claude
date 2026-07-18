# btree_gist.c (+ btree_gist.h)

## One-line summary

Entry point + tiny shared scaffolding for `btree_gist`: module-magic, a no-op
GiST decompress, a placeholder in/out pair for the opaque `gbtreekey*`
storage types, and a `cmptype → BT*StrategyNumber` translator used by GiST's
ordered-operator infrastructure.

## Public API

- `gbt_decompress` — universal pass-through GiST decompress (returns the entry
  unchanged) `source/contrib/btree_gist/btree_gist.c:55`.
- `gbtreekey_in` / `gbtreekey_out` — always raise `ERRCODE_FEATURE_NOT_SUPPORTED`;
  the index storage types (`gbtreekey2`, …, `gbtreekey_var`) are never meant to be
  read or written from SQL `source/contrib/btree_gist/btree_gist.c:25`,
  `source/contrib/btree_gist/btree_gist.c:39`.
- `gist_translate_cmptype_btree` — GiST opclass-level translator that maps
  `CompareType` constants (`COMPARE_EQ`, `COMPARE_LT`, …) to upstream nbtree
  strategy numbers `source/contrib/btree_gist/btree_gist.c:64`. Returns
  `InvalidStrategy` for unknown compare types — this is how GiST signals to a
  caller that the opclass has no operator with the requested semantics.
- `enum gbtree_type` (in the header) — single source of truth for every
  per-type opclass: a tag (`gbt_t_int4`, `gbt_t_text`, `gbt_t_uuid`, …) that
  flows into both `gbtree_ninfo` and `gbtree_vinfo` `t` fields and selects the
  per-type switch arm inside `gbt_num_compress` / `gbt_num_fetch`
  `source/contrib/btree_gist/btree_gist.h:14`.
- `BtreeGistNotEqualStrategyNumber 6` — extension-specific strategy number for
  `<>`, added on top of the 5 standard btree strategies
  `source/contrib/btree_gist/btree_gist.h:10`.

## Key invariants

- Every per-type opclass conforms to one of two shapes: fixed-size keys go
  through `btree_utils_num.c` and use a `[lower|upper]` packed struct, while
  variable-length keys go through `btree_utils_var.c` and use a
  `bytea`-prefixed `[lower-varlena | upper-varlena]` layout.
- The "storage" types `gbtreekey2/4/8/16/32/var` are deliberately opaque from
  SQL — the `gbtreekey_in`/`gbtreekey_out` stubs guarantee that even if a user
  manages to inject a literal of one of these types, parsing fails closed.
- `gbt_decompress` is shared by *every* fixed-size per-type opclass — the
  compressed leaf representation `[v,v]` is already in its on-page form, so
  GiST's decompress is a no-op. Variable-length types use a separate
  `gbt_var_decompress` declared in `btree_utils_var.c`.
- `gist_translate_cmptype_btree` is the GiST-side hook that lets EXCLUDE
  constraints look up operators by `CompareType`; the not-equal extension
  strategy is intentionally not exposed here because it has no `CompareType`
  enumerator.

## Trust boundary / Phase D surface

- **`gbtreekey_in/out` stubs** — these raise `ERRCODE_FEATURE_NOT_SUPPORTED`
  rather than a default `cannot accept` from the typsystem. The error in
  `gbtreekey_out` shows the literal string `"gbtreekey?"` instead of the type
  name `source/contrib/btree_gist/btree_gist.c:43`. That's intentional (the
  function doesn't get the typioparam back on the out side) but it's a small
  loss of diagnostic information — see Issue.
- **No NULL handling here** — NULL handling is delegated entirely to the GiST
  core machinery (which short-circuits NULL keys before calling any of the
  per-opclass functions). Any per-type penalty/consistent function that
  receives a NULL via mis-wiring would crash in the deref; the contract is that
  GiST core never lets that happen.
- **Strategy translation fallback** — `gist_translate_cmptype_btree` returns
  `InvalidStrategy` for unsupported types. The caller MUST treat
  `InvalidStrategy` as "no support" rather than "use a default"; treating it as
  a strategy number would index off the start of the strategy table.

## Cross-references

- `source/src/backend/access/gist/gist.c` — the GiST AM that dispatches into
  every `gbt_*_consistent`, `gbt_*_union`, etc.
- `source/src/include/access/stratnum.h` — defines `BTLessStrategyNumber` etc.
  used by `gist_translate_cmptype_btree`.
- `source/src/include/access/cmptype.h` — defines `CompareType`.
- `knowledge/files/contrib/btree_gist/btree_utils_num.c.md`
- `knowledge/files/contrib/btree_gist/btree_utils_var.c.md`

## Issues spotted

- [ISSUE-DIAGNOSTIC: `gbtreekey_out` reports the literal type name
  `"gbtreekey?"` instead of looking up the actual type from any context (LOW).
  Cosmetic only — these errors are unreachable in normal use since the storage
  types are never returned to SQL.]
- [ISSUE-DOC: `gbt_decompress` has no comment explaining that the apparent
  no-op is the correct behavior for compressed leaf format `[v,v]`; a
  reader who doesn't read both `btree_utils_num.c` and the gist.c contract may
  worry they need to do something here. (LOW)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
