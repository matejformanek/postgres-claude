# btree_text.c

## One-line summary

GiST opclasses for `text` and `bpchar` — uses `btree_utils_var.c` with
**truncation disabled** (`tinfo.trnc = false`) so the index always stores
full-width strings. Collation flows through every comparator via
`DirectFunctionCall2Coll`.

## Public API

Standard 7-function GiST set plus sortsupport, in two parallel groups:

- `gbt_text_{compress,union,picksplit,consistent,penalty,same,sortsupport}`
  `source/contrib/btree_gist/btree_text.c:13-21`.
- `gbt_bpchar_{compress,consistent,sortsupport}` — bpchar delegates compress
  to text (`source/contrib/btree_gist/btree_text.c:184`) but uses its own
  `bpchargt/ge/eq/le/lt/cmp` for whitespace-folding semantics
  `source/contrib/btree_gist/btree_text.c:151-163`.

## Key invariants

- **Key layout:** `bytea`-prefixed `[lower-text|upper-text]`, full width, no
  truncation (`tinfo.trnc = false` at `:85`, `:155`).
- **Comparators go through `DirectFunctionCall2Coll`** with `PG_GET_COLLATION()`
  threaded through `gbt_var_compress/consistent/union/picksplit/penalty/same`
  `source/contrib/btree_gist/btree_text.c:30,180`.
- **`tinfo.eml` (encoding max length) is lazily initialised** on first
  `gbt_text_compress`/`gbt_text_consistent`/`gbt_bpchar_consistent` call
  `source/contrib/btree_gist/btree_text.c:175,207,235`. The cached value is
  stored in the static `tinfo`/`bptinfo` structs (statically initialised to
  `eml = 0`), so this is a one-time-per-backend mutation. Not thread-safe
  but PG backends are single-threaded.
- **`gbt_bpchar_compress` delegates to `gbt_text_compress`** with the comment
  *"This should never have been distinct from gbt_text_compress"* — a kept-
  for-ABI-compat shim `source/contrib/btree_gist/btree_text.c:184`.

## Notable internals

- Sortsupport comparator (`gbt_text_ssup_cmp` at `:288`,
  `gbt_bpchar_ssup_cmp` at `:321`): detoasts both keys, reads the lower bound
  (leaf invariant `lower == upper`), calls `bttextcmp`/`bpcharcmp` with
  `ssup->ssup_collation`. Frees the detoasted copies via `GBT_FREE_IF_COPY`.
- The two static tinfo structs `tinfo`/`bptinfo` are **non-const** because
  `eml` is mutated lazily. Every other per-type opclass uses `const` tinfo.

## Trust boundary / Phase D surface

- **Collation correctness for EXCLUDE constraints:** This file is the *least*
  problematic of the collation-aware paths because (a) every comparator
  passes the collation explicitly and (b) truncation is disabled so the
  byte-prefix vs collation-prefix mismatch in `btree_utils_var.c` never
  bites. An EXCLUDE constraint like `EXCLUDE USING gist (name WITH =)` on a
  text column will use the column's collation correctly — `gbt_text_same`
  passes `PG_GET_COLLATION()` to `gbt_var_same` which passes it to
  `tinfo->f_eq` → `texteq(... collation)`.
- **bpchar trailing-blank semantics:** `bpcharcmp` ignores trailing blanks
  by SQL convention. Two `char(10)` values `'abc'` and `'abc       '` compare
  equal. EXCLUDE constraints rely on this: inserting `'abc'` after
  `'abc   '` correctly conflicts under `gbt_bpchar_consistent`. Verify:
  `gbt_bpchareq` at `:115` calls `bpchareq` which is whitespace-folding.
- **`tinfo.eml` lazy init race in parallel index builds:** if two parallel
  workers initialise `tinfo.eml = 0` simultaneously, both will call
  `pg_database_encoding_max_length()` (a cheap GUC-derived value); the writes
  are word-sized and the value is the same, so this is benign. But the code
  is not annotated as such — anyone adding more lazy fields here needs to
  re-examine.
- **No truncation = no info leak via truncated prefix**, but also no protection
  against very long text values — a `text` column with 1 GB strings would
  produce 1 GB GiST index leaves. Operational, not security.
- **`PG_GET_COLLATION()` from each top-level function** is the collation that
  the *call site* (e.g. index scan, EXCLUDE check) passes. If a user could
  somehow alter the calling collation between leaf insert and node-level
  union, the index would silently desync. This cannot happen via SQL because
  the index's collation is fixed at CREATE INDEX time and used uniformly.

## Cross-references

- `source/src/backend/utils/adt/varlena.c` — `text_gt/ge/eq/le/lt`,
  `bttextcmp`.
- `source/src/backend/utils/adt/varchar.c` — `bpchargt/ge/eq/le/lt`,
  `bpcharcmp`.
- `knowledge/files/contrib/btree_gist/btree_utils_var.c.md` — framework.

## Issues spotted

- [ISSUE-CODE-SMELL: `gbt_bpchar_compress` comment "This should never have
  been distinct from gbt_text_compress" indicates a backward-compatibility
  shim that the authors regret. Could be folded into a single function with
  the type tag selecting `tinfo`, but ABI/opclass-binding constraints make
  this hard to clean up. (LOW)]
- [ISSUE-MEMORY-DISCIPLINE: `gbt_text_consistent` does
  `void *query = DatumGetTextP(PG_GETARG_DATUM(1))` which may detoast and
  allocate. The detoasted result is never freed and lives until the consistent
  call returns — fine because GiST core uses a short-lived memory context,
  but worth noting if anyone moves these functions outside their natural
  caller. (LOW)]
- [ISSUE-NON-CONST: `tinfo`/`bptinfo` are non-const due to lazy `eml` init.
  All other type files use `static const gbtree_vinfo tinfo` — the
  inconsistency is a minor maintainability footgun. A `pg_database_encoding_
  max_length()` is cheap enough that we could just call it every time and
  make tinfo const. (LOW)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
