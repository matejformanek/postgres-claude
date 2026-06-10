---
source_url: https://www.postgresql.org/docs/current/xfunc-volatility.html
fetched_at: 2026-06-09T20:48:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Function Volatility Categories

The contract a function's `VOLATILE`/`STABLE`/`IMMUTABLE` label makes *to the
planner*. Mislabeling is a correctness bug, not a performance hint — this page
is the canonical statement of what each category promises.

## The three contracts

- **`VOLATILE` (the default):** may do anything, including writing the DB, and
  may return different results on successive calls with the same args. The
  planner assumes nothing and **re-evaluates at every row**. Cannot be hoisted
  into an index-scan bound. Gets a **fresh snapshot at the start of each query
  it runs**, so it **sees the calling command's own changes**. [from-docs]
- **`STABLE`:** must not modify the DB; returns the **same result for the same
  args within a single statement**. The planner may collapse repeated calls to
  one and **may use it in an index-scan condition** (the comparison value is
  computed once, not per row). Uses the **calling query's snapshot**, so it does
  **not** see the command's own changes. [from-docs]
- **`IMMUTABLE`:** must not modify the DB; returns the **same result forever**
  for given args. The planner may **pre-evaluate it at plan time when args are
  constants** — e.g. `WHERE x = 2 + 2` folds to `WHERE x = 4` because integer
  `+` is `IMMUTABLE`. [from-docs]

## The classic mislabels (correctness hazards)

- **`current_timestamp` & friends are `STABLE`, never `IMMUTABLE`** — constant
  within a transaction, but they change between transactions. [from-docs]
- **Anything that varies *within* a query — `random()`, `currval()`,
  `timeofday()` — MUST be `VOLATILE`**, or the planner will fold away calls it
  needed to repeat. [from-docs]
- **Functions reading a GUC (e.g. a timestamp depending on `TimeZone`) must be
  `STABLE`, not `IMMUTABLE`**, since the result depends on session config. [from-docs]
- **Falsely marking `IMMUTABLE`** lets the value fold to a constant at plan
  time, so a **cached/prepared plan reuses a stale value** on later executions —
  a notorious PL/pgSQL footgun. [from-docs]

## Why the snapshot rule matters

`VOLATILE` functions take a fresh snapshot per query they execute, so they
observe concurrent and self-made changes; `STABLE`/`IMMUTABLE` ride the calling
query's snapshot and see a frozen view. That's why a `STABLE` function of pure
`SELECT`s is safe against concurrent writers — it sees a consistent point-in-time. [from-docs]
[cross: [[knowledge/architecture/mvcc.md]], [[knowledge/subsystems/access-transam.md]]]

## SQL-body restriction (and its hole)

PG enforces that `STABLE`/`IMMUTABLE` bodies contain **no SQL but `SELECT`**.
This is *not* bulletproof: such a function can still call a `VOLATILE` function
that writes — but those writes stay invisible to the caller's frozen snapshot. [from-docs]

## Operational rule

**Label with the strictest category that is still truthful.** The
`STABLE`-vs-`IMMUTABLE` gap barely matters for one-shot interactive SQL but is
decisive once plans are saved and reused (prepared statements, PL/pgSQL, cached
plans, generic plans). [from-docs]

## Links into corpus
- [[knowledge/subsystems/optimizer.md]] — constant-folding + expression preprocessing where this is consumed.
- [[knowledge/architecture/planner.md]] — where volatility gates index/hoisting decisions.
- [[knowledge/docs-distilled/xfunc-c.md]] — the C-function authoring companion.
- [[knowledge/files/src/include/catalog/pg_proc.h.md]] — `provolatile` ('i'/'s'/'v') column storing the label.
- Skills: `fmgr-and-spi` (function entry points), `catalog-conventions` (`provolatile` in pg_proc.dat).

## Gaps / follow-ups
- Parallel-safety (`proparallel`: safe/restricted/unsafe) is an orthogonal axis
  documented in `parallel-safety`, not here — don't conflate the two labels.
- The exact planner sites that test `provolatile` (`contain_volatile_functions`,
  `eval_const_expressions`) live in the optimizer per-file docs.
