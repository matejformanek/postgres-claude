---
source_url: https://www.postgresql.org/docs/current/storage-file-layout.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §66.1: Database File Layout

How a relation maps to files on disk: `base/<db-oid>/<filenode>`, the
OID-vs-filenode distinction, 1 GB segments, the fork suffixes, and tablespace
symlinks. The mental model behind `pg_relation_filepath`.

## Directory skeleton under PGDATA [from-docs]

- `base/` — one subdirectory per database, **named by the database's OID** in
  `pg_database`. Holds that database's tables, indexes, and most system catalogs.
- `global/` — cluster-wide catalogs (e.g. `pg_database`, `pg_authid`) that belong
  to no single database; the `pg_global` tablespace lives here.
- `pg_tblspc/` — symlinks to user-defined tablespaces.

`pg_default` resolves to `base/`, `pg_global` to `global/` — neither goes through
`pg_tblspc`. [from-docs]

## OID vs filenode — the distinction that bites [from-docs]

- A relation's file is named by its **filenode** (`pg_class.relfilenode`), which
  *often* equals its OID but **is not guaranteed to**.
- `TRUNCATE`, `REINDEX`, `CLUSTER`, `VACUUM FULL`, and some `ALTER TABLE` forms
  **rewrite the relation into a new filenode while preserving the OID**. So
  caching "OID → file" is a bug; the mapping is mutable.
- For some system catalogs (including `pg_class` itself) `relfilenode` is **0** —
  their location is bootstrapped, not stored in the catalog row. Use
  `pg_relation_filenode(oid)` to get the real filenode in that case. [from-docs]
  [verified-by-code, source/src/common/relpath.c — `GetRelationPath`/`relpathbackend`
  build the path from (dbid, spcid, relfilenode, forknum); via
  knowledge/files/src/common/relpath.c.md]

## Forks — one relation, several files [from-docs]

| Fork | Suffix | Contents |
|---|---|---|
| Main | (none) | The table/index data itself |
| Free Space Map | `_fsm` | Approx free space per page (§66.3) |
| Visibility Map | `_vm` | All-visible / all-frozen page bits (tables only, §66.4) |
| Init | `_init` | Empty-image template for **unlogged** tables/indexes |

For filenode `12345`: main `12345`, then `12345_fsm`, `12345_vm`, `12345_init`.
[from-docs]
[verified-by-code, source/src/common/relpath.c — `forkNames[]` =
{"main","fsm","vm","init"} indexed by `ForkNumber`]

The `_init` fork is how crash recovery resets unlogged relations: on crash restart
the main fork is replaced by the init fork's (empty) image. [inferred, from-docs]

## Temporary relations [from-docs]

- Named `t<BBB>_<FFF>` where `BBB` = the owning backend's number and `FFF` = the
  filenode — so temp files from different backends never collide. [from-docs]
  [verified-by-code, source/src/common/relpath.c — the `t%d_` temp-relation
  filename branch]

## Segments — the 1 GB rule [from-docs]

- Any fork exceeding **1 GB** is split into gigabyte **segments**. The first is
  `<filenode>`; later ones are `<filenode>.1`, `<filenode>.2`, … The 1 GB default
  is `--with-segsize` at build time.
- Quote: *"When a table or index exceeds 1 GB, it is divided into gigabyte-sized
  segments. The first segment's file name is the same as the filenode; subsequent
  segments are named filenode.1, filenode.2, etc."* [from-docs]
- `md.c` (the magnetic-disk smgr) is what stitches segments back into one logical
  fork. [inferred]

## Tablespaces [from-docs]

- `pg_tblspc/<tablespace-oid>` is a symlink to the external directory. Inside it:
  a version-stamped subdir (e.g. `PG_18_2026xxxxxx`) → per-database subdirs named
  by **database OID** → filenode-named files. The version stamp keeps multiple
  major versions from clobbering each other on the same mount. [from-docs]

## `pg_relation_filepath` [from-docs]

- Returns the PGDATA-relative path of a relation's **first main-fork segment
  only**. To enumerate all files you must append `.1/.2/…` (segments) and
  `_fsm`/`_vm`/`_init` (forks) yourself. [from-docs]

## TOAST [from-docs]

- A relation with potentially-large attributes gets a companion TOAST table,
  linked via `pg_class.reltoastrelid`; it is itself a relation with its own
  filenode and files. Details in §66.2 / storage-toast. [from-docs]

## Links into corpus

- [[knowledge/files/src/common/relpath.c.md]] — `forkNames[]`, `GetRelationPath`,
  the temp-relation and segment naming; the code behind every claim here.
- [[knowledge/docs-distilled/storage.md]] — parent chapter.
- [[knowledge/docs-distilled/storage-fsm.md]] / [[knowledge/docs-distilled/storage-vm.md]]
  — the `_fsm` / `_vm` forks named here.
- [[knowledge/docs-distilled/storage-toast.md]] — the TOAST companion.
- [[knowledge/subsystems/storage-buffer.md]] — how forks/segments surface through
  the smgr + buffer tag.

## Gaps / follow-ups

- The init-fork crash-recovery reset and the segment-stitching in `md.c` are
  inferred from the docs; a read of `md.c` + `reinit.c` would pin both
  `[verified-by-code]`. No per-file corpus doc for `md.c` yet.
