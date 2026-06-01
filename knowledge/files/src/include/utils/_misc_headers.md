# `src/include/utils/` (misc/activity/hash/resowner/fmgr/mb headers — combined)

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/include/utils/` and adjacent dirs

## utils/misc/ counterparts

- `guc.h` — public GUC API. `GucContext` enum (PGC_INTERNAL ..
  PGC_USERSET), `GucSource` enum, `set_config_option` family,
  `DefineCustomBoolVariable` and friends, `GetConfigOption`.
- `guc_hooks.h` — declarations of every `check_*` / `assign_*` /
  `show_*` hook used by the built-in GUC table.
- `guc_tables.h` — `struct config_generic` and its bool/int/real/string/
  enum subclasses; `pg_settings` view backs onto this.
- `guc_internal.h` — guc.c/guc_funcs.c shared types.
- `ps_status.h` — `init_ps_display`, `set_ps_display`, `get_ps_display`.
- `rls.h` — `RLS_NONE`, `RLS_NONE_ENV`, `RLS_ENABLED`,
  `check_enable_rls`.
- `sampling.h` — `BlockSamplerData`, `ReservoirStateData`,
  `SamplerRandomState`, all the algorithm S/Z helpers.
- `timeout.h` — `TimeoutId` enum, `RegisterTimeout`,
  `enable_timeout_after`, `disable_timeout`, `get_timeout_indicator`.
- `conffiles.h` — `AbsoluteConfigLocation`, `ParseConfigDirectory`,
  `CONF_FILE_MAX_DEPTH`.
- `pg_rusage.h` — `PGRUsage`, `pg_rusage_init`, `pg_rusage_show`.

## utils/activity counterparts

- `wait_event.h` / `wait_event_types.h` — `WaitEventClass` enum,
  per-class event constants (auto-generated), `pgstat_report_wait_start`
  / `_end` inlines.
- `backend_progress.h` — `pgstat_progress_*` family, slot indexes.
- `backend_status.h` — `PgBackendStatus` struct, `PGSTAT_BEGIN_*` /
  `END_*` changecount macros, `pgstat_fetch_stat_beentry`.
- `pgstat.h` — top-level cumulative-stats public API: kind enum,
  `pgstat_report_*` per-kind, fetch functions, `PgStat_KindInfo`.
- `pgstat_internal.h` — private types shared across the activity dir.

## utils/hash & resowner

- `hsearch.h` — `HTAB`, `HASHCTL`, `HASHACTION`, the public dynahash
  API. Flag constants `HASH_ELEM`, `HASH_BLOBS`, `HASH_STRINGS`,
  `HASH_FUNCTION`, `HASH_PARTITION`, `HASH_SHARED_MEM`, `HASH_CONTEXT`.
- `resowner.h` — `ResourceOwner` opaque type, `ResourceOwnerDesc`
  (kind descriptor: name, release_phase, release_priority,
  ReleaseResource callback, optional DebugPrint), `ResourceOwnerCreate`,
  `ResourceOwnerRemember/Forget`, `ResourceOwnerEnlarge`. Per-kind
  constants `RELEASE_PRIO_*`.

## utils/fmgr

See `dfmgr.c` doc + the dedicated `fmgr.h` (already covered in
executor wave): `FunctionCallInfoBaseData`, `PG_FUNCTION_INFO_V1`,
`Pg_magic_struct` and `PG_MODULE_MAGIC_DATA` (the ABI key dfmgr.c
checks), `Pg_abi_values`.

## utils/mb

- `mb/pg_wchar.h` — encoding ids, `pg_wchar`, encoding table
  (`pg_wchar_table[]`) with `mblen` / `mbverify` / `mb2wchar` /
  `wchar2mb` function pointers per encoding.
- `mb/stringinfo_mb.h` — `appendStringInfoStringQuoted` and the
  multibyte-aware StringInfo helpers from `stringinfo_mb.c`.
