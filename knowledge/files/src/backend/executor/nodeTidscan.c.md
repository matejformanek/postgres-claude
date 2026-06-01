# nodeTidscan.c

- **Source:** `source/src/backend/executor/nodeTidscan.c` (≈460 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Fetches a small set of rows from a heap by **known CTIDs** — generated when
the qual is `ctid = ?` or `ctid IN (...)` (or `WHERE CURRENT OF cursor`).
The planner picks this when the qual reduces to a tiny set of TIDs and
saves both heap and index work. [from-comment INTERFACE]

## Mechanics

Init: walks `tidquals` to extract ItemPointer values (`TidExprState[]`),
which may be constants, Params, or arrays. ExecTidScan collects them into
an array, sorts (`qsort`+`qunique` to dedupe), and iterates via
`table_tuple_fetch_row_version`.

## Multiple TIDs and ORDER

After de-dup, TIDs are returned in BlockNumber order to amortize buffer
reads. Caller must not assume rows arrive in any particular logical order.

## Tags

- [verified-by-code] qunique deduplication usage.
- [from-comment] INTERFACE list.
