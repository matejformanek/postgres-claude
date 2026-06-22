---
source_url: https://www.postgresql.org/docs/current/catalogs-overview.html
fetched_at: 2026-06-21T00:00:00Z
anchor_sha: f25a07b2d94c
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §54.1: System Catalogs — Overview

The orientation page for the catalog reference chapter. The per-catalog pages
(`pg_class`, `pg_proc`, …) are excluded from this corpus as reference, but the
*overview*'s structural claims — especially the **shared vs per-database**
distinction — are genuine architecture facts worth pinning, because they govern
correctness when writing catalog-touching backend code.

## The two structural facts that matter

- **Most catalogs are per-database**: they are copied from `template1` when a
  database is created with `CREATE DATABASE`, and thereafter each database has
  its own private copy. Edits in one DB don't affect another. `[from-docs]`
- **A few catalogs are physically shared cluster-wide**: a single copy is
  visible from every database in the cluster. The authoritative list is
  `IsSharedRelation()` in `source/src/backend/catalog/catalog.c` — verified at
  anchor `f25a07b2d94c` to return true for exactly these 11 catalogs (the docs
  explicitly name `pg_database`, `pg_authid`, `pg_tablespace`; the rest are
  confirmed from that function): `[from-docs]` `[verified-by-code]`
  - `pg_database` — the databases themselves (must be cluster-global, by definition)
  - `pg_authid` — roles / authorization identifiers
  - `pg_auth_members` — role membership
  - `pg_tablespace` — tablespaces
  - `pg_replication_origin` — replication origins
  - `pg_parameter_acl` — ACLs on configuration parameters
  - `pg_subscription` — logical-replication subscriptions
  - `pg_db_role_setting` — per-(db,role) GUC settings
  - the **`sh`-prefixed** dependency/annotation catalogs: `pg_shdepend`,
    `pg_shdescription`, `pg_shseclabel` (the `sh` prefix literally marks the
    *shared* analogue of `pg_depend` / `pg_description` / `pg_seclabel`).

## Why the distinction is load-bearing for hackers

- A dependency *from* a per-database object *to* a shared object (e.g. a table
  owned by a role) cannot be recorded in `pg_depend` — it must go in
  **`pg_shdepend`**, because the depended-on object lives outside any single
  database. Getting this wrong is a classic catalog-edit bug. `[inferred]`
  (Pairs with the `catalog-conventions` skill.)
- DDL that creates a shared-catalog object (`CREATE ROLE`, `CREATE DATABASE`,
  `CREATE TABLESPACE`) is *not* transactional in the same per-database sense and
  is visible cluster-wide immediately on commit. `[inferred]`

## Other overview claims

- System catalogs are **ordinary tables** — you *can* `DROP`/`ALTER`/`INSERT`
  into them with sufficient privilege, but doing so is unsupported and a fast
  path to a corrupted cluster; the supported mutation path is always DDL
  commands, which keep all the dependent catalogs consistent. `[from-docs]`
- Catalogs live in the **`pg_catalog`** schema, which is implicitly on the
  front of every `search_path` so catalog names resolve without qualification
  (and user objects can't accidentally shadow them). `[from-docs]`
- Most catalog rows are keyed by a system-assigned **OID** acting as an
  invisible primary key; the `oid` column is what `pg_depend`, `regclass`, etc.
  reference. `[from-docs]`

## Links into corpus

- Catalog authoring layer (how rows get *declared*, not just read):
  [docs-distilled/system-catalog-declarations.md](./system-catalog-declarations.md),
  [docs-distilled/system-catalog-initial-data.md](./system-catalog-initial-data.md)
- BKI / bootstrap (how the initial catalog contents are laid down):
  [docs-distilled/bki.md](./bki.md)
- Relevant skill: `catalog-conventions` (pg_proc.dat, OID policy, catversion,
  shared-vs-local placement).
