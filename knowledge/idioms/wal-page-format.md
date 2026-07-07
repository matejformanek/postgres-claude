# WAL page format — XLogPageHeader + record framing

WAL records aren't stored individually on disk — they're
packed into **WAL pages** (default 8KB matching the heap
page size). Each WAL page begins with a header (`XLogPageHeader`)
that lets crash recovery distinguish complete from torn pages,
and identifies which WAL segment file the page belongs to.
Understanding this format matters for anyone touching the
xlog reader or writer.

Anchors:
- `source/src/include/access/xlog_internal.h:37-90` —
  page-header structs [verified-by-code]
- `knowledge/idioms/wal-record-construction.md` — record
  construction (the level above page format)
- `knowledge/idioms/xlog-region-replay.md` — record replay
  (the level above page format)
- `knowledge/subsystems/access-transam.md` — xlog subsystem

## The short page header

[verified-by-code `xlog_internal.h:37-50`]

```c
typedef struct XLogPageHeaderData
{
    uint16        xlp_magic;       /* magic value (constant) */
    uint16        xlp_info;        /* flag bits */
    TimeLineID    xlp_tli;         /* timeline ID */
    XLogRecPtr    xlp_pageaddr;    /* LSN of this page's start */
    uint32        xlp_rem_len;     /* length of continuation, if any */
} XLogPageHeaderData;
```

Every WAL page starts with this 24-byte header. The magic
identifies it as a WAL page (catches torn writes, mis-routed
reads). The page-addr lets crash recovery confirm the page
is at the expected position.

`xlp_rem_len` carries continuation length when a record
spans page boundaries (which most large records do).

## The long page header

[verified-by-code `xlog_internal.h:52-72`]

When `XLP_LONG_HEADER` flag is set (`xlp_info & 0x0002`),
the page header has extra fields:

```c
typedef struct XLogLongPageHeaderData
{
    XLogPageHeaderData std;        /* the short header */
    uint64             xlp_sysid;  /* system ID, for cross-check */
    uint32             xlp_seg_size;       /* WAL segment size */
    uint32             xlp_xlog_blcksz;    /* WAL block size */
} XLogLongPageHeaderData;
```

Long headers appear on the **first page of each WAL
segment file**. Carrying sysid + segment + blcksz lets
recovery sanity-check that the WAL belongs to this cluster
with the expected build configuration.

If you copy WAL from a different cluster and try to replay,
the long header's sysid mismatch is the catch.

## The page flags

[verified-by-code `xlog_internal.h:75-90`]

| Flag | Value | Meaning |
|---|---|---|
| `XLP_FIRST_IS_CONTRECORD` | 0x0001 | Page starts with a continuation of the previous page's record |
| `XLP_LONG_HEADER` | 0x0002 | Long header (first page of segment) |
| `XLP_BKP_REMOVABLE` | 0x0004 | Full-page-images on this page can be removed safely (post-checkpoint flag) |
| `XLP_FIRST_IS_OVERWRITE_CONTRECORD` | 0x0008 | Continuation overrides previous (rare; CRASH-RECOVERY case) |

The `FIRST_IS_CONTRECORD` flag is what makes WAL readers
cope with record-spanning-page-boundary. The reader checks:
"is the first thing on this page a continuation? then I
should resume the partial record from last page."

## The record framing

WAL records themselves have headers:

```
XLogRecord {
    xl_tot_len    uint32  /* total record length */
    xl_xid        TransactionId  /* xact that emitted */
    xl_prev       XLogRecPtr     /* LSN of previous record */
    xl_info       uint8          /* rmgr-specific info bits */
    xl_rmid       RmgrId         /* resource manager */
    xl_crc        uint32         /* CRC32C over record */
}
... per-block headers and data ...
```

The `xl_prev` field is the **backward-linked-list** trick —
each record points at its predecessor. Crash recovery walks
backward from the last successful record to find the last
checkpoint.

## The page-cross record continuation

A WAL record longer than (page size - page header) spans
multiple pages. The first page contains the record header +
as much data as fits; subsequent pages have a continuation
header with `XLP_FIRST_IS_CONTRECORD` set.

The reader code in `xlogreader.c` reassembles spanning
records transparently.

## The segment files

WAL segments are 16MB by default (configurable at initdb via
`--wal-segsize`). Each segment is `wal_segsize / xlog_blcksz`
pages = 2048 pages × 8KB = 16MB.

Segment filenames encode timeline + segment number:

```
000000010000000200000003
^^^^^^^^         timeline 1
        ^^^^^^^^^^^^^^^^ logical position
```

Used by:
- `pg_walfile_name(lsn)` — convert LSN to segment filename.
- `pg_walfile_name_offset(lsn)` — same + byte offset within
  the segment.

## CRC checking

Every WAL record has a CRC32C checksum computed over the
record's data. On read, the CRC is verified; mismatch =
torn write or storage corruption. Recovery stops at the
first CRC mismatch — that's the "valid WAL up to here"
boundary.

WAL pages don't have a separate page-level CRC; the
per-record CRCs cover the data.

## Common review-time concerns

- **Don't directly read WAL files** — use `xlogreader.c`
  (or the new `pg_walinspect` for inspection). Hand-parsing
  the format misses edge cases.
- **Magic + sysid mismatches indicate WAL from a different
  cluster** — never replay them.
- **`XLP_FIRST_IS_CONTRECORD` handling is mandatory** for
  any WAL-reading code.
- **The segment size is fixed at initdb time** — changing
  it requires a fresh cluster.
- **`xlp_rem_len` zero on a non-CONTRECORD page** — the
  page starts a fresh record at its data area.

## Invariants

- **[INV-1]** Every WAL page begins with `XLogPageHeaderData`.
- **[INV-2]** First page of each segment has the long
  header (with sysid + segment size + block size).
- **[INV-3]** Records spanning page boundaries use
  `XLP_FIRST_IS_CONTRECORD` on the second page.
- **[INV-4]** Each WAL record has its own CRC32C; mismatch
  is the recovery stop boundary.
- **[INV-5]** Segment size set at initdb; can't change for
  the cluster's lifetime.

## Useful greps

- The header struct:
  `grep -A30 'XLogPageHeaderData' source/src/include/access/xlog_internal.h | head -35`
- All flag bits:
  `grep -n 'XLP_' source/src/include/access/xlog_internal.h`
- The reader's CONTRECORD logic:
  `grep -n 'XLP_FIRST_IS_CONTRECORD' source/src/backend/access/transam/xlogreader.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/xlogreader.c`](../files/src/backend/access/transam/xlogreader.c.md) | — | page-level parser |
| [`src/include/access/xlog_internal.h`](../files/src/include/access/xlog_internal.h.md) | 37 | page-header structs |
| [`src/include/access/xlog_internal.h`](../files/src/include/access/xlog_internal.h.md) | — | page-header types |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-index-am`](../scenarios/add-new-index-am.md)
- [`add-new-wal-record`](../scenarios/add-new-wal-record.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/wal-record-construction.md` — records
  packed into pages.
- `knowledge/idioms/xlog-region-replay.md` — records read
  back during recovery.
- `knowledge/idioms/crash-recovery-startup.md` —
  StartupXLOG consumes WAL pages.
- `knowledge/data-structures/xlogreaderstate.md` — the
  reader state that parses pages.
- `knowledge/subsystems/contrib-pg_walinspect.md` — SQL
  inspector for WAL records.
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL skill.
- `source/src/include/access/xlog_internal.h` — page-header
  types.
- `source/src/backend/access/transam/xlogreader.c` —
  page-level parser.
