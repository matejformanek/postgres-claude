# nodeTidrangescan.c

- **Source:** `source/src/backend/executor/nodeTidrangescan.c` (≈530 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Sibling of nodeTidscan, but for **range** predicates over CTID
(`ctid > '(100,0)'`, `ctid <= '(200,16)'`). Used for partial relation scans
where the block range can be derived from the qual. Particularly useful
for chunked processing (`pg_repack`, custom range jobs) and parallel
scanning at the TID level.

## Mechanics

Init: classifies tidquals into a `mintid` / `maxtid` pair via `IsCTIDVar`
macro test (`:21+`). ExecTidRangeScan calls `table_relation_scan_tid_range`
which the heap AM (`heapam_handler`) implements as a block-bounded seqscan.

## Parallel

Supports parallel scan using `ParallelTableScanDesc` like SeqScan, but
restricted to the (mintid, maxtid) block range.

## Tags

- [verified-by-code] IsCTIDVar test + table_relation_scan_tid_range usage.
- [from-comment] interface comment.
