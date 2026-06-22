---
path: src/tools/pg_bsd_indent/err.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 67
depth: read
---

# `src/tools/pg_bsd_indent/err.c` + `err.h` — cut-down BSD `err`/`errx`

## Purpose

A minimal in-tree reimplementation of the BSD `<err.h>` `err()`/`errx()`
functions, "cut down to just the minimum that we need to build indent"
(err.c:30-32, err.h:36-38). PostgreSQL ships these so `pg_bsd_indent` builds on
platforms (notably Windows) that lack the BSD `err` family, rather than
depending on a system `<err.h>`. Covers `err.c` (the two definitions) and the
sibling `err.h` (their prototypes).

## Public symbols

| Symbol | Lines | Behaviour |
|---|---|---|
| `err(int eval, const char *fmt, ...)` | err.c:42-55 | Print `fmt` (printf-style), then `": " + strerror(errno) + "\n"` to stderr; `exit(eval)`. Captures `errno` *first* (err.c:45) before any vararg work can clobber it. |
| `errx(int eval, const char *fmt, ...)` | err.c:57-67 | Like `err` but without the `strerror(errno)` suffix — for errors not tied to a syscall. `exit(eval)`. |

`err.h` declares both as `pg_noreturn` and `pg_attribute_printf(2,3)`
(err.h:40-43), giving the compiler the no-return + format-string-checking
attributes.

## Invariants & gotchas

- **Both are `pg_noreturn` — they `exit()`, never return.** Callers throughout
  the directory (`err(1, NULL)` after a failed `malloc`, `errx(1, "...")` on
  parser overflow) rely on this; the indenter has no error-recovery path, it
  just dies with a message. This is acceptable because it is a one-shot batch
  filter, not a long-lived process.
- `err(eval, NULL)` (the common OOM call, e.g. indent.c:102) prints just
  `strerror(errno)` — the `fmt != NULL` guard at err.c:48 skips the format part.
- Uses real `<stdio.h>`/`<stdarg.h>`; it includes `c.h` only for the PG
  attribute macros. The error text goes to stderr unconditionally (unlike the
  `diag*` family in [[knowledge/files/src/tools/pg_bsd_indent/io.c]], which can
  route to stdout as `/**INDENT**` comments).

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/io.c]] — the other diagnostic path (`diag2/3/4`, recoverable warnings).
- [[knowledge/files/src/tools/pg_bsd_indent/README]] — directory overview.

## Potential issues

(none — a deliberately minimal compatibility shim.)
