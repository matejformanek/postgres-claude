---
source_url: https://www.postgresql.org/docs/current/contrib-spi.html
fetched_at: 2026-07-16
anchor_sha: 572c3b2ddf8c
module: contrib/spi
---

# spi — Server Programming Interface trigger examples

A set of small, standalone trigger functions that double as worked SPI /
trigger-authoring examples. Each is its own installable extension (`autoinc`,
`insert_username`, `moddatetime`, and — in released branches — `refint`). The
canonical "read the source to learn to write a C trigger" contrib module.

## ⚠ Docs-vs-master drift (found this run, anchor 572c3b2ddf8c)

`/docs/current` (PG 17) documents **five** modules including `refint`
(`check_primary_key` / `check_foreign_key`), but on **master** the `refint`
example has been **removed**: `contrib/spi/Makefile` at the anchor reads
`MODULES = autoinc insert_username moddatetime` and `refint.c` / `refint.example`
404 on master, while both still exist on `REL_17_STABLE` and `REL_18_STABLE`.
`timetravel` was removed long before. So on master only three modules remain.
`[verified-by-code source/contrib/spi/Makefile:1 (MODULES = autoinc insert_username moddatetime)]`
`[verified-by-code refint.c present on REL_17_STABLE + REL_18_STABLE, 404 on master]`
→ hf/pgsql-docs candidate: the contrib-spi chapter still fully documents a
module dropped from master. Modules below are described as documented; the
`refint` section is flagged with its removal status.

## Non-obvious claims — per module

### autoinc — `autoinc()` (present on master)
- `BEFORE INSERT` (optionally `BEFORE INSERT OR UPDATE`), `FOR EACH ROW`.
  Fills an integer column from a sequence, but **only if the incoming value is
  0 or NULL** — a user-supplied non-zero value is preserved (unlike a plain
  `DEFAULT nextval()`). `[from-README]`
- Arguments are (column, sequence) **pairs** — an even, >0 count is required
  or it `elog(ERROR "even number gt 0 of arguments was expected")`; multiple
  pairs drive multiple autoincrementing columns from one trigger.
  `[verified-by-code source/contrib/spi/autoinc.c:22,65]`
- If `nextval()` returns 0 it is called again to skip to a non-zero value —
  so 0 stays a reserved "unset" sentinel. `[from-README]`

### insert_username — `insert_username()` (present on master)
- `BEFORE INSERT` and/or `UPDATE`, `FOR EACH ROW`. Overwrites the named text
  column with `current_user` — an audit "who touched this row" stamp.
  `[verified-by-code source/contrib/spi/insert_username.c:5,22,25]`
- Single argument: the text column name. `[from-README]`

### moddatetime — `moddatetime()` (present on master)
- `BEFORE UPDATE`, `FOR EACH ROW`. Stores the current time into the named
  column, which must be `timestamp` / `timestamptz` — a "last modified" stamp.
  `[verified-by-code source/contrib/spi/moddatetime.c:30,33]`
- Single argument: the timestamp column name. `[from-README]`

### refint — `check_primary_key()` / `check_foreign_key()` (REMOVED on master)
- Pre-declarative-constraint referential-integrity enforcement in triggers,
  kept as an SPI example. `[from-README]`
- `check_primary_key()`: `AFTER INSERT OR UPDATE` on the *referencing* table;
  args are (fk cols…, referenced table, referenced key cols…). One trigger per
  FK. `[from-README]`
- `check_foreign_key()`: `AFTER DELETE OR UPDATE` on the *referenced* table;
  args are (N referencing tables, action ∈ {`cascade`,`restrict`,`setnull`},
  pk cols…, then (referencing table, cols…) repeated N times). PK cols must be
  `NOT NULL` with a unique index. `[from-README]`
- Documented footgun: invoked from *another* `BEFORE` trigger,
  `check_foreign_key()` can fail to see a not-yet-visible row inserted earlier
  in the same statement chain. `[from-README]`

## Non-obvious cross-cutting note

- On master, `contrib/spi`'s remaining three modules are all pure
  before-row column-rewrite triggers; none use SPI to run SQL. The historical
  `refint`/`timetravel` were the ones that actually exercised `SPI_execute` /
  saved plans — which is why the chapter is titled "spi" even though the
  survivors barely touch SPI. `[inferred][verified-by-code Makefile MODULES list]`

## Links into corpus

- SPI plan/execution API the examples illustrate:
  `[[knowledge/docs-distilled/spi.md]]`,
  `[[knowledge/docs-distilled/spi-memory.md]]`.
- Trigger data model + firing conditions:
  `[[knowledge/docs-distilled/trigger-interface.md]]`,
  `[[knowledge/docs-distilled/trigger-definition.md]]`.
- Declarative constraints that superseded `refint`:
  `[[knowledge/docs-distilled/ddl-constraints.md]]`.
