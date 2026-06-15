---
path: src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c
anchor_sha: e18b0cb7344
loc: 140
depth: read
---

# src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c

## Purpose

Reference implementation + regression test for the **custom WAL resource
manager** extension API. Registers a minimal `RmgrData` via `RegisterCustomRmgr`
in `_PG_init`, exposes one SQL function to insert a WAL record under that
rmgr, and implements the three required callbacks (`redo`, `desc`, `identify`).
Real users of this API are extensions like `bgworker_rmgr`, `pg_failover_slots`,
and other replicated state stores that need to write their own WAL records.
`[from-comment]` `test_custom_rmgrs.c:3-5,12-14`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `:65` | Calls `RegisterCustomRmgr(RM_TESTCUSTOMRMGRS_ID, &testcustomrmgrs_rmgr)`. Must run from `shared_preload_libraries` or registration ERRORs (`:69-71`) |
| `testcustomrmgrs_redo(XLogReaderState *)` | `:82` | No-op redo; PANIC on unknown info code |
| `testcustomrmgrs_desc(StringInfo, XLogReaderState *)` | `:91` | Formats payload size + bytes for `pg_waldump` |
| `testcustomrmgrs_identify(uint8 info)` | `:106` | Returns `"TEST_CUSTOM_RMGRS_MESSAGE"` for known op |
| `test_custom_rmgrs_insert_wal_record(text)` | `:120` | SQL: `XLogBeginInsert / XLogRegisterData / XLogSetRecordFlags(XLOG_MARK_UNIMPORTANT) / XLogInsert`; returns the resulting `pg_lsn` |

## Internal landmarks

- `RM_TESTCUSTOMRMGRS_ID` is aliased to `RM_EXPERIMENTAL_ID` (`:47`) — the
  reserved scratch slot. Real extensions must reserve a unique ID via the wiki
  (link at `:43-45`).
- `xl_testcustomrmgrs_message` (`:32-36`) — FLEXIBLE_ARRAY_MEMBER payload
  layout. `SizeOfTestCustomRmgrsMessage` (`:38`) = `offsetof(.., message)`,
  the standard pattern for variable-length WAL record bodies.
- `XLogRegisterData` is called twice in
  `test_custom_rmgrs_insert_wal_record` (`:131-132`) — once for the fixed-size
  header (size field), once for the variable-size payload. The two registrations
  are concatenated by `XLogInsert` into the record body.
- `XLogSetRecordFlags(XLOG_MARK_UNIMPORTANT)` (`:135`) — this flag tells WAL
  sync logic the record is non-critical (won't force-flush synchronous standbys).

## Invariants & gotchas

- **TEST MODULE — never load in production**, although the API itself is
  production-grade and used by real extensions.
- **Rmgr ID must be in the custom range.** Built-in IDs are
  `RM_XLOG_ID .. RM_LOGICALMSG_ID` (see `rmgrlist.h`); custom range starts at
  `RM_EXPERIMENTAL_ID = 128`. Collisions are silent corruption — two extensions
  with the same ID will mis-decode each other's records.
- **Registration is per-postmaster and irreversible.** `RegisterCustomRmgr`
  must run during `_PG_init` from `shared_preload_libraries` so all backends
  and the startup process see the same registration. There is no unregister
  API — once registered, the rmgr lives for the postmaster's lifetime.
- **`rm_redo` must be deterministic and idempotent.** The startup process may
  replay the same record after a crash; the no-op redo here is safe only
  because the test asserts no on-disk state.
- `rm_decode` is `NULL` (omitted from the `RmgrData` initializer at `:55-60`),
  so logical decoding will skip these records. Extensions that need logical
  output must supply it.
- `payload` is read via `VARDATA_ANY` / `VARSIZE_ANY_EXHDR` (`:123-124`) — the
  standard short/long varlena-safe accessor pair.

## Cross-refs

- `knowledge/subsystems/wal-and-xlog.md` — RmgrData dispatch, custom rmgr
  registration, record layout.
- `knowledge/files/src/include/access/xlog_internal.h.md` — `RmgrData` struct,
  `RegisterCustomRmgr` prototype, `RM_*_ID` ranges.
- `knowledge/files/src/include/access/xloginsert.h.md` — `XLogBeginInsert /
  XLogRegisterData / XLogInsert / XLogSetRecordFlags` API.
- `knowledge/idioms/bgworker-and-extensions.md` — `shared_preload_libraries`
  loading model that custom rmgrs depend on.
