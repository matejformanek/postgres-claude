---
source_url: https://www.postgresql.org/docs/current/ddl-foreign-data.html
fetched_at: 2026-07-11T19:54:35Z
anchor_sha: 54cd6fc83176d7c03abf95554aef26b0b24acc7d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "5.13 Foreign Data"
---

# Docs distilled — Foreign Data (ddl-foreign-data)

The SQL/MED user-DDL surface: foreign tables are a fourth relation kind
(`RELKIND_FOREIGN_TABLE = 'f'`, beside ordinary `'r'`, partitioned `'p'`, view
`'v'`) whose reads/writes dispatch into a foreign-data-wrapper library. This is
the catalog/DDL face of the FDW callback machinery covered in the fdw-* docs.

## Non-obvious claims

- **A foreign table is a storage-less relation kind.** "a foreign table has no
  storage in the PostgreSQL server"; every access "asks the foreign data wrapper
  to fetch data from the external source, or transmit data … in the case of
  update commands." It is its own `relkind`: `RELKIND_FOREIGN_TABLE = 'f'`.
  [from-docs] + [verified-by-code] `src/include/catalog/pg_class.h:178`.
- **Four-tier object chain, each a catalog object.** FDW (`CREATE FOREIGN DATA
  WRAPPER` → `pg_foreign_data_wrapper`) → server (`CREATE SERVER` →
  `pg_foreign_server`) → user mapping (`CREATE USER MAPPING` →
  `pg_user_mapping`) → foreign table (`CREATE FOREIGN TABLE` →
  `pg_foreign_table` + a `pg_class` row of relkind `'f'`). [from-docs]
- **The wrapper is a *library* implementing SQL/MED handler callbacks.** "A
  foreign data wrapper is a library that can communicate with an external data
  source, hiding the details of connecting … and obtaining data from it." PG
  "implements portions of the SQL/MED specification". The DDL here is inert
  without a handler-providing wrapper. [from-docs]
- **User mappings resolve per-PostgreSQL-role credentials.** Authentication
  "based on the current PostgreSQL role" — the same mechanism postgres_fdw's
  `password_required` security model builds on. [from-docs]
- **Wrappers ship as contrib or are user-written.** postgres_fdw / file_fdw are
  contrib; `IMPORT FOREIGN SCHEMA` bulk-discovers remote table shapes. If none
  fit, "you can write your own" against the `FdwRoutine` callback set.
  [from-docs]
- **Local constraint enforcement is a known gap** — this page is silent on it,
  but by construction the server does not hold foreign-table data, so
  constraints declared on a foreign table are not locally validated against the
  remote contents (they inform the planner but the wrapper owns the data).
  [inferred] — see fdw-callbacks for the enforcement boundary.

## Links into corpus

- [[knowledge/files/src/include/catalog/pg_class.h.md]] — `RELKIND_FOREIGN_TABLE`
  as a distinct relation kind.
- [[knowledge/docs-distilled/fdwhandler.md]] — the `FdwRoutine` handler this DDL
  binds to.
- [[knowledge/docs-distilled/fdw-callbacks.md]] — scan/modify callbacks invoked
  when a foreign table is queried/written.
- [[knowledge/docs-distilled/postgres-fdw.md]] — the reference wrapper +
  user-mapping credential model.
- [[knowledge/docs-distilled/ddl-partitioning.md]] — foreign tables may serve as
  partitions (remote-sharded partitioned tables).
