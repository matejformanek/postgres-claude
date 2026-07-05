---
source_url: https://www.postgresql.org/docs/current/plpgsql-overview.html
fetched_at: 2026-07-05T20:47:00Z
anchor_sha: e0ff7fd9aa2e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/pgSQL overview (internals §43.1 — page body says §41.1)

The chapter root. Thin on hard internals (the mechanism lives in
`plpgsql-implementation.md`), but it fixes the *architectural* framing a backend
hacker needs: PL/pgSQL is a **loadable procedural-language handler**, and its
entire performance argument is **SPI-batching — running the compute + queries
inside the backend instead of shuttling to a client.** Two subsections: §43.1.1
Advantages, §43.1.2 Supported Argument and Result Data Types.

> Chapter is §43 in the current ToC; page body still reads "41.1" (docs lag).

## Non-obvious claims

- **PL/pgSQL is a loadable module even though it's installed by default.**
  "PL/pgSQL is a loadable procedural language" and, since 9.0, "it is still a
  loadable module, so especially security-conscious administrators could choose
  to remove it." It is loaded through the PL handler machinery, not compiled
  into the core backend. [from-docs] → the handler is registered in
  `pg_language`; the C handler entry is `plpgsql_call_handler`
  (`source/src/pl/plpgsql/src/pl_handler.c`). [inferred]
- **The performance thesis is round-trip elimination, i.e. SPI.** The listed
  advantages are all one idea: "group a block of computation and a series of
  queries *inside* the database server" so that "extra round trips between client
  and server are eliminated," "intermediate results that the client does not need
  do not have to be marshaled or transferred," and "multiple rounds of query
  parsing can be avoided." The overview never says "SPI" out loud, but that is
  exactly the SPI manager doing the embedded queries. [from-docs / inferred]
- **Can be defined trusted.** Listed as a design goal ("can be defined to be
  trusted by the server") — trusted means an unprivileged user may create
  functions in it because the language cannot reach outside the SQL sandbox
  (contrast PL/PythonU). [from-docs]
- **The overview deliberately omits the compile/cache mechanism.** No mention of
  first-call compilation, plan caching, or the handler ABI here — that is all in
  §43.11 (`plpgsql-implementation.md`). Do not cite this page for those claims.
  [verified-by-code: WebFetch returned no compilation/caching prose from §43.1]

## Links into corpus

- [[knowledge/docs-distilled/plpgsql-implementation.md]] — where the actual
  compile/cache/PARAM mechanism lives.
- [[knowledge/docs-distilled/plpgsql-structure.md]] — §43.2 block grammar.
- [[knowledge/docs-distilled/plhandler.md]] — the PL handler ABI (`_call_handler`
  / `_inline_handler` / `_validator`) PL/pgSQL implements.
- [[knowledge/docs-distilled/xplang.md]] — installing a procedural language
  (`CREATE LANGUAGE`, the handler registration).
- [[knowledge/docs-distilled/spi.md]] — the SPI manager the "advantages" are
  really describing.

## Open questions

- `pl_handler.c` line for `plpgsql_call_handler` and the `#trusted` marker in
  `plpgsql.control` — pin on a future deep read at anchor `e0ff7fd9aa2e`.
