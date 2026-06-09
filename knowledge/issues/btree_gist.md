# Issues — `contrib/btree_gist`

Per-subsystem issue register for **btree_gist**, the GiST opclass
framework for built-in PG types (enables EXCLUDE constraints + multi-
column GiST indexes alongside geometry types). 27 source files /
~6 725 LOC.

**Parent docs:** `knowledge/files/contrib/btree_gist/*` (24 docs;
3 framework .c+.h pairs combined into single docs + 21 per-type).

**Source:** ~25 entries surfaced 2026-06-09 by A13-3.

## Headlines

1. **`btree_utils_var.c` latent collation footgun** — byte-prefix
   truncation (`gbt_var_node_cp_len`, `gbt_var_node_truncate`) is
   collation-invariant. The ONLY thing keeping text/bpchar indexes
   correct is `tinfo.trnc = false` in `btree_text.c:85,155`. A
   future "shrink index size" optimization flipping this on would
   silently break range queries under ICU collations. Multibyte-
   aware `pg_mblen_range` provides byte-boundary alignment, NOT
   the semantic mismatch between collation order and byte order.

2. **float4/float8 NaN handling diverges from nbtree** — btree_gist
   uses raw IEEE `>`/`==` (NaN unordered); nbtree opclass orders
   NaN as greater-than-all-finite. **`EXCLUDE USING gist (val
   WITH =)` on float permits duplicate NaN rows where btree
   equivalent rejects.** Plus `penalty_num(NaN, ...)` returns 0 →
   pathological NaN page clustering. Sortsupport
   (`gbt_floatN_ssup_cmp`) uses NaN-aware `floatN_cmp_internal` —
   picksplit sort uses one ordering, index-time consistency
   another.

3. **`btree_inet.c` is the only fixed-width opclass needing
   `*recheck = true`** — stores inet as a lossy `double` scalar
   (`convert_network_to_scalar`); IOS impossible.

4. **`btree_enum.c` stores raw enum OIDs** — fragile to
   `pg_upgrade --link` without REINDEX; `gbt_enumeq` uses raw OID
   `==` bypassing `enum_eq`.

5. **`btree_uuid.c` quietly assumes `WORDS_BIGENDIAN` correctly
   configured** for its `uuid_2_double` penalty conversion.
   Misconfigured = silently broken index (correct queries, broken
   perf).

## Cross-sweep references

- **A11 contrib top-4** (postgres_fdw NAME-based aggregate
  pushdown) — btree_gist's `btree_text` raw-byte comparison without
  collation is the same family of cross-correctness gap.
- **A7 ICU finding (`pg_locale_icu`)** — text-via-btree-gist with
  custom ICU rules would compose oddly with the collation-invariant
  truncation logic.
- **A13-1 hstore GiST CRC32 collisions + A13-2 ltree GiST locale
  drift + A13-4 intarray signature-tree mod-hash collisions** —
  the GiST-on-attacker-data collision/correctness cluster.

## Entries (~25 total)

### btree_gist.c + btree_gist.h

- [ISSUE-documentation: gbtreekey_in/out hardcoded "gbtreekey?" in
  error path (nit)].

### btree_utils_num.c + btree_utils_num.h

- [ISSUE-api-shape: penalty_num macro reaches into
  `((GISTENTRY *) PG_GETARG_POINTER(0))->rel->rd_att->natts` —
  hidden caller-signature coupling (nit)].
- [ISSUE-correctness: NaN inputs to penalty_num silently produce 0
  (affects float4/float8) (maybe)] —
  `source/contrib/btree_gist/btree_utils_num.c`.
- [ISSUE-correctness: BtreeGistNotEqualStrategyNumber on singleton
  internal-node range may incorrectly return false (nit)].
- [ISSUE-documentation: gbt_num_consistent explicitly NOT
  collation-aware (header comment line 259) (nit)].

### btree_utils_var.c + btree_utils_var.h

- [ISSUE-correctness: byte-prefix truncation is collation-INVARIANT;
  flipping tinfo.trnc=true for text would silently produce wrong
  results under ICU collation (likely — latent footgun)] —
  `source/contrib/btree_gist/btree_utils_var.c`.
- [ISSUE-defense-in-depth: gbt_var_fetch returns lower bound for
  IOS; adding a fetch function for bytea/bit (trnc=true) would
  expose truncated prefixes (maybe)].
- [ISSUE-documentation: truncation enabled for bytea/bit/varbit;
  disabled for text/bpchar/numeric — deliberate, but worth a
  call-out (nit)].

### btree_text.c

- [ISSUE-correctness: non-const tinfo (lazy
  pg_database_encoding_max_length init); only file in btree_gist
  with mutable tinfo (nit)] —
  `source/contrib/btree_gist/btree_text.c:85,155`.

### btree_bytea.c

- [ISSUE-defense-in-depth: trnc=true; raw byteacmp memcmp; index
  degenerates for high-entropy bytea (SHA hashes) (nit)].

### btree_numeric.c

- [ISSUE-correctness: trnc=false is load-bearing; flipping it would
  break numeric ordering silently (maybe — future-contributor
  footgun)].

### btree_float4.c / btree_float8.c

- [ISSUE-correctness: EXCLUDE WITH = on float columns permits
  duplicate NaN rows (because NaN==NaN is false in IEEE), diverging
  from nbtree opclass (likely)].
- [ISSUE-correctness: penalty_num(NaN, ...) returns 0, causing
  pathological NaN clustering (likely)].
- [ISSUE-correctness: picksplit key_cmp vs sortsupport use
  different NaN semantics (maybe)].

### btree_inet.c

- [ISSUE-correctness: stores inet as single double scalar via
  convert_network_to_scalar — lossy; *recheck=true; no
  gbt_inet_fetch (IOS impossible) (likely)] —
  `source/contrib/btree_gist/btree_inet.c`.
- [ISSUE-defense-in-depth: Assert(!failure) is only defense against
  corrupt inet (nit)].

### btree_uuid.c

- [ISSUE-correctness: misconfigured WORDS_BIGENDIAN would silently
  produce broken index (correct queries, broken perf) (maybe)].
- [ISSUE-defense-in-depth: UUIDv4 random data → near-useless GiST
  internal nodes (nit, by-design for UUIDs)].

### btree_enum.c

- [ISSUE-correctness: pg_upgrade with --link and no REINDEX leaves
  stale enum OIDs in the index (maybe)] —
  `source/contrib/btree_gist/btree_enum.c`.

### btree_time.c

- [ISSUE-correctness: gist_timetz_ops discards timezone for
  ordering — EXCLUDE WITH = on timetz has subtly different
  semantics from the btree equivalent (maybe)].

### btree_date.c

- [ISSUE-correctness: custom penalty using date_mi doesn't
  explicitly handle +/- infinity dates; relies on Max(diff, 0)
  masking any overflow (nit)].

### btree_bit.c

- [ISSUE-defense-in-depth: f_l2n xfrm + truncation + per-strategy
  query xfrm in consistent is the most intricate flow; latent
  footgun (nit)].

### btree_interval.c

- [ISSUE-correctness: KNN distance uses approximate
  INTERVAL_TO_SEC (30-day months); EXCLUDE uses exact
  interval_eq — sound (nit)].

### Trivial per-type files (no significant issues)

- `btree_int2.c`, `btree_int4.c`, `btree_int8.c`, `btree_oid.c`,
  `btree_bool.c`, `btree_cash.c`, `btree_macaddr.c`,
  `btree_macaddr8.c`, `btree_ts.c` — standard fixed-width
  comparators following btree_utils_num framework.
