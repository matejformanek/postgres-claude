---
slug: money-fx-exchange
plan-status: REJECT
plan-produced-via: pg-feature-plan + pg-patch-review Critic E (mental simulation)
anchor: e18b0cb7344
---

# Plan — money-fx-exchange

## Verdict: REJECT THE DESIGN AS STATED

The COVER's stated design violates a foundational PG invariant.
Our planner's job is not to "implement this as designed" but to
**identify what's wrong, propose the correct shape, and ask the
author to revise.** That output IS the plan.

## Why REJECT (with file:line cites)

### Reason 1 (BLOCKING) — Network I/O in a type output function

The proposed design routes a `libcurl` HTTPS call inside the `money`
type's `out` function (`cash_out` in
`source/src/backend/utils/adt/cash.c`). This violates the type-I/O
function contract:

- **Invariant**: type I/O functions are called from every query path
  that materializes the column — `SELECT`, `COPY OUT`, EXPLAIN ANALYZE
  output, `\d+` describe, ad-hoc casts. They must be:
  1. Side-effect-free (no I/O, no GUC mutation, no shared state writes)
  2. Bounded-time (no blocking on external resources)
  3. CPU-only deterministic given their input

- **Cite**: `source/src/include/fmgr.h:118` — function-call info struct
  has no provision for asynchronous I/O. `source/src/backend/utils/
  fmgr/fmgr.c` shows the call sequence assumes immediate return.
  See also `knowledge/idioms/` — type-I/O contract is implicit in
  most uses.

- **Concrete failure modes if implemented:**
  - `EXPLAIN ANALYZE SELECT col::money FROM big_table` now stalls on
    the first row waiting for `api.frankfurter.app` — pathological
    behavior change.
  - A query in `pg_stats_reset` / autovacuum / catalog scan that
    happens to format a `money` value blocks on external HTTPS.
  - In `pg_dump` output, dumping a `money` column now requires
    network connectivity to a third-party API at restore time.
  - Cache invalidation: how does the planner know rates changed?
  - Backup/restore correctness: a `money` column's text dump is no
    longer reproducible — it depends on the exchange rate at dump
    moment.

- **Reviewer prediction (per persona docs):** Tom Lane will reject
  this in the first round with a one-paragraph explanation. Cite:
  `knowledge/personas/tom-lane.md` "API/ABI back-compatibility"
  + the precedent that `pg_proc.proisstrict` / `provolatile` /
  `proparallel` machinery exists specifically to bound I/O
  function behavior.

### Reason 2 (BLOCKING) — `proparallel` + `provolatile` violations

The `money_out` function is currently `proparallel = 's'` (safe) and
`provolatile = 'i'` (immutable wrt its inputs in the LC_MONETARY
era). Adding network I/O would force:

- `provolatile = 'v'` (volatile) — every call may return different
  output. Breaks plan-cache stability + materialized views.
- `proparallel = 'u'` (unsafe) — parallel workers can't safely make
  network calls coordinated across processes.

Cite: `source/src/include/catalog/pg_proc.dat` for the `money_out`
entry's current annotations.

These flips cascade through the planner — any prepared statement
involving `money` becomes non-cacheable, any parallel scan over a
`money` column serialises through the leader. **Performance
regression for all existing users**, in exchange for an opt-in
feature.

### Reason 3 (BLOCKING) — GUC-controlled output of a stored type

A GUC `money_source_currency` whose value affects the **textual
output** of a stored column violates:

- **Backup/restore correctness**: `pg_dump` runs with whatever GUC
  the user happens to have set. Restoring on a different system
  with a different GUC produces different values.
- **Logical replication**: subscriber and publisher disagree on
  output → row comparison breaks.
- **Catalog stability**: `pg_dump --column-inserts` or any text-
  dump form embeds the formatted value in the DDL.

Cite: similar GUC-vs-stored issues were litigated for
`DateStyle` and `IntervalStyle` over decades —
`source/src/backend/utils/adt/timestamp.c` carries explicit
guards against this kind of dependency for date/time types.
A money cast can't escape it because the stored representation
IS the integer-cents value, not the currency tag.

### Reason 4 (MAJOR) — External-service hard dependency in core

PG core has a hard rule: no required external network services
beyond the build/test infrastructure. The proposal embeds
`api.frankfurter.app` as a hardcoded default. Even "configurable
via GUC" doesn't fix this:

- Air-gapped deployments
- Compliance-constrained deployments (GDPR data-localization,
  ITAR, etc.) — a money column now leaks to a third party
- Operator must explicitly disable; a sane default doesn't exist

Cite: contrast with `dblink` / `postgres_fdw` which are explicitly
**contrib modules** + require explicit superuser configuration
to use any network endpoint.

### Reason 5 (MAJOR) — Currency conversion is not a type-system
problem

Currency conversion is a business-logic problem. PG's type system
is for representing values, not computing them. The right shape is:

- A `currency` enum / domain type + a `money_with_currency`
  composite that stores both amount and currency code, OR
- A contrib extension `currency_rates` that wraps a user-provided
  rate table + helper functions like
  `convert_currency(amount, from, to)` operating on user-managed
  data.

The author's COVER doesn't refute either of these — it just
asserts the in-core, in-type-I/O-function path as the solution.

## The CORRECT shape (what we'd propose)

If the goal is "make the `money` type more useful":

1. **Deprecate the singleton `money` type** in favor of a composite.
   Or:
2. **Add a contrib `currency` extension** with:
   - `currency_pair(text, text)` type
   - `rate_table` regular table the user populates
   - `convert(money, currency_pair)` function — pure, deterministic
   - Optional async background worker to refresh rates from external
     APIs into the rate table (with explicit user opt-in + per-API
     credentials).

This shape keeps PG's invariants intact: type I/O stays
deterministic; the type system stays pure; the external dependency
lives behind explicit user choice.

## What the planner would output as a thread reply

> Thanks for the proposal. Before going further on the patch, I think
> we need to revisit the design — putting libcurl I/O inside
> `money_out` would force `provolatile='v'` + `proparallel='u'` on
> every money-formatting call, breaking plan caching + parallel
> scans for existing users. And a GUC affecting textual output of a
> stored column has the `pg_dump` / logical-rep stability problem
> we've worked through repeatedly for `DateStyle` etc.
>
> Have you considered a contrib extension that takes a user-managed
> rate-table + `convert(money, 'USD', 'SEK')` function instead? That
> keeps the type-I/O contract intact and lets operators control
> network policy explicitly. Happy to sketch it.

This is the plan output. The implementation step is **NOT** to
write code — it's to write the thread reply above.

## What the planner did NOT do

- Did NOT design or write the libcurl-in-money_out implementation.
  The COVER's design is fundamentally wrong; implementing it would
  be teaching a lesson the project explicitly rejects.
- Did NOT write a contrib `currency` extension — outside the scope
  of this thread without the original author's agreement to pivot.
- Did NOT score the original patch's code quality (couldn't fetch
  the patch body anyway).

## Cross-references

- `knowledge/personas/tom-lane.md` — predicted lead-reviewer reflex
- `knowledge/personas/peter-eisentraut.md` — type-system style
- `knowledge/personas/daniel-gustafsson.md` — libcurl knowledge
- `knowledge/personas/noah-misch.md` — security@ + side-effect-in-
  I/O reflex
- `knowledge/calibration/gap-catalog.md` — Phase C catalog (none
  of the 11 items quite fit this case; see skill-gaps.md for new
  catalog candidates)
- `source/src/backend/utils/adt/cash.c` — the touched file
- `source/src/include/fmgr.h` — type-I/O contract
- `source/src/include/catalog/pg_proc.dat` — `money_out` annotations
