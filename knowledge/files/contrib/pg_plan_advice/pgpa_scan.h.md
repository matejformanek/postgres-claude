# `contrib/pg_plan_advice/pgpa_scan.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~85
- **Source:** `source/contrib/pg_plan_advice/pgpa_scan.h`

Defines the scan strategy enum + the `pgpa_scan` struct. [verified-by-code]

## API / entry points

- `pgpa_scan_strategy` enum (line 55): `ORDINARY`, `SEQ`, `BITMAP_HEAP`,
  `FOREIGN`, `INDEX`, `INDEX_ONLY`, `PARTITIONWISE`, `TID`.
  `NUM_PGPA_SCAN_STRATEGY` macro. [verified-by-code]
- `pgpa_scan` struct (line 73): `plan`, `strategy`, `relids`. [verified-by-code]
- `pgpa_build_scan` declaration. See `pgpa_scan.c` doc.

## Notable invariants / details

- "A 'scan' includes (1) single plan nodes that scan multiple RTIs, such
  as a degenerate Result node that replaces what would otherwise have been
  a join, and (2) Append and MergeAppend nodes implementing a partitionwise
  scan or partitionwise join." — header file comment (lines 6-11) defining
  the scope of "scan" in this module. [from-comment]
- `PGPA_SCAN_ORDINARY` is the catch-all for cases where no meaningful planner
  decision was made (subquery scans, values scans, single-rel foreign scans,
  Result nodes for provably-empty joins). The user-facing advice tag
  `ORDINARY_SCAN` is emitted but the README warns this case "should not be
  emitted" — and `pgpa_output.c:152` confirms the skip. [from-comment]
- `PGPA_SCAN_PARTITIONWISE` covers BOTH partitionwise scans of a single
  partitioned table AND partitionwise joins. The latter is treated as a
  "scan" because its internal structure is opaque to this module — once a
  partitionwise join is chosen, there's no inner/outer to advise on at
  this level. [from-comment]
- `PGPA_SCAN_FOREIGN` requires >1 relation; single-rel foreign scans collapse
  to `ORDINARY`. [from-comment]

## Potential issues

- `pgpa_scan.h:62-66` — "update NUM_PGPA_SCAN_STRATEGY if you add anything
  here" — same fragile-comment pattern as elsewhere. [ISSUE-style:
  comment-only enum-cardinality sync (nit)]
- `pgpa_scan.h:30-41` — comment for ORDINARY mentions "Result nodes that
  correspond to scans or even joins that are proved empty" — those wouldn't
  be re-provably-empty next time, but no advice is generated for them.
  The chosen tradeoff is documented. [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->
