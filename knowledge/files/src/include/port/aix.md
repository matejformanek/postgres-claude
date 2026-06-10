# `src/include/port/aix.h`

## Role

AIX-specific compatibility shim. Forward-declares two functions that
AIX 7.3 has but fails to declare (`getpeereid`, `wcstombs_l`), and
defines `_PAM_LEGACY_NONCONST` so PG's own PAM code drops `const` to
match AIX's older `pam_conv` signature `[verified-by-code]`
`source/src/include/port/aix.h:8-22`.

## Public API

- `extern int getpeereid(int socket, uid_t *euid, gid_t *egid)`.
- `extern size_t wcstombs_l(char *dest, const wchar_t *src, size_t n,
  locale_t loc)`.
- `#define _PAM_LEGACY_NONCONST 1`.

## Invariants

1. Header is only included on AIX builds (controlled by template-
   based include selection in `c.h`/configure).
2. `_PAM_LEGACY_NONCONST` is mirrored by `solaris.h` for the same
   const-vs-non-const PAM API divergence `[from-comment]`
   `source/src/include/port/aix.h:15-21`.

## Cross-refs

- `source/src/include/port/solaris.h` — same `_PAM_LEGACY_NONCONST`
  pattern.
- `source/src/backend/libpq/auth.c` — PAM integration consumer.

## Issues

- (none; mechanical shim)
