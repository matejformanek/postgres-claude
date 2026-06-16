# username.h

Two-line header for `src/common/username.c`.
(`source/src/include/common/username.h`) [verified-by-code]

## Purpose

Declares the OS-username lookup helpers.

## Key declarations

- `const char *get_user_name(char **errstr)` — pointer into
  libc-owned static storage on POSIX, or a function-local static
  buffer on Windows. NULL on failure with `*errstr` set to a
  `psprintf`'d message.
- `const char *get_user_name_or_exit(const char *progname)` —
  same but exits with the message on failure.

## Phase D notes

## Issues

[ISSUE-trust-boundary: header does not document the static-buffer
lifetime (low)] A caller who holds the pointer across another
`getpwuid`/`getpwnam` call has undefined behavior on glibc; on
Windows the function-local static is reused on every call.

[ISSUE-trust-boundary: `get_user_name` (`username.h:12`) returns
the OS-level effective username; PG tools then compare it against
PG role names. The OS↔PG namespace overlap is a documented design
choice (peer-auth) but the header carries no warning that this
mapping is security-relevant (low)] A2 + A6 cross-link — peer auth
trusts the OS uid lookup.

## Cross-refs

- A2 libpq peer auth — OS uid → PG role mapping.
- A6 `pg_upgrade` / `initdb` — `get_user_name_or_exit` consumer.
- Companion: `src/common/username.c.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->
