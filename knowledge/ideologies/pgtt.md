# pgtt — Oracle-style Global Temporary Tables faked in extension space: a persistent UNLOGGED "template" table plus a per-session `pg_temp` instance, wired together by three hooks that rewrite the relid mid-parse-analysis

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `darold/pgtt` @ branch `master` (`default_version = '4.5.0'`). All
> `file:line` cites point into that repo (not `source/`), since this doc
> characterizes an *external* extension's divergence from core idioms. Cites
> verified against files fetched on 2026-07-06 (see Sources footer). The whole
> feature is one C file, `pgtt.c` (2240 lines); the install script only defines a
> schema and a shadow-catalog table. Read alongside
> `[[knowledge/ideologies/temporal_tables]]` (the closest sibling — a core SQL
> feature synthesized from hooks + shadow state) and `[[knowledge/idioms/fmgr]]`.

## Domain & purpose

Core PostgreSQL has only **session-local** temporary tables: `CREATE TEMP TABLE`
creates a fresh, private relation in `pg_temp_NN` for one backend, gone at session
(or transaction) end. Oracle-style **Global Temporary Tables (GTT)** invert the
persistence split: the *table definition* is permanent and shared across all
sessions, but the *data* is private per session, with `ON COMMIT {DELETE |
PRESERVE} ROWS` governing row lifetime (`README.md:29-33,63-72`) `[from-README]`.
pgtt exists "to provide the Global Temporary Table feature to PostgreSQL waiting
for an in core implementation" so an Oracle migration "can not or don't want to
rewrite the application code" (`README.md:16-21`) `[from-README]`.

The anthropological interest: pgtt synthesizes an entire DDL feature — a new table
*kind* with new persistence semantics — **without patching core**, using a hook
stack, a shadow catalog table, an in-process SPI/`DefineRelation` backing
mechanism, and mid-parse-analysis relid rewriting. It is a GTT engine assembled
entirely from the public extension surface.

## How it hooks into PG

`_PG_init` (`pgtt.c:243-303`) installs **three chained hooks** plus process wiring,
all saving the previous pointer for unload `[verified-by-code]`:

- **`ProcessUtility_hook = gtt_ProcessUtility`** (`pgtt.c:298-299`) — intercepts DDL
  (`CREATE`/`DROP`/`ALTER`/`RENAME`/`COMMENT`/`CREATE INDEX`) and `SET search_path`.
  This is where a GTT template is manufactured and the original statement is
  swallowed (`gtt_check_command` returns `true` → the real command is never run,
  `pgtt.c:353-357,996`) `[verified-by-code]`.
- **`post_parse_analyze_hook = gtt_post_parse_analyze`** (`pgtt.c:295-296`) — the
  rerouting hook: rewrites the first range-table entry's relid from the persistent
  template to the per-session temp instance, lazily creating that instance on first
  touch (`pgtt.c:1865-1981`) `[verified-by-code]`.
- **`ExecutorStart_hook = gtt_ExecutorStart`** (`pgtt.c:293-294`) — a second,
  belt-and-braces creation trigger: for INSERT/UPDATE/DELETE/SELECT it calls
  `gtt_table_exists`, which creates the per-session temp table if the query
  references a registered GTT (`pgtt.c:999-1115`) `[verified-by-code]`.
- **`on_proc_exit(&exitHook, …)`** (`pgtt.c:302`) — a near-noop exit hook that only
  `elog`s (`pgtt.c:322-326`) `[verified-by-code]`.
- One GUC, `pgtt.enabled` (`PGC_USERSET`, default true), a per-session master switch
  checked at the top of every hook (`pgtt.c:266-277`) `[verified-by-code]`.

Load-time policy is itself a divergence: `_PG_init` **refuses**
`shared_preload_libraries` with a `FATAL` and directs the user to
`session_preload_libraries` instead (`pgtt.c:254-260`) `[verified-by-code]`,
because the GTT cache is per-database/per-session state, not shared memory. The
control file is `relocatable = false`, `schema = 'pgtt_schema'` (`pgtt.control:4-5`)
`[verified-by-code]`. Cross-ref `.claude/skills/bgworker-and-extensions/SKILL.md`
(hook installation on `_PG_init`).

## Where it diverges from core idioms

### 1. The backing mechanism: a persistent UNLOGGED "template" + a lazily-created `pg_temp` instance (LIKE-cloned)

This is the load-bearing divergence. When the `ProcessUtility_hook` sees a
`CREATE … TEMPORARY TABLE` carrying the `GLOBAL` marker, it does **not** create a
temp table. It extracts the column-definition substring between the first `(` and
last `)` of the raw query string (`pgtt.c:662-685`) and, via SPI, runs
`CREATE UNLOGGED TABLE pgtt_schema.<name> (<code>)` (`gtt_create_table_statement`,
`pgtt.c:1214-1218`) — a **permanent, crash-truncated** table that serves as the
shared *template*. It then registers the table and sets `work_completed = true` so
the original `CREATE` is discarded (`pgtt.c:690-700`) `[verified-by-code]`.

The per-session **data** table is created lazily on first access.
`create_temporary_table_internal` (`pgtt.c:1622-1860`) builds a `CreateStmt` in C
with a `TableLikeClause` cloning the template
(`CREATE_TABLE_LIKE_DEFAULTS|INDEXES|CONSTRAINTS|IDENTITY|GENERATED|COMMENTS`,
`pgtt.c:1673-1683`), targets `pg_temp` with `relpersistence = RELPERSISTENCE_TEMP`
(`pgtt.c:1668,1689`), runs it through `transformCreateStmt` + `DefineRelation`
directly (not SPI, `pgtt.c:1707-1739`), then hand-drives `NewRelationCreateToastTable`,
`DefineIndex`, and `expandTableLikeClause` for the sub-statements
(`pgtt.c:1756-1811`) `[verified-by-code]`. So one logical "GTT" is really **two
relations**: a persistent UNLOGGED template (definition-of-record) and a real core
temp table (data-of-record) — the exact inversion core's single `TEMP TABLE`
collapses into one relation.

### 2. Query rerouting by relid substitution in `post_parse_analyze`

Core would resolve `SELECT … FROM my_gtt` to a fixed relation OID. pgtt lets the
parser bind to the **template** OID, then swaps it out post-analysis:
`gtt_post_parse_analyze` opens the first RTE's relation, looks it up by name in the
GTT hash, ensures the per-session instance exists, and **overwrites
`rte->relid = gtt.temp_relid`** (`pgtt.c:1952-1965`) `[verified-by-code]`. On PG ≥
16 it also patches the parallel `rteperminfos` entry's relid
(`pgtt.c:1954-1958`) and re-acquires the lock on the new relid while releasing the
template's (`pgtt.c:1959-1963`) `[verified-by-code]`. To make even schema-qualified
access (`SELECT … FROM pgtt_schema.my_gtt`) reroute, `force_pgtt_namespace` rewrites
the session `search_path` so `pg_temp` shadows the template
(`pgtt.c:2009-2067`; behavior documented `README.md:303-370`) `[verified-by-code]`.
Rewriting a bound relid out from under the planner is precisely what core's
relcache/dependency machinery is built to prevent — pgtt does it every query.

### 3. A shadow catalog table paralleling `pg_class` — not a `pg_class` extension

GTT definitions live in a plain user table, `pgtt_schema.pg_global_temp_tables`
(`relid, nspname, relname, preserved, code`, `sql/pgtt--4.5.0.sql:13-21`)
`[verified-by-code]`. It is populated by the SPI `INSERT`s in the create paths
(`pgtt.c:1242-1249,2202-2209`), scanned with `simple_heap_delete` on DROP
(`pgtt.c:1277-1313`), and `pg_extension_config_dump`'d so `pg_dump` carries it
(`sql/pgtt--4.5.0.sql:24`) `[verified-by-code]`. At session start
`gtt_load_global_temporary_tables` table-scans it into a **backend-local `HTAB`**
(`GttHashTable`, keyed by relname, allocated in `CacheMemoryContext`,
`pgtt.c:1469-1489,1549-1620`) `[verified-by-code]`. This is the pg_tle /
temporal_tables shadow-catalog pattern: durable feature metadata kept in a
user-table catalog that parallels `pg_class` rather than extending it. Note: unlike
some GTT tools, pgtt ships **no** `get_global_temporary_tables()` SRF — the shadow
catalog is queried as an ordinary table (verified: no such function in the install
SQL or C) `[verified-by-code]`.

### 4. `ON COMMIT` semantics are delegated to core, not enforced by pgtt

pgtt registers **no** `RegisterXactCallback` and runs no commit-time row deletion
of its own (verified: no `RegisterXactCallback` in `pgtt.c`) `[verified-by-code]`.
Instead it threads the requested lifetime into the *per-session core temp table*:
`create_temporary_table_internal` sets `createStmt->oncommit =
ONCOMMIT_PRESERVE_ROWS` or `ONCOMMIT_DELETE_ROWS` from the stored `preserved` flag
(`pgtt.c:1698-1701`) `[verified-by-code]`, so **core's own temp-table commit
machinery** performs the `ON COMMIT DELETE ROWS` truncation. The `preserved` flag
is captured from the original DDL's `onCommit` field at intercept time
(`pgtt.c:506-507,633-634`) and persisted in the shadow catalog. `ON COMMIT DROP` is
explicitly rejected as incoherent for a GTT (`pgtt.c:516-519,643-646`)
`[verified-by-code]`. This is the elegant reuse point: the hardest semantic
(transaction-scoped row lifetime) is *not* re-implemented — it rides core.

### 5. Feature detection reuses the parsed-but-ignored `GLOBAL` keyword, matched by regex on raw SQL

Core's grammar accepts `GLOBAL`/`LOCAL` before `TEMPORARY` and ignores it (a
deprecation), so `CREATE GLOBAL TEMPORARY TABLE` reaches the hook as an ordinary
`CreateStmt` with `relpersistence = RELPERSISTENCE_TEMP` `[inferred]`. pgtt
distinguishes a GTT from a plain temp table by **regex-matching the raw query
string** for the `GLOBAL` token (or a `/*GLOBAL*/` comment):
`^\s*CREATE\s+(?:/\*\s*)?GLOBAL(?:\s*\*/)?`, executed with `RE_compile_and_execute`
(`pgtt.c:156,490-500,594-603`) `[verified-by-code]`. Parsing intent back out of the
already-parsed query text — because the AST threw the keyword away — is a
divergence forced by working outside the grammar (`README.md:392-399`)
`[from-README]`.

### 6. The libpq linkage is vestigial — backing DDL runs in-process via SPI

The `Makefile` links libpq (`SHLIB_LINK = $(libpq)`, `PG_LDFLAGS = … -lpq`,
`PG_CPPFLAGS = -I$(libpq_srcdir)`, `Makefile:8-13`) `[verified-by-code]`, which
would suggest the extension dials its own server for autonomous DDL. It does **not**:
`pgtt.c` makes **zero** client-libpq calls (`PQconnect`/`PQexec` count: 0; the only
`libpq/*` include is the *backend* header `libpq/pqformat.h`, and `pq_`/`PQ` symbol
count in the file is 0) `[verified-by-code]`. Every backing operation runs inside
the current backend: template creation and shadow-catalog writes go through
`SPI_connect`/`SPI_exec` (`pgtt.c:1209-1268`), and the per-session instance goes
through `DefineRelation` directly (`pgtt.c:1737`). So the libpq link flags are
dead weight carried by the build, not an autonomous-connection design — worth
flagging precisely because the linkage *looks* like the unusual "extension calls
its own server" pattern but isn't.

## Notable design decisions (cited)

- **The original DDL is swallowed, not augmented.** `gtt_check_command` returning
  `true` makes `gtt_ProcessUtility` `return` before `standard_ProcessUtility`, so
  the user's `CREATE GLOBAL TEMPORARY TABLE` never executes as written — pgtt's SPI
  `CREATE UNLOGGED TABLE` replaces it wholesale (`pgtt.c:353-357,388,996`)
  `[verified-by-code]`.
- **Oracle-mimicking restrictions enforced at the hook.** Foreign keys on a GTT are
  rejected both at `CREATE` (regex for `FOREIGN KEY`, `pgtt.c:157,605-616`) and at
  `ALTER TABLE … ADD CONSTRAINT` (`pgtt.c:925-941`); partitioning is rejected
  (`pgtt.c:625-626`) `[verified-by-code]`.
- **"In use" GTTs are frozen against DDL.** Once a session has materialized the
  temp instance (`gtt.created`), `DROP`/`RENAME`/`COMMENT`/non-concurrent `CREATE
  INDEX` on the GTT error out ("can not drop/rename … a GTT that is in use",
  `pgtt.c:803-804,852-853,900-901,984-985`) `[verified-by-code]`.
- **`SET search_path` is rewritten, not just overridden.** The utility hook appends
  `pgtt_schema` to a user's `SET search_path TO …` arg list so the template schema
  stays reachable (`pgtt.c:408-455`) `[verified-by-code]`.
- **Post-rollback self-healing.** `gtt_post_parse_analyze` detects a cached instance
  whose `temp_relid` no longer exists in syscache (after an error/rollback dropped
  it) and resets `created=false` to force recreation (`pgtt.c:1925-1932`)
  `[verified-by-code]`.
- **Skips parallel workers throughout** (`NOT_IN_PARALLEL_WORKER`,
  `ParallelWorkerNumber < 0`, `pgtt.c:86,248-249,334`) `[verified-by-code]`.
- **Vendors `get_extension_schema` from core** for PG < 16 (`pgtt.c:1388-1437`)
  `[verified-by-code]` — a copy-paste of a core static, the standard "reach a
  backend internal an extension isn't given" tax.

## Links into corpus

- `[[knowledge/ideologies/temporal_tables]]` — the closest sibling: a core SQL
  feature (SQL:2011 system-versioning) reconstructed from userspace via hooks/
  triggers + a shadow history table + SPI, staying entirely in public API. Direct
  contrast: temporal_tables rides the trigger contract and `RegisterXactCallback`;
  pgtt rides three query-path hooks and *delegates* transaction semantics to core's
  temp-table `ON COMMIT` machinery.
- `[[knowledge/ideologies/pg_tle]]` — shadow-catalog + `ProcessUtility_hook`
  rerouting of core DDL, the same "user table paralleling a system catalog" stance.
- `[[knowledge/ideologies/pipelinedb]]` — `post_parse_analyze`/planner-hook feature
  synthesis; pgtt's relid-rewriting in `post_parse_analyze` is the same class of
  move.
- `[[knowledge/idioms/fmgr]]` — the extension entry points; pgtt is unusual in
  exposing *no* SQL-callable C functions, only hooks.
- `[[knowledge/idioms/bgworker-and-extensions]]` — hook installation on `_PG_init`,
  saving/chaining previous hook pointers, the `session_preload_libraries` vs
  `shared_preload_libraries` load-timing choice.
- `.claude/skills/bgworker-and-extensions/SKILL.md`,
  `.claude/skills/extension-development/SKILL.md`,
  `.claude/skills/fmgr-and-spi/SKILL.md` — the SPI + `DefineRelation` backing path.

## Anthropology takeaway

pgtt is the corpus's cleanest example of a *new table kind* synthesized outside the
grammar and catalog: it reuses core's parsed-but-discarded `GLOBAL` keyword,
manufactures a persistent UNLOGGED "template" to hold the shared definition, clones
a real `pg_temp` table per session on first access, and rewrites the bound relid in
`post_parse_analyze` so every query silently reroutes to the private instance. The
two sharpest divergences are (a) the **template-plus-instance split** — one logical
GTT is two real relations, the persistent one being definition-of-record and the
temp one data-of-record — and (b) the **delegation of `ON COMMIT` semantics to
core** by simply stamping the per-session temp table's `oncommit` field, so the
hardest part of the feature is reused rather than reimplemented. The cautionary
flags for a `knowledge/issues` note: relid rewriting under the planner, a
`search_path` that the extension silently edits, and a libpq link dependency that
the code never actually uses.

## Sources

Fetched 2026-07-06 (branch `master`, `default_version = '4.5.0'`):

- `https://raw.githubusercontent.com/darold/pgtt/master/pgtt.c` @ 2026-07-06 → HTTP
  200 (64510 bytes, 2240 lines) — THE core: `_PG_init` hook stack,
  `gtt_ProcessUtility`/`gtt_check_command` DDL intercept, `gtt_post_parse_analyze`
  relid rerouting, `gtt_ExecutorStart`, `gtt_create_table_statement`/
  `gtt_create_table_as` (SPI template creation), `create_temporary_table_internal`
  (`DefineRelation` per-session clone), the `GttHashTable` cache,
  `force_pgtt_namespace`. Deep-read.
- `https://raw.githubusercontent.com/darold/pgtt/master/README.md` @ 2026-07-06 →
  HTTP 200 (18492 bytes, 557 lines) — semantics, `ON COMMIT`/`LOGGED` clauses, the
  "How the extension really works" architecture section. Identical byte-for-byte to
  `pgtt.md` (the `DOCS` design doc).
- `https://raw.githubusercontent.com/darold/pgtt/master/pgtt.md` @ 2026-07-06 → HTTP
  200 (18492 bytes, 557 lines) — same content as README.md (the design doc).
- `https://raw.githubusercontent.com/darold/pgtt/master/pgtt.control` @ 2026-07-06 →
  HTTP 200 (177 bytes) — `default_version = '4.5.0'`, `schema = 'pgtt_schema'`,
  `relocatable = false`.
- `https://raw.githubusercontent.com/darold/pgtt/master/Makefile` @ 2026-07-06 →
  HTTP 200 (930 bytes) — `MODULES = pgtt`, `SHLIB_LINK = $(libpq)`, `-lpq`,
  `-I$(libpq_srcdir)`, `DATA = updates/*--*.sql sql/*.sql`, regress test list.
- `https://raw.githubusercontent.com/darold/pgtt/master/sql/pgtt--4.5.0.sql` @
  2026-07-06 → HTTP 200 (current base install: schema grants +
  `pg_global_temp_tables` shadow catalog + `pg_extension_config_dump`).
- `https://raw.githubusercontent.com/darold/pgtt/master/sql/pgtt--2.0.0.sql` @
  2026-07-06 → HTTP 200 (27 lines; older base install that also `CREATE SCHEMA`s —
  same shadow-catalog shape).
- `https://raw.githubusercontent.com/darold/pgtt/master/sql/pgtt--3.0.0.sql`,
  `updates/pgtt--2.0.0--2.1.0.sql` @ 2026-07-06 → HTTP 200 each (probed to confirm
  install/upgrade layout; no SQL-callable functions or SRF defined).

All cites into `pgtt.c` — the hook stack, the `ProcessUtility` DDL intercept, the
SPI template creation, the `DefineRelation` per-session clone, the relid rewriting,
the shadow-catalog scan, and the (unused) libpq linkage — are `[verified-by-code]`
against the fetched file. The Oracle-migration motivation, the `ON COMMIT`/`LOGGED`
clause surface, and the first-access rerouting narrative are `[from-README]` and
cross-checked against the matching code paths. The claim that core's grammar parses
and ignores `GLOBAL` is `[inferred]` (not cited into `source/`).
