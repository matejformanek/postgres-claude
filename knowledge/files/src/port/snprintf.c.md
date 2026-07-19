---
path: src/port/snprintf.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 1515
depth: deep
---

# src/port/snprintf.c

## Purpose

PostgreSQL's **own** portable implementation of the `printf` family
(`pg_snprintf`, `pg_vsnprintf`, `pg_sprintf`, `pg_fprintf`, `pg_printf`, and the
double-to-string `pg_strfromd`). When `USE_REPL_SNPRINTF` is set, the build
`#define`s the standard names to these `pg_*` versions so the *entire* codebase
gets identical, well-defined `printf` semantics on every platform — eliminating
the historical cross-platform variance in return values, `%n$` argument
reordering, `NaN`/`Inf` rendering, and the absence of the `%m` extension.
Derived from the Patrick Powell "bombproof doprnt", heavily extended by PG.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pg_vsnprintf(char *str, size_t count, const char *fmt, va_list args)` | `snprintf.c:174` | Bounded; reserves 1 byte for trailing `\0` |
| `int pg_snprintf(char *str, size_t count, const char *fmt, ...)` | `:202` | Varargs wrapper |
| `int pg_vsprintf` / `pg_sprintf` | `:214` / `:230` | Unbounded (`bufend == NULL`) |
| `int pg_vfprintf` / `pg_fprintf` | `:242` / `:264` | To a `FILE *` via an internal flush buffer |
| `int pg_vprintf` / `pg_printf` | `:276` / `:282` | To stdout |
| `int pg_strfromd(char *str, size_t count, int precision, double value)` | `:1276` | Locale-independent double→string |

## Internal landmarks

- `PrintfTarget` struct (`snprintf.c:125-134`) — `bufptr/bufstart/bufend`,
  optional `FILE *stream`, `nchars` (bytes sent-or-dropped), and a `failed`
  flag. `bufend == NULL` marks the `sprintf` (unbounded) case; snprintf reserves
  one byte so it can always place the terminator (`:112-123`).
- `dopr` (`snprintf.c:373-749`) — the format-string interpreter. Snapshots
  `errno` into `save_errno` at entry (`:375`) so a later `%m` uses the errno
  value *as of the call start*, not whatever subsequent internal calls left.
- `find_arguments` (`:751-972`) — pre-scans the format to support out-of-order
  `%n$` / `*n$` positional arguments (POSIX), capped at `PG_NL_ARGMAX` (31,
  `:44`).
- `fmtstr`/`fmtint`/`fmtfloat`/`fmtchar`/`fmtptr` (`:974-1275`) — the per-
  conversion formatters; `fmtfloat` is where `NaN`/`Inf` get their canonical
  spellings and where the locale-independent decimal point is enforced.
- `%m` handling (`:714`) — expands to `strerror_r(save_errno, …)`.

## Invariants & gotchas

- **Deliberately a C99 *subset* plus PG extensions.** The header enumerates the
  omissions (`snprintf.c:55-71`): no `long double` (`Lf`), no space/`#` flags;
  *added* are `%n$`/`*n$` positional args and `%m` (= `strerror(errno)`). Code
  relying on space/`#`/`L` will silently misformat — these are not supported.
- **`%m` reads errno from call entry**, not the moment the `%m` is reached
  (`:69-71`, `:375`). This is intentional so wrapping logic between the syscall
  and the `ereport` cannot clobber the reported error.
- Return-value contract follows C99 (`:74-91`): for sprintf/snprintf, the count
  that *would* have been written (overrun detectable via `retval >= count`); for
  streams, the actual bytes written; `-1` on a format error or stream write
  failure. Overrunning the snprintf buffer is **not** an error.
- Recursion guard: the file `#undef`s `snprintf`/`printf`/etc. up top
  (`:102-110`) so its own calls hit libc, never re-enter the `pg_*` versions.
- Positional-argument count is hard-limited to 31 (`PG_NL_ARGMAX`); formats
  referencing `%32$` overflow that and are rejected.

## Cross-refs

- `knowledge/files/src/port/strlcpy.c.md` — sibling string primitive in the
  same `libpgport`.
- `knowledge/idioms/error-handling.md` — `%m` is the backbone of `errmsg("…:
  %m")` patterns in `ereport`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
