# pglite-fusion — a Datum that is an entire foreign database engine, deserialized-mutated-reserialized on every call (the inverse of an FDW)

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `frectonz/pglite-fusion` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. The whole extension is one
> file — `src/lib.rs` (260 lines) — plus a pgrx-generated `.control`. Cites
> verified against the files fetched on 2026-06-13 (see Sources footer). Read
> alongside `[[knowledge/ideologies/pgrx]]` (the framework that makes the type
> exist) and `[[knowledge/ideologies/wrappers]]` (the FDW contrast).

## Domain & purpose

pglite-fusion lets you "embed an SQLite database in your PostgreSQL table. AKA
multitenancy has been solved" (`README.md:1-3`) `[from-README]`. It registers a
single new base type, `SQLITE`, whose stored value is a complete, self-contained
SQLite database serialized to bytes, and a family of SQL functions that take such
a value, spin up an in-memory SQLite engine from it, run arbitrary SQLite SQL,
and (for mutating ops) hand back a *new* serialized database value
(`src/lib.rs:12-15, 87-93`) `[verified-by-code]`. The canonical use is a per-row
private database: `database SQLITE DEFAULT init_sqlite('CREATE TABLE todos (task
TEXT)')`, then `UPDATE … SET database = execute_sqlite(database, 'INSERT INTO
todos …')` (`README.md:64-87`) `[from-README]`.

The reason to document it: it is the corpus's sharpest example of **a Datum that
is itself an entire foreign database engine's state**. Core Postgres datums are
scalars (`int4`, `text`), or composites/arrays of scalars — values the executor
understands and can introspect. A `SQLITE` datum is an opaque `Vec<u8>` that only
*becomes* meaningful when a second SQL engine (bundled libsqlite3) is instantiated
to interpret it. This is the precise inverse of a Foreign Data Wrapper: an FDW is
core reaching *out* to a remote engine while the rows stay foreign; pglite-fusion
brings a whole engine *in*, packed inside one heap tuple's column.

## How it hooks into PG

Everything is pgrx attribute macros; there is no hand-written C, no `.sql` (pgrx
generates the install schema at build time), and the `.control` is the stock
pgrx template: `relocatable = false`, `superuser = true`, `trusted = false`
(`pglite_fusion.control:4-6`) `[verified-by-code]`.

- **The type**: `#[derive(Serialize, Deserialize, PostgresType)] struct Sqlite {
  data: Vec<u8> }` (`src/lib.rs:12-15`) `[verified-by-code]`. `PostgresType` is
  pgrx's derive that wires up a new base type; by default pgrx serializes the
  struct via CBOR for the type's `_in`/`_out`/`recv`/`send` functions, so on the
  heap a `SQLITE` value is the CBOR envelope around the raw SQLite page image.
  See `[[knowledge/ideologies/pgrx]]` for the `PostgresType` machinery.
- **The functions**, all `#[pg_extern]` (pgrx's fmgr glue, the Rust analogue of
  `PG_FUNCTION_INFO_V1`):
  - constructors: `empty_sqlite()`, `init_sqlite(query)`,
    `import_sqlite_from_file(path)` (`src/lib.rs:57-74`).
  - mutators returning a fresh `Sqlite`: `execute_sqlite(sqlite, query)`,
    `vacuum_sqlite(sqlite)` (`:87-98`).
  - readers: `query_sqlite` (set-returning), `query_sqlite_json`,
    `list_sqlite_tables`, `sqlite_schema`, `count_sqlite_rows` (`:124-225`).
  - row accessors over the JSON row type: `get_sqlite_text/integer/real`
    (`:102-122`).
  - sink: `export_sqlite_to_file(sqlite, path)` (`:76-85`).

Cross-ref `[[knowledge/idioms/fmgr]]` (the calling convention pgrx emulates),
`[[knowledge/idioms/memory-contexts]]` (where the SQLite handle does *not* live),
`.claude/skills/fmgr-and-spi/SKILL.md`.

## Where it diverges from core idioms

### 1. The Datum is a foreign engine's serialized state, not a value the executor understands

Core base types are atoms the backend can compare, hash, sort, and index. A
`SQLITE` datum is `struct Sqlite { data: Vec<u8> }` (`src/lib.rs:13-14`)
`[verified-by-code]` — an opaque blob with no `=`, no ordering, no opclass, no
cast to any core type. Postgres can store it, `TOAST` it, and pass it around, but
it cannot look inside; only `sqlite.load()` (which instantiates a real SQLite
engine) makes it legible (`:18-45`). The blob is the **entire database file
image** produced by SQLite's `serialize()` API (`dump`, `:47-54`)
`[verified-by-code]` — schema, b-trees, pages, the lot. So one column value is a
complete database, with all the recursion that implies (you can store a table of
databases each containing tables). This is a categorically different thing from
core's "a datum is a value"; here a datum is *another DBMS's whole on-disk state*.

### 2. Deserialize-mutate-reserialize on EVERY call — no persistent handle, O(db size) per operation

The defining cost pattern. Each function that touches a `SQLITE` value calls
`self.load()`, which: opens a fresh in-memory connection, `sqlite3_malloc`s a copy
of the bytes, and `conn.deserialize(...)` reconstructs the engine
(`src/lib.rs:18-45`) `[verified-by-code]`. Mutators then call `Sqlite::dump`,
which `conn.serialize(...).to_vec()` re-emits the **whole** database image
(`:47-54`) `[verified-by-code]`. Consequences that cut hard against core idioms:

- **Every `execute_sqlite` rewrites the entire database.** Inserting one todo row
  reserializes the full SQLite file and produces a brand-new, larger `SQLITE`
  datum (`execute_sqlite`, `:87-93`) `[verified-by-code]`. There is no in-place
  update, no append; the cost of any mutation is O(total db size), and the new
  datum must be written back by an outer SQL `UPDATE` (`README.md:73-87`). Set-
  based SQL over many rows each containing a big SQLite db is therefore quadratic-
  flavored: N rows × full-image reserialize each.
- **No connection lifetime across calls.** The SQLite `Connection` is a local
  created at function entry and dropped at function exit (e.g. `query_sqlite`'s
  `conn` lives only inside the `let table = { … }` block, `:126-142`)
  `[verified-by-code]`. Nothing is cached between calls, between rows, or across
  the statement. Two `query_sqlite` calls on the same column re-instantiate SQLite
  twice from scratch. Contrast the SPI/cached-plan world of core, where a backend
  holds long-lived state — `[[knowledge/idioms/spi]]`.
- **Reads still pay full deserialize.** Even pure reads (`list_sqlite_tables`,
  `count_sqlite_rows`) call `sqlite.load()` and rebuild the whole engine just to
  run one `SELECT` (`:170-225`) `[verified-by-code]`.

### 3. Volatility labels: mutators are `volatile`, readers `stable`, accessors `immutable` — but the readers arguably lie

The labels are explicit pgrx attributes (`src/lib.rs:57,63,70,76,87,95,102,124,
147,169,189,209`) `[verified-by-code]`:

- `empty_sqlite`, `init_sqlite`, `import_sqlite_from_file`, `export_sqlite_to_file`,
  `execute_sqlite`, `vacuum_sqlite` → `volatile`. Correct: they create new state,
  touch the filesystem, or both.
- `query_sqlite`, `query_sqlite_json`, `list_sqlite_tables`, `sqlite_schema`,
  `count_sqlite_rows` → `stable`. Defensible: a given `SQLITE` blob always yields
  the same rows, and the function does no writes — but note SQLite SQL is itself
  arbitrary, so a query like `SELECT random()` makes the result non-stable in
  practice. The label trusts the user not to run non-deterministic SQLite SQL.
  `[inferred]`
- `get_sqlite_text/integer/real` → `immutable` (`:102,112,118`). These are pure
  JSON-cell extractors, so the label fits.

Core's contract is that `immutable`/`stable` are promises the planner relies on
for constant-folding and caching. pglite-fusion's `stable` readers hand that
promise to an embedded engine running unconstrained SQL — a wider trust boundary
than core type functions usually take. `[inferred]`

### 4. Parallel-safety is declared per function, and file I/O opts out

`empty_sqlite`, `init_sqlite`, `execute_sqlite`, `vacuum_sqlite`, and the readers
are `parallel_safe`; `import_sqlite_from_file` and `export_sqlite_to_file` are
`parallel_unsafe` (`src/lib.rs:70,76` vs the rest) `[verified-by-code]`, exactly
because they open files by path (`Connection::open(path)`, `:72,79`). The README
states this plainly: "Every function is parallel-safe except for
`import_sqlite_from_file` and `export_sqlite_to_file`" (`README.md:116`)
`[from-README]`. This is the right call — but it also means a `parallel_safe`
`execute_sqlite` can run in a worker while reserializing a multi-megabyte engine,
multiplying the per-call cost across workers. Cross-ref
`.claude/skills/gucs-bgworker-parallel/SKILL.md`.

### 5. Error bridging is `panic`/`expect`, not `ereport` — pgrx catches the unwind

There is no `ereport` anywhere; every failure path is a Rust `expect`/`panic`:
`"couldn't deserialize the sqlite database"` (`src/lib.rs:41`), `"query execution
failed"` (`:66,90,139`), `"couldn't prepare sqlite query"` (`:128,175,194`),
`panic!("Invalid table name: {}", table)` (`:213-214`) `[verified-by-code]`.
pglite-fusion relies entirely on pgrx's panic-to-ereport bridge: a Rust panic is
caught at the `#[pg_extern]` boundary and converted into a Postgres `ERROR` (this
is *the* job of pgrx's fmgr glue — see `[[knowledge/ideologies/pgrx]]`). The
`Cargo.toml` even forces `panic = "unwind"` in both dev and release profiles
(`Cargo.toml:33-37`) `[verified-by-code]`, which is mandatory: a panic-abort build
would crash the postmaster instead of raising a catchable error. So the entire
error story is "let it panic; pgrx makes it an ERROR" — no SQLSTATE selection, no
`errdetail`/`errhint`, no soft-error `escontext`. Contrast core's deliberate
`ereport` discipline, `[[knowledge/idioms/error-handling]]`.

### 6. Memory: the SQLite engine lives in libsqlite3's own heap, outside Postgres MemoryContexts

`load()` does manual FFI memory management: `sqlite3_malloc` for the deserialize
buffer, `std::mem::forget(buf)` to hand ownership of the input bytes to SQLite,
and `OwnedData::from_raw_nonnull` to let rusqlite own and later free it
(`src/lib.rs:23,28-42`) `[verified-by-code]`. None of this touches a Postgres
`MemoryContext` — the SQLite database, its page cache, and its working memory are
all in malloc/`sqlite3_malloc` territory, invisible to `palloc`, to
`MemoryContextStats`, and to Postgres's per-query reset. A large embedded database
inflates backend RSS in a way `pg_backend_memory_contexts` will never show. The
`Vec<u8>` that crosses the SQL boundary *is* pgrx-allocated, but the live engine
is not. Cross-ref `[[knowledge/idioms/memory-contexts]]` for what core expects
backend allocations to look like.

### 7. The result shape leans on JSON, not core SQL types

`query_sqlite` returns `TableIterator<(SqliteRow,)>` where `SqliteRow =
Vec<pgrx::Json>` (`src/lib.rs:100,124-145`) `[verified-by-code]` — i.e. each
SQLite row arrives in Postgres as a JSON array of cells, and you pull values out
with `get_sqlite_text(row, idx)` etc. SQLite's dynamic typing is mapped to JSON
via `rusqlite_value_to_json` (`Null/Integer/Real/Text/Blob` → JSON, `:227-236`)
`[verified-by-code]`. So the foreign engine's schema is *not* projected into
Postgres's type system as columns; it is funneled through a single weakly-typed
JSON conduit. This sidesteps the hard problem an FDW must solve (declaring a
foreign table's column types to the planner) — pglite-fusion just refuses to, and
makes the caller index into JSON. `[inferred]`

## Notable design decisions (cited)

- **rusqlite is `bundled` + `serialize` + `backup`** (`Cargo.toml:25`)
  `[verified-by-code]`: the extension statically links its own SQLite (no system
  dependency) and depends on SQLite's `serialize`/`deserialize` C API — the exact
  primitives that make "a database as a column value" possible. `backup` powers
  `export_sqlite_to_file` via `Backup::run_to_completion(5, 250ms, …)`
  (`src/lib.rs:81-84`).
- **`init_sqlite` is `strict`** (`src/lib.rs:63`) so a NULL init query yields NULL
  rather than running; `empty_sqlite` is non-strict (no args). Both create the
  empty db then immediately `dump` it (`:58-68`) — i.e. even an "empty" SQLITE
  column carries a full serialized SQLite header image, not zero bytes.
  `[verified-by-code]`
- **`count_sqlite_rows` hand-rolls SQL-injection defense** because the table name
  is interpolated: it rejects any name with non-`[A-Za-z0-9_]` chars before
  `format!("SELECT COUNT(*) FROM {table}")` (`src/lib.rs:210-222`)
  `[verified-by-code]`. A tell that the moment you let users pass SQLite SQL
  fragments, you re-inherit SQLite's own injection surface inside Postgres.
- **No upgrade script / single version**: `default_version =
  '@CARGO_VERSION@'` (`pglite_fusion.control:2`) is substituted from
  `Cargo.toml`'s `version = "0.0.6"` (`Cargo.toml:3`); there is no
  `--X--Y.sql` migration, so the serialized format is implicitly frozen by
  whatever CBOR+SQLite layout 0.0.x emits. `[inferred]`
- **`superuser = true`, `trusted = false`** (`pglite_fusion.control:5-6`): correct,
  since `import_/export_sqlite_*` read and write arbitrary server-side file paths
  (`src/lib.rs:71-79`) `[verified-by-code]` — an unrestricted filesystem reach that
  must not be available to non-superusers.

## Links into corpus

- `[[knowledge/ideologies/pgrx]]` — the framework that makes `SQLITE` a real base
  type (`PostgresType` derive) and turns Rust panics into Postgres errors; every
  hook in this doc is a pgrx macro. Read first.
- `[[knowledge/ideologies/wrappers]]` — the **inverse** design. Wrappers is the
  FDW C API in Rust: core reaches *out* to remote engines, rows stay foreign.
  pglite-fusion brings a whole engine *in*, packed in a datum. The contrast is the
  whole point of this doc.
- `[[knowledge/idioms/fmgr]]` — `#[pg_extern]` is pgrx's emulation of
  `PG_FUNCTION_INFO_V1` / `PG_GETARG`/`PG_RETURN`; the set-returning
  `TableIterator` maps onto core SRF mechanics.
- `[[knowledge/idioms/memory-contexts]]` — the SQLite engine lives outside any
  `MemoryContext` (libsqlite3 malloc), invisible to `palloc`/backend-memory
  introspection.
- `[[knowledge/idioms/error-handling]]` — contrast: pglite-fusion has zero
  `ereport`; all failures are panics caught by pgrx, with no SQLSTATE/detail/hint.
- `[[knowledge/idioms/spi]]` — contrast on engine lifetime: SPI is the in-core way
  to run SQL with cached plans and backend-scoped state; pglite-fusion instead
  rebuilds a foreign engine from bytes on every single call.

## Anthropology takeaway

pglite-fusion is the doc-set's cleanest **"datum as a whole foreign DBMS"** case,
and the inverse-of-an-FDW framing is the sharpest divergence: where an FDW keeps
the foreign data foreign and reaches out per-scan, pglite-fusion swallows an
entire SQLite engine into a single column value and rehydrates it on demand. The
second, equally instructive divergence is the **deserialize-mutate-reserialize-
per-call** cost model: there is no persistent handle and no in-place mutation, so
every write reserializes the full database image (O(db size) per row, per call)
and every read re-instantiates the engine from scratch — a pattern that quietly
breaks the set-based, amortized-state assumptions core SQL is built on. Two
follow-on notes worth a `knowledge/issues` entry: (a) the `stable` volatility on
readers is a promise made on behalf of arbitrary user-supplied SQLite SQL, which
can be non-deterministic — a trust boundary the planner can't see through; and
(b) the embedded engine's memory and the per-call reserialization are both
invisible to Postgres's own accounting (`MemoryContext` stats, TOAST cost
estimates), so a workload can blow up backend RSS and per-tuple CPU in ways the
planner never costs. It's a brilliant, slightly mad demonstration of how far
pgrx's `PostgresType` + panic-bridge lets an extension stretch the meaning of "a
column value."

## Sources

Fetched 2026-06-13 (branch `main`):

- `https://raw.githubusercontent.com/frectonz/pglite-fusion/main/README.md`
  @ 2026-06-13 → HTTP 200 (7021 bytes; usage + per-function API docs, read fully).
- `https://raw.githubusercontent.com/frectonz/pglite-fusion/main/pglite_fusion.control`
  @ 2026-06-13 → HTTP 200 (175 bytes; stock pgrx control template).
- `https://raw.githubusercontent.com/frectonz/pglite-fusion/main/src/lib.rs`
  @ 2026-06-13 → HTTP 200 (8026 bytes; the entire extension, 260 lines,
  deep-read — type, load/dump, all `#[pg_extern]` functions, volatility labels,
  error paths, FFI memory handling).
- `https://raw.githubusercontent.com/frectonz/pglite-fusion/main/Cargo.toml`
  @ 2026-06-13 → HTTP 200 (834 bytes; pgrx 0.16.1, rusqlite 0.34 with
  bundled/serialize/backup, panic=unwind both profiles).

All cites are `[verified-by-code]` against the fetched `src/lib.rs` /
`Cargo.toml` / `.control` except the multitenancy framing and parallel-safety
summary (`[from-README]`), and the volatility-trust / JSON-conduit / format-freeze
observations (`[inferred]`). The pgrx `PostgresType` CBOR-on-the-wire detail rests
on `[[knowledge/ideologies/pgrx]]` plus the visible `#[derive(Serialize,
Deserialize, PostgresType)]`; the SQLite `serialize`/`deserialize` semantics rest
on the rusqlite `serialize`-feature API surface as called at `src/lib.rs:38-54`.
