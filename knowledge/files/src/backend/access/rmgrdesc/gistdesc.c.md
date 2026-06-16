---
path: src/backend/access/rmgrdesc/gistdesc.c
anchor_sha: 4b0bf0788b0
loc: 111
depth: deep
---

# gistdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/gistdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 111

## Purpose

rmgr descriptor routines for the GiST resource manager (`RM_GIST_ID`,
records from `access/gist/gistxlog.c` / `access/gistxlog.h`). Renders
the 5 GiST WAL opcodes for `pg_waldump`. One small static `out_*`
helper per record type. [from-comment, gistdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `gist_desc(buf, record)` | `gistdesc.c:60` | dispatch on info → one `out_*` helper |
| `gist_identify(info)` | `gistdesc.c:86` | opcode → short name |

## Internal landmarks

- **Per-record `out_*` helpers (gistdesc.c:20-58):**
  `out_gistxlogPageReuse` prints the `rel/blk` + `snapshotConflictHorizon`
  Epoch:Xid (standby page-reuse horizon); `out_gistxlogDelete` and
  `out_gistxlogPageDelete` print delete metadata; `out_gistxlogPageSplit`
  prints `npage`.

## Invariants & gotchas

- **`out_gistxlogPageUpdate` is intentionally empty** (gistdesc.c:20-23)
  — `XLOG_GIST_PAGE_UPDATE` carries its interesting state in the
  registered block data / FPI, not in the main record, so its desc line
  is blank. A reader seeing an empty `PAGE_UPDATE` description in
  `pg_waldump` should not read that as truncation. `[from-code]`
- **`gist_desc` has no `default:`** — unknown opcode → empty string;
  `gist_identify` returns `NULL` for unknowns.

## Cross-refs

- Record structs + `XLOG_GIST_*` opcodes:
  `[[src/include/access/gistxlog.h]]`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.

<!-- issues:auto:begin -->
- [Issue register — `access-rmgrdesc`](../../../../../issues/access-rmgrdesc.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: empty PAGE_UPDATE desc is by design]**
  `gistdesc.c:20-23` — `out_gistxlogPageUpdate` is an empty function
  body; the blank `pg_waldump` line for `XLOG_GIST_PAGE_UPDATE` is
  intentional (data lives in block refs) but uncommented. Documented
  here so a future reader doesn't "fix" it. Mirrored to
  `knowledge/issues/access-rmgrdesc.md`.
