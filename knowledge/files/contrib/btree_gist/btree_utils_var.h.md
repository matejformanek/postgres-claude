# `contrib/btree_gist/btree_utils_var.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 81
- **Source:** `source/contrib/btree_gist/btree_utils_var.h`

The variable-length analogue of `btree_utils_num.h`. Declares the
key types, the per-type vtable (`gbtree_vinfo`), one helper macro
(`GBT_FREE_IF_COPY`), and prototypes the cross-cutting `gbt_var_*`
helpers in `btree_utils_var.c`. Used by `btree_text.c`, `btree_bpchar.c`,
`btree_bytea.c`, `btree_bit.c`, `btree_inet.c`. [verified-by-code]

## API / entry points (types)

- `typedef bytea GBT_VARKEY` `:11` — packed key is just a `bytea`.
  Format: a varlena containing two varlenas back-to-back (lower
  bound, then upper bound). [verified-by-code via `btree_utils_var.c`
  consumers]
- `typedef struct { bytea *lower, *upper; } GBT_VARKEY_R` `:14-18`
  — readable form; the two member pointers point into the packed
  GBT_VARKEY. [verified-by-code]
- `typedef struct { enum gbtree_type t; int32 eml; bool trnc;
  bool (*f_gt/ge/eq/le/lt)(const void *, const void *, Oid,
  FmgrInfo *); int32 (*f_cmp)(const void *, const void *, Oid,
  FmgrInfo *); GBT_VARKEY *(*f_l2n)(GBT_VARKEY *, FmgrInfo *); }
  gbtree_vinfo` `:23-42` — per-type vtable. Note the extra
  `Oid collation` argument on every comparator (unlike `gbtree_ninfo`)
  because text comparators are collation-aware.
  - `eml` = cached `pg_database_encoding_max_length()`; 0 = undefined.
  - `trnc` = whether truncation/compression of the key is allowed.
  - `f_l2n` = "leaf to node" — convert a leaf key to a node key
    (i.e. compress / truncate).
  [verified-by-code]

## API / entry points (functions)

All declared `extern`, defined in `btree_utils_var.c`:

- `gbt_var_key_readable(const GBT_VARKEY *k)` `:56` — unpack packed
  key to `GBT_VARKEY_R`. Returns by value. [verified-by-code]
- `gbt_var_key_copy(const GBT_VARKEY_R *u)` `:58` — pack two
  varlenas into a fresh `GBT_VARKEY`. [verified-by-code]
- `gbt_var_compress(entry, tinfo)` `:60` — GiST compress support
  function. [verified-by-code]
- `gbt_var_union(entryvec, &size, collation, tinfo, flinfo)` `:62-63`
  — bounding-box for a set. Takes collation. [verified-by-code]
- `gbt_var_same(d1, d2, collation, tinfo, flinfo)` `:65-66` — equality.
  [verified-by-code]
- `gbt_var_penalty(res, o, n, collation, tinfo, flinfo)` `:68-69` —
  split penalty. Unlike numeric, no inline macro; collation matters.
  [verified-by-code]
- `gbt_var_consistent(key, query, strategy, collation, is_leaf, tinfo,
  flinfo)` `:71-73` — consistent. [verified-by-code]
- `gbt_var_picksplit(entryvec, v, collation, tinfo, flinfo)` `:75-76`
  — page split. [verified-by-code]
- `gbt_var_bin_union(u, e, collation, tinfo, flinfo)` `:78-79` —
  binary union helper. [verified-by-code]

## Macros

- **`GBT_FREE_IF_COPY(ptr1, ptr2) :50-54`** — pfree `ptr1` if it
  isn't actually `DatumGetPointer(ptr2)`. Adapted from the standard
  `PG_FREE_IF_COPY` (which takes `fcinfo`); this version is freed
  from the explicit "original-datum" pointer. Used after
  `PG_DETOAST_DATUM`-style conversion to handle the case where the
  detoasted value is the same buffer as input.
  [from-comment + verified-by-code]

## Notable invariants / details

- **INV-1: Variable-length keys carry a collation Oid through every
  comparator.** Unlike numeric keys where `FmgrInfo` is enough,
  text comparison is collation-sensitive — so every `f_*` callback
  signature includes `Oid collation`. [verified-by-code]
- **INV-2: `eml` is a cached encoding-max-length.** Lazy-init to 0,
  populated on first use. Used by `gbt_var_node_truncate` to find
  safe byte-boundary truncation points in multibyte encodings.
  [verified-by-code — see `btree_utils_var.c::gbt_var_node_truncate`]
- **INV-3: `trnc` (truncation enabled) is set to `false` for text
  and bpchar.** Per the existing issue register
  (`knowledge/issues/btree_gist.md` Headline 1), this is the ONLY
  thing keeping collation-correctness because the underlying
  `gbt_var_node_cp_len` truncation is byte-based, not collation-aware.
  Flipping `trnc = true` for text would silently break range
  queries under ICU/locale-sensitive collations. [from-issue-register]
  **[ISSUE-correctness: trnc=false invariant for text/bpchar is
  load-bearing for collation correctness (likely)]**
- **INV-4: `GBT_FREE_IF_COPY` is `do {} while(0)`-wrapped** for
  safe use in `if`/`else` without braces. Standard PG macro
  hygiene. [verified-by-code]
- **INV-5: `f_l2n` (leaf-to-node) is the truncation point.**
  Distinguishes "what's stored at leaves" from "what's stored at
  inner nodes" — leaves get exact values, inner nodes get
  possibly-truncated keys. [verified-by-code]

## Potential issues

- `:11` `typedef bytea GBT_VARKEY;` is a typedef of a real PG
  type, not a struct — the API takes `bytea *` everywhere. Subtle
  for a reader unfamiliar with varlena conventions. [verified-by-code]
  **[ISSUE-style: GBT_VARKEY = bytea typedef obscures actual
  varlena layout (nit)]**
- `:29` `eml` comment notes "0: undefined" — caching pattern with
  in-band sentinel. A multibyte encoding with max length 1 (e.g.
  pure ASCII fallback in EUC_JP) would never trigger re-init.
  Probably fine; encodings don't change at runtime. [verified-by-code]
- `:42` `gbtree_vinfo` has 7 function pointers + 3 data fields, but
  no per-field comments after the `Methods` heading. [verified-by-code]
  **[ISSUE-doc-drift: gbtree_vinfo methods underdocumented (nit)]**
- The header doesn't expose `gbt_var_node_truncate` or
  `gbt_var_node_cp_len` — they're file-local in
  `btree_utils_var.c`. Those are the actual truncation primitives
  that the trnc=false invariant guards. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `btree_gist`](../../../issues/btree_gist.md)
<!-- issues:auto:end -->
