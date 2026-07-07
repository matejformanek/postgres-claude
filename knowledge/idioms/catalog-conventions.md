# Catalog conventions (bki, OIDs, syscache)

The system catalogs are PostgreSQL's metaprogramming surface: every relation,
type, function, operator class etc. is a row in some `pg_*` table that the
backend itself queries. Bootstrapping these tables (before any backend can
run SQL) is the job of the **BKI** mechanism. Touching catalogs has rules
that don't apply to ordinary tables.

## 1. The BKI mechanism: from `.h` + `.dat` to `postgres.bki`

The pipeline:

```
src/include/catalog/pg_X.h        (schema: CATALOG() struct + macros)
src/include/catalog/pg_X.dat      (initial rows, Perl-ish hash literals)
            |
            v   genbki.pl  (uses Catalog.pm to parse both)
            |
src/backend/catalog/postgres.bki  (compiled-in; consumed by bootstrap.c)
src/include/catalog/pg_X_d.h      (#defines + Anum_*/Natts_* + OID macros)
src/include/catalog/syscache_ids.h, syscache_info.h, system_fk_info.h ...
```

### The header (`pg_X.h`)

A header declares the C struct that *is* the on-disk tuple layout, wrapped in
genbki marker macros that the C compiler sees as no-ops but `genbki.pl`
parses as schema directives. Example from `pg_class.h:34`
[verified-by-code](source/src/include/catalog/pg_class.h:34):

```c
CATALOG(pg_class,1259,RelationRelationId) BKI_BOOTSTRAP
        BKI_ROWTYPE_OID(83,RelationRelation_Rowtype_Id) BKI_SCHEMA_MACRO
{
    Oid       oid;
    NameData  relname;
    Oid       relnamespace BKI_DEFAULT(pg_catalog) BKI_LOOKUP(pg_namespace);
    ...
};
```

What each macro means (defined in `genbki.h`)
[verified-by-code](source/src/include/catalog/genbki.h:42-66):

- `CATALOG(name, oid, oidmacro)` — declares the catalog. The `oid` is the
  pinned OID of the `pg_class` *row* for this catalog (1259 = pg_class
  itself, self-referential). `oidmacro` is the C symbol emitted for it.
- `BKI_BOOTSTRAP` — this catalog must exist before the bootstrap parser
  can run normal `CREATE TABLE`; it gets a hand-built tuple layout.
- `BKI_SHARED_RELATION` — lives in a per-cluster (not per-database) file.
- `BKI_ROWTYPE_OID(oid, macro)` — pins the composite type OID for the
  catalog's implicit rowtype.
- `BKI_DEFAULT(val)` — default value used for any row in the `.dat` that
  omits this column.
- `BKI_LOOKUP(catalog)` / `BKI_LOOKUP_OPT(catalog)` — column holds an OID
  reference to another catalog; `genbki.pl` resolves symbolic names
  (e.g. `'pg_catalog'`) to OIDs in the `.dat` and uses it to derive
  foreign-key info for `pg_get_catalog_foreign_keys()`
  [verified-by-code](source/src/include/catalog/genbki.h:57-66,131-140).
- `BKI_FORCE_NULL` / `BKI_FORCE_NOT_NULL` — null-ness overrides for the
  initial bootstrap rows.
- `#ifdef CATALOG_VARLEN ... #endif` — hides varlena fields from the C
  struct (you can't access them via `Form_pg_X->field`); they're still
  part of the schema. The bootstrap code treats them as nullable
  [verified-by-code](source/src/include/catalog/genbki.h:148-156),
  [verified-by-code](source/src/include/catalog/pg_proc.h:99-130).
- `#ifdef EXPOSE_TO_CLIENT_CODE` — copy this block verbatim into the
  generated `_d.h` so frontend code can use it
  [verified-by-code](source/src/include/catalog/genbki.h:158-166).

Same header also carries declarations that aren't part of the struct:

- `DECLARE_TOAST(name, toastoid, indexoid)` — pin a TOAST table's OIDs
  (required because shared catalogs need stable OIDs)
  [verified-by-code](source/src/include/catalog/genbki.h:68-83).
- `DECLARE_UNIQUE_INDEX_PKEY(name, oid, oidmacro, tbl, decl)` /
  `DECLARE_UNIQUE_INDEX` / `DECLARE_INDEX` — emit a `DefineIndex` at
  bootstrap [verified-by-code](source/src/include/catalog/genbki.h:85-105).
- `DECLARE_OID_DEFINING_MACRO(name, oid)` — claim an OID that isn't a row
  but should still be globally unique (e.g. operator family OIDs declared
  inline) [verified-by-code](source/src/include/catalog/genbki.h:107-113).
- `DECLARE_FOREIGN_KEY[_OPT]` / `DECLARE_ARRAY_FOREIGN_KEY[_OPT]` —
  documentary FK relationships beyond what `BKI_LOOKUP` infers
  [verified-by-code](source/src/include/catalog/genbki.h:115-140).
- `MAKE_SYSCACHE(name, idxname, nbuckets)` — register a syscache built on
  the given unique index
  [verified-by-code](source/src/include/catalog/genbki.h:142-146).

### The data file (`pg_X.dat`)

A Perl array of hash literals — one per initial row. Example from
`pg_proc.dat:42` [verified-by-code](source/src/include/catalog/pg_proc.dat:42-45):

```perl
{ oid => '1242', descr => 'I/O',
  proname => 'boolin', prorettype => 'bool', proargtypes => 'cstring',
  prosrc => 'boolin' },
```

Notes from `pg_proc.dat:14-38`
[from-comment](source/src/include/catalog/pg_proc.dat:14-38):

- Every entry should have a `descr` comment (becomes a `pg_description` row).
- Columns omitted fall back to `BKI_DEFAULT`.
- Symbolic references (`prorettype => 'bool'`) are resolved against the
  target catalog's `.dat` via `BKI_LOOKUP`.
- `pronargs` is computed at parse time by `AddDefaultValues()` in
  `Catalog.pm`, so you don't write it.
- Order: roughly group new entries near related existing ones, not at random
  [from-comment](source/src/include/catalog/pg_proc.dat:36-38).

Not every catalog has a `.dat`: `pg_attribute` is generated at compile time
by `genbki.pl` from the bootstrap catalogs' `CATALOG()` blocks
[from-comment](source/src/include/catalog/pg_attribute.h:6-8).

### `genbki.pl` orchestration

Top-of-file comment [verified-by-code](source/src/backend/catalog/genbki.pl:1-14):

> Perl script that generates postgres.bki and symbol definition headers from
> specially formatted header files and data files. postgres.bki is used to
> initialize the postgres template database.

Skeleton flow [verified-by-code](source/src/backend/catalog/genbki.pl:53-100):

1. `Catalog::ParseHeader` for every `pg_*.h` — fills `%catalogs`, collects
   index decls, toast decls, syscache decls, FK decls, OID-defining macros.
2. `Catalog::ParseData` for every existing `pg_*.dat` — yields the initial
   tuples; `AddDefaultValues()` fills in missing columns and computed ones
   (e.g. `pronargs`).
3. Cross-references: resolves `BKI_LOOKUP` symbolic names to OIDs by
   indexing the referenced catalog's data by its `oid_lookup` column.
4. Detects duplicate manually-assigned OIDs across all catalogs (project
   policy: globally unique, not just per-catalog
   [from-comment](source/src/include/catalog/duplicate_oids:9-11)).
5. Emits:
   - `postgres.bki` — the bootstrap script (a sequence of `create`,
     `insert`, `declare index`, `declare toast`, `build indices` commands
     parsed by `src/backend/bootstrap/bootparse.y`).
   - `pg_X_d.h` for each catalog — `#define`s for relation OID, rowtype
     OID, every row's named OID, every index OID, `Anum_pg_X_col` and
     `Natts_pg_X` macros, and any `EXPOSE_TO_CLIENT_CODE` block.
   - `syscache_ids.h` / `syscache_info.h` — enum + descriptor table
     populated from `MAKE_SYSCACHE` declarations.
   - `system_fk_info.h` / `system_constraints.sql` — fed by FK macros and
     `BKI_LOOKUP`.

The backend then loads `postgres.bki` at `initdb` time only; running
backends never re-parse it.

## 2. OID rules

Three thresholds, all in `access/transam.h`
[verified-by-code](source/src/include/access/transam.h:195-197):

```c
#define FirstGenbkiObjectId    10000
#define FirstUnpinnedObjectId  12000
#define FirstNormalObjectId    16384
```

- **OID < 10000** — manually assigned in catalog `.h` / `.dat` files. These
  are *pinned* (cannot be dropped, no `pg_depend` entry needed). New patches
  that need a fixed OID land here.
- **10000 ≤ OID < 12000** — assigned by `genbki.pl` to bootstrap-time objects
  that didn't get a manual OID (array types, implicit indexes, etc.). Still
  pinned.
- **12000 ≤ OID < 16384** — bootstrap-created but **unpinned**; user can
  drop them. Boundary controlled by `FirstUnpinnedObjectId`
  [from-comment](source/src/include/access/transam.h:195-197).
- **OID ≥ 16384** — handed out at runtime by the OID counter for
  user-created objects.

### Picking an OID for new code

Use the `unused_oids` script in `src/include/catalog`
[verified-by-code](source/src/include/catalog/unused_oids:1-79):

```
$ cd src/include/catalog && ./unused_oids
... ranges of unused OIDs ...
Patches should use a more-or-less consecutive range of OIDs.
Best practice is to start with a random choice in the range 8000-9999.
Suggested random unused OID: 8473 (15 consecutive OID(s) available ...)
```

Conventions [verified-by-code](source/src/include/catalog/unused_oids:73-78):

- New patches pick a random starting OID in **8000-9999** to minimize
  collisions with other in-flight patches.
- Once committed, an OID becomes permanent.
- Before final commit, the committer typically runs `renumber_oids.pl`
  to move new OIDs down into a tidy low range
  [verified-by-code](source/src/include/catalog/renumber_oids.pl) so the
  development-time 8000-range doesn't fragment the namespace.

### Uniqueness check

`duplicate_oids` script scans every `pg_*.h` and `pg_*.dat` and prints any
OID assigned more than once anywhere
[verified-by-code](source/src/include/catalog/duplicate_oids:1-49). Project
policy is **globally unique**, not just unique-per-catalog
[from-comment](source/src/include/catalog/duplicate_oids:8-11). CI runs
this; you should run it too before submitting.

## 3. `CATALOG_VERSION_NO` (catversion bump)

Defined in `src/include/catalog/catversion.h:60`
[verified-by-code](source/src/include/catalog/catversion.h:60):

```c
#define CATALOG_VERSION_NO  202605131
```

Format: `YYYYMMDDN` — date + nth change that day
[from-comment](source/src/include/catalog/catversion.h:51-57). Stored in
`pg_control` by `initdb`; the backend refuses to start against a cluster
with a mismatched catversion
[from-comment](source/src/include/catalog/catversion.h:7-14).

**Bump rule** [from-comment](source/src/include/catalog/catversion.h:26-29):

> if you commit a change that requires an initdb, you should update the
> catalog version number (as well as notifying the pgsql-hackers mailing
> list).

In practice that means **any** of:

- Add / remove / rename a column in a catalog header.
- Add / remove / change a row in a `.dat` file (new function, new opclass,
  changed `prosrc`, etc.).
- Add / remove / rename a system function or operator.
- Change the on-disk format of a catalog (e.g. via changes to genbki.pl).
- Change the external representation of stored parsetrees
  (`primnodes.h` / `parsenodes.h` edits)
  [from-comment](source/src/include/catalog/catversion.h:35-38).
- Change tuple header layout or anything else that breaks read-back.

Tracking down a missing bump after the fact is painful — the symptom is
"my installed cluster mysteriously won't start" — so bump aggressively.

`Catalog.pm` doesn't "orchestrate" the bump (it's a one-line edit); it
*does* parse the headers/dat files that determine whether a bump is
needed. The discipline is on the committer.

## 4. syscache / catcache / relcache

Three caches, three jobs.

### `syscache` (= negative & positive tuple cache keyed by index columns)

A *syscache* is a `catcache` bound to a unique index on a catalog, with a
small fixed-size hash bucket count. The lookup keys are the indexed
columns; the cached value is a `HeapTuple`. Declared per-catalog with
`MAKE_SYSCACHE`. Example from `pg_proc.h:147-148`
[verified-by-code](source/src/include/catalog/pg_proc.h:147-148):

```c
MAKE_SYSCACHE(PROCOID,        pg_proc_oid_index,            128);
MAKE_SYSCACHE(PROCNAMEARGSNSP, pg_proc_proname_args_nsp_index, 128);
```

`genbki.pl` collects these into `syscache_ids.h` (the `SysCacheIdentifier`
enum) and `syscache_info.h` (the descriptor array used by `InitCatalogCache`
in `src/backend/utils/cache/syscache.c`).

API [verified-by-code](source/src/include/utils/syscache.h:25-58):

```c
HeapTuple SearchSysCache1(SysCacheIdentifier cacheId, Datum key1);
HeapTuple SearchSysCache2(...);  /* up to 4 keys */
HeapTuple SearchSysCacheCopy1(...);   /* palloc'd copy, owner-free */
bool      SearchSysCacheExists1(...); /* just probe */
Oid       GetSysCacheOid1(cacheId, Anum_oidcol, key);
void      ReleaseSysCache(HeapTuple tuple);
```

Rules:

- Every successful `SearchSysCache*` (non-Copy) **must** be paired with
  `ReleaseSysCache`. Leaks raise "cache reference leak" warnings at
  transaction end.
- `SearchSysCacheCopy*` returns a heap-allocated copy in
  `CurrentMemoryContext`; release with `heap_freetuple` (or just let the
  context get reset).
- Use the numbered variants (`SearchSysCache1` etc.) — they're faster and
  insulate callers from `MAX_SYSCACHE_KEYS` changes
  [from-comment](source/src/include/utils/syscache.h:30-33).
- A miss returns `NULL`, **not** an error.
- Caches are invalidated automatically by `inval.c` shared-invalidation
  messages on catalog mutation, so cross-backend coherence is free.

### `catcache` (the engine under syscache)

Generic SQL-key → HeapTuple cache; `catcache.c` implements the LRU /
negative-entry / invalidation machinery. You almost never touch it
directly — `syscache` is the curated interface.

### `relcache`

Caches `Relation` structs (= `pg_class` row + `pg_attribute` array + index
info + trigger info + RLS info + …) keyed by OID. One entry per open
relation per backend. Built by `relcache.c` from multiple syscache
lookups + special-case bootstrap handling for the nailed-in core catalogs.
Lifetimes are statement/transaction-scoped, with refcount management
through `RelationIdGetRelation` / `RelationClose`.

Mental model: **syscache** answers "give me tuple from pg_X where keys
match"; **relcache** answers "give me the assembled Relation object for
this OID". A relcache build is many syscache lookups under the hood.

## 5. Adding a new system (builtin) function

The pattern, end-to-end:

1. **Write the C function** in the appropriate backend source file with
   the standard signature:
   ```c
   PG_FUNCTION_INFO_V1(my_new_func);
   Datum my_new_func(PG_FUNCTION_ARGS) { ... }
   ```
2. **Pick an unused OID** via `./unused_oids` (random in 8000-9999 for
   in-flight patches).
3. **Add a `pg_proc.dat` entry**. Required fields: `oid`, `descr`,
   `proname`, `prorettype`, `proargtypes`, `prosrc` (= the C symbol).
   Other columns default sensibly
   [verified-by-code](source/src/include/catalog/pg_proc.h:60-130).
   Example:
   ```perl
   { oid => '8473', descr => 'compute frobnitz of an int',
     proname => 'frobnitz', prorettype => 'int4', proargtypes => 'int4',
     prosrc => 'my_new_func' },
   ```
   If the function is volatile / not strict / parallel-unsafe / returns a
   set / etc., override the relevant `proXxx` column.
4. **Bump `CATALOG_VERSION_NO`** in `catversion.h` to today's date + N.
5. **Run `./duplicate_oids`** in `src/include/catalog`; expect empty output.
6. **Rebuild and re-`initdb`** — old data directories will not be loadable
   (catversion mismatch).
7. **Add a regression test** that calls the function from SQL.

Operators, casts, types, opclasses follow the same pattern but with
correspondingly more `.dat` entries (e.g. `pg_operator.dat` + `pg_proc.dat`
for the impl + `pg_amop.dat` if it's indexable + …).

## 6. Things that bite

1. **Forgot to bump catversion** — your locally-running cluster keeps
   working (you initdb'd against your new binary), but anyone else's
   cluster mysteriously refuses to start. Always bump.
2. **OID collision with a concurrent patch** — your patch and someone
   else's both grabbed 8473. Catch it with `./duplicate_oids` and rerun
   `./unused_oids` to pick a fresh one. CI will scream otherwise.
3. **Editing the `.dat` but not the `.h`** (or vice versa) — `genbki.pl`
   parses both; missing column → parse error or default-substituted
   silently. A column with a `BKI_LOOKUP` reference that points at a name
   not present in the target `.dat` produces a clear error.
4. **Forgetting `ReleaseSysCache`** after a successful `SearchSysCache*`
   — leaks; logged as "cache reference leak" warning at transaction end.
5. **Adding a variable-length column outside `#ifdef CATALOG_VARLEN`** —
   compiles, but reading the field via `Form_pg_X->col` accesses garbage
   because tuple deforming doesn't honor the C struct offset for
   varlenas. All varlena/nullable trailing columns must live in the
   `CATALOG_VARLEN` block.
6. **Pinning vs not pinning** — anything declared via `.h`/`.dat` lands
   below `FirstUnpinnedObjectId` and becomes undroppable. If you actually
   want a droppable bootstrap object (rare), it has to go through normal
   SQL in `system_views.sql` / `information_schema.sql`, not BKI.

## References

- `src/include/catalog/README` (one-liner pointing at the docs)
  [from-readme](source/src/include/catalog/README:1-3)
- `src/include/catalog/genbki.h` — macro documentation
  [verified-by-code](source/src/include/catalog/genbki.h)
- `src/backend/catalog/genbki.pl` and `Catalog.pm` — the generator
  [verified-by-code](source/src/backend/catalog/genbki.pl)
- `src/include/catalog/catversion.h` — catversion rules
  [verified-by-code](source/src/include/catalog/catversion.h)
- `src/include/access/transam.h:195-197` — OID range boundaries
  [verified-by-code](source/src/include/access/transam.h:195-197)
- `src/include/utils/syscache.h` and `src/backend/utils/cache/syscache.c`
- Docs: [bki.html](https://www.postgresql.org/docs/current/bki.html),
  [system-catalog-declarations.html](https://www.postgresql.org/docs/current/system-catalog-declarations.html),
  [catalogs.html](https://www.postgresql.org/docs/current/catalogs.html)
  [from-docs](https://www.postgresql.org/docs/current/bki.html)

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| `src/backend/catalog/genbki.pl` | 1 | Top-of-file comment (-14) |
| `src/backend/catalog/genbki.pl` | 53 | Skeleton flow (-100) |
| [`src/include/access/transam.h`](../files/src/include/access/transam.h.md) | 195 | 12000 ≤ OID < 16384 — bootstrap-created but unpinned; user can drop them. Boundary controlled by... |
| [`src/include/catalog/catversion.h`](../files/src/include/catalog/catversion.h.md) | 7 | (-14) |
| [`src/include/catalog/catversion.h`](../files/src/include/catalog/catversion.h.md) | 26 | Bump rule (-29) |
| [`src/include/catalog/catversion.h`](../files/src/include/catalog/catversion.h.md) | 35 | Change the external representation of stored parsetrees (primnodes.h / parsenodes.h edits) (-38) |
| [`src/include/catalog/catversion.h`](../files/src/include/catalog/catversion.h.md) | 51 | (-57). Stored in |
| [`src/include/catalog/catversion.h`](../files/src/include/catalog/catversion.h.md) | 60 | () |
| [`src/include/catalog/genbki.h`](../files/src/include/catalog/genbki.h.md) | 42 | (-66) |
| [`src/include/catalog/genbki.h`](../files/src/include/catalog/genbki.h.md) | 57 | BKI_LOOKUP(catalog) / BKI_LOOKUP_OPT(catalog) — column holds an OID reference to another catalog;... |
| [`src/include/catalog/genbki.h`](../files/src/include/catalog/genbki.h.md) | 68 | DECLARE_TOAST(name, toastoid, indexoid) — pin a TOAST table's OIDs (required because shared catalogs need... |
| [`src/include/catalog/genbki.h`](../files/src/include/catalog/genbki.h.md) | 85 | DECLARE_UNIQUE_INDEX_PKEY(name, oid, oidmacro, tbl, decl) / DECLARE_UNIQUE_INDEX / DECLARE_INDEX — emit a... |
| [`src/include/catalog/genbki.h`](../files/src/include/catalog/genbki.h.md) | 107 | DECLARE_OID_DEFINING_MACRO(name, oid) — claim an OID that isn't a row but should still be globally unique... |
| [`src/include/catalog/genbki.h`](../files/src/include/catalog/genbki.h.md) | 115 | DECLARE_FOREIGN_KEY / DECLARE_ARRAY_FOREIGN_KEY — documentary FK relationships beyond what BKI_LOOKUP... |
| [`src/include/catalog/genbki.h`](../files/src/include/catalog/genbki.h.md) | 142 | MAKE_SYSCACHE(name, idxname, nbuckets) — register a syscache built on the given unique index (-146) |
| [`src/include/catalog/genbki.h`](../files/src/include/catalog/genbki.h.md) | 148 | #ifdef CATALOG_VARLEN ... #endif — hides varlena fields from the C struct (you can't access them via... |
| [`src/include/catalog/genbki.h`](../files/src/include/catalog/genbki.h.md) | 158 | #ifdef EXPOSE_TO_CLIENT_CODE — copy this block verbatim into the generated _d.h so frontend code can use... |
| [`src/include/catalog/pg_attribute.h`](../files/src/include/catalog/pg_attribute.h.md) | 6 | (-8) |
| [`src/include/catalog/pg_class.h`](../files/src/include/catalog/pg_class.h.md) | 34 | () |
| `src/include/catalog/pg_proc.dat` | 14 | (-38) |
| `src/include/catalog/pg_proc.dat` | 36 | Order: roughly group new entries near related existing ones, not at random (-38) |
| `src/include/catalog/pg_proc.dat` | 42 | pg_proc.dat:42 (-45) |
| [`src/include/catalog/pg_proc.h`](../files/src/include/catalog/pg_proc.h.md) | 60 | (-130) |
| [`src/include/catalog/pg_proc.h`](../files/src/include/catalog/pg_proc.h.md) | 99 | #ifdef CATALOG_VARLEN ... #endif — hides varlena fields from the C struct (you can't access them via... |
| [`src/include/catalog/pg_proc.h`](../files/src/include/catalog/pg_proc.h.md) | 147 | (-148) |
| [`src/include/utils/syscache.h`](../files/src/include/utils/syscache.h.md) | 25 | API (-58) |
| [`src/include/utils/syscache.h`](../files/src/include/utils/syscache.h.md) | 30 | Use the numbered variants (SearchSysCache1 etc.) — they're faster and insulate callers from... |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-aggregate-function`](../scenarios/add-new-aggregate-function.md)
- [`add-new-buffer-strategy`](../scenarios/add-new-buffer-strategy.md)
- [`add-new-builtin-function`](../scenarios/add-new-builtin-function.md)
- [`add-new-cast`](../scenarios/add-new-cast.md)
- [`add-new-data-type`](../scenarios/add-new-data-type.md)
- [`add-new-error-code`](../scenarios/add-new-error-code.md)
- [`add-new-extension`](../scenarios/add-new-extension.md)
- [`add-new-index-am`](../scenarios/add-new-index-am.md)
- [`add-new-node-type`](../scenarios/add-new-node-type.md)
- [`add-new-operator`](../scenarios/add-new-operator.md)
- [`add-new-operator-class`](../scenarios/add-new-operator-class.md)
- [`add-new-pg-stat-view`](../scenarios/add-new-pg-stat-view.md)
- [`add-new-sql-keyword`](../scenarios/add-new-sql-keyword.md)
- [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md)
- [`add-new-system-view`](../scenarios/add-new-system-view.md)
- [`add-new-table-am`](../scenarios/add-new-table-am.md)
- [`add-new-utility-statement`](../scenarios/add-new-utility-statement.md)
- [`bump-catversion`](../scenarios/bump-catversion.md)
- [`remove-from-catalog`](../scenarios/remove-from-catalog.md)

<!-- /scenarios:auto -->
