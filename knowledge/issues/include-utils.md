# Issues — `src/include/utils`

Per-subsystem issue register for the **utils header layer** — ACL/RLS, locale/GUC, type-system, memory primitives, backend-state, relation caches. 70 headers / ~163 entries surfaced 2026-06-09 by A15 (slices A15-1 sec/locale/GUC, A15-2 types/memory/datum, A15-3 backend-state).

**Parent docs:** `knowledge/files/src/include/utils/*` (98 docs total after A15).

**Sibling registers:** `knowledge/issues/utils.md` (A7's `src/backend/utils/{cache,adt}/*.c` 310 entries).

## Headlines

1. **PS title leaks SQL query text** including literal passwords to other OS users running `ps` — `update_process_title=on` is the Unix default. `ps_status.h` is the header anchor.
2. **`USE_INJECTION_POINTS` in a production binary = arbitrary dlopen + symbol execute** — `injection_point.h:30,49` deferred dlopen + first-hit attach hides attach-time failures. Production-build gate is the sole defense.
3. **`is_member_of_role` vs `has_privs_of_role` silent footgun** — header gives no deprecation marker for the legacy function that ignores INHERIT (historical privilege-leak source).
4. **`pg_str{lower,upper,fold}` pipe user `srclen` through ICU casemap (3× expansion) with no MaxAllocSize cap** — direct echo of A7's 50 MB→600 MB to_char finding at the API layer. Affects citext (A13), pg_trgm (A14), every text comparison.
5. **NAME→OID surface in `regproc.h` + `guc_hooks.h` check_search_path/check_default_table_access_method** — extends A3/A6/A7/A8/A9/A10 race; PGC_S_TEST-forgiving check hooks let ALTER DATABASE/ROLE SET pin identifiers that don't exist yet.
6. **`pg_xml_init` must wrap every libxml call** — XXE custom defense (A7) silently bypassed by direct libxml use; the contract is comment-only.
7. **`ParseDateTime` workbuf-sizing contract** is the strongest unstated invariant — direct echo of CVE-2007-3278 / CVE-2010-1170 lineage at the header layer.
8. **Expanded-datum in-place modify must be exception-safe** — `expandeddatum.h:30-34` informal but hard contract; mid-modification palloc failures must leave object internally consistent.
9. **NaN/EPSILON cluster echoes A13/A14** — `float.h` defines PG-specific NaN==NaN sort order, `geo_decls.h` uses non-transitive `FPeq` with DIFFERENT NaN behavior. Mixing in one opclass = recurring family.
10. **`backend_status.h` `st_activity_raw`** carries raw query text to `pg_stat_activity` (`checkUser`-gated); same leak family as A11 pg_stat_statements password capture. Redaction lives in postmaster.c, not enforced at header.
11. **`rel.h` `ViewOptions` (security_barrier / security_invoker / check_option) + `ruleutils.h`** — A7 cross-finding confirmed at header level: `pg_get_viewdef()` does NOT re-emit `WITH (security_*)` clauses. SQL callers silently lose security clauses; `pg_dump` rescues via direct `pg_class.reloptions`.
12. **`selfuncs.h` MCV-leak / stats-poisoning surface** — `acl_ok` + `statistic_proc_security_check` gate enforced per-estimator with NO single chokepoint; new estimators routinely miss it.

## Entries — A15-1 (sec / locale / GUC)

### ACL / RLS / usercontext (`acl.h`, `aclchk_internal.h`, `rls.h`, `usercontext.h`)
- [ISSUE-api-shape: `is_member_of_role` vs `has_privs_of_role` silent footgun (likely)] — `acl.h:216`
- [ISSUE-correctness: `get_role_oid` NAME→OID racey vs concurrent DROP ROLE (maybe)] — `acl.h:220`
- [ISSUE-correctness: `pg_largeobject_aclcheck_snapshot` snapshot parameter is load-bearing (maybe)] — `acl.h:267`
- [ISSUE-audit-gap: `aclcheck_error*` echoes attacker-supplied object names verbatim (nit)] — `acl.h:270-276`
- [ISSUE-correctness: `InternalGrant.privileges` mutated in place; reuse across objtypes silently wrong (maybe)] — `aclchk_internal.h:21`
- [ISSUE-audit-gap: `col_privs` AccessPriv nodes echoed in errors before name resolution (nit)] — `aclchk_internal.h:38`
- [ISSUE-api-shape: `check_enable_rls(noError=true)` collapses RLS_NONE and RLS_ENABLED (likely)] — `rls.h:34-39`
- [ISSUE-audit-gap: `row_security=off` is PGC_USERSET; audit must capture exec-time state (maybe)] — `rls.h:17`
- [ISSUE-documentation: usercontext.h is mute about which SECURITY_* bits `SwitchToUntrustedUser` sets (likely)] — `usercontext.h:23`
- [ISSUE-api-shape: `UserContext` provides no nesting guard for stacked sec-context changes (nit)] — `usercontext.h:15`

### Locale / formatting (`pg_locale.h`, `pg_locale_c.h`, `ascii.h`, `formatting.h`, `tzparser.h`)
- [ISSUE-resource: `pg_str{lower,upper,fold,title}` accept caller srclen with no MaxAllocSize check; ICU casemap 3× (likely)] — `pg_locale.h:183-194`
- [ISSUE-correctness: `pg_locale_t` cached by external modules outlives pg_collation invalidations (likely)] — `pg_locale.h:179` (A13 echo)
- [ISSUE-security: `icu_validation_level` is PGC_USERSET; downgrade bypasses CREATE COLLATION validation (maybe)] — `pg_locale.h:39`
- [ISSUE-correctness: `DEFAULT_COLLATION_OID` pinned by callers — separate static cache path (maybe)] — `pg_locale.h:140-143` (A14 echo)
- [ISSUE-correctness: no bounds guard for `c >= 128` in `pg_char_properties` lookup (maybe)] — `pg_locale_c.h:29`
- [ISSUE-correctness: `is_valid_ascii` reads past `s + len` if `len % chunk != 0` and Assert compiled out (likely)] — `ascii.h:34`
- [ISSUE-resource: `to_char` / `parse_datetime` accept unbounded format strings; ~12× compile expansion (confirmed, A7)] — `formatting.h:30`
- [ISSUE-resource: `str_tolower/upper/casefold` pipe caller `nbytes` to pg_strlower with no cap (likely)] — `formatting.h:21-24`
- [ISSUE-resource: `load_tzoffsets` array growth unbounded; no @INCLUDE depth limit visible (maybe)] — `tzparser.h:37`
- [ISSUE-audit-gap: full filename in tz parser errors leaks symlink targets (nit)] — `tzparser.h:33`

### GUC machinery (`guc.h`, `guc_hooks.h`, `guc_tables.h`, `conffiles.h`)
- [ISSUE-defense-in-depth: no flag for "filesystem-touching GUCs"; audit by convention (likely)] — `guc.h:214-230`
- [ISSUE-api-shape: `GUC_SUPERUSER_ONLY` hides SHOW but doesn't restrict SET; easily confused with PGC_SUSET (likely)] — `guc.h:224`
- [ISSUE-error-handling: `set_config_option` elevel accepts WARNING; silently drops invalid values (maybe)] — `guc.h:445`
- [ISSUE-correctness: assign-hook side effects not replicated to parallel workers via SerializeGUCState (maybe)] — `guc.h:485`
- [ISSUE-defense-in-depth: `ConfigFileName`/`HbaFileName`/etc. exported as mutable PGDLLIMPORT char* (nit)] — `guc.h:312-316`
- [ISSUE-defense-in-depth: `current_role_is_superuser` exported as mutable PGDLLIMPORT bool (nit)] — `guc.h:291`
- [ISSUE-correctness: `PGC_S_TEST` "be forgiving" convention easily broken by new check hooks (maybe)] — `guc.h:95-102`
- [ISSUE-security: `check_role` / `check_session_authorization` critical-trust hooks; header doesn't flag them (likely)] — `guc_hooks.h:122,131`
- [ISSUE-correctness: `check_search_path` is syntactic-only; schema existence lazy (likely)] — `guc_hooks.h:128`
- [ISSUE-correctness: AM/tablespace/ts_config check hooks PGC_S_TEST-forgiving (NAME-vs-OID race) (likely)] — `guc_hooks.h:56-60`
- [ISSUE-audit-gap: `application_name` flows to logs / pg_stat_activity unsanitised (nit)] — `guc_hooks.h:28`
- [ISSUE-correctness: `config_var_value.extra` is untyped void*; no layout agreement check/assign hooks (maybe)] — `guc_tables.h:42-49`
- [ISSUE-correctness: placeholder GUCs across extension-load require `MarkGUCPrefixReserved` discipline (maybe)] — `guc_tables.h:314`
- [ISSUE-security: `GetConfFilesInDir` follows symlinks; no header-documented stance (maybe)] — `conffiles.h:22`
- [ISSUE-defense-in-depth: no path-traversal sandboxing in `AbsoluteConfigLocation` (nit)] — `conffiles.h:20`
- [ISSUE-resource: `GetConfFilesInDir` has no per-directory file-count cap (maybe)] — `conffiles.h:22`

### Backend identity / misc (`ps_status.h`, `pidfile.h`, `injection_point.h`, `help_config.h`, `regproc.h`)
- [ISSUE-security: PS title leaks SQL text (incl. passwords) to any OS user (confirmed)] — `ps_status.h:32`
- [ISSUE-defense-in-depth: `update_process_title` is PGC_SUSET, not PGC_POSTMASTER (nit)] — `ps_status.h:22`
- [ISSUE-audit-gap: postmaster.pid concentrates PID/path/port/socket/listen/shmem-key (nit)] — `pidfile.h:17-32`
- [ISSUE-correctness: in-place pid-file writes are not atomic-rename; crash mid-write leaves partial line (nit)] — `pidfile.h:46-49`
- [ISSUE-dlopen: production build with `USE_INJECTION_POINTS` on = arbitrary-dlopen + symbol-execute (confirmed)] — `injection_point.h:30,49`
- [ISSUE-documentation: superuser requirement for `InjectionPointAttach` not at header level (likely)] — `injection_point.h:49`
- [ISSUE-api-shape: deferred dlopen at first hit hides attach-time failures (nit)] — `injection_point.h:49`
- [ISSUE-correctness: `stringToQualifiedNameList` is parse half of every NAME→OID race (likely)] — `regproc.h:28`
- [ISSUE-security: regproc.h is a core NAME→OID surface (A3/A6/A7/A8/A9/A10 echo) (likely)] — `regproc.h:28`

## Entries — A15-2 (types / memory / datum)

### Varlena types
- [ISSUE-documentation: array_recv DoS surface not surfaced at API level (nit, A7)] — `array.h:6-60`
- [ISSUE-documentation: NumericData on-disk format undocumented at header (nit)] — `numeric.h:55-57`
- [ISSUE-correctness: numeric typmod vs implementation cap easy to confuse (maybe)] — `numeric.h:32-34`
- [ISSUE-documentation: range_recv flag-vs-length consistency not surfaced (maybe)] — `rangetypes.h:38-46`
- [ISSUE-correctness: range LB_NULL/UB_NULL reserved bits masked silently (nit)] — `rangetypes.h:43-44,48-50`
- [ISSUE-correctness: multirange sorted/disjoint contract implicit (maybe)] — `multirangetypes.h:34-37`
- [ISSUE-documentation: inet_recv validation contract hidden (maybe)] — `inet.h:23-89`
- [ISSUE-correctness: varstr_levenshtein `trusted=true` flag is foot-gun (maybe)] — `varlena.h:21-28`
- [ISSUE-correctness: varbit_recv pad-bit-zero contract hidden (maybe)] — `varbit.h:25-28`
- [ISSUE-documentation: array iterator's `i` argument is misleading — iteration is sequential despite the index param; an `i == prev+1` assert under USE_ASSERT_CHECKING would catch misuse (nit)] — `arrayaccess.h:29-30`

### XML / JSON
- [ISSUE-correctness: pg_xml_init must wrap every libxml call (likely)] — `xml.h:65-70` (A7 critical)
- [ISSUE-documentation: XML_PARSE_NONET absence not referenced (maybe)] — `xml.h:1-94`
- [ISSUE-documentation: json stack-depth defense not visible at this layer (maybe)] — `json.h:1-35` (A5/A8 echo)
- [ISSUE-documentation: `pg_parse_json_or_ereport` macro hides hard-error path (nit)] — `jsonfuncs.h:47-48`

### Builtins / specialty
- [ISSUE-documentation: builtins.h grab-bag has no overview (nit)] — `builtins.h:1-140`
- [ISSUE-correctness: hard-error `pg_strtoint*` variants still ambient (maybe)] — `builtins.h:51-67`
- [ISSUE-documentation: cash scale tied to lc_monetary cross-database hazard (nit)] — `cash.h:5-17`
- [ISSUE-correctness: ParseDateTime workbuf sizing contract not surfaced (likely)] — `datetime.h:311-313` (CVE-2007/2010 echo)
- [ISSUE-correctness: datetime field-code range tied to typmod (likely)] — `datetime.h:81-87`
- [ISSUE-correctness: expanded-datum in-place modify exception safety (likely)] — `expandeddatum.h:30-34`
- [ISSUE-correctness: expanded-datum vs short-header collision (maybe)] — `expandeddatum.h:124-127`
- [ISSUE-correctness: expanded-record tupdesc-refcount-callback hazard (maybe)] — `expandedrecord.h:77-82`

### Float / geo
- [ISSUE-documentation: float.h ↔ ecpglib/data.c parallel copies (maybe)] — `float.h:57`
- [ISSUE-correctness: NaN==NaN is PG-only (maybe)] — `float.h:236-241` (A13/A14 echo)
- [ISSUE-correctness: EPSILON intransitivity in geo opclass-author footgun (maybe)] — `geo_decls.h:30-32`
- [ISSUE-correctness: NaN behavior differs between geo_decls.h and float.h (maybe)] — `geo_decls.h:33-34`

### Memory primitives
- [ISSUE-correctness: datumIsEqual is byte-image, not semantic equality (likely)] — `datum.h:42-44`
- [ISSUE-security: dsa handle-prediction privilege boundary undocumented (maybe)] — `dsa.h:127-136` (A8/A14 echo)
- [ISSUE-correctness: cross-area dsa_pointer dereferences silent (nit)] — `dsa.h:160-162`
- [ISSUE-documentation: fmgrtab catversion bump requirement implicit (maybe)] — `fmgrtab.h:1-49`
- [ISSUE-correctness: funccache pad-byte-zero by-comment-only (maybe)] — `funccache.h:59`
- [ISSUE-correctness: hash_seq_term required to avoid leaked scan flag (maybe)] — `hsearch.h:144-149`
- [ISSUE-documentation: pg_crc legacy error-detection properties unknown (nit, A11/A13 cluster echo)] — `pg_crc.h:67-73`
- [ISSUE-documentation: pg_prng not security-grade (nit)] — `sampling.h:16-23`
- [ISSUE-documentation: sentinel write/check is MEMORY_CONTEXT_CHECKING-only; production builds skip it so buffer-overrun sentinels corrupt silently (nit)] — `memdebug.h:51-72`
- [ISSUE-documentation: FPM_PAGE_SIZE is 4 kB, easily confused with the 8 kB BLCKSZ buffer page by readers grepping for the page constant (nit)] — `freepage.h:30`

## Entries — A15-3 (backend-state + relation caches)

### Backend status / pgstat
- [ISSUE-defense-in-depth: backend_status.h doesn't state query-text password-redaction policy (maybe)] — `backend_status.h:157`
- [ISSUE-correctness: `PGSTAT_BEGIN/END_WRITE_ACTIVITY` PANIC-on-error contract is comment-only (nit)] — `backend_status.h:184-187`
- [ISSUE-api-shape: `PGSTAT_KIND_EXPERIMENTAL=24` is shared default for unregistered extensions; collision expected (maybe)] — `pgstat_kind.h:54-59`
- [ISSUE-api-shape: only 9 custom-stats-kind slots cluster-wide; not documented as hard limit (nit)] — `pgstat_kind.h:50-52`
- [ISSUE-correctness: custom-kind `from_serialized_data` runs at startup before backend auth (maybe)] — `pgstat_internal.h:320-340`
- [ISSUE-api-shape: `accessed_across_databases` policy enforced only by single flag; no compile-time check (nit)] — `pgstat_internal.h:240-243`

### Portal / queryenvironment
- [ISSUE-documentation: portal.h Snapshot relationships routinely misunderstood (maybe)] — `portal.h:162-186`
- [ISSUE-documentation: queryenvironment.h gives no list of which subsystems may safely register an ENR (nit)] — `queryenvironment.h:47-49`

### Rel + relmapper + relptr
- [ISSUE-correctness: `RelationIs*View` macros guard relkind only under AssertMacro (cassert-only); release silently reads garbage (maybe)] — `rel.h:440-485`
- [ISSUE-correctness: `rd_toastoid` is a "hack"; release-mode mis-set silently misroutes toast pointers (maybe)] — `rel.h:242-251`
- [ISSUE-correctness: `RelationMapOidToFilenumberForDatabase` reads another DB's map without DB-level locks (maybe)] — `relmapper.h:41`
- [ISSUE-documentation: relmapper.h on-disk CRC discipline not documented (nit)] — `relmapper.h`
- [ISSUE-correctness: relptr offsets unchecked at access time; corrupted offsets undiagnosable (nit)] — `relptr.h:41-50`
- [ISSUE-defense-in-depth: relptr non-HAVE_TYPEOF path drops type check on store (nit)] — `relptr.h:76-80`

### Resource cleanup / triggers
- [ISSUE-documentation: `ResourceOwnerEnlarge` "must call before remember" contract in README only (maybe)] — `resowner.h:148`
- [ISSUE-documentation: reltrigger.h per-kind flag inventory hand-maintained alongside executor switch (nit)] — `reltrigger.h:56-78`

### Ruleutils / selectivity
- [ISSUE-security: ruleutils.h exposes `get_reloptions` but no `pg_get_viewdef` glue; SQL pg_get_viewdef loses security clauses (likely, A7 cross-finding)] — `ruleutils.h:54`
- [ISSUE-security: `statistic_proc_security_check` + `acl_ok` MCV-leak gate enforced per-estimator (likely, CVE class)] — `selfuncs.h:99-100,165`
- [ISSUE-defense-in-depth: `get_relation_stats_hook` lets FDW silently override stats per query without audit (maybe, A11 echo)] — `selfuncs.h:149-158`

### Shared tuplestore + skip
- [ISSUE-security: sharedtuplestore spill files raw MinimalTuple on disk; postgres-uid cross-process leak feasible (maybe)] — `sharedtuplestore.h:38-44`

### Wait / timeout
- [ISSUE-api-shape: timeout.h only 10 USER_TIMEOUT slots; not documented as hard cluster-wide limit (nit)] — `timeout.h:39-42`
- [ISSUE-documentation: timeout.h handler-context (deferred-via-CFI vs signal) not named in header (maybe)] — `timeout.h:46`
- [ISSUE-api-shape: `pgstat_report_wait_start` unconditional (no track_activities check); cross-role-visible even when monitoring "off" (nit)] — `wait_event.h:58-61`
- [ISSUE-documentation: the `0x02` gap in the wait-class encoding is uncommented; future readers may wonder whether it can be claimed (nit)] — `wait_classes.h:19-20`

## Cross-sweep references

- **A7** `src/backend/utils/{cache,adt}/*.c` 310 entries — many surface here at header layer (datetime, xml, formatting, acl, ruleutils, regproc).
- **A11/A13/A14** signature-collision cluster — pg_crc.h header anchor.
- **A13** btree_gist + **A14** seg/cube NaN cluster — float.h + geo_decls.h header anchors.
- **A13** citext + **A14** pg_trgm `DEFAULT_COLLATION_OID` pin — pg_locale.h header anchor.
- **A11** pg_stat_statements query-text capture — backend_status.h header echo.
- **A11** postgres_fdw stats-import — selfuncs.h `get_relation_stats_hook` echo.
- **NAME→OID cluster** (A3/A6/A7/A8/A9/A10) — regproc.h + guc_hooks.h header anchors.
- **A14** monitoring-as-extraction — backend_status.h + pgstat_internal.h + sharedtuplestore.h echoes.

## A22-A: top-level `src/include/*.h` core headers (2026-06-11)

17 core-API headers added in sweep A22 bucket A (~6,726 LOC). These
are the headers every PG backend developer sees first: `c.h`,
`postgres.h`, `postgres_fe.h`, `postgres_ext.h`, `fmgr.h`,
`funcapi.h`, `varatt.h`, `miscadmin.h`, `pgstat.h`, `port.h`,
`pgtime.h`, `pgtar.h`, `pg_trace.h`, `pg_getopt.h`,
`getopt_long.h`, `pg_config_manual.h`, `windowapi.h`.

### A22-A headlines

13. **`varatt_external` is stored UNALIGNED in tuples** (`varatt.h:27-29`) — must memcpy to local before field access; direct dereference SIGBUS on alignment-strict platforms. Equality test goes via memcmp (header must have ZERO padding); no `StaticAssert(sizeof(varatt_external) == 16)`.
14. **TOAST compression-method field is 2 bits** (`varatt.h:45-46, 520-526`) — pglz + lz4 + zstd consumes 3 of 4 patterns; future 4th method = on-disk-format break. The Assert in `VARATT_EXTERNAL_SET_SIZE_AND_COMPRESS_METHOD` is cassert-only.
15. **`Pg_abi_values` compared via memcmp must be padding-free** (`fmgr.h:458-460, 468-476`) — no compile-time check; future field additions could silently break module-compat detection. `FMGR_ABI_EXTRA` ≤ 32 bytes IS asserted.
16. **`fmgr_hook` is a single global with no chaining discipline at header level** (`fmgr.h:830-855`) — two preloaded sec-policy plugins silently overwrite each other; arbitrary-code-execution on every function call.
17. **`pg_disable_aslr` deliberately weakens process ASLR**, only `#ifdef EXEC_BACKEND` (`port.h:147-150`) — developer-only but no "DO NOT USE" warning at header.
18. **`DEFAULT_PGSOCKET_DIR = "/tmp"` socket squatting** (`pg_config_manual.h:181-201`) — known hazard; any local user can create `.s.PGSQL.5432` before postmaster. Default `pg_socket_dir` permission check is the sole mitigation.
19. **`MAXPGPATH = 1024` silently truncates** vs Linux `PATH_MAX = 4096` (`pg_config_manual.h:105`) — deep nesting paths get `strlcpy`-cut with no error.
20. **`PGSTAT_FILE_FORMAT_ID` bump is comment-only** (`pgstat.h:216-221`) — struct change without bump silently loads corrupt stats. `pg_memory_is_all_zeros` pattern also constrains struct layout (counters only, no derived/timestamps fields) without compile-time check.
21. **PS / cancel / session globals exported PGDLLIMPORT-mutable** (`miscadmin.h:269-273, 544; pgstat.h:868-870; pgtime.h:90-91`) — `work_mem`, `shmem_request_hook`, timing counters, `session_timezone`, `log_timezone` all writable by extension code with no audit.
22. **`InitializeSessionUserId(bypass_login_check)` + `INIT_PG_OVERRIDE_ROLE_LOGIN`** (`miscadmin.h:438-440, 506-510`) — bare bool / undocumented flag bypasses NOLOGIN; pg_upgrade uses it.
23. **`SRF_RETURN_NEXT` macro assumes `fcinfo->resultinfo` is `ReturnSetInfo`** (`funcapi.h:311-318`) — DirectFunctionCall on an SRF crashes.
24. **`pg_unreachable()` codegen differs cassert vs release** (`c.h:362-368`) — `abort()` under cassert, `__builtin_unreachable` else; a flow that hits `abort()` in test may silently UB in production.

### Entries — A22-A: c.h / postgres.h / postgres_fe.h / postgres_ext.h (universal)

- [ISSUE-style: `ExceptionalCondition` extern at `c.h:988` is gated by `!FRONTEND`; new extern declarations routinely miss this gate (nit)] — `c.h:982-990`
- [ISSUE-undocumented-invariant: `Min`/`Max` multi-eval not flagged at definition site (nit)] — `c.h:1085-1091`
- [ISSUE-undocumented-invariant: `MemSet`'s `Size _len = (len)` truncates if caller passes wider int (nit)] — `c.h:1107-1132`
- [ISSUE-correctness: `pg_unreachable` codegen differs between cassert and release; abort() in cassert may UB silently in release (likely)] — `c.h:362-368`
- [ISSUE-doc-drift: `HAVE_INT128` gate not mentioned beside `int128` typedef (nit)] — `c.h:646-663`
- [ISSUE-doc-drift: `PGDLLEXPORT` visibility-attribute requirement not loud enough (nit)] — `c.h:1439-1452`
- [ISSUE-stale-todo: MinGW-64 setjmp workaround could be removed once buildfarm drops mingw-w64-x86_64 (nit)] — `c.h:1483-1494`
- [ISSUE-undocumented-invariant: `BoolGetDatum(DatumGetBool(x))` round-trip loses "any-nonzero" property (nit)] — `postgres.h:99-114`
- [ISSUE-undocumented-invariant: PointerGetDatum-macro contract not flagged at alternative inline-function-form rejected (nit)] — `postgres.h:340-355`
- [ISSUE-defense-in-depth: NON_EXEC_STATIC turns module-private state into linker-visible symbols under EXEC_BACKEND (nit)] — `postgres.h:570-574`
- [ISSUE-stale-todo: SIZEOF_DATUM is vestigial; should be `#define DEPRECATED 1` or commented hostilely (nit)] — `postgres.h:76`
- [ISSUE-api-shape: asymmetric GetDatum/DatumGet pair for MultiXactId (nit)] — `postgres.h:288-294`
- [ISSUE-api-shape: `pg_ternary` "unset" easy to miss in switch (nit)] — `postgres.h:556-561`
- [ISSUE-style: defensive `#ifndef FRONTEND` guard accepts non-1 values (nit)] — `postgres_fe.h:22-24`
- [ISSUE-undocumented-invariant: omitting postgres_fe.h fails at link time, not compile time (nit)] — `postgres_fe.h`
- [ISSUE-doc-drift: `Oid8` is backend-only but the comment doesn't explain why it's not in `postgres_ext.h` (nit)] — `c.h:755` ↔ `postgres_ext.h`
- [ISSUE-undocumented-invariant: no static assert that `sizeof(Oid) == 4` at the public-ABI boundary (nit)] — `postgres_ext.h:32`
- [ISSUE-correctness: `atooid` silently truncates inputs > 2^32 on 64-bit `long` platforms (maybe)] — `postgres_ext.h:43`
- [ISSUE-api-shape: PG_DIAG_* namespace is single-char ASCII with no allocation discipline document (nit)] — `postgres_ext.h:55-72`

### Entries — A22-A: fmgr.h / funcapi.h / varatt.h (fmgr surface)

- [ISSUE-undocumented-invariant: no `StaticAssert(sizeof(Pg_abi_values) == expected_packed_size)`; future field additions could silently break ABI compat detection (likely)] — `fmgr.h:468-476`
- [ISSUE-security: fmgr_hook is unrestricted by superuser — any preloaded library can install it (likely)] — `fmgr.h:830-855`
- [ISSUE-api-shape: stack allocation of `FunctionCallInfoBaseData` by sizeof silently under-allocates `args[]` (likely)] — `fmgr.h:78-83`
- [ISSUE-undocumented-invariant: isnull reset on re-use is comment-only; no Assert (maybe)] — `fmgr.h:166-170`
- [ISSUE-api-shape: PG_GETARG_FLOATx has no type-system protection (nit)] — `fmgr.h:282-283`
- [ISSUE-api-shape: PG_MODULE_MAGIC placement contract not enforced (nit)] — `fmgr.h:445-449`
- [ISSUE-style: abi_extra should be ASCII-printable (nit)] — `fmgr.h:475`
- [ISSUE-api-shape: DirectFunctionCall family limited to 9 args (nit)] — `fmgr.h:563-682`
- [ISSUE-defense-in-depth: fmgr_hook lacks chained-hook idiom in header docs (likely)] — `fmgr.h:830-855`
- [ISSUE-style: `load_file` restricted parameter is bare bool (nit)] — `fmgr.h:798`
- [ISSUE-undocumented-invariant: SRF non-memory resource leakage on early-exit is comment-only (likely)] — `funcapi.h:279-288`
- [ISSUE-api-shape: SRF_IS_FIRSTCALL conflates `fn_extra` usage (likely)] — `funcapi.h:305`
- [ISSUE-correctness: SRF_RETURN_NEXT assumes resultinfo is ReturnSetInfo (likely)] — `funcapi.h:311-318`
- [ISSUE-style: MAT_SRF_* flag bits should be enum (nit)] — `funcapi.h:296-298`
- [ISSUE-correctness: HeapTupleGetDatum has no NULL-`t_data` guard (nit)] — `funcapi.h:230-233`
- [ISSUE-style: extract_variadic_args `convert_unknown` is bare bool (nit)] — `funcapi.h:356-358`
- [ISSUE-correctness: unaligned `varatt_external` access (read or write) silently SIGBUS on alignment-strict platforms (confirmed)] — `varatt.h:27-29`
- [ISSUE-undocumented-invariant: no `StaticAssert(sizeof(varatt_external) == 16)` to catch accidental padding (likely)] — `varatt.h:32-39`
- [ISSUE-correctness: pad-byte-zero invariant has no validity check (maybe)] — `varatt.h:175-176`
- [ISSUE-style: vartag_external numbering scheme is undocumented for future additions (nit)] — `varatt.h:84-90`
- [ISSUE-undocumented-invariant: vartag_external numbering scheme is load-bearing for `VARTAG_IS_EXPANDED` macro (nit)] — `varatt.h:94-98`
- [ISSUE-correctness: only 2 compression-method bits available; zstd + pglz + lz4 + 1 more would need an on-disk-format break (maybe)] — `varatt.h:45-46, 520-526`
- [ISSUE-correctness: `VARDATA_ANY` on external/compressed silently garbage (likely)] — `varatt.h:486-489`
- [ISSUE-correctness: compression-method bits not validated in release builds (nit)] — `varatt.h:520-526`
- [ISSUE-doc-drift: 2 GB vs 1 GB limit mismatch not flagged (nit)] — `varatt.h:34`
- [ISSUE-stale-todo: compression-method bit budget tight (likely)] — `varatt.h:45-46`
- [ISSUE-style: `sizeof(varattrib_1b_e)` semantics not documented (nit)] — `varatt.h:148-154`

### Entries — A22-A: miscadmin.h / pgstat.h / port.h (process / stats / portability)

- [ISSUE-defense-in-depth: no header-level guidance for "should this be a crit section?" — answer is almost always no (likely)] — `miscadmin.h:79-84`
- [ISSUE-undocumented-invariant: `MyDatabaseHasLoginEventTriggers` is per-session, stale across CREATE EVENT TRIGGER (maybe)] — `miscadmin.h:214`
- [ISSUE-undocumented-invariant: SECURITY_* bit allocation policy is comment-only (nit)] — `miscadmin.h:319-323`
- [ISSUE-defense-in-depth: shmem_request_hook chaining is extension-author's responsibility, not enforced (likely)] — `miscadmin.h:543-544`
- [ISSUE-doc-drift: MyCancelKey array size opaque at header (nit)] — `miscadmin.h:198-199`
- [ISSUE-defense-in-depth: tuning GUCs mutable via direct symbol access (nit)] — `miscadmin.h:269-273`
- [ISSUE-api-shape: BackendType not extensible (likely)] — `miscadmin.h:340-381`
- [ISSUE-security: bypass_login_check is bare bool; misuse silently bypasses NOLOGIN (likely)] — `miscadmin.h:438-440`
- [ISSUE-security: INIT_PG_OVERRIDE_ROLE_LOGIN is dangerous, no header marker (likely)] — `miscadmin.h:506-510`
- [ISSUE-correctness: CritSectionCount underflow on mis-pairing silent in release (maybe)] — `miscadmin.h:108, 154-156`
- [ISSUE-undocumented-invariant: PGSTAT_FILE_FORMAT_ID bump is comment-only; no static-assert on struct sizes (likely)] — `pgstat.h:216-221`
- [ISSUE-undocumented-invariant: pg_memory_is_all_zeros pattern constrains struct layout; new field additions silently break it if non-zero by default (likely)] — `pgstat.h:126-129, 240-242`
- [ISSUE-correctness: PGSTAT_FILE_FORMAT_ID discipline is comment-only (confirmed echo of A15 ISSUE pattern)] — `pgstat.h:221`
- [ISSUE-style: pgstat.h fan-in too broad (nit)] — `pgstat.h:14-22`
- [ISSUE-api-shape: PgStat_StatDBEntry has no version field (nit)] — `pgstat.h:368-403`
- [ISSUE-doc-drift: slotsync_skip_count is single bucket (nit)] — `pgstat.h:425-426`
- [ISSUE-defense-in-depth: timing counters mutable via PGDLLIMPORT (nit)] — `pgstat.h:868-870`
- [ISSUE-style: pgstat GUCs declared as int (nit)] — `pgstat.h:835-841`
- [ISSUE-style: side-effect in pgstat_should_count_relation (nit)] — `pgstat.h:711-713`
- [ISSUE-leak: pgstat_acquire/drop_replslot pairing not enforced (maybe)] — `pgstat.h:777-782`
- [ISSUE-doc-drift: xl_xact_stats_item layout opaque at header (nit)] — `pgstat.h:822-823`
- [ISSUE-security: `pg_disable_aslr` deliberately weakens process ASLR; only intended for EXEC_BACKEND devs (confirmed)] — `port.h:147-150`
- [ISSUE-stale-todo: libintl printf-replacement undef list is hand-maintained against libintl ABI (nit)] — `port.h:209-232`
- [ISSUE-api-shape: `&printf` function pointer silently bypasses pg_printf (likely)] — `port.h:267`
- [ISSUE-api-shape: `qsort` macro override is sticky (nit)] — `port.h:489`
- [ISSUE-documentation: pg_strong_random init contract not in header (maybe)] — `port.h:529-531`
- [ISSUE-correctness: pg_localeconv_r failure mode opaque (nit)] — `port.h:511-515`
- [ISSUE-style: pg_backend_random alias misleading (nit)] — `port.h:531-536`
- [ISSUE-defense-in-depth: pqsignal vs libc signal not flagged at header (likely)] — `port.h:553`
- [ISSUE-style: HAVE_* unconditional on Unix; documentation trust-the-platform (nit)] — `port.h:575-583`

### Entries — A22-A: time / archive / debug / config / window (utility)

- [ISSUE-correctness: pg_tm convention mismatch is comment-only; no static helper to convert (likely)] — `pgtime.h:28-32`
- [ISSUE-resource: `pg_tzset_offset` cache unbounded (maybe)] — `pgtime.h:95`
- [ISSUE-defense-in-depth: session/log_timezone are PGDLLIMPORT-mutable (nit)] — `pgtime.h:90-91`
- [ISSUE-documentation: pg_tz_acceptable contract opaque (nit)] — `pgtime.h:81`
- [ISSUE-doc-drift: timezone-abbreviation function family is duplicative (nit)] — `pgtime.h:67-71`
- [ISSUE-style: no StaticAssert anchoring tarHeaderOffset values (nit)] — `pgtar.h:38-56`
- [ISSUE-api-shape: tarCreateHeader partial-failure mutation not flagged (nit)] — `pgtar.h:69-72`
- [ISSUE-security: isValidTarHeader does not validate against path traversal (likely)] — `pgtar.h:75-76`
- [ISSUE-correctness: isValidTarHeader has no length parameter (nit)] — `pgtar.h:76`
- [ISSUE-doc-drift: no provision for future PG-specific tar extensions (nit)] — `pgtar.h`
- [ISSUE-stale-todo: pg_trace.h is a one-line stub; consider direct include of probes.h or merging (nit)] — `pg_trace.h:15`
- [ISSUE-api-shape: no probe-name namespace allocation (nit)] — `pg_trace.h`
- [ISSUE-style: portability of optind declaration on Windows is fragile (nit)] — `pg_getopt.h:31-42`
- [ISSUE-style: optreset branch grows linearly with platforms (nit)] — `pg_getopt.h:46-50`
- [ISSUE-correctness: no signature compatibility check at link (nit)] — `pg_getopt.h:53-55`
- [ISSUE-style: no static-assert that `sizeof(struct option)` matches expected (nit)] — `getopt_long.h:15-28`
- [ISSUE-doc-drift: getopt_long porting requirements not documented at header (nit)] — `getopt_long.h:30-35`
- [ISSUE-style: bare global macro names from POSIX (nit)] — `getopt_long.h:25-27`
- [ISSUE-api-shape: NAMEDATALEN = 64 is a hard limit for forks with long identifiers (likely)] — `pg_config_manual.h:39`
- [ISSUE-api-shape: FUNC_MAX_ARGS in ABI block means forks need custom backend (nit)] — `pg_config_manual.h:53`
- [ISSUE-correctness: MAXPGPATH = 1024 silently truncates (likely)] — `pg_config_manual.h:105`
- [ISSUE-security: DEFAULT_PGSOCKET_DIR `/tmp` is a known socket-squatting hazard (confirmed)] — `pg_config_manual.h:181-201`
- [ISSUE-stale-todo: PG_CACHE_LINE_SIZE could be configure-detected (nit)] — `pg_config_manual.h:217`
- [ISSUE-correctness: PG_IO_ALIGN_SIZE = 4 KB may be insufficient for 16 KB sector NVMe (maybe)] — `pg_config_manual.h:223`
- [ISSUE-stale-todo: SLRU_PAGES_PER_SEGMENT could be made GUC-tunable (likely)] — `pg_config_manual.h:30`
- [ISSUE-stale-todo: VG client requests slow non-VG runs (nit)] — `pg_config_manual.h:261-262`
- [ISSUE-style: auto-enable hides perf cost (nit)] — `pg_config_manual.h:328-339`
- [ISSUE-api-shape: NULL TREATMENT support requires explicit window-function opt-in (likely)] — `windowapi.h:46-48`
- [ISSUE-style: window seek type is bare int not enum (nit)] — `windowapi.h:59-65`
- [ISSUE-undocumented-invariant: WinSetMarkPosition usage is performance-only, not correctness; hidden hazard (likely)] — `windowapi.h:55`
- [ISSUE-api-shape: window-frame mode opaque to extensions (likely)] — `windowapi.h:39`
- [ISSUE-api-shape: per-partition memory size contract (nit)] — `windowapi.h:50`
- [ISSUE-documentation: windowapi.h delegates almost all semantic docs to .c file (nit)] — `windowapi.h:6-19`
