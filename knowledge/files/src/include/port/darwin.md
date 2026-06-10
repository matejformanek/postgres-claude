# `src/include/port/darwin.h`

## Role

macOS-specific shim. Three definitions `[verified-by-code]`
`source/src/include/port/darwin.h:3-13`:

- `#define __darwin__ 1` — convenience macro for code that wants a
  one-symbol macOS check.
- `HAVE_FSYNC_WRITETHROUGH` — set if `F_FULLFSYNC` fcntl is declared,
  enabling PG's "write-through" wal_sync_method option that uses the
  macOS-specific `fcntl(fd, F_FULLFSYNC)` instead of `fsync()`.
- `USE_PREFETCH` — enable PG's prefetch support on macOS (which has
  its own implementation; the comment says "platform-specific
  implementation of prefetching" without naming it — likely
  `posix_fadvise`-equivalent or madvise-based).

## Invariants

1. `F_FULLFSYNC` was added in macOS 10.3 (2003); the
   `HAVE_DECL_F_FULLFSYNC` probe handles older releases that PG
   no longer supports `[from-comment]`
   `source/src/include/port/darwin.h:5`.
2. `F_FULLFSYNC` is **stronger than `fsync`** on macOS — it flushes
   the drive cache, which `fsync` alone doesn't on HFS+ / APFS. Real
   durability requires it for crash-safety.

## Trust-boundary / Phase D surface

- **`fsync()` on macOS is a known weak primitive.** Without
  `F_FULLFSYNC`, a power loss can lose acknowledged writes. PG's
  default `wal_sync_method` is `fsync` for portability; users
  serious about durability on macOS dev machines should set
  `wal_sync_method=fsync_writethrough`. Not the header's fault but
  worth noting. **Phase-D-doc-cluster** with linux.h's
  `WAL_SYNC_METHOD_FDATASYNC` default.

## Cross-refs

- `source/src/include/access/xlogdefs.h` — wal_sync_method enum.
- `source/src/backend/access/transam/xlog.c` —
  `issue_xlog_fsync()` consumer.

## Issues

- (none in the header itself; macOS fsync semantics are a known
  ecosystem-level documentation issue)
