# Issues — `contrib/tcn`

Per-subsystem issue register for **tcn**, the 1-function backend
extension that fires LISTEN/NOTIFY payloads for AFTER-ROW
triggers. Created 2026-06-11 by A21 sweep.

**Parent doc:** `knowledge/files/contrib/tcn/tcn.c.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | contrib/tcn/tcn.c:178-181 | correctness | likely | Missing/invalid PK turns trigger into row-level ERROR for every DML | open | knowledge/files/contrib/tcn/tcn.c.md §Potential issues |
| 2026-06-11 | contrib/tcn/tcn.c:165 | leak | maybe | SPI_getvalue palloc'd strings not pfree'd; bulk-load peak memory | open | knowledge/files/contrib/tcn/tcn.c.md §Potential issues |
| 2026-06-11 | contrib/tcn/tcn.c:168 | correctness | maybe | Unbounded payload size; relies on NOTIFY_PAYLOAD_MAX_LENGTH ereport | open | knowledge/files/contrib/tcn/tcn.c.md §Potential issues |
| 2026-06-11 | contrib/tcn/tcn.c:120-121 | undocumented-invariant | nit | UPDATE always emits OLD PK from tg_trigtuple; not documented | open | knowledge/files/contrib/tcn/tcn.c.md §Potential issues |
| 2026-06-11 | contrib/tcn/tcn.c:130-144 | undocumented-invariant | nit | Relies on "at most one indisprimary index" catalog invariant | open | knowledge/files/contrib/tcn/tcn.c.md §Potential issues |
| 2026-06-11 | contrib/tcn/tcn.c:139-141 | style | nit | "should not happen" elog surfaces internal-style message to user | open | knowledge/files/contrib/tcn/tcn.c.md §Potential issues |
| 2026-06-11 | contrib/tcn/tcn.c:113-114 | doc-drift | nit | Default channel "tcn" not in source comment block | open | knowledge/files/contrib/tcn/tcn.c.md §Potential issues |

## Notes

tcn is a thin demo extension; its main practical use is teaching
the AFTER-ROW + NOTIFY pattern. The PK-required restriction makes
it unsuitable for general-purpose change capture; users wanting
that typically reach for logical decoding (test_decoding pattern)
or pglogical / wal2json.
