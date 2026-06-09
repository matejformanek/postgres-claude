# Issues — `src/include/{commands,nodes,parser,tcop,rewrite}`

Per-subsystem issue register for **the command layer + parse-tree nodes + parser entry + tcop dispatch + rewriter** header surface. 28 headers / ~45 entries surfaced 2026-06-09 by A17-3.

**Parent docs:** `knowledge/files/src/include/{commands,nodes,parser,tcop,rewrite}/*` (now full coverage for these sub-trees).

**Sibling registers:** `knowledge/subsystems/parser-and-rewrite.md`, `knowledge/subsystems/tcop.md` (synthesized).

## Headlines

1. **🚨 A11 cleartext-password vector concentrated in 3 sibling headers** — `queryjumble.h` documents the normalization path that EXCLUDES utility statements; `CREATE USER ... PASSWORD '...'` stored verbatim. `tcop/cmdtaglist.h` is the dispatch table for event triggers that ALSO see the raw parsetree. `tcop/deparse_utility.h`'s `CollectedCommand.parsetree` retains the PASSWORD node. **Cross-link as one cluster.**
2. **🚨 `nodes/readfuncs.h` is the hostile-input deserializer documentation never named as a trust boundary** — `stringToNode` called from pg_rewrite, pg_proc, pg_class.relpartbound, plan-cache, parallel-worker DSM (at least 7 catalog/IPC sources; not all fully sanitized at write).
3. **🚨 PG18 SQL/PGQ is a brand-new attack surface across 4 headers** — `propgraphcmds.h`, `parse_graphtable.h`, `rewriteGraphTable.h`, plus `cmdtaglist.h` entries. ACL/RLS propagation from constituent tables to graph references undocumented.
4. **🚨 `subscripting.h` + `supportnodes.h` both expose extension-set "leakproof" / "stable" flags as self-asserted truths** — RLS qual ordering depends on these flags. A mis-flagged extension subscripter or planner-support function silently breaks RLS guarantees. No runtime cross-check exists.
5. **3-site X-macro cluster confirmed** — `tcop/cmdtaglist.h` + `parser/kwlist.h` (this slice) + `access/rmgrlist.h` (A17 sibling slice) + `storage/lwlocklist.h` (A15) = 4 X-macro sites in tree.
6. **A8 deparse_utility.h CollectedCommand carries publisher-side OIDs** — downstream re-resolution by name can bind wrong object (NAME-vs-OID cluster echo).
7. **A11/A14 monitoring-as-extraction echoes** — `progress.h` + `wait.h` + `explain_state.h` are header anchors.

## Entries — commands (10 headers)

### copyapi.h, dbcommands_xlog.h, explain_*.h, progress.h, wait.h
- [ISSUE-defense-in-depth: copyapi.h lacks explicit warning that a format extension runs with backend privilege (nit)] — `copyapi.h:19-22`
- [ISSUE-documentation: FILE_COPY vs WAL_LOG crash-window trade-off not documented in header (maybe)] — `dbcommands_xlog.h:25-46`
- [ISSUE-security: dbase_redo runs with full file-system access on standby; A8 hostile-WAL-stream surface (maybe)] — `dbcommands_xlog.h:56`
- [ISSUE-defense-in-depth: explain_format.h gives no escaping contract — caller's responsibility implicit (maybe)] — `explain_format.h:21-48`
- [ISSUE-security: A7 echo — RLS qual deparsing path runs through these writers (nit)] — `explain_format.h:1-15`
- [ISSUE-security: A14 echo — extension EXPLAIN options bypass per-relation EXPLAIN privilege gates (maybe)] — `explain_state.h:100-107`
- [ISSUE-api-shape: explain_validate_options_hook is a single global; multiple loaded extensions can fight (nit)] — `explain_state.h:87-89`
- [ISSUE-security: A11/A14 echo — relation OIDs published in pg_stat_progress_* readable by pg_read_all_stats but not filtered by per-relation SELECT privilege (maybe)] — `progress.h:21-205`
- [ISSUE-documentation: comment says "you probably also need to update the views" but no CI lint (maybe)] — `progress.h:6-8`
- [ISSUE-documentation: wait.h is bare 3 prototypes — no semantic description of WAIT family (maybe)] — `wait.h:14-22`
- [ISSUE-security: wait.h PG18 — no documented privilege gate; non-superuser DoS surface needs review (maybe)] — `wait.h:19-20`

### PG18 SQL/PGQ + REPACK
- [ISSUE-security: PG18 SQL/PGQ — entirely new attack surface; no security review in header; permission model unclear (likely)] — `propgraphcmds.h:20-21`
- [ISSUE-documentation: propgraphcmds.h minimal; no comment on relationship to pg_class entries or DROP propagation (maybe)] — `propgraphcmds.h:1-23`
- [ISSUE-security: repack.h NewAccessMethod arg unchecked at C level — caller must enforce "owner can pick AM" (maybe)] — `repack.h:49-50`
- [ISSUE-security: repack.h CONCURRENT-mode slot lifecycle on failure not documented — WAL retention DoS (maybe)] — `repack.h:41`
- [ISSUE-security: repack_internal.h decoding worker output files in pg_replslot not encrypted; A14 echo + A8 inherits (maybe)] — `repack_internal.h:67-119`
- [ISSUE-security: repack_internal.h roleid field not validated against current process credentials at worker startup (nit)] — `repack_internal.h:97-98`

### sequence_xlog.h
- [ISSUE-security: A8 — forged sequence WAL record could rewind sequence on standby (maybe)] — `sequence_xlog.h:34-43`
- [ISSUE-documentation: SEQ_MAGIC 0x1717 not explained anywhere visible (nit)] — `sequence_xlog.h:26`

## Entries — nodes (6 headers)

### miscnodes.h, multibitmapset.h
- [ISSUE-documentation: miscnodes.h doesn't warn error_data lives in callee's context — easy UAF if caller switches context (maybe)] — `miscnodes.h:39-43`
- [ISSUE-security: A7 cluster — input functions that partially-update state before soft-erroring expose intermediate state via ErrorData (maybe)] — `miscnodes.h:25-43`
- [ISSUE-documentation: multibitmapset.h "small fraction of API has been built out" (nit)] — `multibitmapset.h:16-19`

### queryjumble.h, readfuncs.h
- [ISSUE-security: A11 — utility statements like CREATE USER...PASSWORD NOT redacted; jumble path stores verbatim text (likely)] — `queryjumble.h:93-97`
- [ISSUE-security: query_id 64-bit + global visibility via pg_stat_activity enables cross-role plan-shape inference (maybe)] — `queryjumble.h:80-100`
- [ISSUE-documentation: header doesn't note EXECUTE-string literals bypass normalization (maybe)] — `queryjumble.h:19-32`
- [ISSUE-security: A14 — deserializer assumes trusted source; no input validation; hostile catalog or replication stream can craft node trees that crash planner (likely)] — `readfuncs.h:36`
- [ISSUE-documentation: header does NOT name catalog columns that hold serialized node trees (maybe)] — `readfuncs.h:1-15`
- [ISSUE-security: parallel-worker plan strings travel through DSM, decoded by stringToNode in worker (nit)] — `readfuncs.h:36`

### subscripting.h, supportnodes.h
- [ISSUE-security: A7 — leakproof flag self-asserted by extension; no runtime check; mis-flagged custom subscripter breaks RLS qual ordering (likely)] — `subscripting.h:39-48`
- [ISSUE-security: SubscriptTransform can invoke arbitrary SQL at parse-time; not documented as constraint (nit)] — `subscripting.h:60-94`
- [ISSUE-security: A15 echo — custom support functions for selectivity/cost can be EXPLAIN-observed by non-owners (maybe)] — `supportnodes.h:146-198`
- [ISSUE-security: A7 echo — InlineInFrom can drop RLS quals if implementer not careful; "must have been passed through rewrite" is comment not assertion (likely)] — `supportnodes.h:114-116`
- [ISSUE-correctness: SupportRequestIndexCondition.lossy default-true is fail-safe but easy to mis-set (maybe)] — `supportnodes.h:263-265`

## Entries — parser (7 headers)

### kwlist.h, parser.h, parsetree.h, scanner.h, scansup.h
- [ISSUE-documentation: kwlist.h "no include guard" but doesn't list multiple consumers (nit)] — `kwlist.h:19`
- [ISSUE-correctness: kwlist.h ASCII-sort checked at code-gen, not in C build; manual edits can silently break ordering (nit)] — `kwlist.h:25`
- [ISSUE-security: A11 echo — parser.h header doesn't mention standard_conforming_strings interaction with backslash_quote (maybe)] — `parser.h:47-57`
- [ISSUE-correctness: rt_fetch macro evaluates rangetable_index twice — side-effect-bearing argument would be bug (nit)] — `parsetree.h:31-32`
- [ISSUE-resource: A11 echo — scanner.h no GUC limit on query length/scanbuf size; large hostile string drives huge palloc (nit)] — `scanner.h:72-73`
- [ISSUE-documentation: scanner.h comment block about token numbers is binding contract but easy to miss (maybe)] — `scanner.h:46-57`
- [ISSUE-security: A11/A13/A14 cluster — scansup.h identifier truncation by BYTE not CHAR allows multibyte boundary collisions (maybe)] — `scansup.h:17-23`
- [ISSUE-documentation: scansup.h has zero comments — invariants are folk knowledge (maybe)] — `scansup.h:1-27`

### parse_enr.h, parse_graphtable.h
- [ISSUE-documentation: parse_enr.h lists 2 funcs, zero context — first-time reader can't tell what an ENR is (maybe)] — `parse_enr.h:14-22`
- [ISSUE-security: A8 echo — ENR vs real-table name collision precedence not commented (nit)] — `parse_enr.h:19-20`
- [ISSUE-security: PG18 — property-ref resolution may bypass underlying-table ACL; needs verification (likely)] — `parse_graphtable.h:20`

## Entries — tcop (3 headers)

### backend_startup.h, cmdtaglist.h, deparse_utility.h
- [ISSUE-security: A2 echo — log_connections SETUP_DURATIONS publishes per-phase auth timing; user-existence timing side-channel (maybe)] — `backend_startup.h:74-118`
- [ISSUE-correctness: CAC_* enum order is wire-significant; changing order = ABI break, not commented (nit)] — `backend_startup.h:33-41`
- [ISSUE-documentation: cmdtaglist.h alphabetic-order invariant relies on developer discipline; no CI lint (nit)] — `cmdtaglist.h:22-24`
- [ISSUE-correctness: rowcount flag is wire-significant; changing TRUE→FALSE breaks libpq clients (nit)] — `cmdtaglist.h:26`
- [ISSUE-security: A11 echo — event-trigger handler sees full statement string including PASSWORD literals (maybe)] — `cmdtaglist.h:53-94`
- [ISSUE-security: A8 — deparse_utility.h CollectedCommand carries publisher-side OIDs; downstream re-resolution by name can bind wrong object (likely)] — `deparse_utility.h:44-106`
- [ISSUE-security: A11 echo — parsetree retains PASSWORD literals; event-trigger handlers see cleartext (maybe)] — `deparse_utility.h:49`

## Entries — rewrite (2 headers)

### prs2lock.h, rewriteGraphTable.h
- [ISSUE-documentation: prs2lock.h "RuleLock" name is misleading; historical fossil (nit)] — `prs2lock.h:36-38`
- [ISSUE-security: A14 echo — pg_rewrite.ev_action is node-tree string deserialized by readfuncs; hostile catalog content (maybe)] — `prs2lock.h:24-32`
- [ISSUE-security: enabled='R' replica-mode rules fire during logical apply; can silently DROP rows or rewrite to side-effecting query (maybe)] — `prs2lock.h:30`
- [ISSUE-security: PG18 — rewriteGraphTable.h doesn't document ACL/RLS propagation contract for graph-vs-constituent-tables (likely)] — `rewriteGraphTable.h:19`

## Cross-sweep references

- **A11 pg_stat_statements password capture** → queryjumble.h + cmdtaglist.h + deparse_utility.h **3-site cluster**.
- **A14 amcheck/pageinspect cross-table read** → readfuncs.h hostile-deserialization echo.
- **A8 logical replication NAME-vs-OID** → deparse_utility.h + parse_enr.h echoes.
- **A14 pg_overexplain + A7 ruleutils security-clause loss** → explain_format.h + explain_state.h.
- **A11/A14 monitoring-as-extraction** → progress.h + wait.h header anchors.
- **A15 lwlocklist.h + A17 rmgrlist.h** + this slice's cmdtaglist.h + parser/kwlist.h = **4-site X-macro cluster** in the corpus.
- **A14 COPY (file_fdw, pg_dump)** → copyapi.h.
- **A7 leakproof / soft-error infrastructure** → miscnodes.h + subscripting.h + supportnodes.h.
- **PG18 SQL/PGQ** = NEW attack surface cluster (propgraphcmds + parse_graphtable + rewriteGraphTable + cmdtaglist entries).
- **PG18 REPACK** = new in-place table compaction; threat profile mirrors pg_repack contrib.
