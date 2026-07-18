# `src/include/port/linux.h`

## Role

Linux-specific shim. Two definitions `[verified-by-code]`
`source/src/include/port/linux.h:14,22`:

- `HAVE_LINUX_EIDRM_BUG` — Linux kernel sometimes returns `EIDRM`
  for `shmctl()` when `EINVAL` is correct (when the low 15 bits of
  the supplied shmid match a newer segment's slot number). PG's
  `PGSharedMemoryIsInUse()` treats EIDRM as EINVAL.
- `PLATFORM_DEFAULT_WAL_SYNC_METHOD WAL_SYNC_METHOD_FDATASYNC` —
  prefer `fdatasync` over the rule-default `open_datasync` because
  open_datasync doesn't perform better AND causes outright failures
  on ext4 `data=journal` filesystems (no O_DIRECT support there).

## Invariants

1. The EIDRM workaround dates to July 2007 `[from-comment]`
   `source/src/include/port/linux.h:3-13`. "Someday that code might
   get upgraded, and we'd have to have a kernel version test" — i.e.
   the workaround is unconditional, no kernel-version probe.
2. fdatasync override mirrors freebsd.h.

## Trust-boundary / Phase D surface

- **EIDRM-as-EINVAL is a portability quirk, not a security issue.**
  The worst case is "we incorrectly conclude another segment is in
  use and refuse to start" — a startup failure, not a corruption
  path.
- **ext4 data=journal incompatibility with O_DIRECT** is a known
  trap for users following advice from non-PG sources. PG protects
  itself via this default but `wal_sync_method=open_datasync` is
  still user-settable and would fail at runtime.

## Cross-refs

- `source/src/backend/port/sysv_shmem.c` —
  `PGSharedMemoryIsInUse` consumer.
- `source/src/include/access/xlogdefs.h`.
- `source/src/include/port/freebsd.h` — same fdatasync override.

## Issues

- **ISSUE-staleness**: the EIDRM workaround comment is from 2007;
  worth re-checking against current Linux 6.x semantics. Comment
  itself acknowledges: "someday that code might get upgraded".
  (severity: low; PG would still work, just suboptimal)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
