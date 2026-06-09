# Issues — `contrib/intarray`

Per-subsystem issue register for **intarray**, the integer-array
type with GiST + GIN support + boolean-query operators. 8 source
files / ~3 506 LOC.

**Parent docs:** `knowledge/files/contrib/intarray/*` (7 docs; _int.h
+ _int_tool.c combined into `_int.md`).

**Source:** ~20 entries surfaced 2026-06-09 by A13-4.

## Headlines

1. **Signature-tree mod-hash trivially spoofable** — `HASHVAL(val,
   siglen) = ((unsigned int) val) % (siglen * 8)`. Default
   siglen=252 → modulo 2016. **Attacker who inserts into intbig-
   indexed column can precompute collisions to amplify recheck
   cost OR plant a 2016-distinct-value array creating an ALLISTRUE
   leaf that defeats pruning.**

2. **`_int_bool.c::bqarr_in` can palloc ~3 GB for max-size query**
   (134M ITEM); single backend OOM via one carefully-sized text.

3. **`makepol` recursion guarded only by `check_stack_depth()`**
   — depth bound = `max_stack_depth` GUC, not intarray-specific.
   Cross-link to A5 jsonapi finding.

4. **`! 42` style queries force full GIN scan**
   (`GIN_SEARCH_MODE_ALL`); reachable via any app exposing `@@`
   query strings.

## Cross-sweep references

- **A5 jsonapi recursive parser** — `_int_bool.c::makepol` is the
  same recursion-depth pattern.
- **A7 stats deserialization** — `_int_selfuncs.c` reads attacker-
  controllable MCE entries.
- **A13-1 hstore + A13-2 ltree + A13-3 btree_gist** — GiST-on-
  attacker-data collision cluster.

## Entries

### _int.h + _int_tool.c (combined)

- [ISSUE-security: signature-tree mod hash (val % siglen_bits) is
  trivially spoofable; intbig opclass on attacker-influenced int4
  columns will degenerate (maybe)].
- [ISSUE-api-shape: internal_size overload of -1 as overflow
  sentinel (nit)].
- [ISSUE-defense-in-depth: `|` / `&` over arbitrary user arrays
  palloc up to (na+nb)*4 bytes with no preflight bound (nit)].
- [ISSUE-correctness: new_intArrayType size arithmetic lacks
  explicit MaxAllocSize/sizeof(int) guard (nit)].

### _int_bool.c

- [ISSUE-security: bqarr_in can palloc ~3 GB for max-size query
  (134M ITEM); single backend OOM via one carefully-sized text
  (likely)].
- [ISSUE-security: makepol recursion guard is check_stack_depth()
  only; depth bound depends on max_stack_depth GUC, not intarray-
  specific (likely)].
- [ISSUE-error-handling: STACKDEPTH=16 overflow message "statement
  too complex" not intarray-specific (nit)].
- [ISSUE-documentation: signature vs exact calcnot semantics inside
  execute() subtle and undocumented (nit)].

### _int_gin.c

- [ISSUE-security: `! 42` style queries force full GIN scan
  (GIN_SEARCH_MODE_ALL); reachable via any app exposing @@ query
  strings (maybe)].
- [ISSUE-api-shape: VAL-order coupling between ginint4_queryextract
  and gin_bool_consistent is comment-only, not enforced (nit)].

### _int_gist.c

- [ISSUE-defense-in-depth: inserting >2*num_ranges (default 200)
  elements into gist__int_ops-indexed column hard-errors INSERT
  path (nit)].
- [ISSUE-defense-in-depth: pickSplit O(maxoff²) with inner
  int_union/inter; perf cliff if page fanout grows (nit)].
- [ISSUE-correctness: `<@` branch (g_int_consistent:96-115) dead
  since intarray 1.4 — candidate for deletion (nit)].

### _int_op.c

- [ISSUE-defense-in-depth: _int_union / _int_inter /
  intarray_concat_arrays palloc up to (na+nb)*4 bytes without
  upfront cap (nit)].
- [ISSUE-correctness: icount does not CHECKARRVALID; counts NULL-
  bitmap entries (nit)].
- [ISSUE-defense-in-depth: _int_contains re-sorts both sides per
  call; high-cardinality @> joins pay O(n log n) per row (nit)].
- [ISSUE-api-shape: sort() rejects "asc " (trailing space) with
  generic error (nit)].

### _int_selfuncs.c

- [ISSUE-security: attacker-controlled MCE entries in pg_statistic
  can mislead planner for @@ (maybe — affects all opclasses, cross-
  link A7)].
- [ISSUE-api-shape: selectivity wrappers hardcode OID_ARRAY_*_OP
  substitution; semantic drift would silently produce wrong
  estimates (nit)].
- [ISSUE-documentation: nnumbers == nvalues + 3 MCE-layout magic
  number is comment-only (nit)].

### _intbig_gist.c

- [ISSUE-security: trivial bit-collision via val % siglen_bits;
  enables attacker-controlled false-positive amplification and
  index DoS (likely — recheck preserves correctness, perf only)].
- [ISSUE-security: malicious 2016-distinct-value array creates
  ALLISTRUE leaf that defeats GiST pruning (likely)].
- [ISSUE-correctness: `<@` branch (lines 536-577) dead since
  intarray 1.4 (nit)].
- [ISSUE-documentation: no warning that siglen=252 default is
  insufficient against adversarial inserts (nit)].
