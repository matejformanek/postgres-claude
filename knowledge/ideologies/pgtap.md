# pgtap — a whole xUnit/TAP test framework built entirely out of PL/pgSQL functions and temp-table state

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `theory/pgtap` @ branch `master` (v1.3.5). All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-07-18 (see Sources footer). This is the corpus's first
> **testing-framework** ideology — a distinct axis from the PLs, index AMs, and
> FDW frameworks catalogued so far.

## Domain & purpose

pgTAP is a unit-testing framework for PostgreSQL. You write test functions in
SQL/PL-pgSQL, call assertion functions (`ok`, `is`, `throws_ok`, `has_table`,
`results_eq`, …), and the functions *return* [TAP](https://testanything.org)
(Test Anything Protocol) text lines like `ok 1 - my description` /
`not ok 2 - …` that a TAP harness (`pg_prove`, `prove`) collects
(`README.md:1-9`) `[from-README]`. The control file's comment is simply "Unit
testing for PostgreSQL", `requires = 'plpgsql'`, `relocatable = true`,
`superuser = false` (`pgtap.control:1-6`) `[verified-by-code]`. It "cannot be
installed remotely" — it must run inside the server it tests
(`README.md:15-16`) `[from-README]`, because every assertion is a server-side
function reading the live catalog.

**The one thing that makes pgTAP structurally distinct.** Almost every other
extension in this corpus hooks into the C backend — a `_PG_init`, a loadable
`.so`, an AM, a hook. pgTAP has **no C, no `.so`, no `_PG_init`**: it is
~11.5k lines of `CREATE FUNCTION` (`pgtap.sql.in`, 11520 lines) `[verified-by-code]`.
Its entire divergence lives in *what SQL functions can be talked into doing*:
(1) it holds mutable per-session framework state in **temp tables** because a
function has nowhere else to keep a counter; (2) it implements **xUnit test
isolation via PL/pgSQL exception-driven subtransaction rollback**, since
plpgsql cannot issue real `COMMIT`/`ROLLBACK`; and (3) it does **reflection-based
test discovery by querying `pg_proc`**. It is the maximal demonstration of how
far you can push the "extension = pure SQL install script" model
(`knowledge/idioms/extension-install-script.md` if present) before you need C.

## How it hooks into PG

It does not hook into PG at the C level at all. Its only integration surfaces
are ordinary SQL objects:

- **Assertion functions returning `TEXT`/`SETOF TEXT`.** `ok(boolean, text)`
  (`pgtap.sql.in:263`) is the primitive: it returns the string
  `ok N - desc` or `not ok N - desc` and, on failure, bumps a counter
  (`add_result`, `pgtap.sql.in:162-167`) `[verified-by-code]`. Everything else
  (`is`, `isnt`, `matches`, `cmp_ok`, …) composes on `ok`.
- **Catalog-introspection assertions.** Hundreds of functions —
  `has_table(NAME,NAME,TEXT)` (`pgtap.sql.in:1014`), `has_column`,
  `col_type_is`, `has_index`, `fk_ok`, … — are thin `SELECT`s against
  `pg_catalog.pg_class` / `pg_attribute` / `pg_proc` / `pg_constraint` wrapped
  in `ok()`. The framework's "assertions" are catalog queries
  `[verified-by-code]`.
- **A reflection-driven runner.** `runtests(NAME, TEXT)` (`pgtap.sql.in:6846`)
  and its siblings dispatch to `_runner(...)` (`pgtap.sql.in:6699`), passing
  five function-name arrays discovered by `findfuncs` `[verified-by-code]`.

## Where it diverges from core idioms

### 1. Per-session framework state in a TEMP table (functions have no other memory)

A test run needs a plan count, a running test number, and a failure count.
A pure SQL function cannot keep a static variable, so `plan(integer)` **creates
a temp table on first call**:

```
CREATE TEMP SEQUENCE __tcache___id_seq;
CREATE TEMP TABLE __tcache__ (id …, label TEXT, value INTEGER, note TEXT …);
CREATE TEMP SEQUENCE __tresults___numb_seq;
```
(`pgtap.sql.in:31-45`) `[verified-by-code]`. All framework state is then read
and written through `_get(text)` / `_set(text,integer,text)` / `_add(...)`,
each of which is a `plpgsql` wrapper around a **dynamic `EXECUTE`** of
`SELECT value FROM __tcache__ …` / `UPDATE __tcache__ …`
(`pgtap.sql.in:71-160`) `[verified-by-code]`. "You tried to plan twice!" is
detected by catching the `duplicate_table` exception when the temp table already
exists (`pgtap.sql.in:47-53`) `[verified-by-code]`. Contrast a core backend
counter, which would live in backend-local C memory or shared memory; pgTAP's
"backend-local variable" is a temp relation, MVCC-versioned and WAL-exempt but
still a heap. The result number is a `TEMP SEQUENCE` (`__tresults___numb_seq`),
so `nextval` is the per-test id generator (`add_result`, `pgtap.sql.in:166`)
`[verified-by-code]`.

### 2. xUnit isolation via a forced `__TAP_ROLLBACK__` exception, not real transaction control

The architecturally striking piece. `_runner` runs each discovered test
function, then **deliberately raises an exception to roll back everything the
test did**:

```
-- Run the actual test function.
FOR tap IN EXECUTE 'SELECT * FROM ' || tests[i] || '()' LOOP … END LOOP;
…
-- Always raise an exception to rollback any changes.
RAISE EXCEPTION '__TAP_ROLLBACK__';
EXCEPTION WHEN raise_exception THEN … -- caught here, run continues
```
(`pgtap.sql.in:6790-6831`) `[verified-by-code]`. A PL/pgSQL `BEGIN … EXCEPTION`
block *is* an internal subtransaction (savepoint); raising out of it rolls the
savepoint back. pgTAP exploits that to give every test a clean slate —
schema/data mutations a test makes are undone before the next test — **without
ever issuing `COMMIT`/`ROLLBACK`**, which a function cannot do. A genuine test
error is caught by the inner `EXCEPTION WHEN OTHERS` (`pgtap.sql.in:6798`),
which snapshots `SQLSTATE`/`SQLERRM` + `GET STACKED DIAGNOSTICS` fields
(`pgtap.sql.in:6800-6813`), then the outer handler emits `Test died: …`
(`pgtap.sql.in:6823-6828`) `[verified-by-code]`. This is the same
subtransaction machinery core uses for `plpgsql` exception blocks
(`knowledge/idioms/plpgsql-exception-subxact.md` if present;
`knowledge/subsystems/access-transam-xact.md`), repurposed as a **test-isolation
harness**. Cost inherited from that machinery: each test burns an XID / SXact
and the per-subxact overhead — a large `runtests` schema is a subtransaction
storm.

### 3. Reflection-based test discovery over `pg_proc`

There is no test registry. `runtests(schema)` classifies functions purely by
**name regex against the catalog**: `findfuncs(NAME, TEXT, TEXT)` is
`SELECT … FROM pg_catalog.pg_proc p JOIN pg_namespace n … WHERE n.nspname = $1
AND p.proname ~ $2 AND ($3 IS NULL OR p.proname !~ $3)`
(`pgtap.sql.in:6592-6603`) `[verified-by-code]`. `runtests(NAME, TEXT)` then
builds the startup/shutdown/setup/teardown/test arrays by five `findfuncs`
calls keyed on the prefixes `^startup`, `^shutdown`, `^setup`, `^teardown`, and
the user match (default `^test`) (`pgtap.sql.in:6846-6855`) `[verified-by-code]`.
Test lifecycle (xUnit `setUp`/`tearDown`) is thus **convention-over-catalog**:
name a function `setup_*` and it runs before each test; the framework learns the
suite by introspecting the system catalog, the same way `has_table` introspects
it for assertions. The no-plan-visible variant (`findfuncs(TEXT,TEXT)`) instead
filters on `pg_function_is_visible(p.oid)` (`pgtap.sql.in:6614`) — search-path
visibility as the discovery scope `[verified-by-code]`.

### 4. The TAP protocol as function return values, and `finish()`/`_finish()` accounting

Core has no notion of a test protocol; pgTAP makes the **result set itself** the
protocol stream. `plan(n)` returns `'1..' || n` (`pgtap.sql.in:57`);
each assertion returns an `ok`/`not ok` line; `finish()` →`_finish(...)`
compares `curr_test` against the planned count and emits a diagnostic if they
disagree, or `RAISE EXCEPTION` if `exception_on_failure` is set
(`pgtap.sql.in:183-233`) `[verified-by-code]`. Because the lines are rows, you
consume a test with `SELECT * FROM runtests();` and pipe psql's output to a TAP
harness — the "output format" is literally a `SETOF TEXT`.

### 5. `throws_ok` — asserting error behavior through the plpgsql exception catcher

Testing that a statement *raises* is done by running it inside a
`BEGIN/EXCEPTION` and matching the caught `SQLSTATE`/message:
`throws_ok(TEXT, CHAR(5), TEXT, TEXT)` (`pgtap.sql.in:657`) and its overloads by
int errcode (`pgtap.sql.in:729`) `[verified-by-code]`. The same subtransaction
mechanism that gives isolation (§2) is here the *unit under assertion* — pgTAP
tests core's error path by catching it.

## Notable design decisions

- **Zero C, `requires = plpgsql` only** (`pgtap.control:4`) — maximally portable,
  installs on any server, but pays the temp-table + subxact costs above rather
  than keeping counters in C `[verified-by-code]`.
- **`.sql.in` templated at build** (`pgtap.sql.in`, `Makefile`) — the shipped
  SQL is generated per server version, so version-specific catalog shapes are
  compiled in rather than branched at runtime `[inferred]` from the `.in`
  suffix + `Makefile` version gate (`README.md:50-52`).
- **`COLLATE "C"` on discovered names** (`findfuncs`, `pgtap.sql.in:6596`) —
  deterministic test ordering independent of the database's collation
  `[verified-by-code]`.
- **Runner resets `__tresults___numb_seq` per subtest and restores it after**
  (`pgtap.sql.in:6742-6746`, `6833-6836`) so nested subtest numbering is local
  `[verified-by-code]`.

## Links into corpus

- Isolation-via-subtransaction rests on the same savepoint machinery as
  `[[plpgsql_check]]` (another pure-catalog-introspection parasite) and the core
  `plpgsql` exception block — see `knowledge/subsystems/` xact/plpgsql notes.
- Reflection over `pg_proc` mirrors how `[[powa-archivist]]` drives ETL from a
  registry table and how `[[index_advisor]]` reads planner output back as an
  oracle — "SQL that inspects the catalog to decide what to do next".
- Contrast the C-heavy testing surface in `.claude/skills/testing/SKILL.md`
  (core's `pg_regress` / isolationtester / TAP `Test::More`): pgTAP is the
  *in-database* analog of core's out-of-process TAP suite.
- The "extension is only an install script" end of the spectrum whose opposite
  pole is `[[orioledb]]`/`[[pgrx]]` (fork-deep C). Cf. `[[pgmq]]`,
  `[[index_advisor]]`, `[[temporal_tables]]` for other pure-SQL / thin-C exts.

## Sources

- `pgtap.sql.in` → HTTP 200 (11520 lines; `plan`/`no_plan`/`_get`/`_set`/`_add`
  state machine :25-233, `ok`/`add_result` :162-508, `throws_ok` :657-741,
  `has_table` family :1014-1035, `findfuncs` :6592-6623, `_runner` :6699-6843,
  `runtests` :6846-6870 deep-read; the ~10k lines of intervening assertion
  functions skimmed as homogeneous `ok`-wrappers).
- `README.md` → HTTP 200 (153 lines; purpose, TAP framing, build/installcheck,
  "cannot be installed remotely").
- `pgtap.control` → HTTP 200 (6 lines; `requires = plpgsql`, `relocatable`,
  `superuser = false`).
- `Makefile` → HTTP 200 (510 lines; `.sql.in` templating + version gate — read
  for the build-time-generation claim).

All cites `[verified-by-code]` against the fetched `pgtap.sql.in`/`.control`
except the end-user TAP-harness workflow (`[from-README]`) and the
`.sql.in`-is-version-templated framing (`[inferred]` from the suffix + Makefile
gate). `pgtap.c` was probed and is **404** — there is no C in this extension,
which is the point.
