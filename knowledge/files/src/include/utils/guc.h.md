# `utils/guc.h` — public GUC (Grand Unified Configuration) API

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/guc.h`)

## Role

The biggest surface for runtime-configurable behaviour. Defines `GucContext`
(when can the value change?), `GucSource` (where did the current value
come from?), the `Define{Bool,Int,Real,String,Enum}Variable` family used
by extensions, the runtime get/set entry points, the flag bits (`GUC_*`),
unit conversions for memory/time GUCs, and the check-hook ereport surface
(`GUC_check_errmsg` / `errdetail` / `errhint`). Every loadable extension
that adds a GUC, every backend startup path, and every SHOW/SET statement
goes through this header.

## Public API

### Enums and flag bits

- `GucContext { PGC_INTERNAL, PGC_POSTMASTER, PGC_SIGHUP, PGC_SU_BACKEND,
  PGC_BACKEND, PGC_SUSET, PGC_USERSET }` —
  `source/src/include/utils/guc.h:71-80`. Encodes the rule for when a
  value can be changed and by whom.
- `GucSource { PGC_S_DEFAULT, PGC_S_DYNAMIC_DEFAULT, PGC_S_ENV_VAR,
  PGC_S_FILE, PGC_S_ARGV, PGC_S_GLOBAL, PGC_S_DATABASE, PGC_S_USER,
  PGC_S_DATABASE_USER, PGC_S_CLIENT, PGC_S_OVERRIDE, PGC_S_INTERACTIVE,
  PGC_S_TEST, PGC_S_SESSION }` — `:111-127`.
- `GucAction { GUC_ACTION_SET, GUC_ACTION_LOCAL, GUC_ACTION_SAVE }` —
  `:200-206`.
- Flag bits — `:214-244`:
  `GUC_LIST_INPUT` `0x000001`,
  `GUC_LIST_QUOTE` `0x000002`,
  `GUC_NO_SHOW_ALL` `0x000004`,
  `GUC_NO_RESET` `0x000008`,
  `GUC_NO_RESET_ALL` `0x000010`,
  `GUC_EXPLAIN` `0x000020`,
  `GUC_REPORT` `0x000040`,
  `GUC_NOT_IN_SAMPLE` `0x000080`,
  `GUC_DISALLOW_IN_FILE` `0x000100`,
  `GUC_CUSTOM_PLACEHOLDER` `0x000200`,
  `GUC_SUPERUSER_ONLY` `0x000400`,
  `GUC_IS_NAME` `0x000800`,
  `GUC_NOT_WHILE_SEC_REST` `0x001000`,
  `GUC_DISALLOW_IN_AUTO_FILE` `0x002000`,
  `GUC_RUNTIME_COMPUTED` `0x004000`,
  `GUC_ALLOW_IN_PARALLEL` `0x008000`.
- Unit masks `GUC_UNIT_KB/BLOCKS/XBLOCKS/MB/BYTE/MEMORY/MS/S/MIN/TIME` —
  `:232-244`.

### Constants

- `MAX_KILOBYTES` — caps GUC values measured in KB to ensure
  `value * 1024` fits in `size_t`. `:26-30`.
- `PG_AUTOCONF_FILENAME = "postgresql.auto.conf"` — `:37`.
- `GUC_QUALIFIER_SEPARATOR '.'` — `:208`.

### Types

- `ConfigVariable { name, value, errmsg, filename, sourceline, ignore,
  applied, next }` — `:139-149`. Doubles as error-report carrier.
- `config_handle = struct config_generic` (opaque) — `:151`.
- `config_enum_entry { name, val, hidden }` — `:173-178`.
- Hook signatures: `GucBoolCheckHook`, `GucIntCheckHook`, …,
  `GucBoolAssignHook`, …, `GucShowHook` — `:183-195`.

### Functions

- `DefineCustomBoolVariable / IntVariable / RealVariable / StringVariable /
  EnumVariable` — `:358-416`. The extension entry points.
- `MarkGUCPrefixReserved` (formerly `EmitWarningsOnPlaceholders`) — `:418-421`.
- `SetConfigOption`, `set_config_option`, `set_config_option_ext`,
  `set_config_with_handle`, `get_config_handle` — `:355,445-460`.
- `GetConfigOption(name, missing_ok, restrict_privileged)` — `:423`.
- `GetConfigOptionResetString`, `GetConfigOptionFlags`,
  `GetConfigOptionByName` — `:425-426, 462`.
- `ProcessConfigFile`, `ParseConfigFile`, `ParseConfigFp`,
  `ParseConfigDirectory` — `:153-164, 427`.
- `AlterSystemSetConfigFile` — `:461`.
- `NewGUCNestLevel`, `RestrictSearchPath`, `AtEOXact_GUC`, `AtStart_GUC` —
  `:433-436`.
- GUC array helpers used by pg_db_role_setting: `TransformGUCArray`,
  `ProcessGUCArray`, `GUCArrayAdd/Delete/Reset` — `:465-471`.
- Serialization for parallel workers:
  `EstimateGUCStateSpace`, `SerializeGUCState`, `RestoreGUCState` — `:484-486`.
- `guc_malloc/realloc/strdup/free` — `:473-476`. Separate allocator
  family because GUC strings outlive any MemoryContext.
- `EXEC_BACKEND` only: `write_nondefault_variables`,
  `read_nondefault_variables` — `:478-481`. Windows fork emulation.
- Check-hook ereport macros:
  `GUC_check_errmsg`, `GUC_check_errdetail`, `GUC_check_errhint`,
  `GUC_check_errcode` — `:497-513`. The check-hook returns `false` and
  these stash the message strings for the caller to ereport.

## Invariants

- A GUC change request is honored only if its `GucSource` >= the current
  source. (`PGC_S_OVERRIDE` is the special bypass.) [from-comment, `:84-87`]
- `PGC_S_INTERACTIVE` is NOT an actual source — it's a marker for
  "anything higher is interactive". [from-comment, `:91-93`]
- `PGC_S_TEST` is used by `ALTER DATABASE/ROLE SET` and `CREATE FUNCTION SET
  clauses` to test the value without applying. Check hooks must be
  forgiving in this case (e.g. NOTICE instead of ERROR for nonexistent
  referenced objects). [from-comment, `:95-102`]
- `PGC_S_DYNAMIC_DEFAULT` is what to use for any non-compile-time default
  on a `PGC_INTERNAL` GUC so that `pg_settings.source` reports "default".
  [from-comment, `:104-107`]
- `GUC_UNIT_KB`-tagged GUCs must compute byte counts as
  `value * (Size) 1024` to avoid 32-bit int overflow. [from-comment, `:23-24`]
- `GUC_NOT_WHILE_SEC_REST`-flagged GUCs refuse SET while a
  `SECURITY_RESTRICTED_OPERATION` is in effect (i.e., inside
  `SwitchToUntrustedUser` or a SECURITY DEFINER function with restricted
  search_path). [inferred from flag name, `:226`]
- `GUC_ALLOW_IN_PARALLEL` — only flagged GUCs are allowed to be set
  while running as a parallel worker. [from-flag, `:230`]
- Check hooks may set `*extra` to a malloc'd struct; PG manages its
  lifetime, but a check hook that returns `false` after malloc'ing `*extra`
  leaks unless the caller frees it. [from-comment in guc_tables.h, see
  guc_tables.h.md]
- Custom-prefix GUC namespace: `MarkGUCPrefixReserved("foo")` declares
  the `foo.*` namespace exclusive — placeholders without a real Define
  call will be warned about. [from-comment, `:418-421`]

## Notable internals

- `guc_malloc` / `guc_realloc` / `guc_strdup` / `guc_free` are a separate
  family from `palloc` because GUC string values must persist past any
  memory-context reset. They take an `elevel` so the caller can decide
  whether OOM should ereport or just return NULL. [verified from
  signature, `:473-476`]
- `GUC_check_errmsg` macro hides a comma-expression that calls
  `pre_format_elog_string` and then sets a globally-visible
  `GUC_check_errmsg_string` — the calling sequence is
  `GUC_check_errmsg("not allowed")` then `return false`, after which
  set_config_option reads the globals and ereports. [verified-by-code,
  `:497-513`]
- `EXEC_BACKEND` mode (Windows) serializes non-default GUC values to a
  temp file when spawning each new backend; non-Windows uses fork to
  inherit them. `write_nondefault_variables` / `read_nondefault_variables`
  are the entry points. [verified-by-code, `:478-481`]

## Trust-boundary / Phase D surface

- `GUC_DISALLOW_IN_FILE` (`:222`) and `GUC_DISALLOW_IN_AUTO_FILE` (`:227`)
  are the only header-level guards on filesystem-touching GUCs. There's
  no flag like "GUC writes a path" that would force review; new GUCs
  that touch the filesystem (e.g. `ssl_ca_file`) need ad-hoc audit.
  [ISSUE-defense-in-depth: no taxonomy/flag for "filesystem-touching
  GUCs"; flag review is by convention (likely)]
- `GUC_SUPERUSER_ONLY` (`:224`) only hides the value from non-superusers;
  it does NOT restrict who can SET — that's controlled by `GucContext`
  (`PGC_SUSET`). The two are easy to confuse. [ISSUE-api-shape:
  GUC_SUPERUSER_ONLY hides on SHOW but doesn't restrict SET; load-bearing
  difference vs PGC_SUSET (likely)]
- `set_config_option(elevel=…)` accepts arbitrary elevel — a caller
  passing `WARNING` when the proper response would be `ERROR` silently
  ignores invalid values. The header has no recommendation on which
  elevel callers should use. [ISSUE-error-handling:
  `set_config_option` elevel parameter is a footgun (maybe)]
- `GUC_check_errmsg` writes to three globals
  (`GUC_check_errmsg_string`, `_errdetail_string`, `_errhint_string`) —
  these are process-wide and NOT thread-safe; nested check-hook
  invocation would clobber each other. PG doesn't nest them today but a
  future async path could. [ISSUE-concurrency: GUC check error globals
  are not reentrant (maybe)]
- `SerializeGUCState`/`RestoreGUCState` is what propagates session GUCs
  to parallel workers. Any GUC NOT marked `GUC_ALLOW_IN_PARALLEL` is
  excluded — but a check hook that mutates a process-global (e.g. opens
  a file) on assignment means the worker won't see the same side effect.
  [ISSUE-correctness: assign-hook side effects (file opens, locale
  setlocale) are NOT replicated to parallel workers via SerializeGUCState
  (maybe)]
- `AllowAlterSystem` (`:293`) is a runtime-toggleable bool that disables
  the `ALTER SYSTEM` command. Some hardening guides recommend
  `alter_system_disable`; the header doesn't expose the precise
  mechanism. [ISSUE-documentation: `AllowAlterSystem` flag undocumented
  in header (nit)]
- `ConfigFileName`, `HbaFileName`, `IdentFileName`, `HostsFileName`,
  `external_pid_file` (`:312-316`) are exposed as `PGDLLIMPORT char *` —
  extensions can read but in principle could rewrite them, which would
  cause the next SIGHUP reload to pull from a different file. Defense in
  depth would be `const char *`. [ISSUE-defense-in-depth: PGDLLIMPORT
  config-file paths are mutable from C (nit)]
- `current_role_is_superuser` (`:291`) is exposed as `PGDLLIMPORT bool` —
  an extension could in principle clobber it to gain privileges. The
  symbol exists for SHOW purposes; in practice it's updated only by
  `SetSessionAuthorization`. [ISSUE-defense-in-depth: superuser bool
  exported as mutable PGDLLIMPORT (nit)]
- `RestrictSearchPath()` (`:435`) is the function CVE-2023-2454
  introduced for restricting search_path during maintenance. Pairs with
  `SwitchToUntrustedUser`; header doesn't cross-reference.
  [ISSUE-documentation: RestrictSearchPath / SwitchToUntrustedUser
  cross-reference missing (nit)]
- The `PGC_S_TEST` "be forgiving" contract (`:95-102`) is enforced only
  by convention in each check hook. A new check hook that hard-errors on
  PGC_S_TEST will break ALTER DATABASE SET / CREATE FUNCTION SET clause
  flows for objects that don't yet exist. [ISSUE-correctness: PGC_S_TEST
  forgiveness is by convention; easy to break (maybe)]

## Cross-refs

- `knowledge/files/src/include/utils/guc_hooks.h.md` — every declared
  check_/assign_/show_ hook for core GUCs.
- `knowledge/files/src/include/utils/guc_tables.h.md` — `config_generic`
  and the per-type structs that back this API.
- `knowledge/files/src/include/utils/conffiles.h.md` — file-include support.
- `knowledge/files/src/include/utils/usercontext.h.md` — `RestrictSearchPath`
  is the GUC-side half of the CVE-2023-2454 fix.
- `knowledge/idioms/gucs-bgworker-parallel.md` — operational checklist.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-defense-in-depth: no flag for "filesystem-touching GUCs"; audit
   is by convention (likely)] — `source/src/include/utils/guc.h:214-230`.
2. [ISSUE-api-shape: `GUC_SUPERUSER_ONLY` hides on SHOW but doesn't
   restrict SET; easily confused with PGC_SUSET (likely)] —
   `source/src/include/utils/guc.h:224`.
3. [ISSUE-error-handling: `set_config_option` elevel parameter accepts
   any level; WARNING silently drops invalid values (maybe)] —
   `source/src/include/utils/guc.h:445`.
4. [ISSUE-concurrency: GUC check-hook error globals
   (`GUC_check_errmsg_string` et al.) are not reentrant (maybe)] —
   `source/src/include/utils/guc.h:497-499`.
5. [ISSUE-correctness: assign-hook side effects are NOT replicated to
   parallel workers via SerializeGUCState (maybe)] —
   `source/src/include/utils/guc.h:485`.
6. [ISSUE-defense-in-depth: `ConfigFileName`/`HbaFileName`/etc. exported
   as mutable PGDLLIMPORT char* (nit)] —
   `source/src/include/utils/guc.h:312-316`.
7. [ISSUE-defense-in-depth: `current_role_is_superuser` exported as
   mutable PGDLLIMPORT bool (nit)] —
   `source/src/include/utils/guc.h:291`.
8. [ISSUE-documentation: `AllowAlterSystem` flag undocumented at header
   level (nit)] — `source/src/include/utils/guc.h:293`.
9. [ISSUE-documentation: `RestrictSearchPath` linkage to
   `SwitchToUntrustedUser` (usercontext.h) is invisible (nit)] —
   `source/src/include/utils/guc.h:435`.
10. [ISSUE-correctness: PGC_S_TEST "be forgiving" is a convention easily
    broken by new check hooks (maybe)] —
    `source/src/include/utils/guc.h:95-102`.
