# `src/bin/pg_combinebackup/copy_file.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~35
- **Source:** `source/src/bin/pg_combinebackup/copy_file.h`

Public header for `copy_file.c`. Declares the `CopyMethod` enum and
the `copy_file()` entry point. [verified-by-code]

## API / entry points

- `enum CopyMethod { COPY_METHOD_CLONE, COPY_METHOD_COPY,
  COPY_METHOD_COPY_FILE_RANGE, COPY_METHOD_COPYFILE (Windows only),
  COPY_METHOD_LINK }`. [verified-by-code]
- `copy_file(...)` — see `copy_file.c.md`.

## Notable invariants / details

- `COPY_METHOD_COPYFILE` is conditionally compiled with `#ifdef
  WIN32`; non-Windows builds must never reference it. This is one of
  the rare places in PG where a public enum has Windows-only members.
  [verified-by-code]

## Potential issues

- Because `COPY_METHOD_COPYFILE` is conditional, any new caller
  writing `switch (copy_method) { ... }` on non-Windows must not
  default-fall-through to a case-label that exists only on Windows.
  Currently only `copy_file.c` switches on this enum so no risk.
  [verified-by-code] [ISSUE-style: enum has #ifdef'd member; consumers
  must be platform-aware (nit)]
