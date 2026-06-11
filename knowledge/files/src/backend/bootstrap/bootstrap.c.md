# `src/backend/bootstrap/bootstrap.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1195
- **Source:** `source/src/backend/bootstrap/bootstrap.c`

Bootstrap mode: a stripped-down standalone backend that doesn't speak
SQL — instead it consumes the BKI bootstrap language (CREATE/OPEN/
CLOSE/INSERT/DECLARE INDEX/BUILD INDICES, parsed by `bootparse.y` /
`bootscanner.l`). Run exactly once per cluster by `initdb`, via
`postgres --boot ... < postgres.bki`. Also reachable via `--check`
for shared-memory sizing validation. [verified-by-code §bootstrap.c:1-13, 224-235]

Two big idioms make this file readable: a hard-coded `TypInfo[]`
table of bootstrap-time built-in types (24 entries) that exists
because `pg_type` doesn't yet have rows when the first CREATE
happens; and a `Typ` list that gets lazy-loaded from `pg_type` once
that catalog has been populated, after which the hard-coded table is
no longer consulted (except in error fallback). [verified-by-code §bootstrap.c:79-142, 195-209, 938-997]

## API / entry points

- **`void BootstrapModeMain(int argc, char *argv[], bool check_only)`**
  — the main entry, called from `main.c`'s dispatcher.
  - getopt loop handles `-B` (shared_buffers), `-c name=value` /
    `--name=value`, `-D`, `-d N` (debug level → log/client_min_messages),
    `-F` (fsync off), `-k` (data checksums on), `-r` (stdout/stderr
    redirect), `-X` (wal_segment_size).
  - Sets `IgnoreSystemIndexes = true` and `BootstrapProcessing` mode.
  - Calls `InitProcess`, `BaseInit`, `BootStrapXLOG`,
    `InitPostgres(NULL, InvalidOid, ...)` to come up far enough to
    do catalog inserts.
  - Calls `boot_yylex_init` / `boot_yyparse(scanner)` to drive the
    BKI parser inside one big transaction
    (`StartTransactionCommand` / `CommitTransactionCommand`).
  - Then `RelationMapFinishBootstrap` writes `pg_filenode.map`.
  - When `check_only`, bails after `set_max_safe_fds` via
    `CheckerModeMain` which just calls `proc_exit(0)`. The XXX
    comment notes this could be its own function.
  [verified-by-code §bootstrap.c:236-446]
- **`void boot_openrel(char *relname)`** — BKI `OPEN` opcode.
  Closes any open rel, `table_openrv` the named rel with `NoLock`
  (bootstrap is single-process so no locks are needed). Captures
  `numattr` and copies each `pg_attribute` into the global
  `attrtypes[]` for subsequent `InsertOneTuple`. Lazy-populates `Typ`
  on the first OPEN if not already populated. [verified-by-code §bootstrap.c:483-522]
- **`void closerel(char *relname)`** — BKI `CLOSE`. Asserts the named
  rel matches the open one. [verified-by-code §bootstrap.c:528-553]
- **`void DefineAttr(char *name, char *type, int attnum, int nullness)`**
  — BKI `DECLARE` column. Picks `attlen/attbyval/attalign/attstorage/
  attcollation` either from `Ap` (most recent `Typ` lookup result) or
  from `TypInfo[typeoid]` (when `Typ == NIL`). Forces collation to
  `C_COLLATION_OID` for any catalog column to keep behaviour
  independent of database collation (so `template0` can be cloned to
  any collation). Auto-infers `attnotnull` for fixed-width columns
  whose predecessors are all fixed-width-and-not-null.
  [verified-by-code §bootstrap.c:566-662]
- **`void InsertOneTuple(void)`** / `InsertOneValue(char *value, int i)`
  / `InsertOneNull(int i)` — BKI `INSERT` per-row + per-value. Use
  `boot_get_type_io_data` to find the typinput and call it via
  `OidInputFunctionCall`. The pg_node_tree column type is special-
  cased: only `pg_proc.proargdefaults` is supported, via
  `InsertOneProargdefaultsValue`. Other pg_node_tree fields raise
  ERROR. [verified-by-code §bootstrap.c:673-879]
- **`static void InsertOneProargdefaultsValue(char *value)`** — parses
  the input as a text[] of cstrings, runs each through the
  corresponding parameter's `typinput`, builds a `List` of `Const`
  nodes, and stores `nodeToString()` of that list as the
  `proargdefaults` text. Also patches in `pronargdefaults` (the
  count) "as a hack". Asserts via `StaticAssertDecl` that
  `pronargs/proargtypes` columns appear before `proargdefaults` in
  the BKI insert order. [verified-by-code §bootstrap.c:767-861]
- **`void index_register(Oid heap, Oid ind, const IndexInfo *)`** —
  BKI `DECLARE INDEX` — record an index in a deferred `ILHead` list.
  Stored in a dedicated `nogc` `AllocSetContext` so they survive
  multiple transactions. The "don't gc index reldescs" XXX comment
  is from mao 10/31/92. [verified-by-code §bootstrap.c:1129-1173]
- **`void build_indices(void)`** — BKI `BUILD INDICES`. Walks ILHead
  and calls `index_build` for each. Used near end of bootstrap once
  all heap inserts are done. [verified-by-code §bootstrap.c:1179-1196]
- **`Oid boot_get_role_oid(const char *rolname)`** — look up one of
  the 17 hard-coded `RolInfo[]` entries (`POSTGRES`,
  `pg_read_all_data`, `pg_monitor`, …) at bootstrap time, equivalent
  to `get_role_oid(name, true)`. [verified-by-code §bootstrap.c:1093-1102]
- **`void boot_get_type_io_data(typid, ...)`** — exported because
  array_in / array_out call it during early bootstrap when the syscaches
  aren't initialised. Mirrors `lsyscache.c:get_type_io_data` but only
  covers text I/O (not binary). [verified-by-code §bootstrap.c:1010-1083]
- **Static helpers:**
  - `CheckerModeMain` — `proc_exit(0)`.
  - `bootstrap_signals` — `pqsignal(SIG…, PG_SIG_DFL)` for HUP, INT,
    TERM, QUIT. Bootstrap mode wants "curl up and die" defaults.
  - `cleanup`, `populate_typ_list`, `gettype`, `AllocateAttribute`.

## Notable invariants / details

- **`MAXATTR`-sized scratch arrays** for `attrtypes[]`, `values[]`,
  `Nulls[]` mean BKI can declare at most `MAXATTR` columns per relation
  (currently 40 per `include/access/htup_details.h`). New
  bootstrappable catalogs that grow past that limit need both
  bump + recompile. [verified-by-code §bootstrap.c:66-67, 190-191]
- **`gettype` is "really ugly"** — its own comment. Returns either
  an integer INDEX into TypInfo[] (during early bootstrap), or a
  real OID (once Typ is populated). Caller must inspect `Typ != NIL`
  to know which is which. This duality permeates `boot_openrel` /
  `DefineAttr`. [from-comment §bootstrap.c:928-936]
- **Bootstrap mode has no LOCKS.** `table_openrv(..., NoLock)`,
  `table_open(..., NoLock)`, `index_open(..., NoLock)`. Comment
  in `build_indices`: "need not bother with locks during bootstrap".
  Safe because the bootstrap backend is the only process running.
  [verified-by-code §bootstrap.c:504, 908, 1187-1189]
- **`IgnoreSystemIndexes = true`** for the duration of bootstrap —
  catalog lookups go via sequential scan rather than syscache/index,
  because indexes haven't been built yet. [verified-by-code §bootstrap.c:364]
- **`nogc` MemoryContext** for `index_register`. Allocated lazily
  the first time `DECLARE INDEX` shows up and never reset. The XXX
  mao comment from 1992 documents that this is the intended
  no-reset region. [verified-by-code §bootstrap.c:1138-1148]
- **C_COLLATION_OID forcing** on every collation-aware catalog
  column is the cornerstone that makes `template0` cloneable to any
  collation — bootstrap mode forces consistency regardless of the
  cluster locale. [from-comment §bootstrap.c:618-625]

## Potential issues

- **File-line `bootstrap.c:75-77`.** "XXX several of these
  input/output functions do catalog scans (e.g., F_REGPROCIN scans
  pg_proc). this obviously creates some order dependencies in the
  catalog creation process." Long-standing; the order constraint
  is encoded in `postgres.bki` ordering. [ISSUE-stale-todo: order-dependency in TypInfo I/O functions (nit)]
- **File-line `bootstrap.c:389-392`.** "XXX: It might make sense to
  move this into its own function at some point." The check-only
  early-exit. Cosmetic. [ISSUE-stale-todo: refactor check-only branch (nit)]
- **File-line `bootstrap.c:1042` and `:1072`.** Duplicate "XXX this
  logic must match getTypeIOParam()" comments — two near-identical
  blocks for the Typ-list and TypInfo-fallback cases. Any change to
  `getTypeIOParam` requires updating both. The static-assert /
  shared-helper refactor never happened. [ISSUE-undocumented-invariant: getTypeIOParam logic duplicated in two branches (likely)]
- **File-line `bootstrap.c:1138-1141`.** "XXX mao 10/31/92" — the
  oldest XXX in the file. The `nogc` context is never reset; small
  leaks for indexes that get re-declared shouldn't happen but the
  comment dates from the era before MemoryContext existed.
  [ISSUE-stale-todo: nogc MemoryContext never reset (nit)]
- **File-line `bootstrap.c:803-804`.** `if (array_count > pronargs)`
  raises ERROR, but if a row passes `array_count == pronargs` with
  some leading NULLs intended for non-default args, the function
  builds a Const list shorter than `pronargs` — and then sets
  `pronargdefaults = array_count` which is what
  `lookup_default_for_param` expects. Not a bug, but the alignment
  isn't asserted. [ISSUE-undocumented-invariant: array entries must align with trailing args (maybe)]
