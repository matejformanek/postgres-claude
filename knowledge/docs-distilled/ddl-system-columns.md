---
source_url: https://www.postgresql.org/docs/current/ddl-system-columns.html
fetched_at: 2026-07-11T19:54:35Z
anchor_sha: 54cd6fc83176d7c03abf95554aef26b0b24acc7d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "5.5 System Columns"
---

# Docs distilled — System Columns (ddl-system-columns)

The six implicit columns every table carries (`tableoid`, `xmin`, `cmin`,
`xmax`, `cmax`, `ctid`). This page is the user-facing face of the **heap tuple
header** — most of these columns are literal reads of `HeapTupleHeaderData`
fields, which is why they matter to a backend hacker.

## Non-obvious claims

- **Five of the six columns are physical tuple-header reads, not derived
  values.** `xmin` → `HeapTupleFields.t_xmin`, `xmax` → `t_xmax`, and
  `cmin`/`cmax` both alias `t_field3.t_cid`; `ctid` is the tuple's own
  `t_ctid`. [verified-by-code] `src/include/access/htup_details.h:124` (t_xmin),
  `:125` (t_xmax), `:129` (t_cid), `:161` (t_ctid).
- **`cmin` and `cmax` occupy the *same* physical field.** Both map to the
  single `t_cid` slot in the tuple header's `t_field3` union; when a tuple is
  both inserted and deleted by commands in the same transaction, the two CIDs
  are packed via a **combo CID** and the header sets the `HEAP_COMBOCID`
  infomask bit. [verified-by-code] `htup_details.h:129` (`t_cid` /
  `t_xvac` union), `:195` (`HEAP_COMBOCID`). The docs frame this only as
  "cmin/cmax overlay the same field". [from-docs]
- **`t_field3` is a three-way union**: `t_cid` (the CID exposed as cmin/cmax)
  *or* `t_xvac` (old-style `VACUUM FULL` xid). So a tuple never simultaneously
  carries a live command-id and a VACUUM-FULL xid. [verified-by-code]
  `htup_details.h:129-131`.
- **`ctid` is volatile and must not be used as a stable row identifier.** It is
  a `(block, offset)` `ItemPointer`, and "a row's `ctid` will change if it is
  updated or moved by `VACUUM FULL`. Therefore `ctid` should not be used as a
  row identifier." Use a primary key. [from-docs]
- **`t_ctid` does not always point at *this* tuple** — for an updated row it
  points forward to the *newer* version (the update chain / HOT chain link),
  which is how the executor walks to the live tuple. [verified-by-code]
  `htup_details.h:161` comment: "current TID of this or newer tuple".
- **A visible row can carry a non-zero `xmax`.** "That usually indicates that
  the deleting transaction hasn't committed yet, or that an attempted deletion
  was rolled back." `xmax` also doubles as the *locking* xid (or a MultiXactId
  when `HEAP_XMAX_IS_MULTI` is set), not only the deleting xid. [from-docs] +
  [verified-by-code] `htup_details.h:125` ("deleting or locking xact ID"),
  `:209` (`HEAP_XMAX_IS_MULTI`).
- **`tableoid` is the only way to tell which physical table a row came from**
  in a partitioned or inheritance query; join it against `pg_class.oid`. It is
  synthesized from the scanned relation, not stored per-tuple. [from-docs]
- **32-bit wraparound caveats are baked into these columns.** Both xids and
  CIDs are 32-bit; "it is unwise … to depend on the uniqueness of transaction
  IDs over the long term (more than one billion transactions)", and there is a
  hard ceiling of 2³² SQL *commands* (not rows) per transaction — and "only
  commands that actually modify the database contents will consume a command
  identifier." [from-docs]

## Links into corpus

- [[knowledge/files/src/include/access/htup_details.h.md]] — the tuple-header
  struct these columns read from (`HeapTupleFields`, `t_field3` union, infomask
  bits).
- [[knowledge/subsystems/access-heap.md]] — heap AM; MVCC visibility uses
  xmin/xmax/cmin/cmax + infomask.
- [[knowledge/docs-distilled/storage-page-layout.md]] — ItemPointer / line
  pointer layout behind `ctid`.
- [[knowledge/docs-distilled/storage-hot.md]] — HOT update chains, the reason
  `t_ctid` forward-links.
- [[knowledge/docs-distilled/transaction-id.md]] + [[knowledge/docs-distilled/mvcc.md]]
  — xid semantics + wraparound behind `xmin`/`xmax`.
- [[knowledge/data-structures/multixactid.md]] — `xmax`-as-MultiXactId when
  `HEAP_XMAX_IS_MULTI`.
