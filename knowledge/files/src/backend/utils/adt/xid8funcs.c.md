# xid8funcs.c — `pg_snapshot` type and `pg_*_xact_id*` functions

## Purpose

Implements `pg_snapshot` (formerly `txid_snapshot` in PG ≤ 12) as a SQL-visible type, plus `pg_current_xact_id()`, `pg_current_snapshot()`, `pg_visible_in_snapshot()`, `pg_snapshot_xmin/xmax/xip()`, and `pg_xact_status()`. These give SQL-level access to the snapshot data normally consumed only by the MVCC machinery.

Source: `source/src/backend/utils/adt/xid8funcs.c` (684 lines).

## Key functions

- `TransactionIdInRecentPast` (98) — given a FullTransactionId, check it's within roughly the last 2^31 transactions (so wraparound-aware compares are still valid). Used by `pg_xact_status`. [verified-by-code]
- `cmp_fxid` (154) — qsort key for FullTransactionId. Unsigned compare. [verified-by-code]
- `sort_snapshot` (174) — sorts the xip array within a `pg_snapshot`. [verified-by-code]
- `is_visible_fxid` (188) — given an fxid and a snapshot, classic xmin/xmax/xip visibility test. [verified-by-code]
- `buf_init` (223), `buf_add_txid` (238), `buf_finalize` (249) — StringInfo builder for snapshot text output. [verified-by-code]
- `parse_snapshot` (266) — parses `xmin:xmax:xip1,xip2,...` text format. Bounds-checked: rejects xip count exceeding PG_SNAPSHOT_MAX_NXIP. [verified-by-code]
- `pg_current_xact_id` (335) — `GetTopFullTransactionId`. [verified-by-code]
- `pg_current_xact_id_if_assigned` (353) — like above but returns NULL when no xid assigned (avoids forcing one). [verified-by-code]
- `pg_current_snapshot` (371) — snapshot-of-now. [verified-by-code]
- `pg_snapshot_in` (421) / `pg_snapshot_out` (437) — text I/O. [verified-by-code]
- `pg_snapshot_recv` (469) / `pg_snapshot_send` (535) — binary. The recv enforces `nxip <= PG_SNAPSHOT_MAX_NXIP` and that xmin <= xmax. [verified-by-code]
- `pg_visible_in_snapshot` (556), `pg_snapshot_xmin` (570), `pg_snapshot_xmax` (583), `pg_snapshot_xip` (596). [verified-by-code]
- `pg_xact_status` (641) — returns 'in progress', 'committed', or 'aborted' for an xid8. [verified-by-code]

## Bounds and overflow defenses

- `StaticAssertDecl(MAX_BACKENDS * 2 <= PG_SNAPSHOT_MAX_NXIP, ...)` at line 80 — compile-time check that the snapshot xip array can hold every possible running xid. [verified-by-code]
- `parse_snapshot` rejects bad text input via the `escontext` soft-error path; no PANIC on bad input. [verified-by-code]
- `pg_snapshot_recv` validates the binary wire format strictly (nxip count + each xip in increasing order). [verified-by-code]

## Phase D notes

- **`TransactionIdInRecentPast` is the key correctness gate** for `pg_xact_status` — outside the "recent past" window, the clog entry may have been truncated, so the function returns NULL (or errors, depending on path). [verified-by-code:98]
- **`pg_current_xact_id_if_assigned` is the public "no side effects" reader** — important because just reading the current xid normally allocates one for the session, with full WAL implications. [verified-by-code:353]
- **64-bit type means no wraparound** — the underlying FullTransactionId has 64 bits, and snapshots are serialized as 64-bit values, so `pg_snapshot` text never needs to encode epoch information.

## Potential issues

- `[ISSUE-correctness: pg_xact_status returns NULL outside the "recent past" window; a monitoring tool querying status of old xids will see NULLs that are ambiguous between "aborted and truncated" and "still in progress, somehow". Documented but easy to misinterpret (low)]`.
- `[ISSUE-dos: parse_snapshot accepts arbitrary-length xip lists up to PG_SNAPSHOT_MAX_NXIP; an attacker submitting a huge snapshot via text I/O forces an O(n log n) sort on parse. Capped, so bounded DoS (low)]`.
- `[ISSUE-undocumented-invariant: pg_current_xact_id forces an xid assignment (and an entry into the commit log); a workload that calls this on every read-only query will silently consume xids (low; documented in user docs)]`.

Confidence: `[verified-by-code]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
