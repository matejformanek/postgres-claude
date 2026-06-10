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
