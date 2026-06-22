---
source_url: https://www.postgresql.org/docs/current/bki-commands.html
chapter: "68.3 BKI Commands"
fetched_at: 2026-06-16
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# BKI commands — §68.3

The seven low-level commands the bootstrap backend understands when reading
`postgres.bki` during `initdb`. The file's *structure* (`#`-comments,
`@oid` references, tokenization) is §68.2
([[knowledge/docs-distilled/bki-structure.md]]); the genbki/`.dat` → `.bki`
generation is the parent ([[knowledge/docs-distilled/bki.md]]). A worked
sequence is §68.4 ([[knowledge/docs-distilled/bki-example.md]]).

## Non-obvious claims

- **`create tablename tableoid [bootstrap] [shared_relation] [rowtype_oid
  oid] (name1 = type1 [FORCE NOT NULL | FORCE NULL], ...)`** — and the
  column-type vocabulary is a **fixed, tiny allowlist**, not arbitrary SQL
  types: `bool, bytea, char, name, int2, int4, regproc, regclass, regtype,
  text, oid, tid, xid, cid, int2vector, oidvector, _int4, _text, _oid,
  _char, _aclitem` (leading `_` = array). Bootstrap can't reference a type
  whose catalog row doesn't exist yet. [from-docs §68.3]
- **The `bootstrap` flag is the deep magic: the table is created *on disk
  only*** — no rows in `pg_class`, `pg_attribute`, etc., and the table is
  **inaccessible via SQL** until its own catalog entries are later
  hard-inserted. This is the chicken-and-egg breaker for the handful of
  "bootstrap relations". [from-docs §68.3]
- `shared_relation` marks the table as shared across the cluster (lives in
  the global tablespace); `rowtype_oid oid` pins the composite row-type OID
  (auto-generated if the clause is omitted). [from-docs §68.3]
- **`open tablename` closes whatever table is currently open first** — only
  one table is "open" for inserts at a time; `close tablename` requires the
  name as a **cross-check** against the currently-open table. [from-docs
  §68.3]
- **`insert ([oid_value] value1 value2 ...)`** is *positional* and uses
  `_null_` (underscore-wrapped) for NULL. Non-identifier values are
  single-quoted; an embedded single quote is **doubled**, and backslash
  escapes work inside strings. [from-docs §68.3]
- **Index declaration is split from index *filling*.** `declare [unique]
  index indexname indexoid on tablename using amname (opclass1 name1
  [, ...])` and `declare toast toasttableoid toastindexoid on tablename`
  **only register** the index/toast table; their contents are **not**
  initialized at that point. A later **`build indices`** command fills every
  previously-declared index in one shot. [from-docs §68.3]
- The implication of the declare/build split: the bootstrap data is inserted
  into heaps first, indices built afterward over the populated heaps — the
  same ordering an offline bulk load would use to avoid per-row index
  maintenance. [inferred]

## Links into corpus

- Worked example: [[knowledge/docs-distilled/bki-example.md]] (§68.4).
- File format / tokenization: [[knowledge/docs-distilled/bki-structure.md]]
  (§68.2). Generation pipeline: [[knowledge/docs-distilled/bki.md]].
- Catalog `.dat`/`.h` declarations that genbki turns into these commands:
  [[knowledge/docs-distilled/system-catalog-declarations.md]] +
  [[knowledge/docs-distilled/system-catalog-initial-data.md]].
- Backend that executes the commands:
  [[knowledge/files/src/backend/bootstrap/bootstrap.c.md]].

## Caveats / verification

- All claims `[from-docs §68.3]`. The exact command grammar is implemented in
  `source/src/backend/bootstrap/bootparse.y` + `bootstrap.c`, and the type
  allowlist in `bootstrap.c`'s `bootstrap_data_types`, at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735`.
