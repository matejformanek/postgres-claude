# `src/fe_utils/option_utils.c`

- **File:** `source/src/fe_utils/option_utils.c` (146 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

Command-line option-processing helpers shared by frontend programs so that
`--help`/`--version` handling, integer-option parsing, the `--sync-method`
option, and mutual-exclusion checks all behave identically across `psql`,
`pg_dump`, `initdb`, `pg_basebackup`, the `scripts/` utilities, etc. Errors are
reported through the frontend logging layer (`pg_log_error`, `pg_fatal`), not
`ereport`. [verified-by-code: includes at `option_utils.c:13-17`]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `handle_help_version_opts` | :24 | If `argv[1]` is `--help`/`-?` or `--version`/`-V`, call the help handler or print version, then `exit(0)`. |
| `option_parse_int` | :50 | Parse an int option with range checking; returns bool, optionally stores result. |
| `parse_sync_method` | :90 | Parse `fsync`/`syncfs` into a `DataDirSyncMethod`. |
| `check_mut_excl_opts_internal` | :125 | Variadic; `pg_fatal` if 2+ of the given options are set. Driven by the `check_mut_excl_opts()` macro. |

## Internal landmarks

- `handle_help_version_opts:27` only inspects `argv[1]`, so `--help`/`--version`
  are recognized only as the *first* argument. [verified-by-code:27-39]
- `option_parse_int:58` uses `strtoint(..., 10)`, then skips trailing whitespace
  (`:64-65`) and rejects any non-whitespace remainder (`:67-72`). Range failure is
  detected via `errno == ERANGE || val < min || val > max` (`:74`). The two error
  messages differ: an unparseable value reports the bad string; an out-of-range
  value reports the range. `*result` is written only on success and only if
  non-NULL (`:81-82`). [verified-by-code]
- `parse_sync_method:94-102` returns false (with a `pg_log_error`) for `syncfs`
  when the build lacks `HAVE_SYNCFS`. [verified-by-code]
- `check_mut_excl_opts_internal:125` asserts an even argument count (`:130`),
  iterates `(bool set, char *opt)` pairs, and `pg_fatal`s on the second set option.
  Only the first colliding pair is reported. The `check_mut_excl_opts()` macro in
  the header supplies `n` automatically. [from-comment:114-123, verified-by-code]

## Invariants & gotchas

- `option_parse_int` returns false on failure (caller decides whether to exit);
  `check_mut_excl_opts_internal` and `parse_sync_method`'s build-unsupported path
  use the frontend logging/exit idioms directly (`pg_fatal` exits, `pg_log_error`
  does not). [verified-by-code]
- The variadic `set` argument is read with `va_arg(args, int)` (`:135`) because
  `bool` promotes to `int` in variadic calls — passing a literal `bool` is correct,
  but the macro must expand to int-compatible expressions. [inferred from:135]
- `handle_help_version_opts` calls `get_progname(argv[0])` for the help handler but
  prints `fixed_progname` for `--version` — i.e. version output uses the caller's
  fixed program name, not the invoked basename. [verified-by-code:31, 36]

## Cross-references

- `source/src/include/fe_utils/option_utils.h` — declarations and the
  `check_mut_excl_opts()` macro.
- `source/src/common/string.c` — `strtoint` used at `option_utils.c:58`.
- `source/src/common/logging.c` — `pg_log_error` / `pg_fatal`.
- `source/src/common/file_utils.h` — `DataDirSyncMethod`, `HAVE_SYNCFS`.

## Confidence tag tally

- `[verified-by-code]` × 8
- `[from-comment]` × 1
- `[inferred]` × 1
