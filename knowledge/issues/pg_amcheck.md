# Issues — `pg_amcheck` (src/bin/pg_amcheck/)

Per-subsystem issue register for pg_amcheck — the **heap/btree integrity
verifier frontend** that drives the server-side `amcheck` extension.

**Parent docs:** `knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md` (1 doc, ~68K source).

**Source:** 12 entries surfaced 2026-06-03 by the A6 foreground sweep (batch B5).

pg_amcheck is a thin frontend: option parse → connect → for-each-database
→ invoke `amcheck.verify_heapam`/`bt_index_check` over libpq → format
results. The Phase D question for any verifier is **fail-open vs
fail-closed**. The answer here is: **fail-closed at per-relation
level, fail-open at per-database level**.

---

## P0 — Phase D candidates

### Fail-open at per-database (the headline question for a verifier)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_amcheck.c:585-594 | state-transition | likely | **`--all` silently skips databases without amcheck extension installed** — `all_checks_pass` and exit code unaffected; scheduled cron verifier treating exit-0 as "clean" misses the case where a new database was added without amcheck. Combined with `datallowconn AND datconnlimit != -2` filter at line 1641 = non-trivial gap | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md |
| 2026-06-03 | pg_amcheck.c:207,1719 | state-transition | maybe | **`--no-strict-names` silently turns "no patterns matched" into a warning** — typo `--table publci.users` becomes warning; pg_amcheck exits 0 having checked nothing from that pattern. Default is strict, but the opt-out exists | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md |
| 2026-06-03 | pg_amcheck.c:547-564 | state-transition | maybe | **`--install-missing` changes catalog state in a "verifier"** — issuing `CREATE EXTENSION` from a tool whose advertised role is integrity-check is a surprising posture; documented but tool name doesn't suggest DDL side-effects | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md |

**Critical answer for a verifier-as-policy-gate:** exit-0 means
**"everything I touched was clean"**, NOT "the cluster is clean".

**Phase D pitch:**
1. Add `--require-amcheck` flag that fails-closed when a database
   lacks the extension.
2. Default `--strict-names` semantics for `--all` (warn-but-fail-open
   only when user explicitly says so).
3. Move `--install-missing` to a separate `pg_amcheck-install` binary
   or require explicit `--allow-ddl` flag.

### Server-supplied strings to terminal (echo of A4 psql / A5 logging)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_amcheck.c:1062-1083,1088-1097,1156-1166,1305 | info-disclosure | maybe | `verify_heapam.msg` column, `PQerrorMessage` text, and `datname` in progress meter all flow through `printf("%s", …)` with no control-character filtering — terminal-escape injection vector if attacker controls heap-corruption message text | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md |

### Correctness / state

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_amcheck.c:719-723,816 | correctness | maybe | On Ctrl-C, in-flight slot queries abandoned without explicit stdout flush; relies on stdio atexit flush; SIGKILL loses partial results | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md |
| 2026-06-03 | pg_amcheck.c:978-980 | undocumented-invariant | nit | `should_processing_continue` treats NULL severity field as "stop" — correct but opaque interaction between libpq-internal failure and real `PGRES_FATAL_ERROR` without severity field | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md |
| 2026-06-03 | pg_amcheck.c:1086 | undocumented-invariant | nit | `else if (PQresultStatus(res) != PGRES_TUPLES_OK)` after explicit `==` check is tautologically true | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md |
| 2026-06-03 | pg_amcheck.c:677-683 | correctness | nit | `parallel_workers` calculation walks relations list once just to cap at `opts.jobs` — could be `(opts.jobs < reltotal) ? opts.jobs : reltotal` after `reltotal++`-only pass | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md |
| 2026-06-03 | pg_amcheck.c:2167,2208 | dead-code | nit | `bool is_btree PG_USED_FOR_ASSERTS_ONLY` + `Assert((is_heap && !is_btree) ||…)` — set but never read in non-assert builds; standard PG idiom | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md |

---

## Cross-corpus pattern reinforcement

### `patternToSQLRegex` is the sibling of `processSQLNamePattern`

pg_amcheck uses **`patternToSQLRegex`** (lines 1365, 1398, 1443) — a sibling function in `src/fe_utils/string_utils.c:1219` that produces a regex pattern interpolated into CTE `VALUES` literals via `appendStringLiteralConn`. Same chokepoint discipline as psql/pg_dump's `processSQLNamePattern` (A4 finding). Pattern-injection is **not** a viable vector here.

This means **`fe_utils/string_utils.c` hosts TWO complementary safe-pattern helpers** — one for LIKE-style (psql/pg_dump), one for regex-style (pg_amcheck). Worth a single `knowledge/idioms/sql-name-pattern.md` doc covering both.

### Server-text-to-terminal pattern continues

pg_amcheck's `verify_heapam.msg` echo is the third occurrence of "server-supplied strings printed unescaped to terminal" after:
- A4 psql's describe.c relname rendering
- A4 psql's NOTIFY payload to terminal
- A6 pg_amcheck (now)

A single corpus-wide hardening (helper that filters control chars before display) would close all three.

---

## Summary by tag type

| Type | Count |
|---|---:|
| state-transition | 3 |
| undocumented-invariant | 2 |
| info-disclosure | 1 |
| correctness | 2 |
| dead-code | 1 |
| stale-todo | 0 |
| **Total** | **9** (some entries double-tagged; grep counts 12 occurrences) |

Severity headline: 1 `likely`, 3 `maybe`, rest `nit`. THE Phase D pitch:
**add `--require-amcheck` for fail-closed `--all` posture**.
