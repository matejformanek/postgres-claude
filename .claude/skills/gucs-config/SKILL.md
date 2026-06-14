---
name: gucs-config
description: Add or modify a custom GUC variable in a PostgreSQL backend patch or extension — covers DefineCustomBoolVariable / IntVariable / RealVariable / StringVariable / EnumVariable, picking the right GucContext (PGC_POSTMASTER / PGC_SIGHUP / PGC_SUSET / PGC_USERSET), MarkGUCPrefixReserved, the check/assign/show hook trio, GUC_LIST_INPUT / GUC_LIST_QUOTE / GUC_UNIT_MS / GUC_UNIT_KB / GUC_REPORT / GUC_EXPLAIN flags, and string-GUC guc_malloc rules. Use whenever a PG patch or extension calls DefineCustom*Variable, picks a GucContext, wires check/assign/show hooks, debugs a placeholder GUC, or marks a GUC reserved via MarkGUCPrefixReserved. Skip for DBA tuning of shared_buffers / max_connections / work_mem in production, dotenv / Viper / Dynaconf / Spring @Value configuration libraries, Kubernetes ConfigMap, Terraform variables, and non-PG application config systems.
when_to_load: Add or modify a custom GUC in a patch or extension; review a GUC's GucContext / flags choice; understand check/assign/show hook contracts; debug a placeholder-GUC issue.
companion_skills:
  - extension-development
  - bgworker-and-extensions
  - parallel-query
  - coding-style
  - error-handling
---

# gucs-config — custom GUC variables

This is the procedural cookbook for adding custom GUC variables to a
PostgreSQL backend patch or extension. For the conceptual model see
`knowledge/idioms/guc-variables.md`.

This skill is one of three siblings that share the
`_PG_init` / postmaster-lifecycle boundary:
- **gucs-config** (this skill) — custom GUC variables.
- `bgworker-and-extensions` — RegisterBackgroundWorker, shared-library hooks.
- `parallel-query` — ParallelContext + parallel-safe markings.

## 1. Picking the right Define*Variable

Five typed entry points, all in `utils/guc.h`.
[verified-by-code `source/src/include/utils/guc.h:358-416`]

| Type | Function | Notes |
|---|---|---|
| bool | `DefineCustomBoolVariable` | |
| int | `DefineCustomIntVariable` | with `minValue` / `maxValue` |
| double | `DefineCustomRealVariable` | with `minValue` / `maxValue` |
| string | `DefineCustomStringVariable` | `valueAddr` is `char **`, see §5 |
| enum | `DefineCustomEnumVariable` | takes a `const struct config_enum_entry[]` |

All five take the same trailing trio of hooks: `check_hook`, `assign_hook`,
`show_hook` (any can be NULL).

## 2. GucContext — when the value can change

[verified-by-code `source/src/include/utils/guc.h:71-80`]

| `GucContext` | When the user can change it |
|---|---|
| `PGC_INTERNAL` | Never — display-only (e.g. `server_version`). |
| `PGC_POSTMASTER` | Only at postmaster startup (`postgresql.conf` / cmd line). |
| `PGC_SIGHUP` | Postmaster start OR config-reload (SIGHUP / `pg_reload_conf()`). |
| `PGC_SU_BACKEND` | Start of backend, superusers can pass via startup packet. |
| `PGC_BACKEND` | Start of backend (libpq `PGOPTIONS`), then fixed. |
| `PGC_SUSET` | Any time by a superuser, including `SET`. |
| `PGC_USERSET` | Any time by anyone. |

**Rule of thumb:** pick the loosest context that's still safe. If
changing the value mid-session would require restarting a worker or
reallocating shared memory, use `PGC_POSTMASTER`. If it just changes
a runtime threshold, use `PGC_SIGHUP` or `PGC_SUSET`.

## 3. Skeleton — `_PG_init` for an extension with GUCs

```c
void
_PG_init(void)
{
    DefineCustomIntVariable("my_ext.naptime",
                            "Seconds between scans.",
                            NULL,           /* long_desc */
                            &my_naptime,    /* int *valueAddr */
                            10,             /* boot_val */
                            1, INT_MAX,     /* min, max */
                            PGC_SIGHUP,
                            GUC_UNIT_S,     /* flags — UNIT_S = seconds */
                            NULL, NULL, NULL); /* check/assign/show */

    DefineCustomStringVariable("my_ext.database",
                               "DB to connect to.",
                               NULL,
                               &my_database,
                               "postgres",
                               PGC_POSTMASTER,
                               0,
                               NULL, NULL, NULL);

    /* MUST be called AFTER all DefineCustom* calls. */
    MarkGUCPrefixReserved("my_ext");
}
```

[verified-by-code `source/src/test/modules/worker_spi/worker_spi.c:303-360`]

## 4. `MarkGUCPrefixReserved`

Call exactly once per extension, **after** every `DefineCustom*Variable` for
your prefix. It does two things:

1. Removes any *placeholder* GUCs (`GUC_CUSTOM_PLACEHOLDER`) under that
   prefix — these get created when a config file mentions a custom variable
   before the defining extension loads. Without removal, parallel-worker
   startup later trips over them.
2. Adds the prefix to a list so future placeholders under it are refused —
   typos in `postgresql.conf` (`my_ext.napitme`) now produce a clear error
   instead of silently being accepted.

[verified-by-code `source/src/backend/utils/misc/guc.c:5178-5228`]

The old name `EmitWarningsOnPlaceholders` is still a `#define` alias —
prefer the new name in new code. [verified-by-code
`source/src/include/utils/guc.h:421`]

## 5. String GUCs and `guc_malloc`

For string GUCs, `valueAddr` is a `char **`. The pointed-to storage is
owned by guc.c and must be allocated with `guc_malloc` / `guc_strdup` —
**never `palloc`**. If a check_hook wants to replace the proposed value
it must `guc_malloc` the new value and `guc_free` the old one.
[from-README `source/src/backend/utils/misc/README:51-60`]

## 6. The hook trio

### `check_hook(newval *, void **extra, GucSource source) → bool`

- Validate the proposed value; return false on reject.
- May modify `*newval` to canonicalize (round, lowercase, ...).
- May allocate an `extra` struct with `guc_malloc` and return it through
  `*extra` to pass derived data to the assign hook.
- For error detail: `GUC_check_errdetail(...)`, `GUC_check_errhint(...)`,
  `GUC_check_errcode(...)`, `GUC_check_errmsg(...)` — never `ereport(ERROR)`
  directly except on OOM.
- May run **outside any transaction** (bootstrap, postmaster startup,
  config reload). Guard catalog lookups with `IsTransactionState()`.
- May also be called just to validate without assigning — must not have
  side effects.

[from-README `source/src/backend/utils/misc/README:25-109`]

### `assign_hook(newval, void *extra) → void`

- Cannot fail (no return). Do all fallible work in the check hook.
- May be called during transaction rollback → no catalog lookups.

### `show_hook(void) → const char *`

- Customise what SHOW displays. Static buffer is fine; not reentrant.

## 7. Useful `flags` bits

[verified-by-code `source/src/include/utils/guc.h:214-242`]

| Flag | Effect |
|---|---|
| `GUC_LIST_INPUT` | Value is a comma-separated list — needed to use lists at all. |
| `GUC_LIST_QUOTE` | Each list element is double-quoted on serialization. Required for lists of identifiers (e.g. `search_path`). |
| `GUC_UNIT_KB` / `_MB` / `_BYTE` / `_BLOCKS` | Int GUC understands `'128MB'`. |
| `GUC_UNIT_MS` / `_S` / `_MIN` | Time units. |
| `GUC_NOT_IN_SAMPLE` | Don't include in generated `postgresql.conf.sample`. |
| `GUC_SUPERUSER_ONLY` | Hide value from non-superusers in `pg_settings`. |
| `GUC_DISALLOW_IN_FILE` | Cannot appear in config file (set only at runtime). |
| `GUC_DISALLOW_IN_AUTO_FILE` | Cannot be set by `ALTER SYSTEM`. |
| `GUC_REPORT` | Auto-send `ParameterStatus` to client on change. |
| `GUC_EXPLAIN` | Include in `EXPLAIN (SETTINGS)` output. |
| `GUC_ALLOW_IN_PARALLEL` | OK to set inside a parallel-mode block. |

## 8. GUC state under workers (cross-cutting)

- **Parallel workers** — GUC state is serialized by the leader and
  restored in each worker by `ParallelWorkerMain` before your code runs.
  Workers see exactly the leader's GUC values at launch time. If a
  `PGC_USERSET` GUC changes mid-flight, in-flight workers do *not* see
  the change. See `parallel-query` for the launch mechanics.

- **Background workers** (non-parallel) — GUC state is whatever
  `postgresql.conf` says at start. To honour SIGHUP, install
  `SignalHandlerForConfigReload` and call
  `ProcessConfigFile(PGC_SIGHUP)` when `ConfigReloadPending` is set.
  See `bgworker-and-extensions` for the signal-handling skeleton.

## 9. Checklist

- [ ] `_PG_init` defines every custom GUC.
- [ ] `MarkGUCPrefixReserved(prefix)` is called *after* all definitions.
- [ ] String storage uses `guc_malloc` / `guc_strdup`, never `palloc`.
- [ ] `check_hook` is side-effect-free and uses `GUC_check_errdetail` (not
      `ereport(ERROR)`) for validation failures.
- [ ] `check_hook` guards catalog lookups with `IsTransactionState()`.
- [ ] Right `GucContext` chosen (don't use `PGC_USERSET` if the change
      would require restarting workers).
- [ ] Unit flag set on int GUCs that represent size or time.
- [ ] List GUCs have `GUC_LIST_INPUT`, and `GUC_LIST_QUOTE` if elements
      are identifiers.

## 10. Useful greps

- All custom GUC definitions:
  `grep -RIn 'DefineCustom\(Bool\|Int\|Real\|String\|Enum\)Variable' source/src`
- All check / assign hooks in tree:
  `grep -RIn 'check_hook\|assign_hook' source/src/include/utils/guc.h`

## Cross-references

- `.claude/skills/bgworker-and-extensions/SKILL.md` — `_PG_init` flow for the surrounding extension; SIGHUP signal handler for picking up config reloads.
- `.claude/skills/parallel-query/SKILL.md` — how GUCs get restored in parallel workers; `GUC_ALLOW_IN_PARALLEL` flag.
- `.claude/skills/extension-development/SKILL.md` — `_PG_init`, `.control` file, `shared_preload_libraries`.
- `.claude/skills/coding-style/SKILL.md` — backend C style for the hook functions.
- `.claude/skills/error-handling/SKILL.md` — `GUC_check_errdetail` vs `ereport(ERROR)`; OOM contract.
- `knowledge/idioms/guc-variables.md` — conceptual model.
- `knowledge/files/src/include/utils/guc.h.md` — per-file doc for the public API surface.
- `knowledge/files/src/backend/utils/misc/guc.c.md` — per-file doc for the implementation.
