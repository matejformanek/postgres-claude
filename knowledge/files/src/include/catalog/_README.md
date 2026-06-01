# src/include/catalog/README

- **Source path:** `source/src/include/catalog/README`
- **Last verified commit:** `ef6a95c7c64`

## Contents

The README is a single line:

```
See <https://www.postgresql.org/docs/devel/bki.html> about the
files in this directory.
```

That is the entire README. Everything else is convention.

## What you actually need to know

The directory is a mix of three kinds of files:

1. **Catalog-defining headers** (`pg_*.h`) — each declares a `CATALOG(...)` struct that genbki.pl turns into a bootstrap directive. The C compiler sees a normal struct because the macros in `genbki.h` expand to nothing. genbki.pl also reads them and produces the `.bki` file.
2. **Catalog data files** (`pg_*.dat`) — sibling Perl data for the headers that need initial rows: pg_proc.dat (the huge function list), pg_type.dat (built-in types), pg_operator.dat, pg_amop.dat, pg_amproc.dat, pg_cast.dat, pg_aggregate.dat, pg_authid.dat, pg_auth_members.dat, pg_collation.dat, pg_conversion.dat, pg_database.dat, pg_language.dat, pg_namespace.dat, pg_opclass.dat, pg_opfamily.dat, pg_range.dat, pg_tablespace.dat, pg_class.dat, pg_am.dat, pg_ts_*.dat.
3. **Tooling** (`genbki.pl`, `Catalog.pm`, `reformat_dat_file.pl`, `renumber_oids.pl`, `meson.build`, `Makefile`, `duplicate_oids`, `unused_oids`).

## OID space convention

- `0` — InvalidOid.
- `1`..`9999` — manually-assigned OIDs in the `.dat` files (system objects).
- `10000`..`FirstNormalObjectId-1 (16383)` — OIDs assigned during initdb's post-bootstrap SQL phase. Don't put fixed references here.
- `FirstNormalObjectId (16384)`..`2^32-1` — runtime-assigned OIDs.

`unused_oids` and `duplicate_oids` are sanity-check artifacts produced by the Perl scripts.

## Reference

See the upstream PG docs link in the README. The complete spec for `.bki` syntax is in `doc/src/sgml/bki.sgml`.
