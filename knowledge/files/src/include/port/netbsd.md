# `src/include/port/netbsd.h`

## Role

NetBSD-specific shim. **Empty** — just the SPDX-style identifier
comment `[verified-by-code]` `source/src/include/port/netbsd.h:1`.

No NetBSD-specific compatibility needed currently; NetBSD's libc
declarations match PG's expectations. The file exists as a
placeholder so the template-based include selection in
`src/template/netbsd` doesn't fail.

## Public API

(none)

## Invariants

1. File exists for the template-based include hook.

## Cross-refs

- `source/src/template/netbsd` — the meson/configure template that
  references this header.

## Issues

- (none)
