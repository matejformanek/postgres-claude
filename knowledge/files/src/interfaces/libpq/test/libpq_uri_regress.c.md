---
path: src/interfaces/libpq/test/libpq_uri_regress.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 84
depth: read
---

# `libpq_uri_regress.c` — conninfo/URI parsing regression helper

## Purpose

A test driver for libpq's connection-string and URI parser. It takes a
single conninfo/URI string on the command line, runs it through
`PQconninfoParse`, and prints every resulting option whose value differs
from the `PQconndefaults` baseline — giving the regression suite a stable,
diffable textual rendering of how a given URI was parsed. It also reports
whether the target resolves to a Unix-domain socket (`(local)`) or a
network host (`(inet)`), mimicking libpq's own host/hostaddr logic. This
is the harness behind the `src/interfaces/libpq` URI test cases, which
matter for catching parser regressions that could silently misroute or
mis-authenticate a connection.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `main(int, char **)` | libpq_uri_regress.c:20 | Requires exactly one arg; returns 1 on usage error or parse failure (printing the parser's `errmsg`), 0 otherwise. |

## Internal landmarks

- Parses with `PQconninfoParse(argv[1], &errmsg)` (line 33) and fetches
  defaults with `PQconndefaults()` (line 40).
- Walks `opts` and `defs` *in lockstep* (line 53), printing
  `keyword='value'` for any non-default option.
- local-vs-inet heuristic (lines 69-74): an option is "inet" if it's a
  non-empty `hostaddr`, or a `host` whose first char isn't `/`. The
  comment notes it tests `'/'` directly rather than `is_absolute_path`,
  matching libpq's own behavior and accepting that it would misbehave on
  Windows (which has no Unix sockets anyway).

## Invariants & gotchas

- **[ISSUE-undocumented-invariant: lockstep walk assumes stable option
  order]** — the `XXX` at libpq_uri_regress.c:50-52 records that the code
  assumes `PQconninfoParse` and `PQconndefaults` always return options in
  the same keyword order. True by construction today (both derive from the
  same `PQconninfoOptions` table), but it's a brittle coupling; logged as
  `nit` in the register rather than a real defect.

## Cross-refs

- `knowledge/files/src/interfaces/libpq/fe-connect.c.md` — defines
  `PQconninfoParse`/`PQconndefaults` (if present in corpus).
- [[libpq_testclient.c]] — sibling test helper.
- `knowledge/issues/libpq-oauth.md` — issue register (shared for this
  cloud run's libpq-tail findings).
