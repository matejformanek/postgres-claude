# `src/include/storage/bufmgr.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 475

## Role

**The buffer-manager public API.** All access to the shared buffer
pool flows through this header: page pinning, reading, dirtying,
flushing, content-locking, prefetch, async batched I/O, eviction,
extension, hint-bit set/finish protocol. The single largest
"surface" header in `storage/`.

Cross-link: `knowledge/subsystems/storage-buffer.md`.

## Public API surface (selected)

- **Pin/Release**: `ReadBuffer`, `ReadBufferExtended`,
  `ReadRecentBuffer`, `ReadBufferWithoutRelcache`,
  `ReleaseBuffer`, `UnlockReleaseBuffer`, `IncrBufferRefCount`
  (lines 234-265)
- **Async/batched read (PG17+)**: `StartReadBuffer`,
  `StartReadBuffers`, `WaitReadBuffers` (lines 245-254). Used by
  read_stream.h.
- **Content lock**: `BufferLockMode` enum (`BUFFER_LOCK_UNLOCK`,
  `_SHARE`, `_SHARE_EXCLUSIVE`, `_EXCLUSIVE` — lines 205-223);
  `LockBuffer` (inline at 333-340) dispatches to
  `UnlockBuffer`/`LockBufferInternal` for branch-prediction
  reasons. `ConditionalLockBuffer`, `LockBufferForCleanup`,
  `ConditionalLockBufferForCleanup`.
- **Dirty/hint-bit**: `MarkBufferDirty`, `MarkBufferDirtyHint`,
  `BufferSetHintBits16`, `BufferBeginSetHintBits`,
  `BufferFinishSetHintBits` (lines 317-321)
- **Extend**: `ExtendBufferedRel`, `ExtendBufferedRelBy`,
  `ExtendBufferedRelTo` (lines 267-283)
- **Prefetch**: `PrefetchBuffer`, `PrefetchSharedBuffer` (lines
  229-233)
- **Inline `BufferGetBlock`, `BufferGetPage`, `BufferGetPageSize`**
  (lines 418-471, hidden under `#ifndef FRONTEND` because
  `pg_waldump` includes this header but can't link the externs)
- **Strategy ring (`BufferAccessStrategy`)** types (`BAS_NORMAL`,
  `BAS_BULKREAD`, `BAS_BULKWRITE`, `BAS_VACUUM`) at lines 34-41;
  helpers at lines 379-385.
- **Pin-limit accounting**: `GetPinLimit`, `GetLocalPinLimit`,
  `GetAdditionalPinLimit`, `LimitAdditionalPins` (lines 350-355).
- **Eviction (debug + manual)**: `EvictUnpinnedBuffer`,
  `EvictAllUnpinnedBuffers`, `EvictRelUnpinnedBuffers` (lines
  357-364) — PG17 user-visible via `pg_buffercache_evict`.
- **Hint-bit GUC + globals**: `zero_damaged_pages`,
  `bgwriter_*`, `effective_io_concurrency`, `io_combine_limit`,
  `track_io_timing` (lines 165-184).

## Invariants

- INV-1: `BufferIsValid(b)` asserts `-NLocBuffer ≤ b ≤ NBuffers`
  in debug builds, but only `b != InvalidBuffer` in release.
  Range check happens via Assert, not in release.
  [verified-by-code] lines 418-425.
- INV-2: `LockBuffer` is `static inline` precisely so the
  `mode == BUFFER_LOCK_UNLOCK` branch is constant-folded at most
  call sites. [verified-by-code] lines 332-340 (and comment 327-331).
- INV-3: `ReadBuffersOperation` private members between
  `StartReadBuffers` and `WaitReadBuffers` must not be touched by
  the caller. [from-comment] lines 140-153.
- INV-4: `BMR_REL/BMR_SMGR` macros at 114-119 are designed so the
  same function works in recovery (where `Relation` may not exist)
  and normal ops. Use `BMR_GET_SMGR` rather than caching
  `bmr.smgr`.
- INV-5: `EB_SKIP_EXTENSION_LOCK` (line 75) safe only if rel is
  private, AEL is held, or process is startup. **Misuse silently
  corrupts** during concurrent extension.

## Notable internals

- `READ_BUFFERS_*` flags (lines 122-128): `ZERO_ON_ERROR`,
  `ISSUE_ADVICE`, `IGNORE_CHECKSUM_FAILURES`, `SYNCHRONOUSLY`.
- `MAX_IO_COMBINE_LIMIT = PG_IOV_MAX` (line 175) — caps IOV
  batching.
- `MAX_IO_CONCURRENCY = 1000` (line 197) — GUC ceiling.
- `aio_shared_buffer_readv_cb` /
  `aio_local_buffer_readv_cb` — PG18 AIO callback constants
  (lines 185-186) — bridge into storage/aio.

## Trust boundary (Phase D)

- **Pin-limit accounting** (`GetPinLimit` family) is a defence
  against backends with unbounded pin counts from runaway
  extensions or buggy queries. Bypass would mean an extension
  retains pins beyond `GetPinLimit` and starves the system.
  No core caller does so; an extension that wraps
  `LockBufferInternal` could in principle.
- **`EvictRelUnpinnedBuffers`/`MarkDirtyAllUnpinnedBuffers`**
  (PG17 testing surface) expose `pg_buffercache`-style state
  manipulation that's superuser-only via the SQL wrappers. The
  C API itself is unprotected — extensions inheriting this could
  expose to non-superusers.
- `READ_BUFFERS_IGNORE_CHECKSUM_FAILURES` (line 126) opens a
  read path that bypasses page-checksum verification. Used by
  `pg_amcheck` to inspect corrupt pages; **must not be exposed
  via SQL to non-superusers** because it allows reading data
  that should have raised a corruption error.
- `RBM_ZERO_ON_ERROR` (line 51) similarly returns an all-zero
  page on read failure — a backdoor around `zero_damaged_pages`
  GUC. Same caution.

## Cross-refs

- `knowledge/subsystems/storage-buffer.md` — primary subsystem
  doc; this header is its public face
- `knowledge/subsystems/storage-aio.md` (if exists) — async
  read path
- `knowledge/files/src/include/storage/buf_internals.h.md`
  (existing) — descriptor / refcount layout
- `knowledge/files/src/include/storage/read_stream.h.md`
- `knowledge/files/src/include/storage/lwlock.h.md` (existing)

## Issues

- ISSUE-TRUST: `READ_BUFFERS_IGNORE_CHECKSUM_FAILURES`
  (line 126) and `RBM_ZERO_ON_ERROR` (line 51) provide
  silent-corruption-tolerant read paths; both need superuser
  gating wherever exposed. Document the requirement at the
  header level. (Low — current callers are all superuser-only
  paths.)
- ISSUE-DESIGN: `EB_SKIP_EXTENSION_LOCK` (line 75) — the
  comment lists 3 cases where it's safe, but there's no Assert
  enforcing those cases. An extension calling
  `ExtendBufferedRel` with this flag set during normal
  concurrent activity can corrupt the relation. Site:
  `source/src/include/storage/bufmgr.h:75`. (Medium — defensive
  Assert would catch.)
- ISSUE-PHASE-D: in-tree `EvictRelUnpinnedBuffers` etc. need
  per-call privilege check at the SQL wrapper (currently in
  `pg_buffercache`); ensure not re-exposed in other extensions.
  (Informational.)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new BufferAccessStrategy ring](../../../../scenarios/add-new-buffer-strategy.md)

<!-- scenarios:auto:end -->
