# Issues — `contrib/ltree`

Per-subsystem issue register for **ltree**, the hierarchical-label
type with `lquery`/`ltxtquery` query languages + GiST + GIN. 11
source files / ~4 620 LOC.

**Parent docs:** `knowledge/files/contrib/ltree/*` (12 docs;
ltree_gist.h is an inline section of ltree.h documented separately).

**Source:** ~52 entries surfaced 2026-06-09 by A13-2.

## Headlines

1. **`parse_lquery` ~400000× memory amplification** — allocates
   `nodeitem[numOR+1]` PER LEVEL where `numOR` is the GLOBAL `|`
   count (`ltree_io.c:322,329`). A ~256 KB query with ~65000 levels
   × ~65000 `|`s = **~100 GB scratch memory**. Canonical memory-DoS.

2. **`lquery_op.c::checkCond` is a regex-class catastrophic
   backtracker** (`lquery_op.c:228-244`). Concrete repro: 6 nested
   `*{0,9}` against 18-level ltree → ~10^6 explorations. Defended
   only by `check_stack_depth` + `CHECK_FOR_INTERRUPTS` +
   `statement_timeout`.

3. **GiST `LTREE_SIGLEN_DEFAULT=64 bits` is too small** —
   saturates to ALLTRUE after ~10 distinct labels (`ltree_gist.c:
   736-746`); lquery searches degrade to full-scan-plus-recheck.
   Reloption exists; default unchanged. `_ltree_gist` default 224
   bits still too small.

4. **`crc32.c` locale-change-at-runtime silently breaks GiST
   signatures** (`crc32.c:27-30`). Locale change (OS upgrade,
   pg_upgrade across platforms, ICU upgrade, `lc_ctype` change)
   produces false-negative index searches with no code-side
   detection. REINDEX is the only fix.

5. **`_ltree_gist::_ltree_compress` lacks `CHECK_FOR_INTERRUPTS`**
   (`_ltree_gist.c:73-78`) — hashes every level of every element of
   `ltree[]` array; bounded only by MaxAllocSize (~85M elements).
   **Per-INSERT CPU DoS class.**

6. **`ltxtquery_io.c::makepol` + `findoprnd` + `infix` all
   recursive** (`ltxtquery_io.c:213-294, 311-362, 507-604`) — no
   `CHECK_FOR_INTERRUPTS` between tokens; only `check_stack_depth`
   guards depth.

## Cross-sweep references

- **A5 jsonapi recursive-parser finding** (depth cap is 6400 in
  incremental parser ONLY; recursive relies on check_stack_depth) —
  ltree's lquery + ltxtquery parsers are the same pattern.
- **A7 `pg_locale_icu`** — ltree's locale-aware ISLABEL +
  crc32.c's case-folding are the second concrete site where ICU
  collation changes can silently corrupt indexed data.
- **A13-1 hstore CRC32 signature collisions** — same trivially-
  collidable hash used in `crc32.c` for ltree GiST signatures.

## Entries (~52 total)

### ltree.h

- [ISSUE-documentation: ISLABEL accepts UTF-8 letters under
  non-C locales; comment misleadingly says "alphanumerics,
  underscores and hyphens" (nit)] — `source/contrib/ltree/ltree.h:130`.
- [ISSUE-defense-in-depth: LTREE_SIGLEN_DEFAULT=8 bytes=64 bits
  saturates after ~10 distinct labels (likely)] —
  `source/contrib/ltree/ltree.h:236`.
- [ISSUE-correctness: LVAR_NEXT over-estimates space per
  known-frozen on-disk-compat comment (nit)] —
  `source/contrib/ltree/ltree.h:67-72`.
- [ISSUE-api-shape: LTG_RNODE aliases LTG_LNODE when LTG_NORIGHT;
  mutation through LTG_RNODE would corrupt left (nit)] —
  `source/contrib/ltree/ltree.h:284-286`.
- [ISSUE-documentation: LQUERY_HASNOT is set but never read; dead
  flag (nit)] — `source/contrib/ltree/ltree.h:127`.
- [ISSUE-defense-in-depth: lquery_level.numvar is u16 (up to 65535
  OR'd alternatives per level); checkLevel iterates all (nit)] —
  `source/contrib/ltree/ltree.h:92`.

### ltree_gist.h (inline in ltree.h:232-314)

- [ISSUE-api-shape: no separate ltree_gist.h exists — GiST opaque
  types are inline in ltree.h:232-314; header coupling artifact
  (nit)].

### ltree_io.c

- [ISSUE-security: parse_lquery per-level palloc0_array (numOR+1)
  where numOR is GLOBAL — ~400000x memory amplification on
  pathological input (likely)] —
  `source/contrib/ltree/ltree_io.c:322,329`.
- [ISSUE-correctness: empty-label errmsg uses identical prefix
  between ltree/lquery (nit)] —
  `source/contrib/ltree/ltree_io.c:622-627`.
- [ISSUE-security: ISLABEL is locale-aware → same value parses
  differently under different lc_ctype (likely)] —
  `source/contrib/ltree/ltree_io.c:78,87`.
- [ISSUE-defense-in-depth: two-pass parse: 1-GB input with 65536
  dots O(N)-scans before erroring (nit)] —
  `source/contrib/ltree/ltree_io.c:56-62`.
- [ISSUE-api-shape: *_recv accepts arbitrary text length after
  version byte; no recv-side cap (maybe)] —
  `source/contrib/ltree/ltree_io.c:241,825`.
- [ISSUE-correctness: atoi(ptr) for {N,M} ranges silently overflows
  (nit)] — `source/contrib/ltree/ltree_io.c:422,440`.
- [ISSUE-memory: OOM during palloc0_array leaks earlier scratch
  (caught by memcontext at abort) (nit)] —
  `source/contrib/ltree/ltree_io.c:568`.
- [ISSUE-documentation: global | count doesn't account for | inside
  {} — lucky correct because parser rejects them there (nit)] —
  `source/contrib/ltree/ltree_io.c:299-303`.

### lquery_op.c

- [ISSUE-security: checkCond exhibits regex-class catastrophic
  backtracking; ~10^6 explorations on 6-nested wildcard against
  18-level ltree (likely)] —
  `source/contrib/ltree/lquery_op.c:228-244`.
- [ISSUE-defense-in-depth: slow-path ltree_label_match does 2
  palloc + maybe repalloc + 2 pfree per comparison (maybe)] —
  `source/contrib/ltree/lquery_op.c:107-141`.
- [ISSUE-correctness: static pg_locale_t locale = NULL cached for
  backend lifetime (nit)] —
  `source/contrib/ltree/lquery_op.c:84-105`.
- [ISSUE-defense-in-depth: compare_subnode is O(Q × T) in
  _-separated lexeme counts (nit)] —
  `source/contrib/ltree/lquery_op.c:43-73`.
- [ISSUE-api-shape: DirectFunctionCall2 pattern means inner
  PG_FREE_IF_COPY is a no-op (no flinfo-driven detoast) (nit)] —
  `source/contrib/ltree/lquery_op.c:306-317`.
- [ISSUE-documentation: LQL_COUNT compat hack needs backref to
  ltree.h:80-86 (nit)] —
  `source/contrib/ltree/lquery_op.c:205-208`.

### ltree_op.c

- [ISSUE-documentation: ltree_compare magnitude factor `* 10 *
  (an+1)` looks meaningful but only sign used (nit)] —
  `source/contrib/ltree/ltree_op.c:60`.
- [ISSUE-correctness: lca_inner excludes last level via
  `num = numlevel - 1`; tree-LCA semantics but surprising (nit)] —
  `source/contrib/ltree/ltree_op.c:505`.
- [ISSUE-defense-in-depth: ltree_index is O(N×M) naive substring;
  no CHECK_FOR_INTERRUPTS (nit)] —
  `source/contrib/ltree/ltree_op.c:425-446`.
- [ISSUE-correctness: subpath with start=INT32_MIN relies on
  signed-overflow UB (nit)] —
  `source/contrib/ltree/ltree_op.c:319-321`.
- [ISSUE-correctness: subltree silently clips endpos > numlevel but
  errors on startpos >= numlevel; asymmetric (nit)] —
  `source/contrib/ltree/ltree_op.c:270-276`.
- [ISSUE-documentation: ltreeparentsel is dead code for extension
  v1.2+ (nit)] — `source/contrib/ltree/ltree_op.c:633-651`.

### ltxtquery_io.c

- [ISSUE-security: makepol recurses on every (; ~13K nesting before
  check_stack_depth fires; no CHECK_FOR_INTERRUPTS between tokens
  (likely)] — `source/contrib/ltree/ltxtquery_io.c:213-294`.
- [ISSUE-security: findoprnd second recursive pass; same depth
  bound (likely)] — `source/contrib/ltree/ltxtquery_io.c:311-362`.
- [ISSUE-security: infix recursive deparser palloc's INFIX buffer
  per frame (maybe)] —
  `source/contrib/ltree/ltxtquery_io.c:507-604`.
- [ISSUE-defense-in-depth: no CHECK_FOR_INTERRUPTS in
  gettoken_query / makepol / findoprnd / infix (likely)] —
  `source/contrib/ltree/ltxtquery_io.c:60-149`.
- [ISSUE-correctness: elog(ERROR, "stack too short") is hard-error;
  bypasses soft-error pathway (nit)] —
  `source/contrib/ltree/ltxtquery_io.c:250-252`.
- [ISSUE-api-shape: ltxtq_send re-deparses through infix — not
  byte-identical to original text input (nit)] —
  `source/contrib/ltree/ltxtquery_io.c:644-662`.

### ltxtquery_op.c

- [ISSUE-security: ltree_execute walker has no CHECK_FOR_INTERRUPTS
  (only check_stack_depth); long &/| chains uninterruptible
  (likely)] — `source/contrib/ltree/ltxtquery_op.c:20-47`.
- [ISSUE-documentation: checkcondition_str existential-match
  semantics not commented at the function (nit)] —
  `source/contrib/ltree/ltxtquery_op.c:55-80`.
- [ISSUE-api-shape: calcnot boolean parameter unexplained at
  definition (nit)] — `source/contrib/ltree/ltxtquery_op.c:20`.

### ltree_gist.c

- [ISSUE-defense-in-depth: default siglen=8 bytes=64 bits too
  small; saturates to ALLTRUE → lquery searches degrade to
  full-scan-plus-recheck (likely)] —
  `source/contrib/ltree/ltree_gist.c:736-746`.
- [ISSUE-correctness: ltree_penalty ignores signature-stretch cost
  (nit)] — `source/contrib/ltree/ltree_gist.c:265-275`.
- [ISSUE-correctness: gist_isparent mutates query->numlevel
  in-place; only safe because strategy 10 uses _P_COPY. Fragile
  (nit)] — `source/contrib/ltree/ltree_gist.c:429-441`.
- [ISSUE-api-shape: strategy numbers 10-17 are bare integer
  literals; no symbolic names (nit)] —
  `source/contrib/ltree/ltree_gist.c:666-714`.
- [ISSUE-documentation: LTG_NORIGHT aliasing implication under-
  documented (nit)] —
  `source/contrib/ltree/ltree_gist.c:62-70`.
- [ISSUE-documentation: strategy 10 uses _P_COPY but strategy 11
  doesn't (nit)] —
  `source/contrib/ltree/ltree_gist.c:667,674`.

### _ltree_gist.c

- [ISSUE-security: _ltree_compress hashes every level of every
  element of ltree[]; no CHECK_FOR_INTERRUPTS; bounded only by
  MaxAllocSize (likely)] —
  `source/contrib/ltree/_ltree_gist.c:73-78`.
- [ISSUE-defense-in-depth: no per-row ltree[] element-count cap
  (maybe)] — `source/contrib/ltree/_ltree_gist.c:59`.
- [ISSUE-correctness: _ltree_gist_options missing
  register_reloptions_validator (nit)] —
  `source/contrib/ltree/_ltree_gist.c:547-557`.
- [ISSUE-correctness: siglen min is 1 here vs INTALIGN(1)=4 in
  scalar opclass; asymmetric (nit)] —
  `source/contrib/ltree/_ltree_gist.c:553`.
- [ISSUE-defense-in-depth: default siglen=28 bytes=224 bits still
  too small for realistic ltree[] (likely)] —
  `source/contrib/ltree/_ltree_gist.c:553`.
- [ISSUE-api-shape: strategy numbers 10-17 bare integers (nit)] —
  `source/contrib/ltree/_ltree_gist.c:522-537`.
- [ISSUE-correctness: _arrq_cons collapses to recheck on saturated
  signatures (nit)] —
  `source/contrib/ltree/_ltree_gist.c:479-501`.

### _ltree_op.c

- [ISSUE-defense-in-depth: array_iterator outer loop has no
  CHECK_FOR_INTERRUPTS; relies on callback-internal checks
  (likely)] — `source/contrib/ltree/_ltree_op.c:54-66`.
- [ISSUE-defense-in-depth: _lt_q_regex is O(num_lqueries ×
  num_ltrees × per-call-cost) with no inter-iteration interrupt
  check (likely)] —
  `source/contrib/ltree/_ltree_op.c:152-161`.
- [ISSUE-correctness: _lca builds the input pointer array in
  REVERSE; relies on lca_inner being commutative (nit)] —
  `source/contrib/ltree/_ltree_op.c:311-316`.

### crc32.c / crc32.h

- [ISSUE-security: locale-change-at-runtime silently breaks CRC
  consistency → GiST signatures incompatible across locale changes
  → silent false negatives in indexed search (likely)] —
  `source/contrib/ltree/crc32.c:27-30`.
- [ISSUE-correctness: MSVC vs non-MSVC produce different CRC values
  for identical labels; cross-platform pg_upgrade broken without
  REINDEX (maybe)] — `source/contrib/ltree/crc32.c:15`.
- [ISSUE-defense-in-depth: static pg_locale_t locale = NULL cached
  for backend lifetime; ignores mid-session SET lc_collate (nit)] —
  `source/contrib/ltree/crc32.c:27-30`.
- [ISSUE-documentation: UNICODE_CASEMAP_BUFSZ bounds depend on PG
  core's Unicode tables remaining current (nit)] —
  `source/contrib/ltree/crc32.c:35,40-41`.
- [ISSUE-api-shape: crc32(buf) macro shadows any caller's local
  crc32 (nit)] — `source/contrib/ltree/crc32.h:10`.
