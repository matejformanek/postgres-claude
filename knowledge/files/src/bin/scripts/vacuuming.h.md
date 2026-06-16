# `src/bin/scripts/vacuuming.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~75
- **Source:** `source/src/bin/scripts/vacuuming.h`

Public header for `vacuuming.c`. Declares the `RunMode` enum,
the `vacuumingOptions` struct (every CLI flag of `vacuumdb` lives
here), the `OBJFILTER_*` bit flags, and the two exported
functions. [verified-by-code]

## API / entry points

- `enum RunMode { MODE_VACUUM, MODE_ANALYZE, MODE_ANALYZE_IN_STAGES }`.
  [verified-by-code]
- `ANALYZE_NO_STAGE = -1`, `ANALYZE_NUM_STAGES = 3`.
  [verified-by-code]
- `struct vacuumingOptions` — 23 fields mirroring command-line
  flags + `echo`/`quiet`/`dry_run`. [verified-by-code]
- `OBJFILTER_ALL_DBS` (0x01), `_DATABASE` (0x02), `_TABLE` (0x04),
  `_SCHEMA` (0x08), `_SCHEMA_EXCLUDE` (0x10) — bit flags packed
  into `vacuumingOptions::objfilter`. [verified-by-code]
- `vacuuming_main(...)` and `escape_quotes(src)` —
  see `vacuuming.c.md`. [verified-by-code]

## Notable invariants / details

- `parallel_workers` is `int` with sentinel `-1` meaning "user
  didn't specify" (comment line 44-45). Distinguishes from `0`
  which is a real user request (PARALLEL 0).
  [verified-by-code]
- The `OBJFILTER_*` enum values are powers of 2 so the validator
  in `vacuumdb.c:check_objfilter` can use bitwise-AND.
  [verified-by-code]
- `RunMode` has only three values; the implicit-vacuum-also-analyze
  case is represented by `mode = MODE_VACUUM` + `and_analyze =
  true`. [verified-by-code]

## Potential issues

- Adding a new VACUUM option (e.g. PG19) requires synchronised
  edits in vacuumdb.c (getopt long_options + switch), this header
  (vacuumingOptions struct), and vacuuming.c (prepare_vacuum_command
  version-gated emission). Easy to miss one of the three.
  [verified-by-code] [ISSUE-style: 3-place edit footprint for
  adding any new VACUUM option; no central registry (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `scripts`](../../../../issues/scripts.md)
<!-- issues:auto:end -->
