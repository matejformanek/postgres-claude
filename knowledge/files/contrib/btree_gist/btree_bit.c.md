# btree_bit.c

## One-line summary

GiST opclass for `bit` and `varbit`. Variable-length framework with
`tinfo.trnc = true`. Uses a custom `f_l2n` leaf-to-node transform
(`gbt_bit_xfrm`) to pad bit strings to byte boundaries before comparison.

## Public API

Standard 7 + 2 sortsupports: `gbt_bit_{compress,union,picksplit,consistent,
penalty,same,sortsupport}` plus `gbt_varbit_sortsupport`
`source/contrib/btree_gist/btree_bit.c:14-21`.

## Key invariants

- **Truncation enabled** (`tinfo.trnc = true` at `:113`).
- Comparators delegate to bit-type SQL operators `bitgt/ge/eq/le/lt`, and
  `f_cmp` delegates to `byteacmp` (not `bitcmp` — bit comparison is
  bytewise after `f_l2n`-style padding).
- **`f_l2n = gbt_bit_l2n`** `:94-107`: when a leaf entry is promoted to a
  node, the varbit is unpacked into a byte-padded bytea via `gbt_bit_xfrm`
  (`:75-89`). The trailing partial byte is zero-padded.
- The same xfrm is applied to query values inside `gbt_bit_consistent` when
  the entry is non-leaf `:158`.

## Trust boundary / Phase D surface

- **Bit-string truncation correctness:** `gbt_bit_xfrm` produces a
  byte-aligned representation that compares correctly via `byteacmp`. Then
  truncation via `gbt_var_node_truncate` works at byte boundaries. As long
  as both sides are xfrm'd, ordering is preserved. The risk is
  **mixed-width** queries: a 3-bit and a 7-bit value xfrm to single bytes
  with different padding; the trailing zero pad makes the shorter value
  compare as less-or-equal to its longer counterpart with the same prefix,
  which is the SQL semantics. Sound.
- **EXCLUDE on bit:** `gbt_biteq` uses `biteq` (proper bit-equality
  including length). Sound.
- **`tinfo.trnc = true` + xfrm:** combination of truncation (after the
  leaf has been promoted to node form) and the xfrm padding means
  internal-node bounds may have trailing zeros — those compare correctly
  via memcmp. No info leak: the padding bytes are explicitly zeroed in
  `gbt_bit_xfrm:84-85`.

## Issues spotted

- [ISSUE-COMPLEXITY: The `f_l2n` indirection + truncation + per-strategy
  query xfrm in `gbt_bit_consistent` is the most intricate flow in
  btree_gist. A future contributor who forgets to xfrm the query for
  non-leaf entries (line 158) would produce silently wrong results. (MED
  — design footgun, current code is correct)]
