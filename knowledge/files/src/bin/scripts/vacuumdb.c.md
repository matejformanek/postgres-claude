# `src/bin/scripts/vacuumdb.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~392
- **Source:** `source/src/bin/scripts/vacuumdb.c`

CLI shell for `vacuuming.c`. Handles the very large set of
VACUUM/ANALYZE flags, validates incompatible combinations
(analyze-only + full, parallel + full, etc.), then delegates to
`vacuuming_main()`. The 'meat' of the vacuuming logic (catalog
queries, SQL generation, parallel dispatch) lives in
`vacuuming.c`. [verified-by-code]

## API / entry points

- `main(argc, argv)` — getopt loop populates a `vacuumingOptions`
  struct + a `SimpleStringList` of objects, then validates
  combinations, then calls `vacuuming_main`. [verified-by-code]
- `check_objfilter(objfilter)` — local helper enforcing
  mutually-exclusive object-filter flag combinations. [verified-by-code]

## Notable invariants / details

- Default `vacopts.parallel_workers = -1` means "user did not
  specify"; `0` is a valid user request (PARALLEL 0, which
  disables parallel workers for that VACUUM). [verified-by-code]
- `do_truncate`, `process_main`, `process_toast` default to
  `true`; the `--no-truncate`/`--no-process-main`/
  `--no-process-toast` flags flip them off. [verified-by-code]
- Analyze-only mode (line 246-274) rejects most VACUUM-specific
  options: `--full`, `--freeze`, `--disable-page-skipping`,
  `--no-index-cleanup`, `--force-index-cleanup`, `--no-truncate`,
  `--no-process-main`, `--no-process-toast`. The `--analyze`
  flag itself (which is the implicit "also analyze") is allowed
  alongside `--analyze-only` for unfortunately-overlapping
  semantic reasons (comment line 273). [verified-by-code]
- `--parallel` rejected with `--analyze-only`,
  `--analyze-in-stages`, AND `--full` (line 277-286): VACUUM
  FULL re-creates the table, so parallel index processing isn't
  available, and analyze never parallelises that way.
  [verified-by-code]
- `--no-index-cleanup` + `--force-index-cleanup` is rejected as
  contradictory (line 289-291). [verified-by-code]
- `--buffer-usage-limit` with `--full` is rejected UNLESS
  `--analyze` is also set (line 297-299) — the rationale being
  that `VACUUM FULL` ignores the ring-buffer setting but
  `VACUUM (FULL, ANALYZE)` still uses it for the analyze pass.
  [verified-by-code]
- `--missing-stats-only` requires `--analyze-only` or
  `--analyze-in-stages` (line 305-308). [verified-by-code]
- `check_objfilter` (line 324) enforces:
  - `--all` xor specific dbname.
  - `--table` xor `--schema`.
  - `--table` xor `--exclude-schema`.
  - `--schema` xor `--exclude-schema`. [verified-by-code]
- `--buffer-usage-limit` passes its value through
  `escape_quotes` (line 206) — strips single quotes and
  backslashes so the value can be safely interpolated as a
  literal in `prepare_vacuum_command`. [verified-by-code]

## Potential issues

- Line 305: `--missing-stats-only` with `MODE_VACUUM` (the
  default) is the case being rejected. The error message lists
  `--analyze-only` or `--analyze-in-stages` as required
  partners. But `--analyze` (also-analyze, which DOES run
  ANALYZE) is NOT listed even though it should suffice
  functionally. [verified-by-code] [ISSUE-doc-drift:
  --missing-stats-only error message omits --analyze as a valid
  enabler (maybe)]
- `--jobs` parses as `int` with `option_parse_int(1, INT_MAX)`,
  so 0 is rejected (line 120). [verified-by-code]
- `--parallel` parses with min `0`, so `--parallel=0` is
  accepted (and means "disable parallel workers" server-side).
  [verified-by-code]
- The `escape_quotes` (line 206) is called only for
  `--buffer-usage-limit`. Other string-typed options like
  `--schema` are passed verbatim into the `SimpleStringList`
  and consumed by `vacuuming.c`. The downstream code
  `vacuuming.c:retrieve_objects` interpolates them after
  appropriate escaping. [verified-by-code]
- Help text line 354 misspells "vacuuming" as expected (it's
  correct), but the description for `-d/--dbname` says "database
  to vacuum" even in analyze-only mode where the action is
  actually ANALYZE. Cosmetic. [verified-by-code]
- Line 244: `check_objfilter` is called BEFORE the
  analyze-mode/parallel/etc. checks. If a user has multiple
  errors, only the first is reported. [verified-by-code]
