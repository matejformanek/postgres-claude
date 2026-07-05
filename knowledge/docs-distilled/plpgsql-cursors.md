---
source_url: https://www.postgresql.org/docs/current/plpgsql-cursors.html
fetched_at: 2026-07-05T20:47:00Z
anchor_sha: e0ff7fd9aa2e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/pgSQL cursors (internals §43.7 — page body says §41.7)

The internals payoff here is one sentence: **a `refcursor` value is literally the
string name of a server-side Portal.** Everything else — bound/unbound variables,
`OPEN FOR [EXECUTE]`, returning a cursor to the caller — follows from that. Pairs
with `spi.md` (SPI cursor ABI) and the Portal machinery. Subsections: §43.7.1
Declaring, .2 Opening, .3 Using (FETCH/MOVE/WHERE CURRENT OF/CLOSE/Returning),
.4 Looping.

## Non-obvious claims

- **`refcursor` = portal name string.** *"Internally, a `refcursor` value is
  simply the string name of the portal containing the active query for the
  cursor."* [from-docs] Verified: `OPEN` reads the name out of the variable
  (`curname = TextDatumGetCString(curvar->value)`,
  `source/src/pl/plpgsql/src/pl_exec.c:2922`) and opens the portal with it
  (`SPI_cursor_open_with_paramlist(curname, query->plan, ...)`, `pl_exec.c:2987`);
  a name collision errors `"cursor \"%s\" already in use"` (`pl_exec.c:2928`).
  [verified-by-code @e0ff7fd9aa2e]
- **A Portal is the server-internal query-state object; names are session-unique.**
  *"Opening a cursor involves creating a server-internal data structure called a
  portal, which holds the execution state for the cursor's query. A portal has a
  name, which must be unique within the session for the duration of the portal's
  existence."* If you don't assign a name, PL/pgSQL auto-generates a unique one
  (`<unnamed cursor N>`; the `refcursor` variable starts null in PG16+). [from-docs]
- **Bound cursors are always plan-cacheable; unbound-via-EXECUTE never are.** A
  `CURSOR FOR SELECT ...` declaration binds the query at declare time and its
  plan "is always considered cacheable; there is no equivalent of `EXECUTE`." An
  unbound `refcursor` opened via `OPEN ... FOR query` caches its plan and does
  PARAM substitution; `OPEN ... FOR EXECUTE string` re-plans and does **not**
  substitute variables — same cache/no-cache split as §43.5. [from-docs]
- **Substituted values are frozen at OPEN time.** *"the value that is substituted
  is the one it has at the time of the `OPEN`; subsequent changes to the variable
  will not affect the cursor's behavior."* [from-docs]
- **`SCROLL` = backward-fetch capability, and it's incompatible with `FOR
  UPDATE/SHARE`.** `NO SCROLL` rejects backward `FETCH`; unspecified is
  query-dependent. Avoid `SCROLL` over volatile functions (re-reading assumes a
  stable result). [from-docs]
- **Returning a cursor hands the caller the portal name.** A function returning
  `refcursor` (or `SETOF refcursor` for several) just `RETURN`s the name string;
  the caller then `FETCH`es from that portal in the same transaction. [from-docs]
- **Portals close at transaction end — hard boundary.** *"All portals are
  implicitly closed at transaction end. Therefore a `refcursor` value is usable
  to reference an open cursor only until the end of the transaction."* (No
  `WITH HOLD` discussion in this section.) [from-docs]
- **`FOR ... IN cursor LOOP` auto-manages the portal.** *"The `FOR` statement
  automatically opens the cursor, and it closes the cursor again when the loop
  exits."* The loop variable is an implicit `record` scoped to the loop. [from-docs]

## Why this design

Making `refcursor` a plain text portal-name is what lets a cursor cross the
function boundary: the function returns a string, the caller looks the portal up
by name in the session's portal table, and no PL-specific handle type has to be
serialized. It also explains the transaction-end death: portals are owned by the
transaction's resource owner, so a `refcursor` you stashed is a dangling name
once the transaction ends. [inferred]

## Links into corpus

- [[knowledge/docs-distilled/spi.md]] — `SPI_cursor_open` / `SPI_cursor_fetch`,
  the ABI PL/pgSQL cursors ride on.
- [[knowledge/docs-distilled/plpgsql-statements.md]] — §43.5: the cache/no-cache
  `EXECUTE` split cursors inherit.
- [[knowledge/docs-distilled/plpgsql-transactions.md]] — §43.8: cursor loops vs
  COMMIT interaction.
- [[knowledge/docs-distilled/protocol-flow.md]] — the extended-query Portal
  concept at the wire level.

## Open questions

- The exact `Portal`-struct fields (`portalContext`, `resowner`) that enforce the
  transaction-end close — trace `portalmem.c` / `AtCleanup_Portals` at anchor
  `e0ff7fd9aa2e`.
