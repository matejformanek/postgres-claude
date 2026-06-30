# `contrib/pageinspect/rawpage.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~377
- **Source:** `source/contrib/pageinspect/rawpage.c`

The pageinspect "foundation" file: provides the central
`get_raw_page()` family that copies an 8 KB page out of shared
buffers as a `bytea`, plus the `page_header()` and `page_checksum()`
helpers that decode the page header from that bytea. Every per-AM
file in pageinspect (`heapfuncs.c`, `btreefuncs.c`, etc.) calls
`get_page_from_raw()` on a bytea produced here. The C-level
`superuser()` check at the top of every entry point makes this a
hard superuser-only debug surface. [verified-by-code]

> **Note:** This file is also discussed at the extension-level in
> `knowledge/files/contrib/pageinspect/pageinspect.md`, which bundles
> `pageinspect.h` + `rawpage.c`. This doc is the per-file form,
> mirroring the naming convention used by the per-AM file docs.

## API / entry points

- `get_raw_page_1_9(text relname, int8 blkno) RETURNS bytea`
  (rawpage.c:46-63) — current entry. Range-checks `blkno` against
  `MaxBlockNumber`, dispatches to `get_raw_page_internal`.
  [verified-by-code]
- `get_raw_page(text relname, int4 blkno) RETURNS bytea`
  (rawpage.c:68-90) — legacy entry for pre-1.9 extension. Checks
  `PG_NARGS() == 2` defensively because early-8.4-beta installs
  defined a 3-arg variant. [verified-by-code] [from-comment]
- `get_raw_page_fork_1_9(text, text forkname, int8 blkno) RETURNS
  bytea` (rawpage.c:97-118) — same but for non-MAIN forks (fsm, vm,
  init). Forkname parsed via `forkname_to_number`.
- `get_raw_page_fork(text, text, int4)` (rawpage.c:123-139) — legacy
  4-byte-blkno entry, no range check on blkno here (relies on
  internal). [verified-by-code]
- `get_raw_page_internal` (rawpage.c:144-201) — the workhorse.
  Superuser gate, relation_openrv with AccessShareLock,
  RELKIND_HAS_STORAGE check, RELATION_IS_OTHER_TEMP reject, range-
  check via `RelationGetNumberOfBlocksInFork`, then
  `ReadBufferExtended` + `LockBuffer(BUFFER_LOCK_SHARE)` + memcpy
  + `UnlockReleaseBuffer`. [verified-by-code]
- `get_page_from_raw(bytea *raw_page) → Page` (rawpage.c:214-234) —
  C-level helper exposed via `pageinspect.h`. Returns a palloc'd,
  MAXALIGN-correct copy. Required because `VARDATA(bytea)` starts
  4 bytes into a palloc'd value, breaking 8-byte alignment that
  `PageHeaderData` needs. [verified-by-code] [from-comment]
- `page_header(bytea) RETURNS record` (rawpage.c:246-327) — decodes
  pd_lsn, pd_checksum, pd_flags, pd_lower/upper/special, page
  size, layout version, pd_prune_xid. Handles two on-disk-compat
  variants (TEXTOID-vs-LSNOID lsn; INT2OID-vs-INT4OID
  lower/upper/special). [verified-by-code]
- `page_checksum_1_9` / `page_checksum`
  (rawpage.c:335-376) — computes `pg_checksum_page(page, blkno)`
  for a passed-in bytea + blkno. Returns NULL on `PageIsNew`.
  [verified-by-code]

## Notable invariants / details

- **Superuser gate at every entry**: rawpage.c:153, 261, 345.
  Three independent `if (!superuser()) ereport(ERROR, …
  ERRCODE_INSUFFICIENT_PRIVILEGE)` checks. There is no per-table
  GRANT path — only superuser, or a SECURITY DEFINER wrapper.
  [verified-by-code]
- **Page is copied under BUFFER_LOCK_SHARE** (rawpage.c:191-196).
  Lock duration is one memcpy then UnlockReleaseBuffer. Any
  concurrent writer waiting on exclusive will see a brief stall.
  [verified-by-code]
- **Temp tables of other sessions are rejected**
  (rawpage.c:173-177) because their pages live in the owning
  session's local buffers; reading from shared buffers would
  return stale or wrong data. The error code is
  `ERRCODE_FEATURE_NOT_SUPPORTED`. [verified-by-code] [from-comment]
- **`get_raw_page` is the central RLS-bypass primitive**: it
  returns the entire 8 KB block including tuples that would be
  filtered by RLS, security barriers, or column-level GRANT. Only
  the superuser gate stops a user from reading another role's
  rows. [verified-by-code] [ISSUE-security: RLS bypass by design
  (likely)]
- The bytea returned is a **verbatim 8 KB image** including hole +
  special area. Decoders downstream trust the page's internal
  invariants (`pd_lower`, `pd_upper`, item-id array) — fabrication
  of a bytea and passing it to a per-AM decoder can crash the
  backend or read arbitrary palloc memory if the decoder doesn't
  re-verify. `heapfuncs.c` re-verifies; some per-AM files don't.
  [verified-by-code] [from-comment]
- `get_page_from_raw` palloc's a fresh BLCKSZ buffer and memcpy's
  in (rawpage.c:229-231). Caller owns the result. Used as the
  alignment fixer for any function that touches PageHeaderData.
  [verified-by-code]
- Backward-compat type handling in `page_header` (rawpage.c:
  278-310): both LSN-as-text and LSN-as-pg_lsn shapes are
  supported, and both INT2 and INT4 variants of the offset fields.
  This survives pageinspect upgrades across major versions without
  the SQL-side `ALTER EXTENSION UPDATE` having been run.
  [verified-by-code]

## Potential issues

- rawpage.c:153, 261, 345. The **three superuser checks are
  duplicated** rather than centralised in `get_page_from_raw`. A
  future entry point added without the manual check would skip
  the gate. [ISSUE-style: superuser check copy-pasted three times
  (nit)]
- rawpage.c:185-197. The memcpy of 8 KB under buffer lock is fine
  but allocates `BLCKSZ + VARHDRSZ` in caller's memory context
  before acquiring the lock — so the allocation can ereport(OOM)
  outside of the lock window. Good ordering. [verified-by-code]
- rawpage.c:191. `RBM_NORMAL` means the buffer is read in if not
  resident. A user can therefore force I/O on any block of any
  relation, which is a minor side-channel for blkno-existence
  probing. Mitigated by the superuser gate. [ISSUE-security:
  user-controllable I/O on arbitrary blocks (nit)]
- rawpage.c:312. `elog(ERROR, "incorrect output types")` is an
  internal-style error — a user calling `page_header` against a
  type-mangled record-shape (e.g., via stale pg_proc) gets a
  programmer-style message rather than a hint. Unlikely in
  practice (would require catalog corruption). [ISSUE-style:
  internal elog (nit)]
- rawpage.c:357. `PageIsNew(page)` returns NULL from
  `page_checksum`. Combined with the lack of input validation that
  the bytea is actually a page header, a fabricated all-zero
  16-byte payload at `VARDATA` triggers PageIsNew → NULL silently.
  Safe but quiet. [ISSUE-style: silent NULL on garbage input
  (nit)]
- rawpage.c:55-58, 110-113. `blkno < 0 || blkno > MaxBlockNumber`
  check exists in the `_1_9` variants but NOT in the legacy
  `get_raw_page_fork` (line 130-138). Legacy code relies on
  `RelationGetNumberOfBlocksInFork` to bound. [ISSUE-style: missing
  range check in legacy variant (nit)]
- rawpage.c:282. The text-LSN format uses `"%X/%08X"` — the lower
  half is fixed-width zero-padded, the upper half is not. Matches
  the historical pg_lsn text format. [verified-by-code]
- rawpage.c:178-182. Block-out-of-range error includes the relation
  name; intentional, useful, and matches PG style. No info leak
  beyond what `pg_class` already exposes.

## Cross-references

- `knowledge/issues/pageinspect.md` — already lists rawpage findings
  including the RLS-bypass headline. This per-file doc should be
  reconciled with `knowledge/files/contrib/pageinspect/pageinspect.md`
  (which bundles `pageinspect.h` + `rawpage.c`).
- `source/src/include/storage/bufmgr.h` — `ReadBufferExtended`,
  `LockBuffer`, `BUFFER_LOCK_SHARE`.
- `source/src/backend/storage/page/bufpage.c` — `PageHeaderData`
  layout that `page_header` decodes.
- Per-AM decoder files: `heapfuncs.c`, `btreefuncs.c`,
  `brinfuncs.c`, `ginfuncs.c`, `gistfuncs.c`, `hashfuncs.c`,
  `fsmfuncs.c`.

<!-- issues:auto:begin -->
- [Issue register — `pageinspect`](../../../issues/pageinspect.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pageinspect.md](../../../subsystems/contrib-pageinspect.md)
