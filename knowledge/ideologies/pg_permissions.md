# pg_permissions — an "extension" that is nothing but catalog views over `has_*_privilege` builtins, plus a declarative desired-state table and an INSTEAD OF trigger that turns view UPDATEs into GRANT/REVOKE

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `cybertec-postgresql/pg_permissions` @ branch `master`. All `file:line`
> cites below point into that repo (not `source/`), since this doc characterizes
> an *external* extension's divergence from core idioms. The shipped payload is
> a set of `pg_permissions--*.sql` install scripts plus a `.control` file — no C.
> Cites verified against files fetched 2026-06-28 (see Sources footer). Read
> alongside `[[knowledge/ideologies/index_advisor]]` (the corpus's other
> "ships ONLY SQL, no `.so`" extension — a single PL/pgSQL function over `EXPLAIN`)
> and `[[knowledge/ideologies/zson]]`'s `pg_extension_config_dump` use, which
> pg_permissions also leans on for its desired-state table.

## Domain & purpose

pg_permissions "allows you to review object permissions on a PostgreSQL
database" (`README.md:4`) `[from-README]`. It does two things: (1) it exposes a
family of views (`table_permissions`, `view_permissions`, `column_permissions`,
`sequence_permissions`, `function_permissions`, `schema_permissions`,
`database_permissions`, and `all_permissions` as their `UNION ALL`) that show,
for every non-superuser role × object × applicable privilege, whether that
privilege is currently `granted` (`pg_permissions--1.3.sql:34-185`)
`[verified-by-code]`; and (2) it lets you declare a *desired* permission state
in a `permission_target` table and diff reality against it with
`permission_diffs()` (`pg_permissions--1.3.sql:331-451`, `README.md:115-134`)
`[verified-by-code]`. It is an auditing/compliance layer for ACLs, written
entirely in SQL and PL/pgSQL. The reason to document it: it is the *minimal end*
of the extension-divergence spectrum — it adds no type that matters at the
storage layer, no operator, no AM, no C, no hook. Its "divergence" is almost
entirely in how it *reads core's permission system back out* (unrolling ACLs via
the `has_*_privilege` builtins rather than parsing `aclitem[]`) and in one
genuinely surprising write path (updatable views that execute DDL).

## How it hooks into PG

It doesn't hook into anything. The package is PGXS with `DATA =
pg_permissions--*.sql`, `DOCS`, and `REGRESS = sample`, and **no `MODULE_big`,
no `OBJS`** (`Makefile:1-9`) `[verified-by-code]`. The control file declares
`relocatable = false`, `superuser = false` (`pg_permissions.control:3-4`)
`[verified-by-code]` — i.e. it installs as an ordinary, non-superuser
extension. There is no `_PG_init`, no `.so`, no shared library to `LOAD`, no
background worker, no GUC. Everything the extension does is built from:

- **Core privilege-inquiry builtins** — `has_table_privilege`,
  `has_column_privilege`, `has_sequence_privilege`, `has_function_privilege`,
  `has_schema_privilege`, `has_database_privilege`, each called with
  `(role_oid, object_oid, privilege_text)` (`pg_permissions--1.3.sql:41, 87-88,
  108, 126, 142, 161`) `[verified-by-code]`. These are the only "engine" the
  views use; pg_permissions never touches `pg_class.relacl` /
  `aclexplode` / raw `aclitem[]` at all — it asks core the boolean question
  per (role, object, privilege) triple instead.
- **The system catalogs** as the object/role enumeration: `pg_class`,
  `pg_attribute`, `pg_proc`, `pg_namespace`, `pg_database`, `pg_roles`
  (`pg_permissions--1.3.sql:42-43, 89-91, 127-128, 143-144, 162-163`)
  `[verified-by-code]`.
- **An ENUM type pair** (`perm_type`, `obj_type`) that is pure labeling —
  `CREATE TYPE perm_type AS ENUM ('SELECT', …, 'MAINTAIN')` and `obj_type AS
  ENUM ('TABLE', …, 'DATABASE')` (`pg_permissions--1.3.sql:6-30`)
  `[verified-by-code]`. These are presentation/constraint enums, not storage
  types with custom I/O.

Cross-ref `[[knowledge/idioms/catalog-conventions]]` (the catalogs it reads),
`.claude/skills/extension-development/SKILL.md` (the `DATA`-only PGXS surface it
minimally uses).

## Where it diverges from core idioms

### 1. The "extension" is a pure catalog-introspection layer — zero new runtime behavior

Like `[[knowledge/ideologies/index_advisor]]`, pg_permissions ships **no
compiled code**: `Makefile:1-9` lists only `EXTENSION` + `DATA` + `DOCS` +
`REGRESS`, no `MODULE_big`/`OBJS` `[verified-by-code]`. It contributes no type
that changes on-disk layout, no operator, no opclass, no access method, no
planner/executor hook. The two ENUMs it does define
(`pg_permissions--1.3.sql:6-30`) exist only to constrain the desired-state
table and label view columns. This makes it the corpus's clearest case of an
extension as a *reporting view-pack over the catalog* — the inverse of the heavy
C extensions (postgis, timescaledb, citus) that add types, AMs, and hooks. Its
entire value is the SQL it ships, not any code that runs in the backend address
space.

### 2. ACLs are unrolled by per-triple `has_*_privilege` calls, not by `aclexplode`

Core stores grants as `aclitem[]` arrays on each object and offers two
read paths: structural (`aclexplode(acl)` → `(grantor, grantee, privilege_type,
is_grantable)` rows) and predicate (`has_table_privilege(role, obj, priv)` →
bool). pg_permissions chooses the predicate path *exhaustively*: it builds a
full cross-product of `pg_roles` × objects × the fixed privilege list for each
object kind, then evaluates `has_*_privilege` once per cell
(`pg_permissions--1.3.sql:42-49, 65-72, 89-92, 109-111, 127-128, 143-145,
162-164`) `[verified-by-code]`. The privilege list per object kind is hard-coded
as a `CROSS JOIN unnest(ARRAY[...])` or `VALUES (...)` — e.g. tables get
`SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER` (plus `MAINTAIN` on
PG ≥ 17) (`pg_permissions--1.3.sql:44-49`), columns get
`SELECT,INSERT,UPDATE,REFERENCES` (`:92`), sequences
`SELECT,USAGE,UPDATE` (`:111`), schemas `USAGE,CREATE` (`:145`), databases
`CREATE,CONNECT,TEMPORARY` (`:164`). Consequences of this choice:

- **It respects inherited/role-membership and default grants** that
  `has_*_privilege` resolves but a raw `aclexplode` would not — a deliberate
  upside: the view shows *effective* privilege, including `PUBLIC` and role
  inheritance, not just the literal ACL entries `[inferred]`.
- **It is O(roles × objects × privileges)** — a cross product evaluated by a
  function call per cell. On a database with many roles and relations this is a
  large scan; that cost is the price of using the predicate API instead of
  exploding the ACL array once per object `[inferred]`.
- The version-gated `MAINTAIN` privilege is handled by branching on
  `current_setting('server_version_num')::integer < 170000` inside the view
  definition (`pg_permissions--1.3.sql:45-48, 68-71`) `[verified-by-code]` — a
  runtime version check baked into a view, because the privilege set is
  PG-version-dependent.

### 3. A declarative desired-state table + a diff function — config-management semantics in SQL

`permission_target (id, role_name, permissions perm_type[], object_type,
schema_name, object_name, column_name)` (`pg_permissions--1.3.sql:331-358`)
`[verified-by-code]` is the declared-intent store: each row says "role R should
have privileges P on objects of this type matching (schema, object, column),
where NULL means *all*" (`README.md:115-123`) `[from-README]`. A CHECK
constraint (`permission_target_valid`) enforces, per `object_type`, that the
right columns are NULL and that `permissions` is a subset of the privileges
legal for that object kind (`pg_permissions--1.3.sql:339-357`)
`[verified-by-code]` — e.g. a `DATABASE` row must have NULL schema/object/column
and `permissions ⊆ {CONNECT,CREATE,TEMPORARY}`. `permission_diffs()` then
double-loops: for each `(target row × unnested privilege)` it scans
`all_permissions` for matching object permissions and emits two finding kinds —
`missing = TRUE` (declared but `NOT granted`) and `missing = FALSE` (granted but
not covered by any target rule, an *extra* grant) (`pg_permissions--1.3.sql:408-450`,
`README.md:127-134`) `[verified-by-code]`. This is essentially a tiny
declarative-compliance engine (the "desired state ⇒ diff" idiom of Terraform /
Ansible) implemented in PL/pgSQL over catalog views. The diff is materialized
into an `ON COMMIT DROP` temp table `findings` and returned `DISTINCT`
(`pg_permissions--1.3.sql:397-405, 450`) `[verified-by-code]`.

### 4. Updatable views whose UPDATE executes GRANT/REVOKE DDL via an INSTEAD OF trigger

The sharpest behavioral divergence: every `*_permissions` view carries an
`INSTEAD OF UPDATE` trigger bound to `permissions_trigger_func()`
(`pg_permissions--1.3.sql:189-327`) `[verified-by-code]`. Updating the boolean
`granted` column of a view row does **not** update any storage — it *synthesizes
and `EXECUTE`s a GRANT or REVOKE statement*: setting `granted` from FALSE→TRUE
emits `GRANT <perm> ON <obj> TO <role>`, TRUE→FALSE emits the matching `REVOKE`
(`pg_permissions--1.3.sql:213-292`, `README.md:109-110`) `[verified-by-code]`.
The trigger refuses any change to a non-`granted` column ("Only the 'granted'
column may be updated", `:204`) and dispatches on `OLD.object_type` to build the
right DDL spelling per kind (TABLE/VIEW/COLUMN/SEQUENCE/FUNCTION/SCHEMA/DATABASE,
`:213-290`). This makes a SELECTable *report* also a *write surface for
privileges* — an UPDATE that is really a side-effecting DDL command, which is
nowhere in core's mental model of a view. Note the DDL is assembled with
`format('GRANT %s ON %s.%s TO %s', …)` using `%s` (raw, not `%I`) for the
permission, schema, object, and role names (`pg_permissions--1.3.sql:217-219,
229-231, 243-245, 255-257, 267-269, 281-282`) `[verified-by-code]` — the
identifiers come from the catalog views (so they are real object names) but they
are interpolated unquoted, so an object whose name needs quoting (mixed case,
reserved word) would produce malformed or mis-targeted DDL `[inferred]`.

### 5. Role visibility is filtered by `NOT rolsuper`, so superusers are invisible by design

Every view carries `AND NOT r.rolsuper` (`pg_permissions--1.3.sql:53, 76, 97,
115, 131, 148, 166`) `[verified-by-code]`, documented as "Superusers are not
shown in the views, as they automatically have all permissions"
(`README.md:112-113`) `[from-README]`. This is a deliberate simplification:
because `has_*_privilege` would return TRUE for every cell of a superuser, the
extension drops superusers entirely rather than report a wall of TRUEs. The
practical effect is that the audit surface is *only* the non-superuser roles —
correct for its intent, but it means the views are not a complete picture of who
can touch an object (a superuser can, and won't appear) `[inferred]`.

### 6. Grants the *world* read access to the views and write access to the target table

Each view is `GRANT SELECT … TO PUBLIC` (`pg_permissions--1.3.sql:55, 78, 99,
117, 133, 150, 168, 185`), and `permission_target` itself is `GRANT SELECT,
INSERT, UPDATE, DELETE … TO PUBLIC` along with `USAGE` on its sequence
(`pg_permissions--1.3.sql:364-365`) `[verified-by-code]`. So any role can read
the whole permission map and edit the desired-state table. Because the views run
with the *querying* role's privileges (no `SECURITY DEFINER` on the trigger
function, `:189-192`), the GRANT/REVOKE a view-UPDATE emits is executed as the
caller — a non-privileged caller's REVOKE simply fails at DDL time rather than
escalating `[inferred]`. The one function that pins context is
`permission_diffs()`, declared `SET search_path FROM CURRENT`
(`pg_permissions--1.3.sql:380`) `[verified-by-code]`, so its unqualified
references to `permission_target` / `all_permissions` resolve against the
install-time search_path rather than the caller's — a defensive touch the
trigger function does *not* share `[inferred]`.

## Notable design decisions with cites

- **`function_permissions` strips the schema-qualified prefix off
  `regprocedure` text with a regex** to recover a bare function signature as
  `object_name`: `regexp_replace(f.oid::regprocedure::text, '^((("[^"]*")|([^"][^.]*))\.)?', '')`
  (`pg_permissions--1.3.sql:123`) `[verified-by-code]`. Functions are the one
  object kind whose name must carry its argument types, so it reuses
  `regprocedure`'s I/O and then trims the schema prefix textually rather than
  building the signature itself.
- **Schema/relation filtering excludes `information_schema` and `pg_%`**
  (`pg_permissions--1.3.sql:50-51, 93-94, 112-113, 129-130, 146-147`)
  `[verified-by-code]`. The 1.4 upgrade fixes these to escape the underscore —
  `NOT LIKE 'pg\_%'` instead of `'pg_%'` (`pg_permissions--1.3--1.4.sql`,
  every view) `[verified-by-code]` — because unescaped `_` is a `LIKE`
  wildcard that would also exclude any user schema like `pgfoo`. The whole 1.4
  upgrade is just this escaping fix re-`CREATE OR REPLACE`d across the views.
- **`permission_target` data is marked for dump** via
  `pg_catalog.pg_extension_config_dump('permission_target', '')` and the same
  for its sequence (`pg_permissions--1.3.sql:367-368`) `[verified-by-code]` —
  the correct catalog-convention touch (cf. `[[knowledge/ideologies/zson]]`'s
  `zson_dict`): the desired-state rows are user data the extension owns, so
  `pg_dump` must emit them.
- **The 1.2→1.3 jump is non-upgradable** because adding the `MAINTAIN`
  enumeration value to `perm_type` cannot be done transactionally in an
  extension upgrade script; the README tells users to drop and recreate,
  dumping `permission_target` first (`README.md:157-162`) `[from-README]`.
  This is the classic "you cannot `ALTER TYPE … ADD VALUE` and use it in the
  same transaction" ENUM limitation surfacing as an extension-versioning wall.
- **The diff loops in PL/pgSQL row-by-row** rather than expressing the
  desired-vs-actual comparison as a single set query
  (`pg_permissions--1.3.sql:408-448`) `[verified-by-code]`: a nested
  `FOR … LOOP` over targets, then over matching `all_permissions` rows, with a
  correlated `NOT EXISTS` against `permission_target` to decide whether an
  observed grant is "extra." Readable, but O(targets × permissions) procedural
  rather than a join — a deliberate clarity-over-speed choice for an
  audit-time function.

## Links into corpus

- `[[knowledge/ideologies/index_advisor]]` — the sibling "ships ONLY SQL, no
  `.so`" extension. index_advisor is one PL/pgSQL function over `EXPLAIN` +
  hypopg; pg_permissions is a view-pack over `has_*_privilege` + a diff
  function. Both are PGXS `DATA`-only packages with no `MODULE_big`, both prove
  a "PostgreSQL extension" can contain zero compiled code, and both turn a core
  read-only surface (EXPLAIN JSON / privilege predicates) into a programmatic
  API.
- `[[knowledge/ideologies/zson]]` — shares the `pg_extension_config_dump`
  idiom for dumping extension-owned table *data* (zson's `zson_dict`,
  pg_permissions' `permission_target`).
- `[[knowledge/idioms/catalog-conventions]]` — the catalogs pg_permissions
  reads (`pg_class`, `pg_attribute`, `pg_proc`, `pg_namespace`, `pg_database`,
  `pg_roles`) and the `pg_extension_config_dump` data-dump convention.
- `.claude/skills/extension-development/SKILL.md` — PGXS `DATA`-only packaging,
  `.control` `relocatable = false` / `superuser = false`, no `MODULE_big`.

## Sources

Fetched 2026-06-28 via `raw.githubusercontent.com/cybertec-postgresql/pg_permissions/master`:

- `README.md` @ 2026-06-28 → 200 (cookbook, desired-state/diff narrative,
  superuser-invisibility note, non-upgradable-1.2→1.3 note).
- `pg_permissions.control` @ 2026-06-28 → 200 (`default_version = '1.4'`,
  `relocatable = false`, `superuser = false`).
- `pg_permissions--1.3.sql` @ 2026-06-28 → 200 (**the substantive install
  script**, deep-read — ENUMs, the seven base views + `all_permissions`,
  the INSTEAD OF UPDATE trigger that emits GRANT/REVOKE, `permission_target`
  + its CHECK constraint, `permission_diffs()`).
- `pg_permissions--1.3--1.4.sql` @ 2026-06-28 → 200 (the entire 1.4 upgrade:
  re-`CREATE OR REPLACE` of the views to escape `LIKE 'pg\_%'`).
- `Makefile` @ 2026-06-28 → 200 (`DATA = pg_permissions--*.sql`, `REGRESS =
  sample`, no `MODULE_big`/`OBJS` — confirms zero C).

Line cites point into `pg_permissions--1.3.sql` because the shipped
`default_version` 1.4 differs from 1.3 only by the `pg\_%` escaping fix (verified
against `pg_permissions--1.3--1.4.sql`); all view/trigger/table/function bodies
cited are identical in 1.4. Manifest gaps: `pg_permissions--1.0.sql`,
`--1.1.sql`, `--1.2.sql`, the `--1.0--1.1`/`--1.1--1.2` upgrades, `CHANGELOG`,
`sql/sample.sql`, and `expected/sample.out` were not fetched; the 1.3 install +
1.4 upgrade are self-contained for the divergence story above.
