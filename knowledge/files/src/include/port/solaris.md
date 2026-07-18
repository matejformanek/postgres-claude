# `src/include/port/solaris.h`

## Role

Solaris/OpenIndiana shim `[verified-by-code]`
`source/src/include/port/solaris.h:1-14`:

- On i386, include `<sys/isa_defs.h>` (provides endianness +
  word-size macros that PG's c.h consumes).
- Define `_PAM_LEGACY_NONCONST 1` — Solaris's `pam_conv` declares
  non-const params; recent OpenIndiana adds `const` by default,
  reverted by this macro to keep PG's call sites consistent
  `[from-comment]` `source/src/include/port/solaris.h:7-13`.

## Public API

- `_PAM_LEGACY_NONCONST 1`.
- (implicit) Whatever `<sys/isa_defs.h>` provides on Solaris i386.

## Invariants

1. `_PAM_LEGACY_NONCONST` is mirrored by `aix.h` for the same PAM
   const-vs-non-const divergence.
2. The `<sys/isa_defs.h>` include is `__i386__`-only — Solaris on
   SPARC / amd64 doesn't need it.

## Cross-refs

- `source/src/include/port/aix.h` — twin `_PAM_LEGACY_NONCONST` use.
- `source/src/backend/libpq/auth.c` — PAM consumer.

## Issues

- (none; mechanical)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
