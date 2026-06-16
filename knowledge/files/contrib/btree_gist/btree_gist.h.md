# `contrib/btree_gist/btree_gist.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 41
- **Source:** `source/contrib/btree_gist/btree_gist.h`

The module-wide top-level header for `contrib/btree_gist`. Tiny:
just declares one strategy-number constant and one type-tag enum
covering all 23 indexed types (used by `gbtree_ninfo.t` and
`gbtree_vinfo.t` to distinguish data-type behaviour at runtime in
shared `gbt_num_*` / `gbt_var_*` helpers). [verified-by-code]

## API / entry points

- `BtreeGistNotEqualStrategyNumber = 6` `:10` — extension strategy
  added by btree_gist on top of the core GiST strategies (1-5 are
  defined in `access/gist.h`). Used for "indexed-column <> value"
  predicates. [verified-by-code]
- `enum gbtree_type` `:14-39` — 23 type tags:
  - Variable-length: `gbt_t_var` (umbrella), `gbt_t_text`,
    `gbt_t_bpchar`, `gbt_t_bytea`, `gbt_t_bit`, `gbt_t_inet`.
  - Numeric-fixed: `gbt_t_int2`, `gbt_t_int4`, `gbt_t_int8`,
    `gbt_t_float4`, `gbt_t_float8`, `gbt_t_numeric`, `gbt_t_oid`,
    `gbt_t_cash`, `gbt_t_bool`, `gbt_t_macad`, `gbt_t_macad8`,
    `gbt_t_uuid`, `gbt_t_enum`.
  - Date/time: `gbt_t_ts`, `gbt_t_time`, `gbt_t_date`,
    `gbt_t_intv`.
  [verified-by-code]

## Notable invariants / details

- The strategy-number constant `6` follows GiST's reserved-strategy
  convention. Core GiST's `RTBelowStrategyNumber` etc. take 1-5.
  Extensions can claim 6+ — btree_gist took 6 for `<>`. [inferred]
- The enum is the discriminator field stored in
  `gbtree_ninfo` (numeric) and `gbtree_vinfo` (variable) info
  structs declared in the sibling utility headers.
  [verified-by-code via `btree_utils_num.h:38` and
  `btree_utils_var.h:28`]
- The header includes `access/nbtree.h` (for strategy numbers and
  comparison support) and `fmgr.h` (for `FmgrInfo`). [verified-by-code]
- No function prototypes here — those live in `btree_utils_num.h` and
  `btree_utils_var.h`. Per-type `gbt_t_*_*` prototypes live in the
  individual `btree_TYPE.c` files (mostly static).
  [verified-by-code]

## Potential issues

- `:14-39` Enum values are sequential and order-dependent: any
  insertion-not-at-end could shift values and break a hypothetical
  switch-on-int (though all current consumers switch on the symbol
  directly). [verified-by-code]
- The `gbt_t_var` umbrella value `:16` overlaps semantically with
  the more specific `gbt_t_text` / `gbt_t_bpchar` / etc. — it's
  used as a generic "variable" placeholder in some contexts. Not
  obvious from this header alone. [from-comment elsewhere]
  **[ISSUE-undocumented-invariant: gbt_t_var role vs specific
  var-types not documented in this header (nit)]**

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `btree_gist`](../../../issues/btree_gist.md)
<!-- issues:auto:end -->
