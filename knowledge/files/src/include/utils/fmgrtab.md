# utils/fmgrtab.h — built-in function dispatch table

Source: `source/src/include/utils/fmgrtab.h` (49 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Declares the auto-generated `fmgr_builtins[]` table and the OID-to-index reverse map. Implementation file `fmgrtab.c` is generated from `pg_proc.dat` by `Catalog.pm` at build time.

## Public API

- `FmgrBuiltin` struct (`fmgrtab.h:25-33`): `foid`, `nargs` (-1 for variadic), `strict`, `retset`, `funcName`, `func` pointer.
- `fmgr_builtins[]` (`fmgrtab.h:35`), `fmgr_nbuiltins` (`fmgrtab.h:37`), `fmgr_last_builtin_oid` (`fmgrtab.h:39`).
- `fmgr_builtin_oid_index[]` (`fmgrtab.h:47`): OID → index in fmgr_builtins, with sentinel `InvalidOidBuiltinMapping = PG_UINT16_MAX` for unmapped OIDs.

## Invariants

- **INV-table-generated-from-pg_proc.dat** [inferred from build]: any change to `pg_proc.dat` must regenerate fmgrtab.c (handled by build system). Manual edits to fmgrtab.c are wiped on rebuild.
- **INV-OID-fits-uint16-index** [verified-by-code, `fmgrtab.h:46`]: the reverse-map index is `uint16`, so the table can hold at most 65535 entries. Adding builtins past that requires widening.
- **INV-fmgr_last_builtin_oid-bounds-table** [verified-by-code, `fmgrtab.h:39-40`]: `fmgr_builtin_oid_index[]` is indexed 0..fmgr_last_builtin_oid inclusive; out-of-range OIDs aren't in this table at all (and route through pg_proc/CatCache).
- **INV-strict-and-retset-pre-baked** [verified-by-code, `fmgrtab.h:29-30`]: avoid re-fetching pg_proc for these flags; they're trusted from this table.

## Trust-boundary / Phase-D surface

- **Adding a new builtin requires catversion bump + initdb** — the header doesn't say it, but Catalog.pm dependency means new entries appear via genbki regen. Skipping initdb after a fmgr table change yields OID/funcptr mismatches.
- **`InvalidOidBuiltinMapping` sentinel** (`fmgrtab.h:46`): callers MUST check before indexing into `fmgr_builtins[]`. A bad OID without the sentinel check yields an out-of-bounds read.

## Cross-refs

- `source/src/include/catalog/pg_proc.dat` — the source-of-truth pg_proc seed data.
- `source/src/backend/utils/Gen_fmgrtab.pl` — generator.
- `source/src/backend/utils/fmgr/fmgr.c` — `fmgr_isbuiltin` / `fmgr_info_C_lang` consumers.

## Issues

- `[ISSUE-DOC: catversion bump requirement implicit (medium)]` — adding a builtin without bumping catversion silently breaks pg_upgrade.
- `[ISSUE-INVARIANT: uint16 index ceiling at 65535 (info)]` — current count is well below this, but worth noting for very-distant-future planning.
