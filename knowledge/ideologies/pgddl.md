# pgddl (extension `ddlx`) — the `pg_get_*def` / ruleutils family reimplemented entirely in SQL, plus everything ruleutils has no deparse function for

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `lacanoid/pgddl` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. The shipped payload is one file,
> `ddlx.sql` (3261 lines, run through a version preprocessor at build time);
> cites verified against files fetched 2026-07-09 (see Sources footer).
> **Naming:** the on-disk extension name is `ddlx` (`EXTENSION=ddlx`,
> `CREATE EXTENSION ddlx`, function prefix `ddlx_`), but the repository and
> common name is `pgddl`. This doc uses "pgddl" for the project and "`ddlx`"
> for the installed artifact. Read alongside `[[pg_permissions]]` (the closest
> structural sibling — a pure-SQL catalog reader that unrolls ACLs) and
> `[[index_advisor]]` (the corpus's other "ships ONLY SQL, no `.so`" extension).

## Domain & purpose

pgddl is "an SQL-only extension … that provides uniform functions for
generating SQL Data Definition Language (DDL) scripts for objects created in a
database" (`README.md:4-5`) `[from-README]`. It answers "what `CREATE` /
`ALTER` statements would reconstruct this existing object?" — the
`SHOW CREATE TABLE` other databases ship, which PostgreSQL deliberately does
*not* have in-server, relegating it to the external `pg_dump` program
(`README.md:9-14`) `[from-README]`. The public API is three functions:
`ddlx_create(oid, options)` builds CREATE statements, `ddlx_drop(oid, options)`
builds DROP, and `ddlx_script(oid, options)` builds a whole dependency-ordered
rebuild script (`README.md:107-111`, `ddlx.sql:3075, 3124, 3221`)
`[verified-by-code]`. Everything is driven off an object's `oid`, with the
various `reg*` alias types (`regclass`, `regproc`, `regtype`, `regrole`, …)
auto-casting to it (`README.md:115-132`) `[from-README]`.

The reason to document it: pgddl is the corpus's sharpest example of a specific
divergence — **it reimplements PostgreSQL's `ruleutils.c` deparse family in
SQL**, in userspace, outside the C backend. Where core exposes a `pg_get_*def`
builtin, pgddl calls it; where core has *no* deparse function (table column
DDL, `CREATE TYPE`, `CREATE AGGREGATE`, GRANT reconstruction, roles, databases,
FDWs, most everything that is not a view/index/constraint/trigger/function),
pgddl hand-assembles the DDL text from raw catalog columns using SQL string
concatenation. It is `pg_dump`'s deparse logic, minus the C, minus the client.

## How it hooks into PG

It does not hook into anything. There is no `_PG_init`, no `.so`, no shared
library, no background worker, no GUC, no planner/executor/utility hook. The
build is PGXS with `DATA_built = ddlx--0.31.sql` and **no `MODULE_big`, no
`OBJS`** (`Makefile:4-7`) `[verified-by-code]`; the control file declares
`default_version = 0.31`, `superuser = false` (`ddlx.control:2-3`)
`[verified-by-code]`. The extension body is a stack of ~90 `CREATE OR REPLACE
FUNCTION … LANGUAGE sql` definitions — all plain SQL functions, marked `strict`
so they return NULL on NULL input. The README makes a point of this: "It is
entirely made out of **plain SQL functions** so you don't have to install any
extra languages, not even PL/PgSQL! It runs on plain vanilla Postgres"
(`README.md:39-40`) `[from-README]`. (Note the `META.json` runtime prereqs
list `plpgsql` (`META.json:15`) — a stale/defensive declaration; no function in
`ddlx.sql` is `LANGUAGE plpgsql` `[verified-by-code]`.)

The "engine" is entirely core's own catalog surface, in two layers:

### The `pg_get_*def` builtins it *does* call

pgddl delegates to ruleutils wherever core offers a deparse function:

- `pg_get_viewdef(oid, true)` — view/matview bodies (`ddlx.sql:946`, also used
  as a search corpus in `ddlx_apropos` `:2383, 2391`).
- `pg_get_constraintdef(oid[, true])` — CHECK / FK / UNIQUE / PK / EXCLUDE
  (`ddlx.sql:596, 1181, 1453`).
- `pg_get_triggerdef(oid, true)` — trigger definitions (`ddlx.sql:673, 1507`).
- `pg_get_ruledef(oid, true)` — rewrite rules (`ddlx.sql:627, 1497`).
- `pg_get_indexdef(oid)` — index definitions (`ddlx.sql:1182`).
- `pg_get_functiondef(oid)` — non-aggregate functions (`ddlx.sql:1640`).
- `pg_get_expr(adbin, adrelid[, true])` — default expressions, generated-column
  expressions, partition bounds, RLS quals (`ddlx.sql:455, 513, 529, 889,
  1391, 1907, 1982`).
- `pg_get_function_arguments(oid)` (`:746`), `pg_get_partkeydef(oid)` (`:907`),
  `pg_get_serial_sequence(...)` (`:539`), `pg_get_statisticsobjdef(oid)`
  (`:2966`), `pg_get_userbyid(...)` (throughout), and `format_type(oid, typmod)`
  (throughout) `[verified-by-code]`.

### Where it goes BEYOND core — DDL for objects ruleutils cannot deparse

This is the substance. Core has no `pg_get_tabledef`, no `pg_get_typedef`, no
`pg_get_roledef`, no `pg_get_grantsdef`. pgddl builds these from raw catalog
columns:

- **Table column DDL** — `ddlx_describe(regclass, text[])` (`ddlx.sql:433-566`)
  is the workhorse core lacks entirely: it reads `pg_attribute` + `pg_attrdef`
  + `pg_type` + `pg_collation` + `pg_constraint` and hand-assembles each
  column's `name type[typmod] [COLLATE] [NOT NULL] [DEFAULT] [GENERATED …
  IDENTITY] [GENERATED … STORED]` fragment via one giant `format('%I %s%s%s…')`
  (`ddlx.sql:488-538`) `[verified-by-code]`. `ddlx_create_table`
  (`ddlx.sql:842-933`) then wraps those column fragments in `CREATE [UNLOGGED|
  TEMPORARY] TABLE`, handling `OF type`, `PARTITION OF`, `INHERITS`, `PARTITION
  BY`, `WITH OIDS`, and foreign-table `SERVER … OPTIONS` — all reconstructed
  in SQL from `pg_class`, `pg_inherits`, `pg_partitioned_table`,
  `pg_foreign_table` `[verified-by-code]`.
- **`CREATE TYPE`** — base (`ddlx_create_type_base` `:1055-1100`), enum
  (`:1130-1143`), domain (`:1147-1169`), range (`:1105-1126`), and composite
  (routed to `ddlx_create_class`) — none of which core can deparse.
- **`CREATE AGGREGATE`** — `ddlx_create_aggregate` (`ddlx.sql:1580-1628`)
  hand-builds the aggregate definition from `pg_aggregate` because
  `pg_get_functiondef` *refuses* aggregates; `ddlx_create_function` branches on
  `sql_kind='AGGREGATE'` to call it instead (`ddlx.sql:1638-1641`)
  `[verified-by-code]`.
- **GRANT / ACL reconstruction** — `ddlx_grants(oid)` (`ddlx.sql:2139-2201`)
  and `ddlx_grants_columns` (`:2073-2106`) unroll `aclitem[]` via
  `aclexplode(acl)` and emit `GRANT … ON … TO …[WITH GRANT OPTION]`; role
  membership grants come from `pg_auth_members` (`ddlx_grants(regrole)`
  `:1648-1685`). Core has no ACL-deparse function.
- **Roles** — `ddlx_create_role` / `ddlx_alter_role` (`ddlx.sql:1699-1779`)
  reconstruct `CREATE USER/GROUP` + `ALTER ROLE WITH LOGIN/SUPERUSER/…`,
  per-role `rolconfig` settings, `VALID UNTIL`, `CONNECTION LIMIT`, and even
  `ENCRYPTED PASSWORD` from `pg_authid` (`ddlx_alter_role_auth` `:1689-1696`).
- **Comments** — `ddlx_comment` (`ddlx.sql:783-802`) reconstructs `COMMENT ON`
  via `obj_description` / `col_description` / `shobj_description` (the latter
  for shared objects like databases and tablespaces `:794-797`).
- **Storage / reloptions / statistics targets** — `ddlx_alter_table_storage`
  (`:1312-1346`) and `ddlx_alter_table_settings` (`:1350-1382`) emit `ALTER …
  SET STORAGE / SET COMPRESSION / SET TABLESPACE / SET (reloptions) / SET
  STATISTICS`, decoding `pg_options_to_table(...)` and per-attribute options.
- **The long tail** — schema, extension, database, tablespace, FDW, server,
  user mapping, cast, collation, conversion, language, operator, operator
  class/family, `amproc`/`amop`, text-search config/dict/parser/template,
  event trigger, access method, policy (RLS), transform, publication,
  subscription — each with its own `ddlx_create_*` function
  (`ddlx.sql:1806-2879`) `[verified-by-code]`.

The generic entry point tying it together is `ddlx_identify(oid)`
(`ddlx.sql:12-427`) — a single function whose body is a **~35-branch
`UNION ALL`** over nearly every system catalog (`pg_class`, `pg_proc`,
`pg_type`, `pg_roles`, `pg_rewrite`, `pg_namespace`, `pg_constraint`,
`pg_trigger`, `pg_attrdef`, `pg_operator`, `pg_ts_*`, `pg_foreign_*`,
`pg_cast`, `pg_collation`, `pg_conversion`, `pg_language`, `pg_opfamily`,
`pg_database`, `pg_tablespace`, `pg_opclass`, `pg_extension`,
`pg_event_trigger`, `pg_amproc`, `pg_amop`, `pg_policy`, `pg_transform`,
`pg_am`, `pg_statistic_ext`, `pg_publication`, `pg_subscription`) that maps
any oid to `(classid, name, namespace, owner, sql_kind, sql_identifier, acl)`
`[verified-by-code]`. This is a userspace reimplementation of core's
`pg_identify_object` / `getObjectDescription` object-address machinery.

Cross-ref `[[catalog-conventions]]` (the catalogs it reads),
`[[ddl-deparse-via-event-triggers]]` (core's *own* structured-DDL-capture path,
the direct C-side contrast), `.claude/skills/extension-development/SKILL.md`
(the PGXS `DATA`-only surface it minimally uses).

## Where it diverges from core idioms

### 1. DDL reconstruction lives in SQL, not in `ruleutils.c`

Core's stance is that DDL reconstruction is C work: `ruleutils.c` deparses the
handful of objects with `pg_get_*def` functions, and `pg_dump` (a client
program walking the catalog in C) does the rest. pgddl rejects the "external
tool" half of that (`README.md:12-14`) `[from-README]` and moves the *entire*
deparse surface into SQL functions that any client running plain SELECTs can
call (`README.md:21-31`) `[from-README]`. The consequences that make this a
real divergence, not just a packaging choice:

- **It duplicates catalog-decoding logic core keeps private.** For example, the
  trigger-type bitmask decode (`t.tgtype::integer & 2/4/8/16/…` →
  BEFORE/INSERT/…) is re-derived in SQL (`ddlx.sql:653-672`), as is the
  `pg_policy.polcmd` char → SELECT/INSERT/UPDATE/DELETE/ALL mapping
  (`:1893-1900`) and the `pg_attribute.attidentity`/`attgenerated` →
  `GENERATED … AS IDENTITY/STORED` decode (`:507-533`). These are internal
  encodings that core deparse code owns; pgddl re-encodes them by hand and must
  track them as catalogs evolve.
- **Aggregates prove why the reimplementation is unavoidable, not gratuitous.**
  `pg_get_functiondef` deliberately errors on aggregates, so pgddl *has* to
  hand-build `CREATE AGGREGATE` from `pg_aggregate` (`ddlx.sql:1580-1628`) —
  there is no core function to lean on. The same is true for tables, types,
  roles, and grants: the reimplementation exists precisely in the gap where
  core offers nothing.

### 2. Version differences are resolved at BUILD time by a C-preprocessor-style pass, not at runtime

This is the sharpest contrast with the sibling `[[pg_permissions]]`, which
branches on `current_setting('server_version_num')` inside a live view.
`ddlx.sql` is not valid SQL as shipped — it is run through a custom
preprocessor (`bin/pgsqlpp`) at `make` time to emit a version-specific
`ddlx--0.31.sql` (`Makefile:17-19`, `README.md:71-73`) `[verified-by-code]`.
The source is littered with `#if 14` / `#if 9.5` / `#else` / `#end` / `#unless
12` / `#require 10` / `#required` directives (`ddlx.sql:58, 84, 138, 456, 910,
1950, 2067`, and hundreds more) that select which catalog columns and which
DDL spellings to compile in for the target major version `[verified-by-code]`.
Implications:

- **The installed extension is pinned to the exact PG version it was built
  against.** The generated SQL reads catalog columns that only exist on that
  version — `a.attcompression` (PG 14+ `:541`), `c.relpartbound` (PG 10+
  `:888`), `sub.subfailover` (PG 17+ `:2053`), `set_option`/`inherit_option`
  role-membership flags (PG 16+ `:1659-1660`). Build against the wrong version
  and the SQL references nonexistent columns.
- **Catalog-schema drift is the standing risk.** Because pgddl reads raw
  catalog columns directly (not through a stable API), every PG major release
  that renames, retypes, or removes a column is a potential break; the
  preprocessor is the maintenance burden that keeps ~9.1-through-18 support
  alive in one source file (`README.md:61-64`) `[from-README]`. Core's own
  `pg_get_*def` functions absorb exactly this churn behind a stable signature —
  which is the value pgddl forgoes for the columns core doesn't cover.
- **Development target is stated as PG 13, recommended 17** (`README.md:61`,
  `META.json:19-20`) — the corpus of `#if` guards is the historical record of
  every catalog change from 9.1 forward.

### 3. Injection-safety is real but uneven: `format()`/`quote_*` and the `reg*::text` idiom, mixed with bare `||`

pgddl generates SQL-as-text, so identifier/literal escaping is a correctness
*and* safety concern. Its primary defenses:

- **`format()` with `%I` (identifier) and `%L`/`quote_nullable`/`quote_literal`
  (literal)** — e.g. column DDL (`ddlx.sql:488`), `COMMENT ON … IS %L`
  (`:787`), storage ALTERs (`:1320, 1329`), options lists via
  `quote_ident(option_name)||' '||quote_nullable(option_value)` (`:493-494,
  917, 1823`) `[verified-by-code]`.
- **The `reg*::text` cast as an escaping primitive** — casting an oid through
  `regclass` / `regprocedure` / `regoperator` / `regtype` and taking `::text`
  yields a properly schema-qualified, correctly-quoted identifier for free,
  because core's `reg*` output functions do the quoting. pgddl leans on this
  everywhere (`c.oid::regclass::text` `:1179, 1210`; `oprcode::regproc as text`
  `:2431`; `castfunc::regprocedure` `:2554`) — it is the single most common
  identifier idiom in the file `[verified-by-code]`.

But the coverage is not uniform. Many fragments concatenate catalog values with
bare `||` and only *sometimes* wrap them in `quote_ident`. Owner names go
through `quote_ident(owner)` in `ddlx_alter_owner` (`:834`) but raw
`obj.sql_kind` (a pgddl-computed keyword, safe) and raw `obj.namespace` appear
unquoted in places (`nullif(obj.namespace,current_schema())||'.'` `:2429`,
guarded by `quote_ident` in some sites `:2709` but not all). The
`reg*::text`-heavy style is generally safe because the escaping happens in
core, but the hand-built branches are where a pathological identifier would
most plausibly produce malformed DDL `[inferred]`.

### 4. `superuser = false`, `SECURITY INVOKER`, unpinned `search_path` — a caller-privileged catalog reader

The extension installs as an ordinary non-superuser extension
(`ddlx.control:3`) and every function is plain `LANGUAGE sql` with the default
`SECURITY INVOKER` and **no `SET search_path` pin** (the only `SET` anywhere is
`set datestyle = iso` on `ddlx_alter_role` `:1780` and `SET
client_min_messages = warning` at file top `:6`) `[verified-by-code]`.
Consequences:

- **It runs with the caller's privileges and sees only what the caller can
  see.** Several functions filter by predicate builtins:
  `ddlx_describe` requires `has_table_privilege(c.oid,'select') AND
  has_schema_privilege(s.oid,'usage')` (`ddlx.sql:562`), and `ddlx_apropos`
  gates its function/view search on `has_function_privilege` /
  `has_table_privilege` / `has_schema_privilege` (`:2366-2367, 2399-2400`)
  `[verified-by-code]`. So generated DDL is privilege- and search_path-
  dependent, not a pure function of the oid.
- **Password extraction is explicitly guarded.** `ddlx_alter_role` only calls
  `ddlx_alter_role_auth` (which dumps `rolpassword` from `pg_authid`) when
  `has_table_privilege('pg_catalog.pg_authid','select')` is true
  (`ddlx.sql:1748-1750`) `[verified-by-code]` — a deliberate defensive touch,
  since `pg_authid` is superuser-only by default.
- **Unpinned `search_path` is a documented operational wart, not a hardening
  gap.** Because cross-function calls (`ddlx_identify($1)`, `ddlx_describe($1)`)
  are unqualified, the extension only works if its schema is on the caller's
  `search_path`; the README's fix is to install it into `pg_catalog`
  (`CREATE EXTENSION ddlx SCHEMA pg_catalog`, `README.md:91-97`)
  `[from-README]`, which requires superuser and sidesteps the issue by putting
  the functions in the always-present schema. The same unpinned `search_path`
  also means the generated DDL's *own* schema-qualification behavior is
  intentionally `search_path`-relative: objects not in the current schema are
  qualified, objects in it are not (`README.md:192-193`) `[from-README]`.

### 5. DDL text is assembled by the "array of nullable fragments → `array_to_string`" idiom

The pervasive code-generation pattern is: build a SQL `array[...]` of optional
clause fragments, each either a string or NULL, then `array_to_string(arr,
sep)` — NULLs vanish, present clauses join. This is how nearly every
`ddlx_create_*` assembles a multi-clause statement: `CREATE TYPE (…)` options
(`ddlx.sql:1059-1096`), `CREATE AGGREGATE` (`:1584-1624`), `ALTER ROLE WITH …`
(`:1731-1741`), `CREATE OPERATOR` (`:2428-2448`), `CREATE DATABASE WITH …`
(`:2644-2648`) `[verified-by-code]`. It is a clean SQL analogue of the
`appendStringInfo`-with-`if` chains that `ruleutils.c` and `pg_dump` use in C —
the same deparse shape, expressed as set-valued SQL. Pretty-printing (newlines,
two-space indents) is baked into the separators and `E'\n  '` literals, aiming
at the README's "reasonable balance between detail and clutter" for
human-copy/paste output (`README.md:32-38`) `[from-README]`.

## Notable design decisions with cites

- **`ddlx_get_dependants` reimplements `pg_dump`'s topological sort as a
  recursive CTE over `pg_depend`** (`ddlx.sql:2227-2302`) `[verified-by-code]`.
  It walks the dependency graph, folds in partition children via
  `pg_partition_tree` (`:2248-2258`), carries an `edges` array and tests
  `NOT (t.edges @> array[...])` for **cycle detection** (`:2272`), then keeps
  each object at its *maximum* depth so it sorts after everything it depends on
  (`:2287-2291`). `ddlx_script` (`:3221-3239`) uses this to emit
  commented-out DROPs for dependants at the top and CREATEs to rebuild them at
  the bottom, wrapped in `BEGIN;`/`END;` (transactional DDL) unless `nowrap`.
- **`ddlx_identify` is a ~35-way `UNION ALL` doing generic object resolution in
  one SQL function** (`ddlx.sql:12-427`). Every `ddlx_create_*` starts with
  `with obj as (select * from ddlx_identify($1))`, making it the spine of the
  whole extension. It even carries a PG-14 "hack to hide duplicated oids" for
  NOT NULL constraints that collide with catalog rows (`:138-142`)
  `[from-comment]`.
- **GRANTs are unrolled structurally via `aclexplode`, not via predicate
  `has_*_privilege`** (`ddlx.sql:2079, 2149`) — the exact inverse of the
  sibling `[[pg_permissions]]`, which uses the predicate builtins exhaustively.
  pgddl needs the literal `(grantor, grantee, privilege, is_grantable)` tuples
  to spell out `GRANT` statements, so it explodes the `aclitem[]` array;
  pg_permissions only needs a boolean, so it asks the predicate. Same ACL data,
  opposite read path, driven by opposite goals (reproduce vs. audit).
- **Idempotent-DDL options.** `ine`/`ie` inject `IF NOT EXISTS`/`IF EXISTS` in
  many places (`README.md:150-151`), including via a `regexp_replace` that
  rewrites `CREATE … INDEX` → `CREATE … INDEX IF NOT EXISTS` on the output of
  `pg_get_indexdef` (`ddlx.sql:1194-1196`) `[verified-by-code]` — i.e. it
  string-patches core's deparse output because `pg_get_indexdef` has no IF NOT
  EXISTS mode. Constraint-backing indexes are emitted as `ALTER TABLE … ADD
  CONSTRAINT` rather than bare `CREATE INDEX` (`:1176-1183`).
- **`lite` option targets SQLite compatibility** (`README.md:153`): it inlines
  defaults and constraints into `CREATE TABLE` and omits PG-specific storage /
  settings / rules (`ddlx.sql:512-513, 873-879, 1305`) `[verified-by-code]` —
  a divergence-from-PG-*output* knob, generating DDL a different engine can eat.
- **`data` option fakes data preservation with temp tables** — `ddlx_data_backup`
  emits `CREATE TEMPORARY TABLE name$oid AS SELECT * FROM …` and
  `ddlx_data_restore` emits the `INSERT … OVERRIDING SYSTEM VALUE … / DROP
  TABLE` round-trip (`ddlx.sql:3162-3190`) `[verified-by-code]`, so a
  drop/recreate script can carry rows across.
- **It mixes `information_schema` reads with direct catalog reads** — sequence
  parameters come from `information_schema.sequences` (`ddlx.sql:972`) and
  routine privileges from `information_schema.routine_privileges` (`:2132`),
  even though most of the file reads `pg_catalog` directly. The
  information_schema views are the SQL-standard, more-stable surface where they
  exist; the raw catalogs are used everywhere they don't.
- **All functions are `strict`** (NULL oid → NULL output) rather than raising —
  a uniform convention across the file (e.g. `:427, 565, 1200`) that lets the
  dispatchers compose fragments with `||` without NULL-guarding every call.

## Links into corpus

- `[[pg_permissions]]` — the closest structural sibling: a pure-SQL,
  no-`.so`, `superuser=false` catalog-introspection extension. The instructive
  contrast is the ACL read path (pgddl explodes `aclitem[]` via `aclexplode` to
  *reproduce* GRANTs; pg_permissions calls `has_*_privilege` predicates to
  *audit* effective privilege) and the version-handling strategy (pgddl resolves
  version differences at build time via a preprocessor; pg_permissions branches
  at runtime on `server_version_num`).
- `[[index_advisor]]` — the corpus's other "a PostgreSQL extension can contain
  zero compiled code" case. index_advisor is one PL/pgSQL function; pgddl is
  ~90 pure-SQL functions. Both are PGXS `DATA`-only packages with no
  `MODULE_big`, both turn a core read-only surface into a programmatic API.
- `[[ddl-deparse-via-event-triggers]]` — core's *own* structured-DDL-capture
  path (`ddl_command_end` event triggers + `pg_ddl_command` + the C deparse
  infrastructure). The direct contrast: core captures DDL as it happens, in C,
  as structured nodes; pgddl reconstructs DDL after the fact, in SQL, from the
  resting catalog state. Same goal (recover a CREATE statement), opposite
  mechanism and layer.
- `[[catalog-conventions]]` — the system-catalog surface pgddl reads
  wholesale (`pg_class`, `pg_attribute`, `pg_proc`, `pg_type`, `pg_constraint`,
  `pg_depend`, `pg_authid`, and ~30 more), and the `pg_get_*def` / ruleutils
  builtins it delegates to.
- `.claude/skills/extension-development/SKILL.md` — PGXS `DATA_built`-only
  packaging, `.control` `superuser = false`, no `MODULE_big`.

## Sources

Fetched 2026-07-09 via `raw.githubusercontent.com/lacanoid/pgddl/master`:

- `README.md` @ 2026-07-09 → HTTP 200 (11583 bytes; purpose, the
  "no pg_dump / no PL/pgSQL / plain SQL" framing, the three-function public API,
  the options list, the `search_path` / `SCHEMA pg_catalog` install note, the
  "developed on PG 13, recommended 17" version note).
- `ddlx.control` @ 2026-07-09 → HTTP 200 (79 bytes; `default_version = 0.31`,
  `superuser = false`).
- `ddlx.sql` @ 2026-07-09 → HTTP 200 (116443 bytes, 3261 lines; **the entire
  extension**, deep-read — `ddlx_identify`'s 35-catalog UNION ALL, `ddlx_describe`
  column-DDL assembly, the `ddlx_create_*` family, `pg_get_*def` delegation
  sites, `aclexplode` GRANT reconstruction, `ddlx_get_dependants` recursive
  dependency CTE, the `#if`/`#else`/`#require` version preprocessor directives,
  and the `ddlx_create` / `ddlx_drop` / `ddlx_script` dispatchers).
- `Makefile` @ 2026-07-09 → HTTP 200 (1176 bytes; PGXS `DATA_built` via the
  `bin/pgsqlpp` preprocessor, no `MODULE_big`/`OBJS`, `REGRESS` suites).
- `META.json` @ 2026-07-09 → HTTP 200 (1279 bytes; PGXN metadata, version
  0.31.0, runtime `requires plpgsql` — noted as stale against the all-`LANGUAGE
  sql` body — and `recommends PostgreSQL 17`).

All cites are `[verified-by-code]` against the fetched `ddlx.sql` /
`ddlx.control` / `Makefile` except purpose/framing/version statements
(`[from-README]`), the "hide duplicated oids" note (`[from-comment]`), and the
identifier-quoting-coverage and `search_path`-dependence observations
(`[inferred]` from the code). Manifest gaps not fetched: `ROADMAP.md`, the
`bin/pgsqlpp` preprocessor script itself, the `test/` regression suite
(`test/expected/manifest.out` — the authoritative function list), and
`docs/function_usage.svg`; the single `ddlx.sql` source plus the manifest files
are self-contained for the divergence story above.
