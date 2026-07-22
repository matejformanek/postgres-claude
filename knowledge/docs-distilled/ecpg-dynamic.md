---
source_url: https://www.postgresql.org/docs/current/ecpg-dynamic.html
fetched_at: 2026-07-21T18:50:00Z
anchor_sha: 0da71d90d623
title: "ECPG — Dynamic SQL (§36 leaf): EXECUTE IMMEDIATE vs PREPARE/EXECUTE USING/INTO, the ECPGprepare/ECPGdeallocate runtime, tie-in to descriptors"
maps_to_skill: wire-protocol
---

# ECPG — Dynamic SQL (runtime-composed statements)

How ECPG runs SQL that isn't known at preprocessing time — text built at
runtime or read from outside. Three tiers of increasing capability:
`EXECUTE IMMEDIATE` (fire-and-forget), `PREPARE`+`EXECUTE … USING` (input
params), and `PREPARE`+`EXECUTE … INTO`/cursor (result sets). The metadata for
unknown-shape results is discovered via `DESCRIBE` into a descriptor or SQLDA.

## Non-obvious claims

- **`EXECUTE IMMEDIATE :stmt` is the no-params, no-results tier.** For DDL /
  `INSERT`/`UPDATE`/`DELETE` composed as a runtime string with no host
  variables and no returned rows — it prepares, runs, and discards in one step.
  It **cannot** run a statement that retrieves data (a `SELECT`) — that raises
  an error rather than silently dropping rows. [from-docs]

- **Input parameters use `?` placeholders bound positionally by `USING`.**
  `EXEC SQL PREPARE mystmt FROM :stmt;` where `:stmt` contains `INSERT INTO t
  VALUES(?, ?)`, then `EXEC SQL EXECUTE mystmt USING 42, 'foobar';`. This is the
  same `?`→positional binding the preprocessor uses internally for static
  statements (see `ecpg-develop`), surfaced to the application. `EXEC SQL
  DEALLOCATE PREPARE name;` releases it. The runtime calls are `ECPGprepare` /
  `ECPGdeallocate` (`source/src/interfaces/ecpg/include/ecpglib.h:35-37`).
  [verified-by-code][from-docs]

- **A single `EXECUTE` can carry `INTO`, `USING`, both, or neither.** For a
  known-width single-row result: `EXEC SQL EXECUTE mystmt INTO :v1, :v2, :v3
  USING 37;` — outputs bound by `INTO`, inputs by `USING`, in one statement.
  Neither-clause degenerates to `EXECUTE IMMEDIATE`-like behavior. [from-docs]

- **Multi-row dynamic results still require a cursor over the prepared name.**
  `PREPARE stmt1 FROM :stmt; DECLARE cursor1 CURSOR FOR stmt1; OPEN cursor1;
  FETCH cursor1 INTO …; CLOSE cursor1;` — you cannot `EXECUTE … INTO` an array
  for a dynamic multi-row set the way a static array target works; the cursor is
  the supported path. [from-docs]

- **Unknown-shape results are the reason descriptors/SQLDA exist.** When the
  application doesn't know the column count or types at compile time, `DESCRIBE
  … INTO SQL DESCRIPTOR` / `INTO DESCRIPTOR sqlda` fills the metadata so the
  program can allocate and bind at runtime — dynamic SQL is the primary
  consumer of the descriptor machinery. Descriptor-index/unknown-descriptor
  failures surface as the −240-band codes (`ECPG_UNKNOWN_DESCRIPTOR −240`,
  `ECPG_INVALID_DESCRIPTOR_INDEX −241`,
  `source/src/interfaces/ecpg/include/ecpgerrno.h:43-47`). [verified-by-code][from-docs]

## Links into corpus

- Result-metadata mechanisms this feeds:
  `knowledge/docs-distilled/ecpg-descriptors.md`.
- The `?`-placeholder / positional binding lineage:
  `knowledge/docs-distilled/ecpg-develop.md`.
- Server-side prepared-statement path:
  `knowledge/docs-distilled/libpq-exec.md` (`PQprepare`/`PQexecPrepared`),
  `knowledge/docs-distilled/protocol-flow.md` (extended query).
- Skill: `wire-protocol`.
