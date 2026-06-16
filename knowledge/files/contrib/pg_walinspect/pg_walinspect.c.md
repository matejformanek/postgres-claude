# `pg_walinspect/pg_walinspect.c` — WAL-record introspection for online clusters

**Verified against source pin `4b0bf0788b0`** (path: `source/contrib/pg_walinspect/pg_walinspect.c`)

## Role

SQL-callable WAL reader: between an `(start_lsn, end_lsn)` range, return
per-record info (rmgr, length, FPI length, block refs, optionally raw
block data and FPI bytes) and aggregate stats per rmgr/record-type. The
in-process counterpart to the `pg_waldump` CLI; the comment at line
30-33 explicitly says "any code change or issue fix here, it is highly
recommended to give a thought about doing the same in pg_waldump tool as
well."

## Public API

Defined in `pg_walinspect--1.0.sql` and `pg_walinspect--1.0--1.1.sql`:

- `pg_get_wal_record_info(pg_lsn) -> record` — `source/contrib/pg_walinspect/pg_walinspect.c:473`
- `pg_get_wal_records_info(start_lsn pg_lsn, end_lsn pg_lsn) -> SETOF record` — `:602`
- `pg_get_wal_records_info_till_end_of_wal(pg_lsn) -> SETOF record` (compat) — `:831`
- `pg_get_wal_stats(start_lsn, end_lsn, per_record bool) -> SETOF record` — `:814`
- `pg_get_wal_stats_till_end_of_wal(pg_lsn, bool) -> SETOF record` (compat) — `:849`
- `pg_get_wal_block_info(start_lsn, end_lsn, show_data bool) -> SETOF record` — `:425`

All `REVOKE EXECUTE FROM PUBLIC` + `GRANT EXECUTE TO
pg_read_server_files` [verified-by-code] (`pg_walinspect--1.0.sql:25-118`,
`pg_walinspect--1.0--1.1.sql`).

## Invariants

- All functions validate LSNs via `ValidateInputLSNs`: `start_lsn ≤ current LSN`,
  `start_lsn ≤ end_lsn`, end_lsn clamped to current LSN
  (`source/contrib/pg_walinspect/pg_walinspect.c:525-544`).
- `InitXLogReaderState` rejects LSNs below `XLOG_BLCKSZ` (bootstrap
  page) and finds the first valid record at or after the requested LSN
  via `XLogFindNextRecord` [verified-by-code]
  (`source/contrib/pg_walinspect/pg_walinspect.c:109-145`).
- WAL reader uses `read_local_xlog_page_no_wait` — does NOT reserve a
  slot, can encounter read errors for historical WAL [from-comment lines
  150-157]; gracefully returns NULL on end-of-WAL.
- A per-record temporary memory context (`AllocSetContextCreate`) is
  used for both rec-info and block-info paths to bound the leak
  pattern (`source/contrib/pg_walinspect/pg_walinspect.c:440-462,
  564-591`); the docstring on `GetWALRecordInfo` says "This function
  leaks memory."
- `CHECK_FOR_INTERRUPTS()` called per record in the read loops
  (`source/contrib/pg_walinspect/pg_walinspect.c:447, 588, 797`).
- `pg_get_wal_block_info` accepts a `show_data` argument that controls
  whether raw block-data (`blk->data`) AND the restored FPI page
  (`RestoreBlockImage`) are emitted as `bytea`
  (`source/contrib/pg_walinspect/pg_walinspect.c:377-409`).

## Notable internals

- The compat functions `pg_get_wal_records_info_till_end_of_wal` and
  `pg_get_wal_stats_till_end_of_wal` are explicitly marked "removed in
  newer versions in 1.1, but they are kept around for compatibility"
  (`source/contrib/pg_walinspect/pg_walinspect.c:826-829`). They
  hard-clamp `end_lsn = GetCurrentLSN()`.
- `FillXLogStatsRow` computes percentages with a divide-by-zero guard
  on each total.
- `GetWALRecordInfo` always emits 11 columns; `GetWALBlockInfo` always
  20. Output schemas are encoded in the SQL install scripts.
- FPI bytes are restored into a stack-allocated `PGAlignedBlock buf`
  via `RestoreBlockImage`; the resulting page is then copied into a
  freshly palloc'd `bytea`
  (`source/contrib/pg_walinspect/pg_walinspect.c:392-406`).

## Trust-boundary / Phase D surface

This is **the most sensitive module in this slice from a Phase-D
perspective.** Block data and FPIs in WAL contain raw tuple bytes —
including pre-update versions, deleted tuples, and bytes from columns
the caller has no privileges to read at the SQL level.

1. **`show_data=true` returns raw block-data and FPI page bytes.** An
   attacker with execute on `pg_get_wal_block_info` and access to
   recent WAL can read:
   - DELETE'd tuple contents (the page-image FPI before vacuum)
   - UPDATE'd-from values (FPI before the update)
   - Heap tuples from tables they have no SELECT privilege on
   - Tuples that violated RLS for them
   The C-side has no per-relation privilege check; the gate is `GRANT
   EXECUTE TO pg_read_server_files`, which is a "read any data from
   the OS filesystem" role — semantically equivalent to bypassing all
   per-table privileges. So the model is self-consistent (already a
   superuser-equivalent role), but it's worth flagging that the
   `pg_read_server_files` role's documented purpose is "read files
   from server-side", and pg_walinspect extends that to "read
   pre-deletion / pre-update tuple data from WAL FPIs."
   [ISSUE-defense-in-depth: pg_get_wal_block_info(show_data=true)
   returns FPIs containing DELETE'd / pre-UPDATE tuple bytes that
   bypass RLS, column privs, and table SELECT; gated only by
   pg_read_server_files role (likely)]
   (`source/contrib/pg_walinspect/pg_walinspect.c:377-409, 425-467`).
2. **`pg_get_wal_record_info` / `pg_get_wal_records_info` emit `description`
   text** via `rm_desc(&rec_desc, record)`. The description format
   depends on the rmgr but for heap rmgrs it often includes
   transaction ids, offset numbers, and other internals. Less
   sensitive than block data but useful for transaction-existence
   probing
   (`source/contrib/pg_walinspect/pg_walinspect.c:217-247`).
3. **No CHECK_FOR_INTERRUPTS in `GetWALBlockInfo`'s per-block-ref loop.**
   The outer `pg_get_wal_block_info` loop checks per record (line 447),
   but a single record with `XLR_MAX_BLOCK_ID + 1 = 33` block refs
   does N=33 iterations without an interrupt check
   [verified-by-code]. Negligible in practice.
   [ISSUE-correctness: per-block-ref inner loop in GetWALBlockInfo has
   no CHECK_FOR_INTERRUPTS; bounded by ~33 iterations so trivial (nit)]
   (`source/contrib/pg_walinspect/pg_walinspect.c:284-416`).
4. **Memory allocation in `GetWALBlockInfo` for `flags` array** uses
   `palloc0_array(Datum, bitcnt)` where `bitcnt` is computed as
   `pg_popcount(&blk->bimg_info, sizeof(uint8))`, so at most 8. Safe.
5. **`pg_get_wal_record_info` operates on a single record but `InitXLogReaderState`
   reads ahead to find a valid record.** A caller can probe whether a
   given LSN is at a record boundary by observing whether the LSN is
   echoed back as `start_lsn` vs different. Negligible.
6. **Validation order**: in `pg_get_wal_record_info` (line 473), the
   validation `lsn > curr_lsn` is checked at line 488 BEFORE calling
   `get_call_result_type` and `InitXLogReaderState`. But the LSN < XLOG_BLCKSZ
   check happens INSIDE `InitXLogReaderState` (line 109) after the
   palloc/alloc of the reader. Tiny memory wasted on bad inputs, not
   a real issue.
7. **`XLogReaderAllocate` is freed via `XLogReaderFree`** at the end of
   each function. The intermediate `tmp_cxt` for per-record allocations
   is `MemoryContextReset`'d each iteration and `MemoryContextDelete`'d
   at exit — clean pattern.
8. **`elog(ERROR, "internal_error", ...)` after `RestoreBlockImage`
   failure** uses `errmsg_internal`. Looks fine; the error is genuinely
   internal (the WAL record's own errormsg_buf).

## Cross-refs

- `knowledge/subsystems/wal.md` — XLogReader, rmgr table, FPI semantics
- `knowledge/idioms/wal-and-xlog.md` — block ref structure
- `knowledge/files/contrib/pageinspect/` — A12, similar page-bytes exposure but for live pages
- `knowledge/files/contrib/amcheck/` — A12, similar bypass-MVCC pattern

<!-- issues:auto:begin -->
- [Issue register — `pg_walinspect`](../../../issues/pg_walinspect.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-defense-in-depth: show_data=true returns raw FPI page bytes — DELETE'd / pre-UPDATE tuples bypass RLS, column privs (likely)] — `source/contrib/pg_walinspect/pg_walinspect.c:377-409, 425-467`
2. [ISSUE-defense-in-depth: pg_get_wal_record_info description text leaks transaction internals to pg_read_server_files holders (nit)] — `source/contrib/pg_walinspect/pg_walinspect.c:217-247`
3. [ISSUE-correctness: per-block-ref inner loop has no CHECK_FOR_INTERRUPTS (bounded ~33 iters, nit) (nit)] — `source/contrib/pg_walinspect/pg_walinspect.c:284-416`
