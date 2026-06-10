# `src/include/port/freebsd.h`

## Role

FreeBSD-specific shim. Single definition `[verified-by-code]`
`source/src/include/port/freebsd.h:7-8`:

- `PLATFORM_DEFAULT_WAL_SYNC_METHOD WAL_SYNC_METHOD_FDATASYNC` —
  override the xlogdefs.h default (which would pick `open_datasync`
  on FreeBSD 13+) because `open_datasync` is "not a good choice on
  many systems" `[from-comment]` `source/src/include/port/freebsd.h:3-7`.

## Invariants

1. xlogdefs.h's general rule prefers `open_datasync` whenever
   `OPEN_DATASYNC_FLAG` is available; this file is the only override
   for FreeBSD `[from-comment]`.
2. Mirrors linux.h's same override — both prefer `fdatasync` over
   `open_datasync` for the same reason (kernel-side write ordering
   bugs, ext4 data=journal failures).

## Cross-refs

- `source/src/include/access/xlogdefs.h`.
- `source/src/include/port/linux.h` — same override.

## Issues

- (none)
