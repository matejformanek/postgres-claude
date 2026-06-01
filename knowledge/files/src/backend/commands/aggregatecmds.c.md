# aggregatecmds.c

- **Source path:** `source/src/backend/commands/aggregatecmds.c`
- **Lines:** 493
- **Last verified commit:** `ef6a95c7c64`

## Purpose

CREATE AGGREGATE entry; the DefineAggregate routine "takes the parse tree and picks out the appropriate arguments/flags, passing the results to the AggregateCreate routine (in src/backend/catalog), which does the actual catalog-munging." [from-comment, aggregatecmds.c:3-15]

## Public surface

- `DefineAggregate` — parse the `( BASETYPE | SFUNC | STYPE | FINALFUNC | INITCOND | MSFUNC | MINVFUNC | MSTYPE | … )` option soup, validate consistency (e.g. a moving-aggregate must define MSFUNC+MINVFUNC+MSTYPE; ordered-set must define direct-args), then call `AggregateCreate` which writes pg_aggregate + pg_proc rows.

## Moving aggregates

`MSFUNC` + `MINVFUNC` enable the "window-frame moving-aggregate optimisation" — the executor can update the aggregate by adding a new row entering the frame and inverting out a row leaving the frame, instead of recomputing from scratch. Required for `OVER (ROWS BETWEEN N PRECEDING AND M FOLLOWING)` to be fast.

## Confidence tag tally

`[verified-by-code]=2 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
