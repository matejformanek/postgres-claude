# contrib-pg_logicalinspect (logical-decoding snapshot inspector)

- **Source path:** `source/contrib/pg_logicalinspect/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `pg_logicalinspect.control`)
- **Trusted:** no (exposes replication internals)

## 1. Purpose

Inspect **serialized logical-decoding snapshots** stored in
`pg_logical/snapshots/`. Logical decoding builds historical
catalog snapshots so an output plugin can decode WAL records
that touched catalog state at past LSNs. These snapshots are
durable on disk; pg_logicalinspect surfaces their contents to
SQL.

Added in PG 17. Used for:
- **Debugging stuck logical replication** — "what does the
  snapshot at LSN X look like?"
- **Capacity planning** — measure snapshot size before
  enabling a heavy logical-decoding workload.
- **Research / education** — see how the consistent-snapshot
  algorithm progresses.

## 2. SQL surface

[verified-by-code `pg_logicalinspect.c:26-27`]

| Function | Returns |
|---|---|
| `pg_get_logical_snapshot_meta(filename)` | metadata (magic, version, crc, length) |
| `pg_get_logical_snapshot_info(filename)` | full snapshot state |

Inputs are snapshot filenames as found in
`pg_logical/snapshots/`. The filename encodes the LSN at
which the snapshot was taken.

## 3. The SnapBuildState — 4 phases

[verified-by-code `pg_logicalinspect.c:35-50`]

```c
get_snapbuild_state_desc(SnapBuildState state):
    SNAPBUILD_START              → "start"
    SNAPBUILD_BUILDING_SNAPSHOT  → "building"
    SNAPBUILD_FULL_SNAPSHOT      → "full"
    SNAPBUILD_CONSISTENT         → "consistent"
```

Logical decoding's snapshot construction walks through these
states:

1. **START** — no in-progress transactions visible; can't
   decode yet.
2. **BUILDING** — observed at least one running-xact record;
   collecting transaction info.
3. **FULL** — have a complete view of in-flight xids; can
   decode catalog-only changes.
4. **CONSISTENT** — all transactions that started before
   FULL state have committed; full decoding can begin.

Decoding cannot begin until **CONSISTENT**. A standby that's
"behind" in logical replication may still be in BUILDING.

## 4. The snapshot file format

Each snapshot file contains:

```
SnapBuildOnDisk {
    magic       uint32      = 0x51A1E001
    version     uint32      = 6 (as of PG 17)
    length      uint32      = total file size
    checksum    uint32      = CRC32C
}
SnapBuild {
    state, last_serialized_snapshot, xmin, xmax, ...
}
xip[]              array of in-progress xids
sublxids[]         array of subtransaction ids
```

The metadata function reads the header; the info function
reads + deserializes the full SnapBuild.

## 5. What the info function returns

Sample output (1 row per snapshot file):

```
state              | consistent
xmin               | 5000
xmax               | 5050
start_decoding_at  | 0/1234ABCD
two_phase_at       | 0/1234ABCD
last_serialized    | 0/1234ABCD
catchange_xcnt     | 12
catchange_xip      | {4998, 4999, 5001, ...}
committed_xcnt     | 8
committed_xip      | {4990, 4992, ...}
```

Useful for:
- Verifying the slot's snapshot has reached CONSISTENT.
- Checking xmin progression vs the cluster's
  GetOldestNonRemovableTransactionId.
- Counting in-progress xids that decoding still must wait
  for.

## 6. The snapshot lifecycle

Snapshots are created when:
- A new logical slot is created (`SNAPSHOT_EXPORT` /
  `SNAPSHOT_USE`).
- The slot's restart_lsn advances substantially.
- A checkpoint passes.

Snapshots are removed when:
- The slot is dropped.
- The slot's restart_lsn passes the snapshot's LSN.

`pg_logical/snapshots/` directory size is bounded by the
above; a single inactive slot doesn't unboundedly grow it
(slot xmin pinning is the real bloat hazard, not snapshot
storage).

## 7. Use cases

```sql
-- List all snapshot files:
SELECT * FROM pg_ls_dir('pg_logical/snapshots');

-- Inspect each:
SELECT s.filename, m.*, i.*
FROM (SELECT * FROM pg_ls_dir('pg_logical/snapshots')) s,
     LATERAL pg_get_logical_snapshot_meta('pg_logical/snapshots/' || s.filename) m,
     LATERAL pg_get_logical_snapshot_info('pg_logical/snapshots/' || s.filename) i;
```

Run when:
- A logical slot appears stuck (active but no data flowing).
- Logical decoding errors mention snapshot state.
- Auditing pre-production logical-decoding load.

## 8. Production-use guidance

- **Read-only.** Inspection only; no modifications.
- **Requires superuser by default.** Replication internals
  are sensitive.
- **Output stable within a major version.** PG version
  bumps may change field set.
- **Pair with `pg_replication_slots`** — slot info plus
  snapshot detail tells the full story.

## 9. Invariants

- **[INV-1]** Read-only inspection of serialized snapshots.
- **[INV-2]** 4 SnapBuildState values; CONSISTENT is the
  decoding-ready state.
- **[INV-3]** Magic = 0x51A1E001 — file-format identifier.
- **[INV-4]** File version bumped on format change.
- **[INV-5]** Reads from `pg_logical/snapshots/` — file
  path is server-side relative.

## 10. Useful greps

- The entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/pg_logicalinspect/pg_logicalinspect.c`
- The state mapping:
  `grep -n 'SnapBuildState\|SNAPBUILD_' source/contrib/pg_logicalinspect/pg_logicalinspect.c`
- The on-disk format:
  `grep -n 'SnapBuildOnDisk\|SNAPBUILD_MAGIC' source/src/backend/replication/logical/snapbuild.c | head -10`

## 11. Cross-references

- `knowledge/subsystems/replication.md` — logical decoding
  subsystem.
- `knowledge/idioms/replication-slot-advance.md` — slot
  xmin/restart_lsn that snapshots tie back to.
- `knowledge/idioms/snapshot-acquisition.md` — runtime
  snapshots; pg_logicalinspect is for serialized history.
- `knowledge/idioms/xmin-horizon-management.md` — logical
  slots pin catalog_xmin via these snapshots.
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL + replication
  context.
- `source/src/backend/replication/logical/snapbuild.c` —
  snapshot builder.
- `source/contrib/pg_logicalinspect/pg_logicalinspect.c` —
  207 LOC implementation.
