# src/test/modules/dummy_index_am/dummy_index_am.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 353
**Verification depth:** full read

## Role

A minimal pluggable index access method ("Index AM template"): it provides an `amhandler` (`dihandler`) returning a fully-populated `IndexAmRoutine` whose build/insert/scan/vacuum callbacks are stubs that do nothing, and it exercises the full reloptions API by declaring one of every relopt type (int, real, bool, ternary, enum, two strings). Its primary purpose is to be a skeleton for new index AMs and to test `CREATE ACCESS METHOD` / reloptions plumbing. [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:4` [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:293`

## Public API

- `dihandler(internal)` — index AM handler returning a pointer to a static `IndexAmRoutine`. [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:293`
- `_PG_init()` — builds the reloptions table (`create_reloptions_table`). [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:349`

## Invariants

- INV-1: The reloptions parse table `di_relopt_tab` has 8 slots but exactly 7 options are registered (`option_int`, `option_real`, `option_bool`, `option_ternary_1`, `option_enum`, `option_string_val`, `option_string_null`); `dioptions` passes `lengthof(di_relopt_tab)` to `build_reloptions`. [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:25` [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:241`
- INV-2: A `DummyIndexOptions` struct used with `build_reloptions` must begin with `int32 vl_len_` (varlena header) and store string options as offsets, not pointers. [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:37`
- INV-3: `dicostestimate` deliberately sets startup and total cost to `1.0e10` so the planner never chooses this index. [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:218`
- INV-4: The handler must set `.type = T_IndexAmRoutine`; callbacks that the AM does not implement (e.g. `amgettuple`, `amgetbitmap`, `amcanreturn`, parallel-scan hooks) are explicitly `NULL`. [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:296` [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:336`

## Notable internals

- `create_reloptions_table` calls `add_reloption_kind()` then `add_{int,real,bool,ternary,enum,string}_reloption` for each option, recording `optname`/`opttype`/`offset` into `di_relopt_tab`; the enum uses a `relopt_enum_elt_def[]` value table terminated by a NULL name. [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:74` [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:49`
- One string option has a non-NULL default ("DefaultValue") and one has a NULL default and NULL description, with a shared `validate_string_option` validator that emits a NOTICE. [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:124` [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:62`
- `IndexAmRoutine` declares the AM's capability flags (`amstrategies = 0`, `amsupport = 1`, all `amcan*` false, `amparallelvacuumoptions = VACUUM_OPTION_NO_PARALLEL`, `amkeytype = InvalidOid`). [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:296`
- Stub callbacks: `dibuild` returns an `IndexBuildResult` claiming 0 heap and 0 index tuples; `diinsert` returns false; `dibulkdelete`/`divacuumcleanup` return NULL; `dibeginscan` builds a scan via `RelationGetIndexScan`; rescan/endscan are no-ops. [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:153` [verified-by-code] `source/src/test/modules/dummy_index_am/dummy_index_am.c:260`

## Cross-refs

- `source/src/include/access/amapi.h` — `IndexAmRoutine` struct and the index-AM callback signatures.
- `source/src/backend/access/index/amapi.c` — `amvalidate`/handler-validation helpers.
- `source/src/backend/access/common/reloptions.c` — `add_reloption_kind`, `add_*_reloption`, `build_reloptions`, `relopt_enum_elt_def`.
- `source/src/backend/access/index/genam.c` — `RelationGetIndexScan`.

## Potential issues

- **[ISSUE-undocumented-invariant: oversized relopt table]** `dummy_index_am.c:25` — `di_relopt_tab` is sized `[8]` but only 7 entries are filled, and `dioptions` passes `lengthof(di_relopt_tab)` (8) as the element count to `build_reloptions`. The 8th element is zero-initialized (static storage), so `build_reloptions` iterates one entry with `optname == NULL`; this is tolerated by reloptions.c but the slack slot is undocumented and easy to misread as a bug. Severity: nit.
