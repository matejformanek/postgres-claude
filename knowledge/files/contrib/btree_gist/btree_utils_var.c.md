# btree_utils_var.c (+ btree_utils_var.h)

## One-line summary

Shared framework for **variable-length** `btree_gist` opclasses (text, bytea,
bit, numeric). Provides a `bytea`-prefixed `[lower-varlena | upper-varlena]`
key layout with optional truncation of internal-node keys to "common prefix +
1 byte", plus collation-aware compress/union/penalty/consistent/picksplit/same.

## Public API

- Header types/macros (`btree_utils_var.h`):
  - `typedef bytea GBT_VARKEY` — opaque varlena holding the packed
    `[lower|upper]` `source/contrib/btree_gist/btree_utils_var.h:11`.
  - `GBT_VARKEY_R { bytea *lower, *upper; }` — readable view; on a leaf,
    `lower == upper` (literally same pointer) `source/contrib/btree_gist/btree_utils_var.h:14`.
  - `gbtree_vinfo` — per-type vtable: type tag `t`, cached
    `pg_database_encoding_max_length` `eml`, **`bool trnc` truncate-flag**,
    5 boolean comparators + `f_cmp` + optional `f_l2n` leaf-to-node hook
    (used by `btree_bit.c` to apply right-padding before comparing)
    `source/contrib/btree_gist/btree_utils_var.h:23`.
  - `GBT_FREE_IF_COPY(ptr1, ptr2)` — variant of `PG_FREE_IF_COPY` that takes a
    Datum rather than `fcinfo` `source/contrib/btree_gist/btree_utils_var.h:50`.

- Exported functions:
  - `gbt_var_decompress(fcinfo)` — `PG_DETOAST_DATUM` then return a new
    GISTENTRY pointing at the de-toasted bytes
    `source/contrib/btree_gist/btree_utils_var.c:35`.
  - `gbt_var_key_readable(k)` — split a packed key into `lower`/`upper`
    pointers; `INTALIGN`s the boundary
    `source/contrib/btree_gist/btree_utils_var.c:55`.
  - `gbt_var_key_copy(u)` — pack a `GBT_VARKEY_R` back into a single varlena
    `source/contrib/btree_gist/btree_utils_var.c:88`.
  - `gbt_var_compress(entry, tinfo)` — wrap a leaf Datum into a 1-element
    `[v]` key (lower==upper, stored as a single varlena prefix)
    `source/contrib/btree_gist/btree_utils_var.c:290`.
  - `gbt_var_fetch(fcinfo)` — extract the lower bound as a Datum for IOS
    `source/contrib/btree_gist/btree_utils_var.c:315`.
  - `gbt_var_union`, `gbt_var_same`, `gbt_var_penalty`,
    `gbt_var_consistent`, `gbt_var_picksplit`, `gbt_var_bin_union`.

## Key invariants

- **Leaf key layout:** a single varlena containing one `bytea` ("lower" only;
  `gbt_var_key_readable` sets `upper = lower` when the outer varlena's size
  matches `VARHDRSZ + VARSIZE(lower)`)
  `source/contrib/btree_gist/btree_utils_var.c:60`.
- **Node key layout:** outer varlena containing `[lower-bytea | INTALIGN
  padding | upper-bytea]`. Total size: `VARHDRSZ + INTALIGN(VARSIZE(lower)) +
  VARSIZE(upper)` `source/contrib/btree_gist/btree_utils_var.c:91`.
- **Truncation discipline (`tinfo->trnc`):** if set, `gbt_var_union` and
  `gbt_var_picksplit` cut both `lower` and `upper` down to `common_prefix +
  1 byte` after computing the union
  `source/contrib/btree_gist/btree_utils_var.c:354`,
  `source/contrib/btree_gist/btree_utils_var.c:539`.
- **Truncation enabled for:** `bytea` (`tinfo.trnc = true`,
  `btree_bytea.c:75`), `bit/varbit` (`btree_bit.c:113`). **Disabled for:**
  `text`/`bpchar` (`btree_text.c:85` and `:155`), `numeric` (`btree_numeric.c:80`).
- **Consistent on truncated nodes uses `gbt_var_node_pf_match`** — a query
  matches a node if either bound is a prefix of the query
  `source/contrib/btree_gist/btree_utils_var.c:200`. This is what makes range
  queries against truncated indexes work.
- **All `consistent` callers set `*recheck = false`** — text/bytea/bit/numeric
  all claim exact matches. Combined with truncation, this is correct because
  the **leaf** entries are stored full-width (truncation only applies to node
  keys produced via union/picksplit), and consistent at a leaf goes through
  `tinfo->f_eq`/`f_cmp` on the un-truncated lower bound.
- **`f_l2n` ("leaf-to-node") indirection** lets `btree_bit.c` transform a
  varbit leaf into a byte-aligned padded form before any node-level operation
  `source/contrib/btree_gist/btree_utils_var.c:104`.

## Notable internals

### `gbt_var_node_cp_len` — common prefix length

`source/contrib/btree_gist/btree_utils_var.c:122`. Walks `lower` and `upper`
byte-by-byte computing the matching prefix length. **Multibyte-aware**: if
`tinfo->eml > 1` (multi-byte encoding), it uses `pg_mblen_range` to detect
character boundaries and refuses to truncate in the middle of a character
`source/contrib/btree_gist/btree_utils_var.c:142`. If `lower` and `upper`
start with characters of *different* byte length, the function bails out at
that position. **However**: text and bpchar disable truncation entirely
(`tinfo.trnc = false`), so this multibyte handling is currently exercised only
by `btree_bit.c` (single-byte) and `btree_bytea.c` (also single-byte). Good
defence in depth but currently dead-coded for varying-encoding paths.

### `gbt_var_node_truncate` — the truncation

`source/contrib/btree_gist/btree_utils_var.c:213`. Cuts both bounds to
`min(len, cpf_length + 1)`. Single byte after the common prefix is preserved
so that internal-node ranges retain enough information to discriminate `lower
< upper`.

### `gbt_var_penalty`

`source/contrib/btree_gist/btree_utils_var.c:387`. Three cases:
1. Empty old key → penalty 0.
2. New key fits inside old (either by comparison or by prefix-match):
   penalty 0 (no update needed).
3. Otherwise: penalty proportional to the *reduction* of common-prefix length
   when merging old+new, falling back to a byte-distance metric on the first
   differing byte if prefix length is unchanged.

The byte-distance metric `abs(tmp[0]-tmp[1]) + abs(tmp[3]-tmp[2])` treats
beyond-length positions as 0
`source/contrib/btree_gist/btree_utils_var.c:435`, which means a key ending at
the prefix is "closer" than one extending beyond.

### `gbt_var_consistent` — strategy switch with collation

`source/contrib/btree_gist/btree_utils_var.c:563`. Critical structural
difference from `gbt_num_consistent`: it **passes `Oid collation` to every
`tinfo->f_*` callback**. This is what allows text/bpchar to honour
collation-aware ordering. Each non-equal strategy at internal nodes also
checks `gbt_var_node_pf_match` so that truncated nodes can still match.

## Trust boundary / Phase D surface

- **Truncation + collation interaction (text)** — `btree_text.c` sets
  `tinfo.trnc = false` and `eml` to `pg_database_encoding_max_length()`. By
  *not* truncating text, the implementation sidesteps a fundamentally hard
  problem: ICU/glibc collation does not respect byte-level prefixes (e.g. for
  Unicode normalisation, a "prefix" in collation order is not a byte prefix).
  This is correct but means text/bpchar indexes are larger than they could
  be — leaf and node both store the full string. See ISSUE-DESIGN.
- **Truncation + `f_cmp` (bytea)** — `btree_bytea.c` sets `trnc = true` and
  uses raw `byteacmp` (memcmp). Truncated keys retain memcmp ordering, so
  this is correct. **However:** if a future patch ever changed `byteacmp` to
  do anything non-monotonic with respect to prefix (e.g. case-fold), the
  truncated index would silently return wrong results. The invariant is load
  bearing.
- **`gbt_var_decompress` calls `PG_DETOAST_DATUM`** — toasted index entries
  are rare but possible after a `VACUUM FULL` on a stale layout. The DETOAST
  must succeed; a corrupted TOAST pointer would `ereport(ERROR)` from
  `detoast_attr`, which is the correct fail-closed behaviour. No data leak
  surface here — DETOAST is an in-memory deserialisation, not an SQL injection
  vector.
- **`gbt_var_compress` `entry->leafkey` check** — assumes the GiST AM core has
  marked leafkey correctly. If an internal-node entry were ever mis-marked
  `leafkey=true`, `gbt_var_key_from_datum` would interpret the packed node
  varlena as a single bound, producing a key with random `upper`. Caller
  contract; not validated here.
- **`gbt_var_picksplit` leaf-to-node `f_l2n`** — invoked when a leaf entry is
  passed to picksplit `source/contrib/btree_gist/btree_utils_var.c:501`.
  For `btree_bit.c`, this allocates a new bytea via `palloc` and stuffs it
  into `sv[svcntr]`. The bookkeeping counter `svcntr++` is only incremented
  when `sv[svcntr] != cur` — a subtle correctness condition: if `f_l2n` happens
  to return its argument unchanged, the entry is *not* tracked in `sv` and
  won't get an explicit pfree (relies on memory context cleanup). Defensible
  for the bit-vector use case where `f_l2n` always allocates.
- **EXCLUDE constraint correctness** — `gbt_var_same` and `gbt_var_consistent`
  for the equality strategy both go through `tinfo->f_cmp`/`f_eq`, which for
  text passes the collation. Therefore EXCLUDE constraints with
  `gist_text_ops` will use the *index's* collation (from the column type) to
  decide equality — usually correct, but a `=` exclusion in collation `und-x-icu`
  may not match a `=` in collation `C` for the same string pair. Test coverage:
  see `expected/text.out`. The Phase D risk: if anyone refactored
  `gbt_var_same` to take a `nil` collation, EXCLUDE constraints on collated
  text would silently start permitting violating tuples.
- **Multibyte prefix handling is unused for text** but exists in
  `gbt_var_node_cp_len`. If someone enabled `tinfo.trnc = true` for text,
  the multibyte logic kicks in and would truncate at character boundaries,
  but collation correctness is still broken — see ISSUE-COLLATION.
- **`gbt_var_penalty` writes through `*res` then multiplies by huge `FLT_MAX
  / (natts+1)` scale factor** — same convention as `penalty_num`. Penalty
  values cannot be interpreted absolutely; only relative ordering matters.

## Cross-references

- `source/src/backend/access/gist/gistutil.c` — gistMakeUnionItVec, etc.
- `source/src/backend/utils/mb/wchar.c` — `pg_mblen_range` used at
  `:144`-ish for multibyte detection.
- `source/src/include/varatt.h` — `VARSIZE`, `VARHDRSZ`, `SET_VARSIZE`
  macros used pervasively.
- `knowledge/files/contrib/btree_gist/btree_text.c.md`,
  `knowledge/files/contrib/btree_gist/btree_bytea.c.md`,
  `knowledge/files/contrib/btree_gist/btree_numeric.c.md`,
  `knowledge/files/contrib/btree_gist/btree_bit.c.md`.

## Issues spotted

- [ISSUE-COLLATION: `gbt_var_node_cp_len` does byte-level prefix computation
  that is collation-INVARIANT. If `tinfo.trnc` is true for any collation-aware
  type, internal-node keys are truncated by byte prefix while leaf-level
  comparison uses collation. For strict collations (e.g. ICU `und-x-icu`)
  the byte-prefix of two strings may not be a collation-prefix, leading to
  incorrect `gbt_var_node_pf_match` results and missed tuples at non-equal
  strategies. The current text/bpchar tinfo deliberately disables truncation
  (`tinfo.trnc = false` at btree_text.c:85, :155) to dodge this — but the
  fact that the code path exists is a footgun for a future contributor.
  (HIGH — would manifest as silently-wrong query results)]
- [ISSUE-DESIGN: Variable-length GiST keys for `text`/`bpchar` are stored
  full-width in both leaves and internal nodes due to `trnc = false`. This
  inflates index size dramatically compared to nbtree (which has a sophisticated
  truncation in `nbtsplitloc.c`). Operational issue for large text columns.
  (LOW — known limitation, not a bug)]
- [ISSUE-INFOLEAK: `gbt_var_fetch` (called for index-only scans) returns the
  stored lower bound. For truncated bytea/bit indexes this is "common prefix
  + 1 byte" rather than the original value — IOS results from a truncated
  index would be silently wrong. The GiST AM is expected to detect truncated
  keys and disable IOS for them via the `gist_*_fetch` opclass member; for
  bytea there IS no `gbt_bytea_fetch`, so IOS is implicitly disabled. But this
  is a brittle convention — anyone adding a fetch for a truncated type would
  produce wrong results. (MED — design pitfall, not a current bug)]
- [ISSUE-MEMORY: `gbt_var_picksplit` `f_l2n` accounting at
  `source/contrib/btree_gist/btree_utils_var.c:501-505` only counts an
  allocation if the returned pointer differs from input. If `f_l2n` ever
  returns a new allocation that happens to equal the input pointer (impossible
  in practice but not statically enforced), the allocation tracking would
  miscount. Relies on `f_l2n` invariant: returned pointer differs iff a new
  buffer was allocated. (LOW)]
- [ISSUE-COMMENT: `gbt_var_node_cp_len` comment "If the underlying type is
  character data, the prefix length may point in the middle of a multibyte
  character" is stale — the function explicitly handles multibyte via
  `pg_mblen_range` and refuses to split mid-character. The comment predates
  the multibyte fix. (LOW)]
- [ISSUE-INPUT-VALIDATION: `gbt_var_compress` calls `PG_DETOAST_DATUM` on
  `entry->key` but does not validate the resulting varlena's size against
  any maximum. A degenerate but valid 1 GB text value would be detoasted
  into backend memory and copied into the index — same memory pressure as
  nbtree. No new attack surface, but worth noting for the inventory. (LOW)]
