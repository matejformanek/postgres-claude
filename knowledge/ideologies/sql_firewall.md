# sql_firewall — ideology / divergence notes

Extension: **uptimejp/sql_firewall** (`master`, control `default_version =
'0.8'`, `comment = 'Prevent query execution which is not allowd by the
rules'`, `sql_firewall.control:2-3`). A C extension that turns
`pg_stat_statements` inside-out: instead of *counting* normalized queries it
*gates* them, blocking any statement whose `(userid, queryid)` fingerprint is
not on a previously-learned allowlist. Three enforcement modes —
`learning` / `permissive` / `enforcing` (plus `disabled`) — selected by a GUC
(`sql_firewall.c:248-263`).

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> All `file:line` cites point into the fetched repo files (`sql_firewall.c`,
> `sql_firewall--0.8.sql`, `sql_firewall.control`, `Makefile`), **not**
> `source/`. Cites verified against files fetched 2026-07-14 (see Sources
> footer). This extension sits at the *intersection* of two corpus clusters:
> (1) the **pg_stat_statements-derived** jumble/queryid cluster —
> `[[pg_stat_monitor]]`, `[[pgsentinel]]`, `[[pg_stat_kcache]]`,
> `[[pg_qualstats]]`, `[[pg_wait_sampling]]`, `[[pg_tracing]]` — from which it
> is a near-verbatim *fork*, not a dependent; and (2) the **security /
> gatekeeping** cluster — `[[pgaudit]]`, `[[set_user]]`, `[[credcheck]]`,
> `[[supautils]]`, `[[pg_permissions]]`, and core `[[contrib-sepgsql]]` /
> `[[contrib-passwordcheck]]` / `[[contrib-auth_delay]]`. Its distinguishing
> move is *repurposing an observability tool as an enforcement point*: the same
> query-jumble that pg_stat_statements uses for aggregation becomes an
> allow/deny key. Status: pinned to an **old PG** (pre-9.6 shmem/LWLock API,
> pre-10 hook signatures — see §Divergence 6); `[inferred]` from the APIs it
> calls.

---

## Domain & purpose

sql_firewall is a **query allowlist firewall**. In `learning` mode it records
the fingerprint of every statement a role runs; in `enforcing` mode it aborts
any statement whose fingerprint was not learned; in `permissive` mode it merely
warns; in `disabled` mode it is inert (`sql_firewall.c:248-263`)
`[verified-by-code]`. The control-file comment states the mission bluntly —
"Prevent query execution which is not allowd by the rules"
(`sql_firewall.control:2`) `[verified-by-code]`. The unit of protection is the
**`(userid, queryid)` pair** (`sql_firewall.c:131-135`) `[verified-by-code]`:
rules are per-role, so the identical query text run by a different role is a
different rule and is blocked. The learned ruleset is a **file-backed shared
hash table** persisted across restarts, plus a CSV export/import path for
moving rules between clusters (`sql_firewall.c:1683-1792`) `[verified-by-code]`.
The header comment is explicit about the lineage: "sql_firewall is built on the
top of pg_stat_statements" (`sql_firewall.c:8`) `[from-comment]` — the file even
carries pg_stat_statements.c's original banner and copyright verbatim
(`sql_firewall.c:12-67`) `[verified-by-code]`.

---

## How it hooks into PG

Requires `shared_preload_libraries`: `_PG_init` bails out immediately if
`!process_shared_preload_libraries_in_progress` (`sql_firewall.c:361-362`)
`[verified-by-code]`, and every SQL-callable function re-checks it via
`ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE` (`sql_firewall.c:1384-1386,
1439-1441, 1695-1697, 2001-2003`) `[verified-by-code]`.

- **Seven hooks installed**, saving each predecessor for chaining
  (`sql_firewall.c:408-421`) `[verified-by-code]`:
  `shmem_startup_hook`, `post_parse_analyze_hook`, `ExecutorStart_hook`,
  `ExecutorRun_hook`, `ExecutorFinish_hook`, `ExecutorEnd_hook`, and
  `ProcessUtility_hook`. `_PG_fini` restores all seven
  (`sql_firewall.c:430-437`) `[verified-by-code]`. This is the full
  pg_stat_statements hook set — but the enforcement decision is bolted into the
  store path rather than any new hook. See `[[process-utility-hook-chain]]`.
- **Two GUCs**, both `PGC_POSTMASTER`:
  `sql_firewall.max` (`DefineCustomIntVariable`, default 5000, min 100, max
  `INT_MAX`, `sql_firewall.c:367-378`) and `sql_firewall.firewall`
  (`DefineCustomEnumVariable` over `mode_options`, default `PGFW_MODE_DISABLED`,
  `sql_firewall.c:383-393`) `[verified-by-code]`, followed by the pre-PG-15
  `EmitWarningsOnPlaceholders("sql_firewall")` (`sql_firewall.c:395`)
  `[verified-by-code]`. Because both are `PGC_POSTMASTER`, **flipping
  learning→enforcing needs a server restart** (`sql_firewall.c:374,389`)
  `[verified-by-code]`. The inherited pg_stat_statements knobs are *hardcoded*
  rather than exposed: `pgss_track = PGSS_TRACK_TOP` and `pgss_save = true` are
  assigned in `_PG_init`, not registered as GUCs
  (`sql_firewall.c:380-381`) `[verified-by-code]`; the `track_options[]` array
  is `#ifdef NOT_USED` dead code (`sql_firewall.c:238-246`) `[verified-by-code]`.
  See `[[guc-variables]]`.
- **Shared memory** requested the pre-9.6 way:
  `RequestAddinShmemSpace(pgss_memsize())` + `RequestAddinLWLocks(1)`
  (`sql_firewall.c:402-403`) `[verified-by-code]`, attached in
  `pgss_shmem_startup` with `ShmemInitStruct("sql_firewall", …)` and
  `ShmemInitHash("sql_firewall hash", pgss_max, pgss_max, …)`, the lock obtained
  via the removed-in-9.6 `LWLockAssign()` (`sql_firewall.c:472-500`)
  `[verified-by-code]`. The shared struct `pgssSharedState` carries the
  hashtable `LWLock *lock`, a spinlock `mutex`, and — the sql_firewall
  additions — `int64 error_count` / `warning_count`
  (`sql_firewall.c:165-176`) `[verified-by-code]`.
- **Three on-disk files** in the stats permanent directory: the rule file
  `sql_firewall_statements.stat`, the counter file `sql_firewall.stat`, and the
  external query-text temp file `sql_firewall_query_texts.stat`
  (`sql_firewall.c:97-108`) `[verified-by-code]`.
- **SQL surface** (`sql_firewall--0.8.sql`): a `sql_firewall` schema with views
  `sql_firewall_statements` and `sql_firewall_stat`, plus C functions
  `sql_firewall_reset`, `sql_firewall_statements`, `sql_firewall_stat_*`,
  `sql_firewall_export_rule(text)`, `sql_firewall_import_rule(text)`
  (`sql_firewall--0.8.sql:6-60`) `[verified-by-code]`. The mutating/superuser
  functions are `REVOKE ALL … FROM PUBLIC` (`sql_firewall--0.8.sql:62-66`)
  `[verified-by-code]`. Built with PGXS `MODULE_big = sql_firewall`,
  `DATA = sql_firewall--0.8.sql`, `subdir = contrib/sql_firewall`
  (`Makefile:3-14`) `[verified-by-code]` — it is packaged as if it were an
  in-tree contrib module. See `[[extension-development]]`.

---

## Where it diverges from core idioms

### 1. Enforcement is *post-execution* — the query already ran when it's blocked

The headline. The allow/deny decision lives in `pgss_store`, not in a
pre-execution gate. For DML, `pgss_store` is called from the **ExecutorEnd**
hook (`sql_firewall.c:1022-1027`), i.e. *after* `ExecutorRun` has already
produced and streamed the result rows; for utility statements it is called in
`pgss_ProcessUtility` **after** `standard_ProcessUtility` has already run the
statement (`sql_firewall.c:1076-1083` then `:1138-1143`) `[verified-by-code]`.
Inside `pgss_store`, an unlearned fingerprint in `enforcing` mode does
`LWLockRelease` → `stat_error_increment` → `ereport(ERROR, …)`
(`sql_firewall.c:1257-1264`) `[verified-by-code]`. So the firewall relies on the
**transaction abort triggered by the ERROR to undo the statement's effects**,
rather than preventing execution. Consequences `[inferred]`: a blocked `SELECT`
has already sent its tuples to the client before the ERROR is raised (rows leak
despite the "block"); a blocked utility statement with non-transactional side
effects (e.g. anything that commits or touches the filesystem inside
`ProcessUtility`) is not rolled back. This is the sharpest departure from the
gatekeeping cluster's pre-flight model (`[[contrib-sepgsql]]` checks at
`object_access_hook` / `ExecutorCheckPerms`; `[[credcheck]]` checks at
`ProcessUtility` *entry*) — sql_firewall checks at the *exit*. Tag:
`[verified-by-code]` for the call ordering; `[inferred]` for the leak/rollback
consequences.

### 2. A verbatim fork of pg_stat_statements, not a dependency on it

sql_firewall does not `LOAD` or require the `pg_stat_statements` extension; it
**copies the entire machine** into one 3463-line `.c`: the `pgssSharedState` /
`pgssEntry` / `pgssHashKey` / `pgssJumbleState` structs
(`sql_firewall.c:131-207`), the external-query-text file with garbage
collection (`qtext_store` / `qtext_load_file` / `gc_qtexts` /
`need_gc_qtexts`, `sql_firewall.c:326-334`), and the whole query-jumble
walker (`JumbleQuery` / `JumbleExpr` / `JumbleRangeTable` /
`generate_normalized_query`, defined in-file at `sql_firewall.c:2752`)
`[verified-by-code]`. It even declares `extern void JumbleQuery(…)` at
`sql_firewall.c:209` and then defines that same symbol lower in the file — a
vendoring tell. The upstream locking-discipline comment is carried across
unchanged (`sql_firewall.c:46-58`) `[verified-by-code]`. Divergence from the
sibling cluster: `[[pg_stat_monitor]]` and `[[pgsentinel]]` re-implement or
extend jumbling for their own ends, but sql_firewall's fork exists purely to
**reuse the queryid as an authorization key** — the observability code is
retained only as scaffolding.

### 3. LRU eviction is deliberately disabled — a full allowlist refuses to learn

Core pg_stat_statements calls `entry_dealloc()` to evict the least-used entries
when the hash table fills, so it can keep tracking new queries. sql_firewall
**cannot** do that: silently dropping a learned rule would re-block a
legitimate query. So `entry_dealloc` (and its `entry_cmp` comparator) are
wrapped in `#ifdef NOT_USED` (`sql_firewall.c:2181-2198, 2200-2206`) and never
called. Instead `entry_alloc` refuses to add past the cap:
`if (hash_get_num_entries(pgss_hash) >= pgss_max)` → `ereport(WARNING, …
exceeded the <sql_firewall.max> limit)` → `return NULL`
(`sql_firewall.c:2153-2158`) `[verified-by-code]`. This is a *correct*
adaptation of the borrowed code to the security use case — an allowlist must be
append-only within a learning window, never LRU-decayed — but it means a
cluster whose learning phase overflows `sql_firewall.max` will, in enforcing
mode, block every query it never got room to learn. `[inferred]` operational
consequence; `[verified-by-code]` for the disabled eviction.

### 4. The rule store is node-local, file-backed, and never WAL-logged

The ruleset persists only as flat files under `PGSTAT_STAT_PERMANENT_DIRECTORY`
(`sql_firewall.c:97-98`) `[verified-by-code]`, written by
`update_firewall_rule_file` via a write-tmp-then-`rename` atomic swap
(`sql_firewall.c:712-767`) `[verified-by-code]`, and — crucially — only at
shutdown, **and only when the mode is `learning`**:
`if (pgfw_mode == PGFW_MODE_LEARNING) update_firewall_rule_file();`
(`sql_firewall.c:839-841`) `[verified-by-code]`. Nothing about this touches
WAL, catalogs, or replication. Implications `[inferred]`: (a) the allowlist is
**not replicated** — a physical standby has no rules of its own, so a standby
promoted while `sql_firewall.firewall = enforcing` would block *all* traffic
until re-learned; (b) rules learned in a session that crashes (rather than
shuts down cleanly) are lost, since persistence happens only in the
`pgss_shmem_shutdown` on-exit hook (`sql_firewall.c:824-853`); (c) the error /
warning **counters** are persisted separately in a tiny text file via
`fprintf(file, "%ld %ld", warnings, errors)` (`sql_firewall.c:800-809`)
`[verified-by-code]`. Contrast `[[pgaudit]]`, which emits to the server log (an
already-replicated/archived channel) rather than inventing a private store.

### 5. Fingerprint semantics: normalized for optimizable queries, *literal* for utility

For an optimizable statement the key is the jumble-derived
`query->queryId = hash_any(jstate.jumble, jstate.jumble_len)` computed in
`pgss_post_parse_analyze` (`sql_firewall.c:900-901`) `[verified-by-code]`, so
`SELECT … WHERE id = 1` and `… WHERE id = 2` collapse to one rule (constants
normalized). But **utility statements are keyed on the raw string**:
`queryId = pgss_hash_string(queryString)` where `pgss_hash_string` is
`hash_any((unsigned char *) str, strlen(str))` with no normalization
(`sql_firewall.c:1136, 1191-1195`) `[verified-by-code]`. Divergence
consequence `[inferred]`: `DROP TABLE foo` and `DROP TABLE bar` are *distinct*
rules; learning one does not allow the other, and whitespace/case differences
in DDL produce different fingerprints. The queryid is also a **32-bit**
`hash_any` (`sql_firewall.c:134` field is `uint32`), the pre-PG-11 width — a
narrower collision space than modern core's 64-bit queryid, and a collision
here is a *security* event (an unlearned query hashing onto a learned one is
silently allowed). `[inferred]`.

### 6. Frozen against an old PG ABI

The code targets roughly **PG 9.5**: it uses `RequestAddinLWLocks` +
`LWLockAssign` (`sql_firewall.c:403,479`), both removed in 9.6; the
`post_parse_analyze_hook` two-argument signature `(ParseState *, Query *)`
(`sql_firewall.c:859`), which gained a `JumbleState *` in PG 14; the
`ProcessUtility_hook` signature taking `Node *parsetree` and
`char *completionTag` (`sql_firewall.c:1040-1042`), replaced by `PlannedStmt *`
in PG 10; and `EmitWarningsOnPlaceholders` (`sql_firewall.c:395`), renamed to
`MarkGUCPrefixReserved` in PG 15 `[verified-by-code]`. This ABI-pinning is a
maintenance-cost divergence: unlike a lean hook extension, a whole
pg_stat_statements fork must be re-synced against every core jumble change to
build on a modern server. `[inferred]` from the API surface.

### 7. Locking discipline inherited, with the ERROR-path lock release done right

The hash-table lock protocol is pg_stat_statements' verbatim: `LW_SHARED` to
look up, promote to `LW_EXCLUSIVE` to insert (`sql_firewall.c:1308-1310`), a
per-entry `slock_t mutex` spinlock guarding `counters.calls`
(`sql_firewall.c:1352-1356`), and a shared-state `mutex` guarding
`error_count`/`warning_count`/`extent`/`gc_count`
(`sql_firewall.c:1200-1215, 276-282`) `[verified-by-code]`. The one
security-relevant addition — the enforcing-mode `ereport(ERROR)` — correctly
**releases `pgss->lock` before throwing** (`sql_firewall.c:1259-1263`)
`[verified-by-code]`, so the longjmp does not escape while holding the LWLock;
this matches `[[lwlock-rank-discipline]]` / `[[spinlock-discipline]]`. The
permissive-mode WARNING path instead `goto done` to the unified
`LWLockRelease(pgss->lock)` at the bottom (`sql_firewall.c:1265-1270,
1359-1360`) `[verified-by-code]`.

---

## Notable design decisions (with cites)

- **Mode as an enum GUC, checked at the store site.** `PGFWMode`
  {disabled, learning, permissive, enforcing} (`sql_firewall.c:248-263`); the
  four-way branch lives entirely in `pgss_store`
  (`sql_firewall.c:1255-1274`) `[verified-by-code]`. There is no separate
  "check" hook — the store *is* the enforcement point.
- **Blocked-query reporting.** `enforcing` →
  `ereport(ERROR, errcode(ERRCODE_S_R_E_PROHIBITED_SQL_STATEMENT_ATTEMPTED),
  errmsg("Prohibited SQL statement"))` (`sql_firewall.c:1261-1263`);
  `permissive` → `ereport(WARNING, errmsg("Prohibited SQL statement"))`
  (`sql_firewall.c:1267`) `[verified-by-code]`. The SQLSTATE `2F004`
  (prohibited SQL statement attempted) is a semantically apt choice — the same
  class core uses for SECURITY-DEFINER function restrictions. See
  `[[error-handling]]`.
- **Per-role rules.** `pgssHashKey = {Oid userid; uint32 queryid}`, key set
  from `GetUserId()` at store time (`sql_firewall.c:131-135, 1247-1248`)
  `[verified-by-code]` — the allowlist is scoped per authenticated user, not
  global.
- **Superuser + disabled-mode gate on all rule mutation.**
  `sql_firewall_reset`, `sql_firewall_export_rule`, `sql_firewall_import_rule`
  each require `superuser()` *and* `pgfw_mode == PGFW_MODE_DISABLED`, else
  `ERRCODE_INSUFFICIENT_PRIVILEGE` (`sql_firewall.c:1373-1386, 1699-1707,
  2006-2013`) `[verified-by-code]`. Editing rules while the firewall is live is
  forbidden by construction.
- **CSV rule interchange.** `sql_firewall_export_rule` walks the hash with
  `hash_seq_search` and writes `userid,queryid,"query",calls` with RFC-style
  quote-doubling (`sql_firewall.c:1725-1775`); import re-derives
  `query_offset` / `query_len` / `encoding` and calls `pgss_restore` →
  `entry_alloc` (`sql_firewall.c:1794-1854`) `[verified-by-code]`. This is the
  intended way to promote a learned ruleset from staging to production, and to
  seed a standby (working around the no-replication gap of §4).
- **Counters stripped to one field.** `Counters` keeps only `int64 calls`
  (`sql_firewall.c:140-143`) `[verified-by-code]`, though `pgss_store` still
  computes and passes full `BufferUsage` from the ProcessUtility path
  (`sql_firewall.c:1109-1143`) that is then ignored — dead weight carried from
  the fork.
- **`relocatable = true`** control file (`sql_firewall.control:5`)
  `[verified-by-code]` — honest, since the C code hardcodes its own schema
  (`CREATE SCHEMA sql_firewall`, `sql_firewall--0.8.sql:6`) and file paths and
  does not embed a search-path assumption.

---

## Links into corpus

- `[[contrib-pg_stat_statements]]` — the parent this is forked from: the
  jumble/queryid machinery, the shared hash + external query-text file + GC, and
  the verbatim locking comment (§Divergence 2). The single most important edge.
- `[[process-utility-hook-chain]]` — the `ProcessUtility_hook` +
  Executor{Start,Run,Finish,End} hook set installed in `_PG_init`
  (`sql_firewall.c:408-421`); note enforcement is wired into ExecutorEnd, not a
  dedicated pre-exec check (§Divergence 1).
- `[[guc-variables]]` — `DefineCustomIntVariable` / `DefineCustomEnumVariable`,
  `PGC_POSTMASTER` restart semantics, `EmitWarningsOnPlaceholders`
  (`sql_firewall.c:367-395`).
- `[[error-handling]]` — the blocked-query `ereport(ERROR/WARNING)` with
  `ERRCODE_S_R_E_PROHIBITED_SQL_STATEMENT_ATTEMPTED` and the lock-release-
  before-throw discipline (`sql_firewall.c:1257-1270`).
- `[[lwlock-rank-discipline]]`, `[[spinlock-discipline]]` — the inherited
  LWLock-shared-then-exclusive + per-entry spinlock protocol
  (`sql_firewall.c:1308-1356`).
- `[[query-tree-walkers]]` — the vendored `JumbleQuery` / `JumbleExpr` tree walk
  that derives the fingerprint (`sql_firewall.c:2743-...`).
- Security / gatekeeping cluster (the ideology sibling set): `[[pgaudit]]`
  (logs rather than blocks; replicated channel vs private file — §4),
  `[[set_user]]`, `[[credcheck]]` (blocks at ProcessUtility *entry* — contrast
  §1), `[[supautils]]`, `[[pg_permissions]]`, and core
  `[[contrib-sepgsql]]` / `[[contrib-passwordcheck]]` / `[[contrib-auth_delay]]`.
- pg_stat_statements-derived cluster (the fork/queryid siblings):
  `[[pg_stat_monitor]]`, `[[pgsentinel]]`, `[[pg_stat_kcache]]`,
  `[[pg_qualstats]]`, `[[pg_wait_sampling]]`, `[[pg_tracing]]`.

> Corpus gap: there is no `idioms/queryid-as-authorization-key.md` capturing the
> pattern of *repurposing the pg_stat_statements jumble/queryid as an
> allow/deny key* (as opposed to an aggregation key). sql_firewall is the
> canonical instance; a future `pg_hba`-style query firewall would anchor the
> same idiom. Today it hangs off `[[contrib-pg_stat_statements]]`. `[inferred]`

---

## Sources

Fetched 2026-07-14 (branch `master`), all via `raw.githubusercontent.com`.
The Makefile's `DATA = sql_firewall--0.8.sql` line disclosed the install-script
name; the guessed version-suffixed names (`--1.0.sql`, `--2.0.sql`, …) all
404'd, as did every README/doc/expected-output probe (the repo ships no README
at these paths in `master`):

- `https://raw.githubusercontent.com/uptimejp/sql_firewall/master/sql_firewall.c`
  → HTTP 200, 2026-07-14T23:09:41Z (3463 lines; deep-read — `_PG_init` hook +
  GUC wiring, the four-mode enforcement branch in `pgss_store`, the ExecutorEnd
  / ProcessUtility store call sites, shmem startup + file persistence, the
  disabled `entry_dealloc`, CSV export/import, and the vendored jumble walker).
- `https://raw.githubusercontent.com/uptimejp/sql_firewall/master/sql_firewall--0.8.sql`
  → HTTP 200, 2026-07-14T23:10:01Z (66 lines; schema, views, C function
  declarations, PUBLIC revokes).
- `https://raw.githubusercontent.com/uptimejp/sql_firewall/master/sql_firewall.control`
  → HTTP 200, 2026-07-14T23:09:41Z (5 lines; `default_version = '0.8'`,
  `relocatable = true`, comment).
- `https://raw.githubusercontent.com/uptimejp/sql_firewall/master/Makefile`
  → HTTP 200, 2026-07-14T23:09:41Z (18 lines; PGXS `MODULE_big`, `EXTENSION`,
  `DATA`, `subdir = contrib/sql_firewall`).

404'd probes (2026-07-14T23:09:28Z / 23:10:01Z): `sql_firewall--1.0.sql`,
`sql_firewall--1.0.0.sql`, `sql_firewall--2.0.sql`, `sql_firewall--2.0.0.sql`,
`sql_firewall--1.1.sql`, `sql_firewall--1.0.1.sql`, `README.md`, `README`,
`README.euc_jp`, `doc/README.md`, `expected/sql_firewall.out`,
`expected/sql_firewall_1.out`, `sql/sql_firewall.sql`, `META.json`,
`README.rst`, `sql_firewall.sql`, `uninstall_sql_firewall.sql`, `.travis.yml`.

All cites are `[verified-by-code]` against the fetched files except: the
"built on pg_stat_statements" lineage and locking comment (`[from-comment]`);
and the reasoned consequence points tagged `[inferred]` — the post-execution
result leak / non-rollback (§1), the full-allowlist lockout (§3), the
no-replication / crash-loss behavior (§4), the utility-literal and 32-bit
collision risks (§5), and the old-ABI pinning (§6). **pg_stat_statements
internals are not re-derived here**; claims about what `JumbleQuery` /
`qtext_store` / `gc_qtexts` do are grounded in the copied code present in this
file, not in core `source/`.
