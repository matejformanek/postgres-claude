# Issues — `src/include/` (misc small dirs)

Combined issue register for the small include subdirectories not
big enough to warrant their own register:
`portability/`, `datatype/`, `mb/`, `archive/`, `bootstrap/`,
plus the top-level `src/include/miscadmin.h` (which names this
register in its own cross-ref block).

**Parent docs:** `knowledge/files/src/include/{portability,datatype,mb,archive,bootstrap}/*.h.md`
and `knowledge/files/src/include/miscadmin.h.md`.

## Open / Triaged

### portability/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/portability/instr_time.h:21-25 | doc-drift | nit | `INSTR_TIME_SET_CURRENT_FAST` vs `INSTR_TIME_SET_CURRENT` (OOO vs fenced) is easy to confuse for benchmarks | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/instr_time.h:152-153 | question | nit | `pg_set_timing_clock_source(TSC)` false-return on unavailability — should frontends ereport on fallback? | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/instr_time.h:160-162 | undocumented-invariant | nit | `timing_tsc_frequency_khz = -1` sentinel on `int32` — would break on signed→unsigned migration | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/instr_time.h:227-239 | correctness | nit | `pg_get_ticks_system` uses `Assert(timing_initialized)`; release builds skip the check, returning a pre-init clock read | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/instr_time.h:170-174 | question | nit | `TscClockSourceInfo.frequency_source[128]` — fixed-size buffer for CPUID strings could truncate | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/mem.h:41-44 | stale-todo | nit | `MAP_FAILED` fallback comment says "really old systems"; unreachable on any modern POSIX target | open | files/.../portability/mem.h.md |
| 2026-06-11 | src/include/portability/mem.h:28-31 | doc-drift | nit | `MAP_HASSEMAPHORE` current-platform impact not stated | open | files/.../portability/mem.h.md |
| 2026-06-11 | src/include/portability/mem.h:15 | style | nit | `IPCProtection = 0600` octal literal — could be `S_IRUSR|S_IWUSR` for clarity | open | files/.../portability/mem.h.md |

### datatype/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/datatype/timestamp.h:115-118 | question | nit | `DAYS_PER_MONTH = 30` and `DAYS_PER_YEAR = 365.25` foot-gun in EXTRACT(epoch FROM interval); not flagged in user docs | open | files/.../datatype/timestamp.h.md |
| 2026-06-11 | src/include/datatype/timestamp.h:47-53 | undocumented-invariant | likely | `Interval` is 16 bytes (time:8 + day:4 + month:4); cannot change without breaking on-disk compat | open | files/.../datatype/timestamp.h.md |
| 2026-06-11 | src/include/datatype/timestamp.h:41 | stale-todo | likely | `fsec_t` is int32 microseconds — "beware of overflow if many seconds"; foot-gun in callers | open | files/.../datatype/timestamp.h.md |
| 2026-06-11 | src/include/datatype/timestamp.h:227-231 | undocumented-invariant | nit | `IS_VALID_JULIAN` is intentionally looser than `IS_VALID_DATE`; ordering must be maintained | open | files/.../datatype/timestamp.h.md |

### mb/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/mb/pg_wchar.h:401-420 | correctness | likely | `utf8_to_unicode` returns `0xffffffff` on invalid input; callers must check (inline signature doesn't enforce) | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:65-72 | undocumented-invariant | likely | `pg_enc` numbering is pinned to libpq major version 5-era ABI — no compile-time check | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:148-155 | security | maybe | `MAX_CONVERSION_GROWTH=4` is a global cap; a user-defined conversion that exceeds it would overrun output buffers sized `4*srclen` | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:618-620 | security | maybe | `local2local` takes `tab` pointer without length argument; table size is caller-provided convention | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:550 | undocumented-invariant | likely | `pg_database_encoding_character_incrementer()` returns fn pointer; caller must keep current-DB-encoding context aligned | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:481-487 | style | nit | libpq-shim macros redirect `pg_char_to_encoding` etc. — historical baggage that's correct but dense | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/stringinfo_mb.h:21 | doc-drift | nit | `maxlen` unit (chars vs bytes) not documented in header | open | files/.../mb/stringinfo_mb.h.md |

### archive/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/archive/archive_module.h:43-49 | undocumented-invariant | likely | `ArchiveModuleCallbacks` ABI has no version field; reorder = silent miscall | open | files/.../archive/archive_module.h.md |
| 2026-06-11 | src/include/archive/archive_module.h:32-41 | doc-drift | nit | Callback semantics referenced via "the archive modules documentation" but no in-header link | open | files/.../archive/archive_module.h.md |
| 2026-06-11 | src/include/archive/archive_module.h:63-65 | style | nit | `arch_module_check_errdetail` is a comma-expression macro; misuse is silent | open | files/.../archive/archive_module.h.md |
| 2026-06-11 | src/include/archive/shell_archive.h:14-22 | doc-drift | nit | `archive_library = ''` sentinel for in-tree shell archiver not in header | open | files/.../archive/shell_archive.h.md |

### bootstrap/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/bootstrap/bootstrap.h:26 | undocumented-invariant | likely | `MAXATTR = 40` is a silent ceiling for system-table column counts | open | files/.../bootstrap/bootstrap.h.md |
| 2026-06-11 | src/include/bootstrap/bootstrap.h:33 | question | nit | `attrtypes[MAXATTR]` is statically sized; is there ereport on overflow in DefineAttr? | open | files/.../bootstrap/bootstrap.h.md |

### miscadmin.h (top-level)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-16 | src/include/miscadmin.h:81-84 | defense-in-depth | likely | No header-level guidance on "should this be a critical section?"; only XLOG insertion uses one today, and a recoverable error inside a crit section turns ERROR into PANIC — the answer is almost always no. | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h | undocumented-invariant | maybe | `MyDatabaseHasLoginEventTriggers` is a per-backend cached flag set at InitPostgres; it goes stale across `CREATE EVENT TRIGGER`, so a connection restart is needed to observe login-event-trigger changes. | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h:319-323 | style | nit | `SECURITY_*` flags use 3 of ~32 bits with no `SECURITY_MAX_BIT` constant and no comment on reserved bits; the bit-allocation policy is comment-only. | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h:198-199 | doc-drift | nit | `MyCancelKey[]` cancel-key buffer size is opaque at the header (the fixed size lives in the implementation); the header gives no size hint. | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h:269-273 | defense-in-depth | nit | Tuning GUCs (`work_mem` etc.) are exposed as mutable `PGDLLIMPORT int`; an extension can scribble on them mid-query with no protection. | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h:340-381 | api-shape | likely | `BackendType` is a hard-coded enum; pluggable extension worker types (e.g. logical-replication apply workers) all lump into `B_BG_WORKER`, and new entries must also update `child_process_kinds` in launch_backend.c plus `NUM_AUXILIARY_PROCS`. | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h:438-440 | security | likely | `InitializeSessionUserId(..., bypass_login_check)` is a bare bool; passing `true` bypasses NOLOGIN checks — a security-sensitive flag with no enum naming. | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h:506-510 | security | likely | `INIT_PG_OVERRIDE_ROLE_LOGIN = 0x0004` bypasses the LOGIN check (used by pg_upgrade); no "INTERNAL USE ONLY" marker warns off new callers. | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h:544 | defense-in-depth | likely | `shmem_request_hook` is a single-global mutable `PGDLLIMPORT`; multi-extension installs must chain, and an extension that overwrites rather than chains silently loses the prior subscriber (no header-level chaining idiom). | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h:128 | style | nit | `CHECK_FOR_INTERRUPTS()` is a do/while macro; the `if (cond) CHECK_FOR_INTERRUPTS(); else ...` semicolon hazard is real but caught by `-Wempty-body`. Already mitigated. | open | files/src/include/miscadmin.h.md |
| 2026-06-16 | src/include/miscadmin.h:108,154-156 | correctness | maybe | `CritSectionCount` is `volatile uint32`; a mis-paired `END_CRIT_SECTION` without `START` underflows to `0xFFFFFFFF`, silently enabling crit-section semantics globally. The cassert Assert catches it but release builds wrap. | open | files/src/include/miscadmin.h.md |
| 2026-06-29 | c.h:988 | style | nit | `ExceptionalCondition` extern at `c.h:988` is gated by `!FRONTEND` per the contract; new extern declarations routinely miss this gate | open | knowledge/files/src/include/c.h.md §Potential issues |
| 2026-06-29 | c.h | undocumented-invariant | nit | `Min`/`Max` multi-eval not flagged at definition site | open | knowledge/files/src/include/c.h.md §Potential issues |
| 2026-06-29 | c.h | undocumented-invariant | nit | `MemSet`'s `Size _len = (len)` truncates if caller passes wider int | open | knowledge/files/src/include/c.h.md §Potential issues |
| 2026-06-29 | c.h | correctness | likely | `pg_unreachable` codegen differs between cassert and release; a flow that hits `abort()` in cassert may UB silently in release | open | knowledge/files/src/include/c.h.md §Potential issues |
| 2026-06-29 | c.h | doc-drift | nit | `HAVE_INT128` gate not mentioned beside `int128` typedef | open | knowledge/files/src/include/c.h.md §Potential issues |
| 2026-06-29 | c.h | doc-drift | nit | `PGDLLEXPORT` visibility-attribute requirement not loud enough | open | knowledge/files/src/include/c.h.md §Potential issues |
| 2026-06-29 | c.h | stale-todo | nit | MinGW-64 setjmp workaround could be removed once buildfarm drops mingw-w64-x86_64 | open | knowledge/files/src/include/c.h.md §Potential issues |
| 2026-06-29 | fmgr.h | undocumented-invariant | likely | no compile-time `StaticAssert(sizeof(Pg_abi_values) == expected_packed_size)`; future field additions could silently break ABI compatibility detection | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | fmgr.h | security | likely | fmgr_hook is unrestricted by superuser — any preloaded library can install it | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | fmgr.h | api-shape | likely | stack allocation of `FunctionCallInfoBaseData` by sizeof silently under-allocates `args[]` | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | fmgr.h | undocumented-invariant | maybe | isnull reset on re-use is comment-only; no Assert | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | fmgr.h | api-shape | nit | PG_GETARG_FLOATx has no type-system protection | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | fmgr.h | api-shape | nit | PG_MODULE_MAGIC placement contract not enforced | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | fmgr.h | style | nit | abi_extra should be ASCII-printable | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | fmgr.h | api-shape | nit | DirectFunctionCall family limited to 9 args | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | fmgr.h | defense-in-depth | likely | fmgr_hook lacks chained-hook idiom in header docs | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | fmgr.h | style | nit | `load_file` restricted parameter is bare bool | open | knowledge/files/src/include/fmgr.h.md §Potential issues |
| 2026-06-29 | funcapi.h | undocumented-invariant | likely | SRF non-memory resource leakage on early-exit is comment-only | open | knowledge/files/src/include/funcapi.h.md §Potential issues |
| 2026-06-29 | funcapi.h | api-shape | likely | SRF_IS_FIRSTCALL conflates `fn_extra` usage | open | knowledge/files/src/include/funcapi.h.md §Potential issues |
| 2026-06-29 | funcapi.h | correctness | likely | SRF_RETURN_NEXT assumes resultinfo is ReturnSetInfo | open | knowledge/files/src/include/funcapi.h.md §Potential issues |
| 2026-06-29 | funcapi.h | style | nit | flag bits should be enum | open | knowledge/files/src/include/funcapi.h.md §Potential issues |
| 2026-06-29 | funcapi.h | correctness | nit | HeapTupleGetDatum has no NULL-`t_data` guard | open | knowledge/files/src/include/funcapi.h.md §Potential issues |
| 2026-06-29 | funcapi.h | style | nit | bare bool api parameter | open | knowledge/files/src/include/funcapi.h.md §Potential issues |
| 2026-06-29 | getopt_long.h | style | nit | no static-assert that `sizeof(struct option)` matches expected | open | knowledge/files/src/include/getopt_long.h.md §Potential issues |
| 2026-06-29 | getopt_long.h | doc-drift | nit | getopt_long porting requirements not documented at header | open | knowledge/files/src/include/getopt_long.h.md §Potential issues |
| 2026-06-29 | getopt_long.h | style | nit | bare global macro names from POSIX | open | knowledge/files/src/include/getopt_long.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | correctness | likely | MAXPGPATH = 1024 < Linux PATH_MAX = 4096 silently truncates long paths | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | api-shape | likely | NAMEDATALEN = 64 is a hard limit for forks with long identifiers | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | api-shape | nit | FUNC_MAX_ARGS in ABI block means forks need custom backend | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | correctness | likely | MAXPGPATH = 1024 silently truncates | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | security | confirmed | DEFAULT_PGSOCKET_DIR `/tmp` is a known socket-squatting hazard | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | stale-todo | nit | PG_CACHE_LINE_SIZE could be configure-detected | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | correctness | maybe | PG_IO_ALIGN_SIZE = 4 KB may be insufficient for 16 KB sector NVMe | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | stale-todo | likely | SLRU_PAGES_PER_SEGMENT could be made GUC-tunable | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | stale-todo | nit | VG client requests slow non-VG runs | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_config_manual.h | style | nit | auto-enable hides perf cost | open | knowledge/files/src/include/pg_config_manual.h.md §Potential issues |
| 2026-06-29 | pg_getopt.h | style | nit | portability of optind declaration on Windows is fragile | open | knowledge/files/src/include/pg_getopt.h.md §Potential issues |
| 2026-06-29 | pg_getopt.h | style | nit | optreset branch grows linearly with platforms | open | knowledge/files/src/include/pg_getopt.h.md §Potential issues |
| 2026-06-29 | pg_getopt.h | correctness | nit | no signature compatibility check at link | open | knowledge/files/src/include/pg_getopt.h.md §Potential issues |
| 2026-06-29 | pg_trace.h | stale-todo | nit | pg_trace.h is a one-line stub; consider direct include of probes.h or merging | open | knowledge/files/src/include/pg_trace.h.md §Potential issues |
| 2026-06-29 | pg_trace.h | api-shape | nit | no probe-name namespace allocation | open | knowledge/files/src/include/pg_trace.h.md §Potential issues |
| 2026-06-29 | pgstat.h | undocumented-invariant | likely | PGSTAT_FILE_FORMAT_ID bump is comment-only; no static-assert on struct sizes | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | undocumented-invariant | likely | pg_memory_is_all_zeros pattern constrains struct layout; new field additions silently break it if non-zero by default | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | style | nit | pgstat_track_functions GUC declared as `int` not enum | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | style | nit | pgstat.h fan-in too broad | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | correctness | maybe | PGSTAT_FILE_FORMAT_ID discipline is comment-only (confirmed echo of A15 ISSUE pattern) | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | api-shape | nit | PgStat_StatDBEntry has no version field | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | doc-drift | nit | slotsync_skip_count is single bucket | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | defense-in-depth | nit | timing counters mutable via PGDLLIMPORT | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | style | nit | pgstat GUCs declared as int | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | style | nit | side-effect in pgstat_should_count_relation | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | leak | maybe | pgstat_acquire/drop_replslot pairing not enforced | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgstat.h | doc-drift | nit | xl_xact_stats_item layout opaque at header | open | knowledge/files/src/include/pgstat.h.md §Potential issues |
| 2026-06-29 | pgtar.h | style | nit | no StaticAssert anchoring tarHeaderOffset values | open | knowledge/files/src/include/pgtar.h.md §Potential issues |
| 2026-06-29 | pgtar.h | api-shape | nit | tarCreateHeader partial-failure mutation not flagged | open | knowledge/files/src/include/pgtar.h.md §Potential issues |
| 2026-06-29 | pgtar.h | security | likely | isValidTarHeader does not validate against path traversal | open | knowledge/files/src/include/pgtar.h.md §Potential issues |
| 2026-06-29 | pgtar.h | correctness | nit | isValidTarHeader has no length parameter | open | knowledge/files/src/include/pgtar.h.md §Potential issues |
| 2026-06-29 | pgtar.h | doc-drift | nit | no provision for future PG-specific tar extensions | open | knowledge/files/src/include/pgtar.h.md §Potential issues |
| 2026-06-29 | pgtime.h | resource | maybe | `pg_tzset_offset` cache unbounded | open | knowledge/files/src/include/pgtime.h.md §Potential issues |
| 2026-06-29 | pgtime.h | correctness | likely | pg_tm convention mismatch is comment-only; no static helper to convert | open | knowledge/files/src/include/pgtime.h.md §Potential issues |
| 2026-06-29 | pgtime.h | defense-in-depth | nit | session/log_timezone are PGDLLIMPORT-mutable | open | knowledge/files/src/include/pgtime.h.md §Potential issues |
| 2026-06-29 | pgtime.h | documentation | nit | pg_tz_acceptable contract opaque | open | knowledge/files/src/include/pgtime.h.md §Potential issues |
| 2026-06-29 | pgtime.h | doc-drift | nit | timezone-abbreviation function family is duplicative | open | knowledge/files/src/include/pgtime.h.md §Potential issues |
| 2026-06-29 | port.h | security | confirmed | `pg_disable_aslr` deliberately weakens process ASLR; only intended for EXEC_BACKEND devs | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | port.h | security | likely | pg_disable_aslr should be more loudly marked dev-only | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | port.h | stale-todo | nit | libintl printf-replacement undef list is hand-maintained against libintl ABI | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | port.h | api-shape | likely | `&printf` function pointer silently bypasses pg_printf | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | port.h | api-shape | nit | `qsort` macro override is sticky | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | port.h | documentation | maybe | pg_strong_random init contract not in header | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | port.h | correctness | nit | pg_localeconv_r failure mode opaque | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | port.h | style | nit | pg_backend_random alias misleading | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | port.h | defense-in-depth | likely | pqsignal vs libc signal not flagged at header | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | port.h | style | nit | HAVE_* unconditional on Unix; documentation trust-the-platform | open | knowledge/files/src/include/port.h.md §Potential issues |
| 2026-06-29 | postgres.h | undocumented-invariant | nit | callers that round-trip `BoolGetDatum(DatumGetBool(x))` lose the "any nonzero" property; a custom Datum holding `0x42` becomes `0x01` | open | knowledge/files/src/include/postgres.h.md §Potential issues |
| 2026-06-29 | postgres.h | undocumented-invariant | nit | PointerGetDatum-macro contract not flagged at the alternative inline-function-form rejected at `postgres.h:340-351` | open | knowledge/files/src/include/postgres.h.md §Potential issues |
| 2026-06-29 | postgres.h | defense-in-depth | nit | NON_EXEC_STATIC turns module-private state into linker-visible symbols under `EXEC_BACKEND`; a load-time attacker on Windows can locate them | open | knowledge/files/src/include/postgres.h.md §Potential issues |
| 2026-06-29 | postgres.h | stale-todo | nit | SIZEOF_DATUM is vestigial; should be `#define DEPRECATED 1` or commented hostilely | open | knowledge/files/src/include/postgres.h.md §Potential issues |
| 2026-06-29 | postgres.h | api-shape | nit | asymmetric GetDatum/DatumGet pair for MultiXactId | open | knowledge/files/src/include/postgres.h.md §Potential issues |
| 2026-06-29 | postgres.h | api-shape | nit | `pg_ternary` "unset" easy to miss in switch | open | knowledge/files/src/include/postgres.h.md §Potential issues |
| 2026-06-29 | postgres_ext.h | doc-drift | nit | `Oid8` is backend-only but the comment at `c.h:755` doesn't explain why it's not in `postgres_ext.h` | open | knowledge/files/src/include/postgres_ext.h.md §Potential issues |
| 2026-06-29 | postgres_ext.h | undocumented-invariant | nit | no static assert that `sizeof(Oid) == 4` at the public-ABI boundary | open | knowledge/files/src/include/postgres_ext.h.md §Potential issues |
| 2026-06-29 | postgres_ext.h | correctness | maybe | `atooid` silently truncates inputs > 2^32 on 64-bit `long` platforms | open | knowledge/files/src/include/postgres_ext.h.md §Potential issues |
| 2026-06-29 | postgres_ext.h | api-shape | nit | PG_DIAG_* namespace is single-char ASCII with no allocation discipline document | open | knowledge/files/src/include/postgres_ext.h.md §Potential issues |
| 2026-06-29 | postgres_fe.h | style | nit | defensive `#ifndef FRONTEND` guard accepts non-1 values | open | knowledge/files/src/include/postgres_fe.h.md §Potential issues |
| 2026-06-29 | postgres_fe.h | undocumented-invariant | nit | omitting postgres_fe.h fails at link time, not compile time | open | knowledge/files/src/include/postgres_fe.h.md §Potential issues |
| 2026-06-29 | varatt.h | undocumented-invariant | likely | no `StaticAssert(sizeof(varatt_external) == 16)` to catch accidental padding | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | undocumented-invariant | nit | vartag_external numbering scheme is load-bearing for `VARTAG_IS_EXPANDED` macro | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | correctness | maybe | only 2 compression-method bits available; zstd + pglz + lz4 + 1 more would need an on-disk-format break | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | correctness | confirmed | unaligned `varatt_external` access (read or write) silently SIGBUS on alignment-strict platforms | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | correctness | maybe | pad-byte-zero invariant has no validity check | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | style | nit | vartag_external numbering scheme is undocumented for future additions | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | correctness | likely | `VARDATA_ANY` on external/compressed silently garbage | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | correctness | nit | compression-method bits not validated in release builds | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | doc-drift | nit | 2 GB vs 1 GB limit mismatch not flagged | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | stale-todo | likely | compression-method bit budget tight | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | varatt.h | style | nit | `sizeof(varattrib_1b_e)` semantics not documented | open | knowledge/files/src/include/varatt.h.md §Potential issues |
| 2026-06-29 | windowapi.h | api-shape | likely | NULL TREATMENT support requires explicit window-function opt-in | open | knowledge/files/src/include/windowapi.h.md §Potential issues |
| 2026-06-29 | windowapi.h | style | nit | window seek type is bare int not enum | open | knowledge/files/src/include/windowapi.h.md §Potential issues |
| 2026-06-29 | windowapi.h | undocumented-invariant | likely | WinSetMarkPosition usage is performance-only, not correctness; hidden hazard | open | knowledge/files/src/include/windowapi.h.md §Potential issues |
| 2026-06-29 | windowapi.h | api-shape | likely | window-frame mode opaque to extensions | open | knowledge/files/src/include/windowapi.h.md §Potential issues |
| 2026-06-29 | windowapi.h | api-shape | nit | per-partition memory size contract | open | knowledge/files/src/include/windowapi.h.md §Potential issues |
| 2026-06-29 | windowapi.h | documentation | nit | windowapi.h delegates almost all semantic docs to .c file | open | knowledge/files/src/include/windowapi.h.md §Potential issues |

## Wontfix / Submitted / Landed

(empty)

## Notes

- **`portability/`** is mostly historical-clean-up / minor
  documentation gaps. The TSC clock-source path (`instr_time.h`) is
  the only place with non-trivial concurrency contract
  (`ticks_per_ns_scaled` mutating mid-measurement).
- **`datatype/timestamp.h`** carries on-disk-compat invariants that
  prevent any meaningful change; the issues filed are
  documentation-grade.
- **`mb/pg_wchar.h`** is the highest Phase-D leverage in this misc
  bucket: encoding conversion is a frequent CVE surface area, and
  the `MAX_CONVERSION_GROWTH` and `local2local` invariants are
  externally relied on without compile-time checks.
- **`archive/archive_module.h`** has the same ABI-version-field
  weakness as `fdwapi.h`'s `FdwRoutine` — pattern worth tracking
  across all "plug in a function-pointer struct" interfaces.
- **`bootstrap/bootstrap.h`** is small but `MAXATTR=40` is a
  catalog-design hard ceiling worth flagging in any
  `catalog-conventions` skill update.
