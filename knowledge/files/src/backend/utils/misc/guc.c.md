# `src/backend/utils/misc/guc.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 6863 (largest file in the subsystem)
- **Source:** `source/src/backend/utils/misc/guc.c`

## Purpose

Generic Unified Configuration (GUC) machinery: define, look up, validate,
and stack/restore every PG run-time setting. SQL-level entry points
(`SET`/`SHOW`) live in `guc_funcs.c`; the parameter array lives in
`guc_tables.c`; this file is the engine. [from-comment] (`guc.c:1-14`)

## Mental model

- Each GUC is a `config_generic` (with bool/int/real/string/enum subclasses
  in `guc_tables.h`). It tracks `source`, `scontext` (where it was set),
  `srole`, plus a per-nest-level `stack` of prior values for ROLLBACK.
- All GUCs registered with `build_guc_variables` (`guc.c:871`) at startup
  go into a single hash table (dynahash with case-insensitive comparator
  `guc_name_compare`, `guc.c:1178`). `find_option` (`guc.c:1114`) is the
  universal lookup.
- "Placeholder" GUCs (`guc.c:1058`) hold custom values for not-yet-loaded
  extensions; when the extension calls `DefineCustomXxxVariable`,
  `define_custom_variable` (`guc.c:4837`) reapplies the stacked placeholder
  values onto the freshly-typed real variable. (`reapply_stacked_values`,
  `guc.c:4938`)
- **Sources are ranked.** `PGC_S_*` ordering (`PGC_S_DEFAULT < FILE <
  ENV_VAR < OVERRIDE < INTERACTIVE < TEST < SESSION < USER < DATABASE <
  CLIENT < ARGV < OVERRIDE`) decides who wins on conflict — file changes
  don't override an explicit `SET` (`set_config_option_ext`'s precedence
  logic, `guc.c:3288`-).
- **Contexts** (`PGC_INTERNAL`, `PGC_POSTMASTER`, `PGC_SIGHUP`,
  `PGC_SU_BACKEND`, `PGC_BACKEND`, `PGC_SUSET`, `PGC_USERSET`) gate who
  can change what when. `set_config_with_handle` (`guc.c:3311`) is where
  context vs. caller is enforced.

## Spine

- `InitializeGUCOptions` (`guc.c:1408`) — postmaster start: walks
  `guc_variables` array, calls `InitializeOneGUCOption` for each (apply
  the bootval, run check_hook on it, set source = `PGC_S_DEFAULT`).
- `InitializeGUCOptionsFromEnvironment` (`guc.c:1467`) — pulls
  `PGPORT`/`PGDATESTYLE`/etc.
- `SelectConfigFiles` (`guc.c:1656`) — locate `postgresql.conf`,
  `postgresql.auto.conf`, `pg_hba.conf` paths and apply once at startup.
- `ProcessConfigFileInternal` (`guc.c:285`) — re-parse postgresql.conf on
  SIGHUP; walks the parsed list, applies values whose source ≤ FILE.
- `set_config_with_handle` (`guc.c:3311`) — the universal setter. Handles
  source/context promotion rules, runs check_hook, captures previous value
  on the stack, runs assign_hook on commit-time.
- `push_old_value` / `AtEOXact_GUC` (`guc.c:2041`, `:2169`) — transactional
  stacking. Each `SET LOCAL` or `SET` inside a (sub)xact pushes; on COMMIT
  we pop without restoring; on ABORT we pop and restore via assign_hook.
- `parse_and_validate_value` (`guc.c:3028`) — parse string into the GUC's
  declared type, apply unit conversion (`convert_to_base_unit`,
  `guc.c:2578`), run check_hook, materialize `extra`.
- `AlterSystemSetConfigFile` (`guc.c:4508`) — implementation of `ALTER
  SYSTEM SET ...`: edits `postgresql.auto.conf` atomically via
  `write_auto_conf_file` + rename.
- `BeginReportingGUCOptions` / `ReportChangedGUCOptions` (`guc.c:2453`,
  `:2503`) — `GUC_REPORT`-tagged values (e.g. `client_encoding`,
  `server_version`, `in_hot_standby`) get streamed to the client via
  `ParameterStatus` messages whenever they change.
- `EstimateGUCStateSpace` / `SerializeGUCState` / `RestoreGUCState` — pass
  the current GUC environment to parallel workers (called from
  `parallel.c`).

## Unit machinery

- Two tables: memory and time. **No chained conversions** — every (from,
  to) needs a direct entry; this is why adding a new memory unit means
  adding all of {kB,MB,GB,TB}↔base rows. [from-comment] (`guc.c:88-101`)
- Base units are GUC-declared via `GUC_UNIT_*` flags. Memory base is
  blocks (when `GUC_UNIT_BLOCKS`) or bytes; time base is ms or s.
- `parse_int` / `parse_real` (`guc.c:2775`, `:2865`) accept optional
  trailing unit, convert via `convert_to_base_unit`.

## Stack discipline (transactional)

- `NewGUCNestLevel` (`guc.c:2142`) is called by xact begin and **every
  function call** with `SET` in `proconfig`. Each nest level gets its own
  set of stacks; popping restores values that were SET LOCAL or SET at
  that nest level. (`guc.c:2169`-)
- `AtEOXact_GUC(isCommit, nestLevel)` walks every GUC with a non-null
  stack, pops entries at or above `nestLevel`. On `isCommit=true`, the
  top-of-stack values "win"; on abort, they're discarded and the
  pre-xact value restored.
- `RestrictSearchPath` (`guc.c:2153`) — convenience wrapper used by
  maintenance code to force `search_path = pg_catalog, pg_temp` for the
  current nest level.

## Custom variables

- Extensions call `DefineCustomBoolVariable` / `Int` / `Real` / `String` /
  `Enum` (`guc.c:5049`-) which all funnel through `init_custom_variable`
  (`guc.c:4777`) → `define_custom_variable` (`guc.c:4837`).
- Custom name validation (`guc.c:957`, `:1002`): must contain a dot
  (`.`), must not collide with built-ins, prefix can be reserved via
  `MarkGUCPrefixReserved` (`guc.c:5186`) to prevent unknown vars under
  that prefix from going into placeholders.
- ACL on parameters: `pg_parameter_acl` rows let non-superusers `SET`
  specific GUCs; checked by `pg_parameter_aclcheck` invocations inside
  `set_config_with_handle`.

## Reporting and EXPLAIN

- `get_explain_guc_options` (`guc.c:5238`) returns the GUCs with
  `GUC_EXPLAIN` flag whose current value differs from `boot_val` — these
  appear in `EXPLAIN` output's "Settings:" block.
- `ShowGUCOption` (`guc.c:5372`) is the string-formatting entry point;
  applies `show_hook` if set.

## Notable invariants

- `guc_name_compare` is case-insensitive ASCII (folds via lower-case),
  so all lookups are case-blind. (`guc.c:1178`-)
- `check_GUC_init` (`guc.c:1314`) Asserts every static GUC's `boot_val`
  passes its own `check_hook` — catches table errors at start.
- A GUC's `assign_hook` runs only at commit-time of the setting transaction
  (not at `SET` time), so it can use it as "this value is now official."
  Pre-commit, only `check_hook` has run.
- `BLCKSZ` and `XLOG_BLCKSZ` must be 1KB..1MB or compilation aborts
  (`guc.c:114-119`). Several unit tables encode this assumption.

## Cross-refs

- `guc_funcs.c` — SQL-level SET/SHOW/RESET, `pg_settings` view,
  `current_setting()` / `set_config()`.
- `guc_tables.c` + `guc_parameters.dat` — the registry of built-in GUCs
  (auto-generated config_*_vars arrays).
- `guc-file.l` — lexer for `postgresql.conf`.

## Tag tally

`[verified-by-code]` 2 / `[from-comment]` 5

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
