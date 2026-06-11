# `src/bin/pg_combinebackup/write_manifest.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~33
- **Source:** `source/src/bin/pg_combinebackup/write_manifest.h`

Public header for `write_manifest.c`. Uses an opaque `typedef
manifest_writer` via incomplete struct + typedef, exposing only the
three public functions. Forward-declares `struct manifest_wal_range`.
[verified-by-code]

## API / entry points

- `create_manifest_writer`, `add_file_to_manifest`,
  `finalize_manifest` — see `write_manifest.c.md`.
  [verified-by-code]

## Notable invariants / details

- The struct definition is hidden inside `write_manifest.c` (line
  27). Callers cannot inspect internal state, which keeps the
  contract narrow. [verified-by-code]

## Potential issues

- Forward declaration `struct manifest_wal_range` (line 17) requires
  callers passing a non-NULL `first_wal_range` to also include
  `load_manifest.h`. Not a bug but a mild ergonomic wrinkle.
  [verified-by-code]
