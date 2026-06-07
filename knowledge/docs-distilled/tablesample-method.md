---
source_url: https://www.postgresql.org/docs/current/tablesample-method.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
note: the per-callback contract is taken from source/src/include/access/tsmapi.h at the anchor SHA (the docs chapter defers the callback list to §59.1 tablesample-support-functions, which did not render through the fetch pipeline).
---

# Docs distilled — Chapter 61: Writing a Table Sampling Method

The plug-in behind `TABLESAMPLE <method>(...)`. A method is a single SQL function
returning `tsm_handler`, which yields a `TsmRoutine` of callbacks. Built-ins are
`SYSTEM` (block-level Bernoulli) and `BERNOULLI` (row-level). The interesting
design points are the **two-level block-then-tuple sampling loop** and the **two
repeatability flags** that constrain what plans the planner may choose.

## Registration

- A method is `method_name(internal) RETURNS tsm_handler`; the `internal` dummy
  arg blocks direct SQL invocation. The function `palloc`s and returns a
  `TsmRoutine`. [from-docs]
  [verified-by-code, source/src/include/access/tsmapi.h:55 — `typedef struct
  TsmRoutine`]
- Built-in methods live in `src/backend/access/tablesample`; add-on examples in
  `contrib`. The struct is declared in `tsmapi.h`. [from-docs]

## `TsmRoutine` fields (tsmapi.h:55)

- `NodeTag type;` (`:57`). [verified-by-code]
- `List *parameterTypes;` (`:60`) — OIDs of the args the `TABLESAMPLE` clause
  accepts. Built-ins use `FLOAT4OID` (the percentage). This is how the parser
  type-checks the method's arguments. [verified-by-code] [from-docs]
- `bool repeatable_across_queries;` (`:63`) — if false, the `REPEATABLE` seed
  clause is **rejected** for this method (it can't promise the same sample in a
  later query). [from-docs] [verified-by-code]
- `bool repeatable_across_scans;` (`:63`) — if false, **the planner will not pick
  plans that scan the sampled table more than once** (e.g. inner side of a
  nested loop), because a re-scan would yield a different sample and corrupt
  results. This flag directly constrains the path space. [from-docs]
  [verified-by-code]

## The callbacks (tsmapi.h:24-73)

- `SampleScanGetSampleSize(root, baserel, paramexprs, *pages, *tuples)` (`:24-26`,
  field `:66`) — **planner-time** estimate of how many pages/tuples the sample
  will touch; feeds costing. Required. [verified-by-code]
- `InitSampleScan(node, eflags)` (`:28-29`, field `:69`) — optional
  (`/* can be NULL */`); executor init of method-private state. [verified-by-code]
- `BeginSampleScan(node, params, nparams, seed)` (`:31-33`, field `:70`) — start a
  scan with the evaluated parameter Datums and the `REPEATABLE` seed. Required.
  [verified-by-code]
- `NextSampleBlock(node, nblocks)` (`:35-36`, field `:71`) — **optional
  (`/* can be NULL */`)**; return the next block to examine. If NULL, the core
  uses the heapam sequential block sampler (scan every block, sample tuples
  within) — i.e. the method only needs `NextSampleTuple`. This is the key
  "you can be lazy" hook: row-level methods like BERNOULLI leave it NULL.
  [verified-by-code] [from-comment]
- `NextSampleTuple(node, blockno, maxoffset)` (`:38-39`, field `:72`) — return the
  next offset to sample within the given block, or `InvalidOffsetNumber` to move
  on. Required. [verified-by-code]
- `EndSampleScan(node)` (`:41-42`, field `:73`) — optional (`/* can be NULL */`);
  teardown. [verified-by-code]

## The two-level sampling model (why two callbacks)

- Sampling is **block-then-tuple**: the executor's `SampleScan` node asks
  `NextSampleBlock` which page to read next, then repeatedly asks
  `NextSampleTuple` which rows on that page to emit. A method that wants
  block-level sampling (SYSTEM) drives `NextSampleBlock`; a method that wants
  per-row sampling (BERNOULLI) leaves `NextSampleBlock` NULL and decides per tuple.
  [inferred from the callback split] [verified-by-code, the NULL-block fallback at
  tsmapi.h:71 comment]
- `seed` (from `REPEATABLE`) is the only determinism input; combined with
  `repeatable_across_queries`/`repeatable_across_scans` it defines whether two
  evaluations can be required to match. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/tableam.md]] — sibling pluggable-callback chapter;
  TABLESAMPLE rides on top of the table AM's block/tuple access.
- [[knowledge/subsystems/executor.md]] — the `SampleScan` executor node that
  drives `NextSampleBlock`/`NextSampleTuple`.
- [[knowledge/docs-distilled/custom-scan.md]] / [[knowledge/docs-distilled/fdwhandler.md]]
  — other "implement a struct of callbacks" extension surfaces.
- access-method-apis skill.

## Gaps / follow-ups

- §59.1 (`tablesample-support-functions.html`, the per-callback prose) did not
  render through the fetch pipeline; the contract above is header-sourced and
  should be re-cross-checked against that page on a future run. No per-file corpus
  doc yet for `src/backend/access/tablesample/{system,bernoulli,tablesample}.c`
  or `src/backend/executor/nodeSamplescan.c`.
