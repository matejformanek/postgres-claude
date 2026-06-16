---
path: src/backend/access/rmgrdesc/hashdesc.c
anchor_sha: 4b0bf0788b0
loc: 178
depth: deep
---

# hashdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/hashdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 178

## Purpose

rmgr descriptor routines for the hash-index resource manager
(`RM_HASH_ID`, records from `access/hash/hash_xlog.c` /
`access/hash_xlog.h`). Renders the hash WAL opcodes — bucket
init/split/squeeze/vacuum and meta-page updates — for `pg_waldump`.
[from-comment, hashdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `hash_desc(buf, record)` | `hashdesc.c:19` | render one hash record |
| `hash_identify(info)` | `hashdesc.c:130` | opcode → short name |

## Internal landmarks

- Pure switch-on-`info`; each case casts `rec` to its `xl_hash_*`
  struct and `appendStringInfo`s the scalar fields. The
  `SPLIT_ALLOCATE_PAGE` case (hashdesc.c:59) decodes two flag bits
  (`XLH_SPLIT_META_UPDATE_MASKS` / `_SPLITPOINT`) into `T/F`.

## Invariants & gotchas

- **`hash_desc` renders only 11 of the 13 opcodes.**
  `XLOG_HASH_SPLIT_PAGE` and `XLOG_HASH_SPLIT_CLEANUP` are listed in
  `hash_identify` (hashdesc.c:152, 167) but have **no case** in
  `hash_desc` — they carry no main-record payload beyond what the
  registered buffers hold, so their `pg_waldump` description line is
  intentionally empty. Don't read the blank line as a bug. `[from-code]`
- **`num_tuples` / `ntuples` are doubles** (`%g`, hashdesc.c:31, 113) —
  the hash meta page stores tuple counts as `double`, a detail that
  surprises readers expecting integer counts.
- **No `default:`** — unknown opcode → empty string; `hash_identify`
  returns `NULL` for unknowns.

## Cross-refs

- Record structs + `XLOG_HASH_*` opcodes + `XLH_SPLIT_*` flags:
  `[[src/include/access/hash_xlog.h]]`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.

<!-- issues:auto:begin -->
- [Issue register — `access-rmgrdesc`](../../../../../issues/access-rmgrdesc.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: SPLIT_PAGE/SPLIT_CLEANUP have no desc
  case]** `hashdesc.c:130` — two opcodes known to `hash_identify` lack a
  `hash_desc` switch case, so they emit an empty description. Believed
  intentional (no extra main-record data) but uncommented. Mirrored to
  `knowledge/issues/access-rmgrdesc.md`.
