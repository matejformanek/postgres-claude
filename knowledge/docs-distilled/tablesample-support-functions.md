---
source_url: https://www.postgresql.org/docs/current/tablesample-support-functions.html
chapter: "59.1 Sampling Method Support Functions"
fetched_at: 2026-06-15
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# TABLESAMPLE method support functions (`TsmRoutine`) — §59.1

Distilled from §59.1. Parent:
[[knowledge/docs-distilled/tablesample-method.md]]. The TSM handler
returns a palloc'd `TsmRoutine` of function pointers — same
handler-returns-struct idiom as index AM / table AM / FDW.

## Non-obvious claims

- `SampleScanGetSampleSize(root, baserel, paramexprs, *pages, *tuples)`
  (required) runs at *planning* time and **must not fail** — it has to
  return page/tuple estimates even when the TABLESAMPLE argument
  expressions can't be reduced to constants (use
  `estimate_expression_value()` to try). [from-docs §59.1]
- `InitSampleScan` is optional; if present it runs before
  `BeginSampleScan`, can `palloc` and stash state in `node->tsm_state`,
  but **the scan descriptor `node->ss.ss_currentScanDesc` is not yet set
  up** there. Honor `EXEC_FLAG_EXPLAIN_ONLY` (minimum work only). Omit it
  and `BeginSampleScan` must do all init. [from-docs §59.1]
- `BeginSampleScan(node, params, nparams, seed)` (required) is called
  just before the first tuple AND again on every rescan. `seed` is the
  hash of the `REPEATABLE` value if given, else a fresh `random()` — this
  is the mechanism behind `REPEATABLE` determinism. [from-docs §59.1]
- **Two performance knobs the method may flip in `BeginSampleScan`:**
  `node->use_bulkread` (default true → set false when reading only a
  small fraction of pages, to avoid the bulk-read ring buffer) and
  `node->use_pagemode` (default true → set false when selecting few
  tuples per page, to skip whole-page visibility checks). [from-docs §59.1]
- **The prefetch landmine in `NextSampleTuple`:** its `blockno` argument
  is from *some previous* `NextSampleBlock` call, NOT necessarily the
  most recent one — core may call `NextSampleBlock` ahead to drive
  prefetch. So `NextSampleTuple` must not assume `blockno` equals the
  last block handed out. It *may* assume consecutive calls stay on one
  page until it returns `InvalidOffsetNumber`. [from-docs §59.1]
- `NextSampleBlock` is optional: return `InvalidBlockNumber` when done;
  if the pointer is NULL, **core performs a sequential full scan with
  synchronized-scan support**, so a method that omits it cannot assume a
  consistent page-visit order. [from-docs §59.1]
- **The method is not told which offsets are live.** `NextSampleTuple`
  may return offsets for missing/invisible tuples; core silently ignores
  those requests *without introducing sampling bias*. A method can
  consult `node->donetuples` if it wants to know how many real tuples it
  has actually returned. [from-docs §59.1]
- A TSM marked `repeatable_across_scans` must, on a fresh
  `BeginSampleScan` with unchanged params+seed, select the **identical
  set of tuples** — required for correct rescans (e.g. as the inner side
  of a nested loop). [from-docs §59.1]
- `EndSampleScan` is optional and only matters for external resources
  (palloc'd memory is reclaimed automatically). [from-docs §59.1]

## Links into corpus

- Parent chapter: [[knowledge/docs-distilled/tablesample-method.md]].
- Source struct: [[knowledge/files/src/include/access/tsmapi.h.md]]
  (`TsmRoutine`).
- Built-in methods (reference implementations):
  [[knowledge/files/src/backend/access/tablesample/system.c.md]]
  (block-level BERNOULLI/SYSTEM split),
  [[knowledge/files/src/backend/access/tablesample/bernoulli.c.md]],
  [[knowledge/files/src/backend/access/tablesample/tablesample.c.md]].
- Other handler-returns-struct AMs: [[knowledge/docs-distilled/index-api.md]],
  [[knowledge/docs-distilled/tableam.md]],
  [[knowledge/docs-distilled/fdw-callbacks.md]].

## Caveats / verification

- `[from-docs §59.1]`. The `repeatable_across_method_calls` flag is named
  in the chapter title but the page body did not elaborate it; verify
  both `repeatable_across_*` flags against
  `source/src/include/access/tsmapi.h` at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735`.
