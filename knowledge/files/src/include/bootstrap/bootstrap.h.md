# `src/include/bootstrap/bootstrap.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~70
- **Source:** `source/src/include/bootstrap/bootstrap.h`

Public interface of the bootstrap subsystem — the single-user
mini-backend that initdb runs to populate the system catalogs from
`postgres.bki`. Exports the parser/lexer entry points (driven by
`backend/bootstrap/bootparse.y` + `bootscanner.l`), the relation
machinery (`boot_openrel` / `closerel`), and helpers for inserting
catalog tuples one column at a time. [verified-by-code]

## API / declarations

### Constants

- `MAXATTR = 40` — maximum attributes in a relation supported at
  bootstrap time (system tables only). [verified-by-code]
- `BOOTCOL_NULL_AUTO = 1`, `BOOTCOL_NULL_FORCE_NULL = 2`,
  `BOOTCOL_NULL_FORCE_NOT_NULL = 3` — `DefineAttr` nullness flag.

### State (file-scope in bootstrap.c)

- `extern Relation boot_reldesc;` — currently-open boot relation.
- `extern Form_pg_attribute attrtypes[MAXATTR];` — the column
  descriptors built up via `DefineAttr`.
- `extern int numattr;`

### Main entry

- `pg_noreturn void BootstrapModeMain(argc, argv, check_only);` —
  invoked when `postgres --boot` is run by initdb.

### Relation management

- `closerel(relname)` — close the currently-open boot relation.
- `boot_openrel(relname)` — open the named relation; populates
  `boot_reldesc` and `attrtypes[]`.

### Attribute / tuple construction

- `DefineAttr(name, type, attnum, nullness)`.
- `InsertOneTuple(void)` — flush attrtypes[] state as a heap tuple.
- `InsertOneValue(value, i)` / `InsertOneNull(i)`.

### Index machinery

- `index_register(heap, ind, indexInfo)` — register an index to be
  built at the end of bootstrap.
- `build_indices(void)` — flush all registered indexes.

### Type I/O lookup

- `boot_get_type_io_data(typid, *typlen, *typbyval, *typalign,
  *typdelim, *typioparam, *typinput, *typoutput, *typcollation)`
  — bootstrap-mode replacement for `getTypeIoInfo` (because the
  catalogs being looked up are not yet fully populated).

### Role helper

- `boot_get_role_oid(rolname)` — bootstrap-mode role-OID lookup
  (only "postgres" and the bootstrap user are typically present).

### Parser hooks (re-entrant flex+bison)

- `union YYSTYPE; typedef void *yyscan_t;`
- `boot_yyparse(yyscan_t)`,
- `boot_yylex_init(yyscan_t *)`,
- `boot_yylex(YYSTYPE *, yyscan_t)`,
- `pg_noreturn void boot_yyerror(yyscan_t, message)`.

## Notable invariants / details

- `MAXATTR = 40` is the bootstrap limit, NOT the runtime catalog
  limit. A new system table column that pushes a table over 40
  attributes would silently truncate during bootstrap.
  [verified-by-code]
- `boot_get_type_io_data` is needed because the bootstrap path
  reads `pg_type` rows before the catalog is fully built —
  callers must NOT use the regular fmgr/typcache lookups.
  [inferred]
- The parser uses the re-entrant flex/bison API (`yyscan_t` opaque
  state, `boot_yylex_init`) rather than global state — same
  pattern as the SQL parser. [verified-by-code]

## Potential issues

- `MAXATTR = 40` is a silent cap; adding a 41st column to any
  system table would corrupt bootstrap. [ISSUE-undocumented-invariant:
  MAXATTR is a hard ceiling that catalog reviewers must respect
  (likely)]
- `attrtypes[MAXATTR]` is statically sized — overflows would write
  past the array. Detection relies on a comparison in
  `DefineAttr` (in `bootstrap.c`, not shown here).
  [ISSUE-question: is there an assert/ereport on overflow? (nit)]
- `boot_yyerror` is `pg_noreturn` — callers shouldn't expect
  return-and-continue parsing. Convention but worth noting for
  any modification to the bootstrap grammar.
- `BootstrapModeMain` is also `pg_noreturn` — it exits via
  `proc_exit(0)` on success and `ereport(FATAL)` on failure.
  [inferred]
