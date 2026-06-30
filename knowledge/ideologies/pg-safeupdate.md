# pg-safeupdate — a single-hook DML guard-rail extension

> Ideology note produced by the pg-extension-anthropologist cloud routine.
> Repo: `eradman/pg-safeupdate` @ branch `master` (release 1.6), fetched 2026-06-29.
> Caveat: characterization based on the files actually fetched — `safeupdate.c`,
> `README.md`, `Makefile`. The repo's `test.rb` Ruby harness was referenced but
> not fetched (the GitHub "Ruby" language tag is that harness; the extension
> itself is a single C file).

## Domain & purpose

`pg-safeupdate` is a defensive-policy extension: it raises an error when an
`UPDATE` or `DELETE` is executed without a `WHERE` clause, so that an
unqualified full-table mutation is rejected rather than silently rewriting every
row. It was originally written to protect data exposed through PostgREST, where
a malformed request could otherwise wipe a whole table
[from-README]. The entire extension is one ~80-line C file plus a PGXS
`Makefile`; it is the canonical minimal example of a *behavioral-policy*
extension — it changes no data layout, adds no SQL-callable function, and
defines exactly one GUC.

## How it hooks into PG

The hook is **`post_parse_analyze_hook`**, NOT an executor hook. The extension
inspects the analyzed `Query` tree immediately after parse-analysis, before
planning or execution.

- `_PG_init` saves the previous hook into a static and installs its own:
  `prev_post_parse_analyze_hook = post_parse_analyze_hook;` then
  `post_parse_analyze_hook = delete_needs_where_check;`
  (`safeupdate.c:77-78`) [verified-by-code].
- The callback `delete_needs_where_check(ParseState *, Query *, JumbleState *)`
  chains the previous hook first, then applies the policy
  (`safeupdate.c:15-26`) [verified-by-code]. The signature is version-gated:
  `const JumbleState *` for `PG_VERSION_NUM >= 190000`, plain `JumbleState *`
  below (`safeupdate.c:16-20`) [verified-by-code].
- The single GUC `safeupdate.enabled` is a bool defaulting to **true**, defined
  at `PGC_SUSET` (so a superuser can flip it per session but an ordinary user
  cannot quietly disable the guard mid-session)
  (`safeupdate.c:67-76`) [verified-by-code].
- Load model: no `.control` file and no `CREATE EXTENSION`. The `Makefile` uses
  bare `MODULES = safeupdate` PGXS (`Makefile`, `MODULES` line)
  [verified-by-code], so it is activated via `LOAD 'safeupdate';` per session,
  `shared_preload_libraries=safeupdate` cluster-wide, or
  `session_preload_libraries` per database [from-README].

### The policy check itself

For `CMD_DELETE` and `CMD_UPDATE`, the callback asserts `query->jointree != NULL`
and rejects the statement when `query->jointree->quals == NULL`, i.e. the
parse-analysis produced no qualification, raising
`ERRCODE_CARDINALITY_VIOLATION` with "UPDATE/DELETE requires a WHERE clause"
(`safeupdate.c:43-61`) [verified-by-code]. Modifying CTEs are handled by
recursing into each `cteList` entry when `query->hasModifyingCTE` is set
(`safeupdate.c:33-41`) [verified-by-code] — this is why a `WITH ... UPDATE`
inside a `SELECT` is also caught [from-README].

Two early-outs precede the check: it returns immediately under
`IsBinaryUpgrade` (so `pg_upgrade`'s internal DML is never blocked) and when
`!safeupdate_enabled` (`safeupdate.c:28-31`) [verified-by-code].

## Where it diverges from core idioms

- **It adds a cross-cutting DML policy core has no equivalent of.** Core
  PostgreSQL has no built-in "require a WHERE clause" mode; the closest analogues
  are client-side (e.g. `psql`'s nothing-of-the-sort, or MySQL's `sql_safe_updates`,
  which PG does not have). The extension supplies a server-side policy by
  intercepting every analyzed statement [inferred].
- **Hook-chaining discipline.** It follows the canonical save/restore-the-previous
  hook idiom: capture the existing `post_parse_analyze_hook` into a static at
  `_PG_init` time and unconditionally invoke it from the callback before doing
  its own work (`safeupdate.c:13`, `:25-26`, `:77`) [verified-by-code]. It does
  NOT restore the prior hook on unload — there is no `_PG_fini`, consistent with
  PG's recommendation that loaded modules are not safely unloadable
  [inferred].
- **It checks the Query tree, not a plan tree.** The divergence angle is subtler
  than "walk the plan / ModifyTable node": by hooking *parse-analysis* it reads
  `query->jointree->quals` directly off the rewritten-but-not-yet-planned
  `Query` (`safeupdate.c:47`, `:54`) [verified-by-code]. This is cheaper and
  earlier than an `ExecutorStart_hook`/`ExecutorCheckPerms_hook` approach, and it
  fires before any plan is built — but it keys on *syntactic* absence of a
  qualification (no `quals` node) rather than on a runtime row count, so
  `WHERE 1=1` satisfies it even though it matches every row [from-README].
- **Per-session, superuser-gated GUC nuance.** `PGC_SUSET` means the guard is on
  by default and only a superuser may set `safeupdate.enabled=0`; this is a
  deliberate "secure default, privileged override" choice rather than a plain
  `PGC_USERSET` toggle (`safeupdate.c:72`) [verified-by-code].

## Notable design decisions

- **Hook choice: parse-analyze, not executor.** Catching the missing-WHERE at
  `post_parse_analyze_hook` rejects the statement before planning/execution and
  also naturally reaches modifying CTEs via the `Query` tree
  (`safeupdate.c:13-62`) [verified-by-code].
- **Recurse into modifying CTEs.** Rather than trusting that the top-level
  `commandType` is `CMD_UPDATE`/`CMD_DELETE`, it descends `cteList` whenever
  `hasModifyingCTE` is set, catching `WITH u AS (UPDATE ... RETURNING *) SELECT ...`
  (`safeupdate.c:33-41`) [verified-by-code].
- **`IsBinaryUpgrade` bypass.** Skips the check during `pg_upgrade` so the
  dump/restore path is never blocked (`safeupdate.c:28`) [verified-by-code].
- **`ERRCODE_CARDINALITY_VIOLATION` as the SQLSTATE.** A defensible, semantically
  honest choice — an unqualified mutation touches an unbounded cardinality of
  rows (`safeupdate.c:49`, `:56`) [verified-by-code].
- **Secure-by-default GUC.** Default `true` at `PGC_SUSET`
  (`safeupdate.c:71-72`) [verified-by-code].
- **No `.control` / no `CREATE EXTENSION`.** Plain PGXS `MODULES` build, loaded
  as a library — the leanest possible packaging for a hook-only module
  (`Makefile`) [verified-by-code].

## Links into corpus

No sibling ideology or idiom docs exist yet (this is the first
`knowledge/ideologies/` doc; `knowledge/idioms/` is currently empty). Future
hook-chaining and planner/executor-hook siblings — e.g. a `pg_hint_plan`
ideology note or a hook-chaining idiom doc — should back-link here. None are
linked now because the target paths do not yet exist (verified by directory
scan, 2026-06-29).

## Sources

- `https://raw.githubusercontent.com/eradman/pg-safeupdate/master/safeupdate.c`
  — HTTP 200. Primary source; all `file:line` cites above point into it.
- `https://raw.githubusercontent.com/eradman/pg-safeupdate/master/README.md`
  — HTTP 200. Load model, options, examples.
- `https://raw.githubusercontent.com/eradman/pg-safeupdate/master/Makefile`
  — HTTP 200. Confirms PGXS `MODULES` build, release 1.6, Ruby test harness.
- `https://api.github.com/repos/eradman/pg-safeupdate/git/trees/master?recursive=1`
  — HTTP 403 (proxy/API forbidden). Full file listing not obtained; file set
  inferred from the Makefile and known repo layout.
- `https://raw.githubusercontent.com/eradman/pg-safeupdate/master/test/safeupdate.rb`
  — HTTP 404. The test harness is `test.rb` at repo root (per `Makefile`
  `@${RUBY} ./test.rb`), not under `test/`; not fetched. No `.control` file
  exists (the extension is loaded as a library, not via `CREATE EXTENSION`).
