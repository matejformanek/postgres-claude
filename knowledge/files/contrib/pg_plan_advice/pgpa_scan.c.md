# `contrib/pg_plan_advice/pgpa_scan.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~289
- **Source:** `source/contrib/pg_plan_advice/pgpa_scan.c`

Analyzes a single Plan node and classifies it into a `pgpa_scan` with one of
the `pgpa_scan_strategy` values. Handles the unusual cases — elided
Append/MergeAppend nodes (representing partitionwise scans/joins after a
single child survived setrefs), foreign scans across multiple relations,
scan-level Materialize wrappers around non-repeatable tablesamples — and
pulls up child Append/MergeAppend `child_append_relid_sets` as separate
scans. [verified-by-code]

## API / entry points

- `pgpa_build_scan(walker, plan, elided_node, beneath_any_gather,
  within_join_problem)` (line 44): main builder. Determines strategy +
  relids, builds child append scans, registers the result in
  `walker->scans[strategy]` and (if not beneath Gather, not Append/MergeAppend)
  also adds the relids to `walker->no_gather_scans`. Returns NULL for nodes
  with no RTIs (which throws ERROR if `within_join_problem`). [verified-by-code]
- `pgpa_make_scan` (line 238): static helper — alloc a `pgpa_scan`, append
  to the strategy-indexed walker list. [verified-by-code]
- `unique_nonjoin_rtekind(relids, rtable)` (line 260): static — assert that
  all non-JOIN RTEs in the set share an rtekind; return it. Used to
  distinguish partitionwise (RTE_RELATION) from setop (RTE_SUBQUERY) over
  an Append/MergeAppend. ERRORs on mismatched kinds or all-JOIN sets.
  [verified-by-code]

## Notable invariants / details

- `pgpa_build_scan` has three top-level branches based on plan shape:
  - **Has elided_node** (line 54): the node had something stacked on top in
    the original plan tree (e.g. an Append/MergeAppend before partitionwise
    pruning, or a SubqueryScan). Strategy is `PARTITIONWISE` iff
    Append/MergeAppend over RTE_RELATION; otherwise `ORDINARY`.
  - **Has scanrelid** (line 89): a single-relation scan node. Maps NodeTag
    → strategy directly. Default for unrecognized → `ORDINARY` (covers
    single-rel ForeignScan, FunctionScan, etc.).
  - **Has multi-relation relids via `pgpa_relids`** (line 134): multi-table
    ForeignScan (→ `FOREIGN`), Append/MergeAppend (→ `PARTITIONWISE` if all
    children are relations).
  [verified-by-code]
- Scan-level Materialize (line 124) is a narrow exception — only triggered
  by non-repeatable tablesample. Treated as a single-relation `ORDINARY`
  scan with relid taken from the Materialize's child.
  See `set_tablesample_rel_pathlist`. [from-comment]
- For Append/MergeAppend, `child_append_relid_sets` (line 162-164, 173-175)
  represents PullUp-merged child Append nodes — each becomes a separate
  `pgpa_scan` with the same strategy but a child relids subset.
  [verified-by-code]
- `no_gather_scans` accumulates the set of relids that are NOT under any
  Gather. Append/MergeAppend nodes are skipped (line 225) because the
  underlying scan will be visited and added there. [verified-by-code]
- Comment line 86: "Join RTIs can be present, but advice never refers to
  them." Hence `pgpa_filter_out_join_relids` is applied to both the elided
  case (line 87) and the multi-rel case (line 184). [from-comment]

## Potential issues

- `pgpa_scan.c:209-212` — when `relids == NULL`, throws ERROR only inside
  a join problem; outside, silently returns NULL. The split is intentional
  but worth documenting. [from-comment]
- `pgpa_scan.c:280-283` — `elog(ERROR, "rtekind mismatch: %d vs. %d")`
  triggers if an Append/MergeAppend mixes RTE kinds. Defensive; should
  never happen in core PG. A pluggable executor or custom RTE might.
  [ISSUE-correctness: extensibility limitation around mixed-rtekind
  Append (maybe)]
- `pgpa_scan.c:155-156` — `unique_nonjoin_rtekind` is called eagerly inside
  the Append branch even when we already know it's PARTITIONWISE — but
  the result is used for the conditional, so it's needed. No redundant
  compute. [verified-by-code]
- `pgpa_scan.c:113-121` — `default: strategy = PGPA_SCAN_ORDINARY;` catches
  single-relation ForeignScan as "ordinary"; multi-relation handled in the
  next branch. This split is documented inline. [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_plan_advice.md](../../../subsystems/contrib-pg_plan_advice.md)
