# pageinspect.md — `pageinspect.h` + `rawpage.c`

Covers `source/contrib/pageinspect/pageinspect.h` (30 lines, declarations
only) and `source/contrib/pageinspect/rawpage.c` (377 lines, the foundation
that every per-AM file in this module depends on).

## One-line summary

`get_raw_page()` copies one 8 KB block out of shared buffers as a `bytea`
under a `BUFFER_LOCK_SHARE`; this is the choke-point that every other
pageinspect function reads from, and the hard `superuser()` gate that
makes the whole module a superuser-only debug surface.

## Public API / entry points

- `get_raw_page(text relname, int4 blkno)` — `source/contrib/pageinspect/rawpage.c:71`
  (legacy v1.8 entry).
- `get_raw_page_1_9(text relname, bigint blkno)` — `source/contrib/pageinspect/rawpage.c:49`
  (v1.9+ takes int8 blkno).
- `get_raw_page_fork(text relname, text forkname, int4 blkno)` —
  `source/contrib/pageinspect/rawpage.c:126`.
- `get_raw_page_fork_1_9(text relname, text forkname, bigint blkno)` —
  `source/contrib/pageinspect/rawpage.c:100`.
- `page_header(bytea)` — `source/contrib/pageinspect/rawpage.c:246`,
  decodes `PageHeaderData` (LSN, checksum, flags, lower/upper/special,
  pageSize, layoutVersion, prune_xid).
- `page_checksum(bytea, int4)` / `page_checksum_1_9(bytea, int8)` —
  `source/contrib/pageinspect/rawpage.c:373` / `:364`, calls
  `pg_checksum_page()` against the supplied bytea + the user-supplied
  block number (because checksum is salted with blkno).
- C export `Page get_page_from_raw(bytea *raw_page)` —
  `source/contrib/pageinspect/rawpage.c:214`; the shared 8-byte-aligned
  copier consumed by every per-AM decoder. Validates that
  `VARSIZE_ANY_EXHDR(raw_page) == BLCKSZ` and errors otherwise
  (`source/contrib/pageinspect/rawpage.c:222`). [verified-by-code]

## Key invariants

- INV-1: Every entry point is gated by `if (!superuser())` —
  `source/contrib/pageinspect/rawpage.c:153, 261, 345`. The error
  message is "must be superuser to use raw page functions"
  [verified-by-code].
- INV-2: The bytea returned by `get_raw_page` is exactly `BLCKSZ`
  payload bytes plus `VARHDRSZ` (4-byte header); `get_page_from_raw`
  re-copies into a maxaligned palloc'd `Page` so 8-byte aligned reads
  (`PageHeaderData` requires MAXALIGN=8) don't fault on machines where
  `palloc` returns 4-byte-aligned `varlena` payload —
  `source/contrib/pageinspect/rawpage.c:206-213` (comment) [from-comment].
- INV-3: Block number must be in `[0, MaxBlockNumber]` AND
  `< RelationGetNumberOfBlocksInFork()` — checked twice
  (`:55, :110, :178`) [verified-by-code]. `RelationGetNumberOfBlocksInFork`
  flushes any in-flight extension count; this is the bounds-check that
  prevents `get_raw_page('tbl', 999999999)` from reading past EOF.
- INV-4: Refuses non-storage relkinds via `RELKIND_HAS_STORAGE`
  (`:161`) — e.g. views, composite types — and refuses other-session
  temp relations via `RELATION_IS_OTHER_TEMP` (`:173`)
  [verified-by-code].
- INV-5: Reads are done under `BUFFER_LOCK_SHARE` via
  `ReadBufferExtended(... RBM_NORMAL ...)` then `LockBuffer(buf,
  BUFFER_LOCK_SHARE)` (`:191-192`) and immediately
  `UnlockReleaseBuffer` after the `memcpy` (`:196`). The page contents
  are a snapshot; nothing in the bytea reflects later mutations.

## Notable internals

**Copy semantics.** `get_raw_page_internal` palloc's `BLCKSZ + VARHDRSZ`
(`:185`), grabs a share lock on the buffer, `memcpy`'s 8192 bytes out
(`:194`), releases. There is no zero-copy path. The user gets a
detached snapshot; the buffer is unpinned by the time the SRF returns
to the executor.

**Two-step alignment dance.** `get_raw_page` returns a `bytea` whose
payload sits 4 bytes into the palloc allocation. Per-AM decoders MUST
call `get_page_from_raw` (`:214`), which `palloc(BLCKSZ)` and
`memcpy`'s again to get 8-byte alignment safe for `PageHeader` field
reads. Bypassing this and casting `VARDATA_ANY(raw_page)` directly to
`PageHeader` is a latent UB hazard on strict-alignment platforms.

**Checksum re-computation, not re-verification.**
`page_checksum_internal` (`:338`) recomputes
`pg_checksum_page(page, blkno)` from supplied bytes + supplied
blkno; it does NOT compare to the stored `pd_checksum` and does NOT
verify checksums are even enabled on the cluster. This is intentional
(the function is the *building block* for verifying), but it means a
caller who passes a wrong blkno (or a fabricated bytea) silently gets
a wrong-but-confident result.

**Version-aware tuple shape.** `page_header` looks at the declared
return rowtype to decide whether to emit int2 (pre-1.10) or int4
(1.10+) lower/upper/special, and text-LSN (pre-1.2) vs `pg_lsn` —
`source/contrib/pageinspect/rawpage.c:278-313` [verified-by-code].
Multiple `Assert()`s would `PANIC` on cassert builds if the rowtype
is inconsistent.

## Trust boundary / Phase D surface

**The single gate is `superuser()`** at the top of every C function
(`:153, :261, :345`). Unlike pgstattuple, there is **no
`pg_stat_scan_tables` `GRANT` discipline in any `pageinspect--*.sql`
script** [verified-by-code: `grep -n REVOKE /Users/matej/Work/.../source/contrib/pageinspect/*.sql`
returns nothing]. The C-level superuser check is the whole story; the
SQL extension is effectively unrevokeable downward — a DBA cannot
"grant pageinspect to monitoring role" the way they can with
pgstattuple. To delegate, you must either (a) wrap each function in a
SECURITY DEFINER and grant the wrapper, or (b) hand the user
`SUPERUSER`. There's no middle ground.

**[ISSUE-defense-in-depth: pageinspect has no `pg_stat_scan_tables`
parallel; admins cannot delegate without writing SECDEF wrappers
(likely)]**

**RLS bypass.** `get_raw_page` returns the raw 8 KB block. Every tuple
on that page — including rows that an RLS policy would normally
filter out — is in the bytea, in clear. `heap_page_items` on the
result then exposes them as columns. The superuser check is the only
defense; for an installation that's granted pageinspect via SECDEF
wrappers, this is the canary surface to audit.
**[ISSUE-security: `get_raw_page` is a full RLS bypass for anyone with
EXECUTE on it; if a DBA wraps it in SECDEF to share with monitoring,
they have effectively granted "read all RLS-protected tables"
(confirmed)]**

**Bounds-checking discipline (good).** `:55, :110, :178`: the int64
blkno is validated against `[0, MaxBlockNumber]` AND against
`RelationGetNumberOfBlocksInFork()` BEFORE the `ReadBufferExtended`
call. Bogus block numbers cannot read random kernel pages or
trigger an unbounded relation extension. **The check at `:178` runs
after relkind/temp checks** — order is correct.

**`page_checksum` does not bounds-check the bytea content.** It calls
`get_page_from_raw` (which only checks the bytea is exactly BLCKSZ)
and then trusts `pd_pagesize_version` enough to pass to
`pg_checksum_page`. `pg_checksum_page` itself reads through
`((PageHeader)page)->pd_checksum` and computes a 16-bit FNV-style
checksum over the page bytes; no further bounds reads happen, so a
fabricated bytea produces garbage-but-not-crashing output. [inferred
from `pg_checksum_page` being checksum-only over the fixed-size 8 KB
window; not independently verified in this read].

**Auto-vacuum interaction (no issue).** `AccessShareLock` + buffer
`SHARE` lock means a concurrent VACUUM that's pruning the page will
be serialized against the bytea copy; the snapshot the user sees is
post-prune if VACUUM beat us to the lock, pre-prune otherwise. No
torn reads.

**CONCURRENTLY-built index.** `rawpage.c` doesn't care about
`indisready` / `indisvalid` — it pulls raw bytes from any
`RELKIND_HAS_STORAGE` relation. So `get_raw_page` works against an
in-progress CIC index. Per-AM decoders later may complain (e.g.
`btreefuncs.c` doesn't, but `pgstatindex` does). **[ISSUE-correctness:
get_raw_page on an indisvalid=false index returns bytes that the
btreefuncs decoder will happily process; results may be misleading
(nit)]**

**page_header version drift.** The Assert pattern at `:294-296,
:303-305` will crash a cassert build if the catalog rowtype goes out
of sync with the source. On non-assert builds, the `default:` arm
errors cleanly (`:311`). No security impact, but it's a sign that
the version-coupling between the SQL-side rowtype and the C decoder
is fragile.

## Cross-references

- `source/src/include/storage/bufpage.h` — `PageHeaderData`,
  `PageGetLSN`, `PageGetPageSize`, `PageGetPageLayoutVersion`.
- `source/src/backend/storage/page/checksum.c` — `pg_checksum_page`.
- `source/src/backend/storage/buffer/bufmgr.c` —
  `ReadBufferExtended`, `LockBuffer`, `UnlockReleaseBuffer`.
- `knowledge/files/contrib/amcheck/` (A12-1, sibling) — amcheck uses
  the same buffer-lock pattern for its index reads but operates on
  parsed pages, not bytea.
- `knowledge/files/contrib/pgstattuple/pgstattuple.c.md` — the
  contrast: same author tradition (Nagayasu), but pgstattuple has
  `REVOKE … FROM PUBLIC` + `GRANT … TO pg_stat_scan_tables`, while
  pageinspect has only hardcoded `superuser()`.

<!-- issues:auto:begin -->
- [Issue register — `pageinspect`](../../../issues/pageinspect.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-security: `get_raw_page` is an RLS bypass primitive; if a
  DBA delegates pageinspect via SECDEF, they must understand they
  have granted "read every tuple regardless of policy"
  (confirmed)]** — `source/contrib/pageinspect/rawpage.c:191-196`.
- **[ISSUE-defense-in-depth: pageinspect lacks any
  `pg_stat_scan_tables` GRANT pattern, unlike pgstattuple; no graceful
  delegation path exists (likely)]** — no REVOKE/GRANT in any
  `pageinspect--*.sql`.
- **[ISSUE-correctness: `get_raw_page` does not refuse indexes with
  `indisvalid = false`; per-AM decoders may produce misleading output
  (nit)]** — `source/contrib/pageinspect/rawpage.c:161-166` only
  checks `RELKIND_HAS_STORAGE`.
- **[ISSUE-api-shape: `page_checksum` recomputes rather than verifies;
  callers passing a wrong `blkno` get a silently-wrong checksum
  (nit, documented behavior)]** —
  `source/contrib/pageinspect/rawpage.c:338-360`.
- **[ISSUE-documentation: the `superuser()` check is sometimes
  duplicated (e.g. `page_checksum_internal` AND its caller path), but
  not consistently — `get_page_from_raw` itself has no check because
  it's static and the C function entry points already gate
  (nit)]** — `source/contrib/pageinspect/rawpage.c:214` has no
  recheck; OK because callers gate, but a future caller could forget.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pageinspect.md](../../../subsystems/contrib-pageinspect.md)
