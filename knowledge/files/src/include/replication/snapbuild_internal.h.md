# src/include/replication/snapbuild_internal.h

## Purpose

Internal layout of `struct SnapBuild` (the historic-snapshot builder
state) and the on-disk `SnapBuildOnDisk` checkpoint format used to
serialize snapbuild progress to `pg_replslot/<slot>/snap-<lsn>.snap`.
Carved out of `snapbuild.c` so that `pg_logicalinspect` and
`pg_walinspect` can read serialized snapshots without exporting the
full module API. Source pin
`4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role in PG

This header is the "the struct is no longer fully private" admission for
snapbuild. Comment line 23 explicitly warns: "It is exposed to the
public, so pay attention when changing its contents." Anything that
adds, removes, or reorders fields in `struct SnapBuild` becomes a
catalog-version-style break for `pg_logicalinspect` users who hold
serialized snap files across upgrades. The `SnapBuildOnDisk.version`
field exists precisely to support such evolution — bump version, write
a migrator.

## Key types/struct fields

- `struct SnapBuild` (lines 26-158):
  - `state` (SnapBuildState) — see `snapbuild.h.md`. [verified-by-code]
  - `context` (MemoryContext) — every snapbuild allocation lives in
    this private context; cleanup is a single
    `MemoryContextDelete`. [verified-by-code]
  - `xmin` / `xmax` (TransactionId) — visibility horizon for the
    historic snapshot. [verified-by-code]
  - `start_decoding_at` (XLogRecPtr) — commits below this LSN are
    dropped; never retreats (comment line 42). [from-comment]
  - `two_phase_at` (XLogRecPtr) — LSN past which two-phase decoding is
    enabled; PREPAREs before this LSN are deferred to their COMMIT
    PREPARED. [verified-by-code]
  - `initial_xmin_horizon` (TransactionId) — minimum xmin that any
    running xact must be above before the snapshot can advance.
    [verified-by-code]
  - `building_full_snapshot` (bool) — true ⇒ rebuild full snapshot
    (slot creation with `EXPORT_SNAPSHOT`), false ⇒ catalog-only.
    [from-comment]
  - `in_slot_creation` (bool) — disables fast-restart from a serialized
    snap file because the start point isn't known yet (comment lines
    66-72). [from-comment]
  - `snapshot` (Snapshot) — currently-published historic snapshot.
    [verified-by-code]
  - `last_serialized_snapshot` (XLogRecPtr) — debounces redundant
    snap-file writes. [verified-by-code]
  - `reorder` (ReorderBuffer *) — the per-slot reorder buffer that
    holds queued changes; snapbuild calls into it to install snapshots
    on commit. [verified-by-code]
  - `next_phase_at` (TransactionId) — pivot xid for state-machine
    advances. [verified-by-code]
  - `committed` substruct (lines 100-130) — array of catalog-modifying
    xacts that committed between xmin and xmax. NOT kept in
    xidComparator order — comment lines 122-128 contains a TODO
    questioning whether the unsorted choice still makes sense.
    [from-comment]
  - `catchange` substruct (lines 150-157) — array of running, catalog-
    modifying xids serialized into the snap file; consulted on restart
    to make sure we don't lose track that a long-running xact had DDL.
    [from-comment]
- `struct SnapBuildOnDisk` (lines 175-194):
  - `magic` (uint32) — file-format magic. [verified-by-code]
  - `checksum` (pg_crc32c) — CRC over everything from `version`
    onward; comment line 179 names the constants
    (`SnapBuildOnDiskConstantSize`,
    `SnapBuildOnDiskNotChecksummedSize`) the implementer must keep in
    sync. [from-comment]
  - `version` (uint32) — comment line 185 explicitly notes "in case we
    want to support pg_upgrade". [from-comment]
  - `length` (uint32) — variable-tail length excluding the constant
    prefix. [verified-by-code]
  - `builder` (SnapBuild) — embedded full struct. [verified-by-code]
- `SnapBuildRestoreSnapshot` (line 196) — loads a SnapBuildOnDisk image
  from `pg_replslot/<slot>/snap-<lsn>.snap`. [verified-by-code]

## Phase D notes

This header is the closest thing to a "private struct layout exposed
for forensic tooling" pattern in the replication subsystem. The
explicit `SnapBuildOnDisk.version` plus the comment about pg_upgrade
hints at a long-running concern: snap files survive across minor
versions and (in principle) across major-version upgrades via
pg_upgrade. Stale TODO at lines 122-128 about whether unsorted
`committed.xip` still makes sense — has been in tree since at least the
2024 file creation date.

The CRC covers everything after the magic and checksum fields (lines
180-181). A snap file is read on slot recovery, validated by CRC, then
its contents directly populate `struct SnapBuild`. A corrupted snap
that passes CRC (collision) but has malformed `committed.xcnt` /
`catchange.xcnt` could overflow allocations, but `length` is supposed
to gate that.

`pg_logicalinspect` and any external extension that learned to parse
the on-disk format from this header is a *de facto* part of the API
surface. Field reorderings without a version bump silently break those
readers.

## Potential issues

- [ISSUE-stale-todo: TODO at lines 122-128 questioning whether
  `committed.xip` being unsorted is still the right choice — has been
  in tree since 2024 file creation, unresolved (sev=unlikely)]
- [ISSUE-wire-protocol: `SnapBuildOnDisk` format is partially public
  (pg_logicalinspect reads it); silent struct reorder is an ABI break
  for forensic tooling but only `version` would flag it
  (sev=maybe)]
- [ISSUE-undocumented-invariant: header doesn't say what
  `SnapBuildRestoreSnapshot(missing_ok=true)` returns if the file
  exists but fails CRC; caller must check (sev=unlikely)]
- [ISSUE-state-transition: `last_serialized_snapshot` is the only
  guard against re-serializing — if shmem is cleared without resetting
  it, two writers could race on the same `*.snap` file (sev=unlikely)]
