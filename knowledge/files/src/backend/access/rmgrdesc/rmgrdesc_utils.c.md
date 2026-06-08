---
path: src/backend/access/rmgrdesc/rmgrdesc_utils.c
anchor_sha: 4b0bf0788b0
loc: 61
depth: read
---

# rmgrdesc_utils.c

- **Source path:** `source/src/backend/access/rmgrdesc/rmgrdesc_utils.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 61

## Purpose

Shared formatting helpers for the per-rmgr `*_desc` routines that
render WAL records as human-readable strings (for `pg_waldump` and
`rmgr` debug logging). Provides a generic array printer plus a few
element-printer callbacks, so every rmgrdesc emits arrays in the one
canonical format described in the directory README.
[from-comment, rmgrdesc_utils.c:1-22]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `array_desc(buf, array, elem_size, count, elem_desc, data)` | `rmgrdesc_utils.c:23` | print `" [e0, e1, …]"` (or `" []"`) via a per-element callback |
| `offset_elem_desc(buf, offset, data)` | `rmgrdesc_utils.c:43` | print an `OffsetNumber` |
| `redirect_elem_desc(buf, offset, data)` | `rmgrdesc_utils.c:49` | print a redirect pair `"a->b"` (two `OffsetNumber`s) |
| `oid_elem_desc(buf, relid, data)` | `rmgrdesc_utils.c:57` | print an `Oid` |

## Invariants & gotchas

- **The output format is a contract** — the README describes the
  ` [a, b, c]` shape, and tools/tests parse `pg_waldump` output; changing
  the spacing/brackets here ripples to every rmgrdesc and to anything
  scraping waldump. [from-comment, rmgrdesc_utils.c:20-22]
- **`elem_desc` advances caller state via `data`** — e.g. heapdesc's
  `plan_elem_desc` uses the `void *data` to walk a parallel
  `frz_offsets` array, mutating the caller's pointer as it prints. The
  generic printer is intentionally stateless; the per-element callback
  carries the cleverness.

## Cross-refs

- Header: `src/include/access/rmgrdesc_utils.h`.
- Consumers: every `*desc.c` in this directory, prominently
  `heapdesc.c` (freeze plans, redirects), `spgdesc.c`, `gindesc.c`.
- README: `source/src/backend/access/rmgrdesc/README`.

## Tally

`[verified-by-code]=2 [from-comment]=2 [inferred]=0`
