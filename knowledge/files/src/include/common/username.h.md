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

[ISSUE-trust-boundary: header does not document the static-buffer
lifetime (low)] A caller who holds the pointer across another
`getpwuid`/`getpwnam` call has undefined behavior on glibc; on
Windows the function-local static is reused on every call.
