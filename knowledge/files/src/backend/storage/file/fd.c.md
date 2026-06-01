# `src/backend/storage/file/fd.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~4100
- **Source:** `source/src/backend/storage/file/fd.c`

## Purpose

The Virtual File Descriptor (VFD) cache. PG servers open more files
than the OS lets a single process hold open (typically ~1024), so this
file maintains a logical pool of `File` handles (small ints into the
`VfdCache` array) backed by an LRU of *actually* open kernel fds. Any
backend code that calls `open(2)`/`fopen(3)` directly is buggy — the
fd.c routines (PathNameOpenFile, AllocateFile, BasicOpenFile, …) must
be used so VFD eviction can reclaim kernel slots as needed.
[from-comment] (`fd.c:12-69`)

## Top of file

Lines 12–69 are an interface-routine listing — the comment is the
single best entry point for understanding the file. Distinguishes:
- **VFDs** (`PathNameOpenFile`/`OpenTemporaryFile` → `File`) —
  long-lived, LRU-evictable.
- **AllocateFile/Dir/PipeStream/TransientFile** — fopen-style wrappers
  tracked per-subtransaction.
- **BasicOpenFile** — bare `open()` wrapper that asks fd.c to evict a
  VFD first if needed; no automatic cleanup.
- **AcquireExternalFD / ReserveExternalFD / ReleaseExternalFD** —
  for non-VFD long-lived fds the caller wants counted against
  `max_safe_fds`.

## Public surface (fd.h)

GUCs: `max_files_per_process`, `max_safe_fds`, `data_sync_retry`,
`recovery_init_sync_method`, `io_direct_flags`, `file_extend_method`.

Core VFD API:
`PathNameOpenFile`, `PathNameOpenFilePerm`, `OpenTemporaryFile`,
`FileClose`, `FileReadV`, `FileWriteV`, `FileStartReadV` (AIO),
`FileSync`, `FileZero`, `FileFallocate`, `FileSize`, `FileTruncate`,
`FileWriteback`, `FilePrefetch`, `FilePathName`, `FileGetRawDesc`,
`FileGetRawFlags`, `FileGetRawMode`.

Plus: `PathNameCreateTemporaryDir`, `PathNameCreateTemporaryFile`,
`PathNameOpenTemporaryFile`, `PathNameDeleteTemporaryFile`,
`PathNameDeleteTemporaryDir`.

Plus: `AllocateFile`, `AllocateDir`, `OpenPipeStream`, `FreeFile`,
`FreeDir`, `ClosePipeStream`.

Plus: `BasicOpenFile`, `BasicOpenFilePerm`, `AcquireExternalFD`,
`ReserveExternalFD`, `ReleaseExternalFD`, `set_max_safe_fds`.

Plus: `pg_fsync`, `pg_fsync_no_writethrough`, `pg_fsync_writethrough`,
`pg_fdatasync`, `pg_flush_data`, `pg_truncate`, `fsync_fname`,
`durable_rename`, `durable_unlink`, `SyncDataDirectory`.

## Types of note

- `Vfd` (lines 200–213): one cache entry. Fields: `fd` (the kernel
  descriptor, `VFD_CLOSED=-1` if currently evicted), `fdstate`
  (FD_DELETE_AT_CLOSE / FD_CLOSE_AT_EOXACT / FD_TEMP_FILE_LIMIT
  bits), `resowner`, `nextFree` (free-list link), `lruMoreRecently` /
  `lruLessRecently` (LRU doubly-linked list links), `fileSize` (for
  temp files), `fileName`, `fileFlags`, `fileMode`.
- `VfdCache[]` (line 220): heap-allocated array, doubled on demand
  starting at 32. Element 0 is the LRU sentinel — its `fd` is always
  `VFD_CLOSED` and it forms the circular ring head.
- `nfile` (line 226): count of VFDs currently holding an actual
  kernel fd. Compared against `max_safe_fds - numAllocatedDescs -
  numExternalFDs` to decide when to evict.
- `AllocateDesc` (declared in this file): tracks
  `AllocateFile`-class handles per-subtransaction for auto-cleanup.

## The VFD LRU — the load-bearing trick

(lines 297–328 doc comment; functions `LruDelete`/`Insert`/`LruInsert`/
`ReleaseLruFile`/`ReleaseLruFiles` at 1272–1399)

- **Doubly-linked ring**: VfdCache[0] is the anchor; its
  `lruLessRecently` points to the most-recently-used VFD, its
  `lruMoreRecently` to the least-recently-used. Only VFDs currently
  holding a kernel fd are in the ring.
- **Eviction policy**: whenever `nfile + numAllocatedDescs +
  numExternalFDs >= max_safe_fds`, `ReleaseLruFiles` closes the LRU
  victim via `LruDelete` until under the limit (`fd.c:1391-1399`).
- **`LruDelete` (lines 1272–1298)**: calls `pgaio_closing_fd` (so the
  AIO subsystem can drain pending operations against that fd), then
  `close(2)`, then sets `fd=VFD_CLOSED`, decrements `nfile`, removes
  from the ring. *fileName is kept*, so the VFD can be reopened
  transparently later. [verified-by-code]
- **`LruInsert` (lines 1322–1364)**: if the VFD is currently
  evicted (`FileIsNotOpen`), first calls `ReleaseLruFiles()` to free
  a slot, then re-opens with the stored `fileName/fileFlags/fileMode`,
  then puts it at the MRU end of the ring. [verified-by-code]
- **`FileAccess` (lines 1479–…)**: every read/write/seek call goes
  through this; if the VFD is closed it re-opens, if it's not at the
  MRU end it moves it (a "touch"). This is what makes the LRU update
  on every IO.
- **Failure mode**: re-open after eviction can itself fail (system
  fd table full, file unlinked). Returns -1; caller of e.g. `FileWriteV`
  surfaces that as a normal IO error.

The `pgaio_closing_fd` hook in LruDelete is the bit that lets AIO
operate against VFDs that can be evicted underneath in-flight IOs:
the AIO worker will re-acquire the fd via the smgr_aio_reopen
callback. `[verified-by-code]` (`fd.c:1284`)

## Other invariants

- **Reserved fds**: `NUM_RESERVED_FDS = 10` are *always* left free for
  `system()`, dynamic loader, etc. `FD_MINFREE = 48` is the
  configure-time minimum usable VFD count. (lines 115–139)
- **Resource owner integration**: every VFD created with a non-NULL
  resowner is auto-released at subxact/xact end. The
  `file_resowner_desc` (lines 365–372) registers a callback that
  closes the file in `RESOURCE_RELEASE_AFTER_LOCKS` phase.
- **Temp-file accounting**: VFDs with FD_TEMP_FILE_LIMIT track their
  `fileSize` in `temporary_files_size`; `temp_file_limit` is enforced
  here. `have_xact_temporary_files` flag (line 232) is a "worth
  scanning?" shortcut.
- **`pg_fsync` (lines 389–434)**: in assert builds verifies that the
  fd was opened with write-compatible flags for files, read-only for
  directories — fsync portability requirement. Dispatches to
  `pg_fsync_writethrough` (F_FULLFSYNC on macOS) or
  `pg_fsync_no_writethrough` depending on `wal_sync_method`.
- **`SyncDataDirectory` (line 3593)**: post-crash walk of the data
  directory issuing fsync (or `syncfs` per `recovery_init_sync_method`)
  to ensure pre-crash writes hit disk before recovery starts.

## Functions of note

- `PathNameOpenFile(name, flags)` / `…Perm` (1562–) — allocate a VFD,
  open the file, link into LRU.
- `OpenTemporaryFile(interXact)` (1711–) — create an anonymous temp
  file under one of the temp tablespaces; auto-unlinked on close.
- `FileReadV` / `FileWriteV` (2148–, 2230–) — pwritev/preadv vectored
  IO with EINTR retry and partial-IO handling.
- `FileFallocate` / `FileZero` (2407–, 2362–) — used by mdzeroextend.
- `FileStartReadV` (declared in fd.h:140) — AIO entry; hands off to
  the io_method.
- `BasicOpenFile` (1089–) — bare `open()` with VFD-eviction
  cooperation (calls `ReleaseLruFile` in a retry loop on EMFILE).
- `AcquireExternalFD` / `ReserveExternalFD` (1171–, 1206–) — tell
  fd.c that a non-VFD long-lived fd exists so it's counted against
  `max_safe_fds`.

## Cross-refs

- Heavily called by: `md.c` (for every read/write/extend/sync),
  `xlog.c` (WAL files), `xact.c` (twophase state files),
  `relmapper.c`, `slru.c` (which has its own page cache atop fd.c),
  `buffile.c` (via OpenTemporaryFile).
- Calls into `aio.c` (`pgaio_closing_fd`, `FileStartReadV`).

## Open questions

- The AIO + VFD-eviction interaction (LruDelete calling
  `pgaio_closing_fd`) — the precise drain semantics live in the AIO
  subsystem, not here. `[unverified]`
- Whether `numExternalFDs` accurately captures all non-VFD fds used by
  contrib modules is by contract, not enforcement. `[unverified]`

## Tag tally

`[verified-by-code]` 8 / `[from-comment]` 7 / `[unverified]` 2.
