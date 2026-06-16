# `contrib/pg_plan_advice/pg_plan_advice.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~74
- **Source:** `source/contrib/pg_plan_advice/pg_plan_advice.h`

Public header — declares the five feedback bits, the advisor-hook function
pointer typedef, the GUC `extern`s, and the three `PGDLLEXPORT` functions
that other loadable modules can call to participate in advice-generation /
advice-overriding. [verified-by-code]

## API / entry points

- `PGPA_FB_*` flag macros (lines 41-45): `PGPA_FB_MATCH_PARTIAL` (0x0001),
  `PGPA_FB_MATCH_FULL` (0x0002), `PGPA_FB_INAPPLICABLE` (0x0004),
  `PGPA_FB_CONFLICTING` (0x0008), `PGPA_FB_FAILED` (0x0010). Used as bits
  in `pgpa_trove_entry.flags` and surfaced via `Supplied Plan Advice` in
  EXPLAIN output. [verified-by-code]
- `pg_plan_advice_advisor_hook` typedef (line 48): function pointer signature
  for hooks plugged via `pg_plan_advice_add_advisor`. Receives `PlannerGlobal*`,
  `Query*`, query string, cursor options, and the `ExplainState*`; returns
  an advice string or NULL. [verified-by-code]
- `pg_plan_advice_add_advisor`, `pg_plan_advice_remove_advisor`,
  `pg_plan_advice_request_advice_generation` — see `pg_plan_advice.c` doc.
  All `PGDLLEXPORT`. [verified-by-code]
- `pg_plan_advice_get_mcxt`, `pg_plan_advice_should_explain`,
  `pg_plan_advice_get_supplied_query_advice` — internal helpers shared across
  this contrib's `.c` files (not PGDLLEXPORT). [verified-by-code]

## Notable invariants / details

- The header documents that `PGPA_FB_INAPPLICABLE` being set does NOT mean the
  advice had no effect — only that it doesn't properly apply (e.g.
  `INDEX_SCAN(foo bar_idx)` where `bar_idx` doesn't exist on foo). [from-comment]
- `PGPA_FB_CONFLICTING` example given in header: `JOIN_ORDER(a b)` vs
  `HASH_JOIN(a)` — the former requires `a` outer, the latter requires `a` inner.
  [from-comment]
- The flag values are bit positions; the file does not use a `pg_attribute_aligned`
  or any packed/explicit-storage decoration. Stored as `int` in
  `pgpa_trove_entry.flags`. [verified-by-code]

## Potential issues

- `pg_plan_advice.h:41-45` — flags are exposed publicly but the canonical
  flag-printer `pgpa_trove_append_flags` is not declared here. A third-party
  advisor that wants to log feedback bits has to reach into `pgpa_trove.h`.
  [ISSUE-style: API surface split awkwardly between this header and
  `pgpa_trove.h` (nit)]
- `pg_plan_advice.h:46-52` — the advisor hook receives an `ExplainState*` so
  a hook can adjust behavior under `EXPLAIN`, but it is *not* told whether the
  caller intends to use the result, only what `pg_plan_advice` itself does.
  [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->
