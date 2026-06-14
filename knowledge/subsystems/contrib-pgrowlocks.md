# contrib-pgrowlocks (row-level lock inspector)

- **Source path:** `source/contrib/pgrowlocks/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.2` (per `pgrowlocks.control`)
- **Trusted:** no (per-relation `SELECT` privilege or
  `pg_stat_scan_tables` membership)

## 1. Purpose

Identify every row currently held under a row-level lock
(`SELECT FOR UPDATE / FOR SHARE / FOR NO KEY UPDATE / FOR KEY
SHARE`) on a heap table. Resolves the "which transactions are
blocking which rows" question that `pg_locks` (page/relation
granularity) cannot answer. The canonical first probe when an
application reports phantom locks or "I can't update this row
but nobody else seems to be."

## 2. SQL surface — one function

```sql
SELECT * FROM pgrowlocks('schema.table');
```

Returns one row per **locked** heap tuple:

| Column | Meaning |
|---|---|
| `locked_row` | the TID of the locked tuple |
| `locker` | xmax (the locker XID or MultiXact ID) |
| `multi` | bool — true if `locker` is a MultiXact ID |
| `xids[]` | for multi: the member XIDs |
| `modes[]` | for multi: each member's lock mode |
| `pids[]` | for multi: PIDs of the locker backends (NULL if no live backend) |

[verified-by-code `pgrowlocks.c:51` PG_FUNCTION_INFO_V1 registration]

## 3. Mental model — a seq-scan that reads xmax

The implementation is a textbook heap walk:

1. `table_beginscan(rel, GetActiveSnapshot(), 0, NULL, SO_NONE)`
   [verified-by-code `pgrowlocks.c:118`].
2. For each visible tuple:
   - `LockBuffer(hscan->rs_cbuf, BUFFER_LOCK_SHARE)`
     [verified-by-code `pgrowlocks.c:131`].
   - `HeapTupleSatisfiesUpdate(tuple, GetCurrentCommandId(false),
     hscan->rs_cbuf)` [verified-by-code `pgrowlocks.c:134`].
   - If the result is `TM_BeingModified`, the row is held by
     an active locker; emit a row.
3. If `t_infomask & HEAP_XMAX_IS_MULTI`, decode the
   MultiXact membership via `GetMultiXactIdMembers` and
   populate the `xids[] / modes[] / pids[]` arrays.

The buffer lock is acquired SHARED for each tuple's HTSU call
because HTSU may inspect commit-log state and needs a stable
view of the tuple header.

## 4. Lock-mode decoding

The `t_infomask` and `t_infomask2` bits encode the lock mode
even for non-multi lockers. The output `modes[]` array maps:

- `KeyShareLock` — `SELECT FOR KEY SHARE`
- `ShareLock` — `SELECT FOR SHARE`
- `NoKeyExclusiveLock` — `SELECT FOR NO KEY UPDATE`
- `ExclusiveLock` — `SELECT FOR UPDATE`
- `Update` — the row's xmax came from an actual UPDATE/DELETE
- `For Key Share / For Share / For Update / For No Key Update`
  for the explicit-locking flavors

For MultiXact lockers, every member's mode is decoded
independently — a single row can be lock-held by 3 transactions
each at a different mode.

## 5. Heap AM only

[verified-by-code `pgrowlocks.c:100-102`]

```c
ereport(ERROR,
        (errcode(ERRCODE_FEATURE_NOT_SUPPORTED),
         errmsg("only heap AM is supported")));
```

The function works only on plain heap tables. Foreign tables,
table-access-method extensions, partitioned tables (without
descending into children), and indexes all ERROR.

## 6. Permission model

[verified-by-code `pgrowlocks.c:108-115`]

- `SELECT` privilege on the target relation, OR
- membership in the predefined `pg_stat_scan_tables` role.

The latter is the production pattern — monitoring users get
`pg_stat_scan_tables` and can inspect locks across all tables
without needing per-table `SELECT` grants.

## 7. Cost characteristics

- **Full sequential scan** of the target relation. ~50 MB/s
  per-spindle reading, plus the per-tuple HTSU overhead.
- **Buffer-share-lock per tuple** + **commit-log probe** per
  tuple. On a hot OLTP table with many locks, the share locks
  can be observed by writers as latency hiccups.
- **MultiXact decode** is the slow path — fetches members
  from `pg_multixact/`. A heavily-multi-locked table makes the
  scan I/O-bound on the MultiXact pages.

Acceptable on a problem-symptom-investigation. Not suitable
for a periodic `cron` job on a large hot table.

## 8. Production-use guidance

- **Pair with `pg_stat_activity` to identify the locker
  process.** The output `pids[]` array shows the backend PID,
  not the application identity. Join on `pid` to find query +
  user.
- **MultiXact decode failures (`{0}`, `{transient upgrade
  status}`)** [verified-by-code `pgrowlocks.c:163-167`] are
  legitimate edge cases — old MultiXact members that have been
  truncated by VACUUM. Treat as "no useful detail" rather than
  corruption.
- **The function returns currently-held locks, not historical
  ones.** A lock acquired and released between two calls is
  invisible. Use `pg_locks` + log-based audit for historical
  tracking.

## 9. Invariants

- **[INV-1]** Only heap AM is supported; other relkinds
  ERROR with `ERRCODE_FEATURE_NOT_SUPPORTED`.
- **[INV-2]** Buffer share-lock held per tuple during HTSU.
- **[INV-3]** Output is currently-held locks at scan time;
  not transactional, not historical.
- **[INV-4]** Permission gate is `SELECT` OR
  `pg_stat_scan_tables` membership.
- **[INV-5]** MultiXact members with no live backend produce
  NULL PID, not an error.

## 10. Useful greps

- The HTSU call site:
  `grep -n 'HeapTupleSatisfiesUpdate' source/contrib/pgrowlocks/pgrowlocks.c`
- MultiXact membership decoding:
  `grep -n 'GetMultiXactIdMembers' source/contrib/pgrowlocks/pgrowlocks.c`
- Permission check:
  `grep -n 'pg_class_aclcheck\|ROLE_PG_STAT_SCAN_TABLES' source/contrib/pgrowlocks/pgrowlocks.c`

## 11. Cross-references

- `.claude/skills/debugging/SKILL.md` — pgrowlocks is the
  canonical "who's holding this row?" probe.
- `.claude/skills/locking/SKILL.md` — row-level lock modes
  (KeyShare/Share/NoKeyExclusive/Exclusive); MultiXact
  semantics.
- `knowledge/data-structures/multixactid.md` — the MultiXact
  ID this function decodes when `infomask & HEAP_XMAX_IS_MULTI`.
- `knowledge/subsystems/access-heap.md` — `HeapTupleSatisfiesUpdate`
  + visibility semantics.
- `knowledge/idioms/heaptuple-update-chain.md` — adjacent
  topic; xmax semantics on chain members.
- `source/contrib/pgrowlocks/pgrowlocks.c` — full
  implementation (280 LOC).
