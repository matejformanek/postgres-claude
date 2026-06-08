---
path: src/backend/access/rmgrdesc/standbydesc.c
anchor_sha: 4b0bf0788b0
loc: 140
depth: deep
---

# standbydesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/standbydesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 140

## Purpose

rmgr descriptor routines for `RM_STANDBY_ID` (`storage/ipc/standby.c`)
— the hot-standby support records: access-exclusive lock conflicts,
running-xacts snapshots, and cache invalidations. Also exports
`standby_desc_invalidations`, the **shared renderer for
SharedInvalidationMessage arrays** reused by `xactdesc.c` and
`heapdesc.c`. [from-comment, standbydesc.c:1-17, 99]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `standby_desc(buf, record)` | `standbydesc.c:46` | render LOCK / RUNNING_XACTS / INVALIDATIONS |
| `standby_identify(info)` | `standbydesc.c:78` | opcode → name |
| `standby_desc_invalidations(buf, nmsgs, msgs, dbId, tsId, relcacheInitFileInval)` | `standbydesc.c:100` | render a `SharedInvalidationMessage[]` (shared with xact/heap descs) |

## Internal landmarks

- **`standby_desc_running_xacts` (standbydesc.c:19)** decodes
  `xl_running_xacts`: `nextXid`, `latestCompletedXid`,
  `oldestRunningXid`, then the xid array, the `subxid_overflow` flag,
  and the trailing subxact array. This is the snapshot a standby uses to
  build its initial `KnownAssignedXids` set.
- **`standby_desc_invalidations` (standbydesc.c:100)** decodes each
  `SharedInvalidationMessage` by its `id` discriminant: ≥0 = catcache N;
  the negatives are CATALOG / RELCACHE / SMGR / RELMAP / SNAPSHOT /
  RELSYNC. SMGR and RELMAP are commented "not expected" in this context
  but printed anyway.

## Invariants & gotchas

- **`standby_desc_invalidations` is the canonical inval decoder** — the
  comment at standbydesc.c:99 ("also used by non-standby records having
  analogous invalidation fields") is why commit records (`xactdesc.c`)
  and inplace-update records (`heapdesc.c`) print invals identically.
  Any new `SharedInvalidationMessage` type must be taught here or it
  prints "unrecognized id".
- **The subxact array is contiguous with the main xid array** in
  `xl_running_xacts` — subxacts start at `xids[xcnt]`
  (standbydesc.c:42), a single flexible array split by count, not two
  separate arrays.
- **`relcacheInitFileInval`** triggers a special "relcache init file
  inval" prefix (standbydesc.c:112-114) — this is the standby's signal
  to nuke its `pg_internal.init` cache file, the same mechanism commit
  records use via `XactCompletionRelcacheInitFileInval`.

## Cross-refs

- Record structs: `src/include/storage/standbydefs.h`
  (`xl_running_xacts`, `xl_standby_locks`, `xl_invalidations`).
- Inval message types: `src/include/storage/sinval.h`.
- Backend redo: `standby.c::standby_redo`.
- Shared-inval consumers: `xactdesc.c.md`, `heapdesc.c.md`.
- Hot standby / running-xacts: `knowledge/subsystems/replication.md`.

## Tally

`[verified-by-code]=4 [from-comment]=2 [inferred]=0`
