# Issues — `contrib/pageinspect`

Per-subsystem issue register for **pageinspect**, the low-level
page/tuple/index introspection extension. 9 source files / ~3 700
LOC. Functions are `superuser()`-gated at the C-level.

**Parent docs:** `knowledge/files/contrib/pageinspect/*` (8 docs:
`pageinspect.md` combines `pageinspect.h`+`rawpage.c`; `heapfuncs`,
`btreefuncs`, `brinfuncs`, `ginfuncs`, `gistfuncs`, `hashfuncs`,
`fsmfuncs`).

**Source:** ~30 entries surfaced 2026-06-09 by A12-2.

## Headlines

1. **`get_raw_page` is THE central RLS-bypass primitive** —
   `rawpage.c:191-196`. Returns full 8 KB block bytea including
   RLS-filtered tuples; only `superuser()` gates it. Every per-AM
   decoder downstream is essentially a "decode the RLS-bypassed
   bytes" function.

2. **`tuple_data_split(do_detoast=true)` follows attacker-controlled
   TOAST pointers without cross-checking that `va_toastrelid`
   matches the `relid` argument's TOAST relation** — `heapfuncs.c:
   357-408, 391-392`. **Cross-table read primitive** if delegated
   via SECDEF; only the superuser gate prevents arbitrary use.

3. **Pageinspect has ZERO `pg_stat_scan_tables` discipline** —
   unlike pgstattuple, `.sql` files contain no REVOKE/GRANT lines.
   Only delegation path is SECDEF wrappers most installs don't have.

4. **Per-AM decoders leak indexed-column values** — B-tree raw
   keys, GIN lexemes/jsonb paths, GiST geometry/range/inet/tsquery,
   hash hashes (reversible for low-cardinality columns).

5. **Uneven bounds-checking discipline** — `rawpage.c` +
   `heapfuncs.c` exhaustively check `lp_off + lp_len ≤ BLCKSZ`; per-AM
   decoders (brin, gin, gist, btree-bytea) trust `PageGetItem`
   invariants when handed fabricated bytea. Chain-of-trust:
   "superuser-gated input is trusted input" — safe today, fragile
   to SECDEF refactor.

6. **hashfuncs is the model-citizen decoder** — `GIST_PAGE_ID`-style
   magic + version + special-size + page-type-mask checks before
   parsing.

## Cross-sweep references

- **A11 pgcrypto + A12 sslinfo + A12 amcheck** all share the
  "default PUBLIC EXECUTE" anti-pattern at the SQL surface; only
  pgcrypto has the new `pgcrypto.builtin_crypto_enabled` GUC kill
  switch.
- **A12-1 amcheck** has the same "superuser-gated input is trusted
  input" assumption for verify_heapam's TOAST decoder, but is
  better-defended at the bytea-decode layer.

## Entries (~30 total)

### pageinspect (pageinspect.h + rawpage.c)

- [ISSUE-security: `get_raw_page` is the central RLS-bypass
  primitive — returns full 8 KB block bytea including RLS-filtered
  tuples; only `superuser()` gates it (confirmed)] —
  `source/contrib/pageinspect/rawpage.c:191-196`.
- [ISSUE-defense-in-depth: no `pg_stat_scan_tables` GRANT pattern
  anywhere in `pageinspect--*.sql`; admins cannot delegate
  gracefully (likely)].
- [ISSUE-correctness: `get_raw_page` doesn't refuse
  `indisvalid=false` indexes; per-AM decoders may produce
  misleading output (nit)].
- [ISSUE-api-shape: `page_checksum` recomputes (using user-supplied
  blkno) rather than verifies against stored value (nit)].
- [ISSUE-documentation: `superuser()` redundantly duplicated at
  multiple layers; `get_page_from_raw` itself has no check (nit)].

### heapfuncs.c

- [ISSUE-security: `tuple_data_split` bypasses type-input validation;
  returns on-disk bytes per column (confirmed)] —
  `source/contrib/pageinspect/heapfuncs.c:357-408`.
- [ISSUE-security: `do_detoast=true` follows attacker-controlled
  TOAST pointers; no cross-check that the pointer belongs to
  `relid`'s TOAST relation → cross-table read primitive if
  delegated via SECDEF (likely)] —
  `source/contrib/pageinspect/heapfuncs.c:391-392`.
- [ISSUE-correctness: tupdesc fetched fresh at decode time can
  disagree with bytea's pre-ALTER layout (nit)].
- [ISSUE-defense-in-depth: `heap_tuple_infomask_flags` requires
  superuser despite touching no relation (nit)].
- [ISSUE-correctness: `t_infomask2 & HEAP_NATTS_MASK` lower than
  tupdesc silently truncates to ADD-COLUMN-style NULL fill (maybe)].

### btreefuncs.c

- [ISSUE-security: surfaces index-key on-disk bytes verbatim → RLS
  bypass for indexed columns (likely)].
- [ISSUE-correctness: bytea-path `PageGetItem` not preceded by
  explicit `lp_off+lp_len ≤ BLCKSZ` check (maybe)].
- [ISSUE-correctness: no `indisvalid` check; mid-CIC inspection
  uncertain (nit)].
- [ISSUE-api-shape: `bt_metap` SQL rowtype check exists since 1.8;
  pre-1.8 silently mis-mapped columns (nit)].
- [ISSUE-defense-in-depth: inconsistent error wording: "pageinspect
  functions" vs "raw page functions" in same file (nit)].
- [ISSUE-correctness: !heapkeyspace heuristic may mis-classify
  pivot tuples on pre-PG12 indexes (nit)] —
  `source/contrib/pageinspect/btreefuncs.c:568`.

### brinfuncs.c / ginfuncs.c / gistfuncs.c / hashfuncs.c / fsmfuncs.c

- [ISSUE-correctness: brin bytea not cross-validated against
  `indexRelid`'s BrinDesc (nit)].
- [ISSUE-correctness: brin no `lp_off+lp_len` bounds check before
  `PageGetItem` (likely)].
- [ISSUE-security: brin output-functions invoked on attacker bytes
  (maybe)].
- [ISSUE-security: BRIN summaries leak min/max-style distribution
  for RLS rows (likely)].
- [ISSUE-correctness: GIN `ginPostingListDecode` called on
  potentially-malicious bytes; nbytes from page → over-read risk
  (likely)].
- [ISSUE-security: GIN leaf-pages leak inverted-index keys
  (lexemes, jsonb paths) for RLS-filtered rows (likely)].
- [ISSUE-correctness: GIN pending-list invisible to
  `gin_leafpage_items` (nit)].
- [ISSUE-correctness: GiST bytea + regclass not cross-validated;
  may crash output fns (likely)].
- [ISSUE-correctness: GiST `IndexTupleSize` from on-page bytes used
  as `memcpy` length without explicit upper bound (maybe)].
- [ISSUE-security: GiST keys leak geometry/range/inet/tsquery data
  — particularly impactful for geo PII (likely)].
- [ISSUE-security: GiST output-fn call on attacker bytes (maybe)].
- [ISSUE-defense-in-depth: `GIST_PAGE_ID` magic check is good
  pattern to replicate (nit, positive)].
- [ISSUE-security: hash_page_items leaks per-row hashes; reversible
  for low-cardinality columns (maybe)].
- [ISSUE-correctness: `_hash_ovflblkno_to_bitno` relies on
  downstream error (nit)].
- [ISSUE-correctness: hash no `indisvalid` check (nit)].
- [ISSUE-defense-in-depth: hashfuncs is the most-hardened
  pageinspect bytea-decoder (magic+version+special-size+page-type-
  mask) (nit, positive)].
- [ISSUE-defense-in-depth: fsm no "is this actually FSM" check;
  mis-identified input → confusing-but-harmless output (nit)].
