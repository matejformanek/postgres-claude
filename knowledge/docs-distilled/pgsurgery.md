---
source_url: https://www.postgresql.org/docs/current/pgsurgery.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pg_surgery (last-resort heap forensics)

`contrib/pg_surgery` performs **low-level surgery on a damaged heap**: it can
kill or freeze tuples by TID without examining their contents. It is the partner
to the read-only inspection modules (pageinspect/amcheck) — you diagnose the bad
TIDs there, then operate here. Explicitly "unsafe by design." `[from-docs]`

## The two functions (verified against source)

- `heap_force_kill(regclass, tid[])` — marks the named line pointers **dead**
  without reading the tuples, removing rows that are otherwise inaccessible.
  `PG_FUNCTION_INFO_V1(heap_force_kill)` at
  `source/contrib/pg_surgery/heap_surgery.c:38`; dispatches to
  `heap_force_common(fcinfo, HEAP_FORCE_KILL)` (`:58-60`). `[verified-by-code]`
- `heap_force_freeze(regclass, tid[])` — forcibly **freezes** the named tuples
  (bypassing corrupt xmin/xmax visibility) so the table can be read/VACUUMed.
  Defined at `:39,73-75`. `[verified-by-code]`
- Both route through `heap_force_common` (`heap_surgery.c:81`), which requires the
  caller be **table owner or superuser** (`aclcheck_error(ACLCHECK_NOT_OWNER…)`,
  `:123-125`). `[verified-by-code]`

## What it's for

- Recover from corruption that normal paths choke on: tuples whose xmin predates
  `relfrozenxid`, or whose xmin/xmax point at a transaction whose status can't be
  read ("could not access status of transaction …") — cases where VACUUM itself
  errors out. `[from-docs]`

## The non-obvious mechanics & risks

- It **does emit WAL**: after modifying a page it calls
  `if (RelationNeedsWAL(rel)) log_newpage_buffer(buf, true);` (and the VM page if
  touched) at `heap_surgery.c:322-328` — so changes are crash-safe and
  replicated, even though they bypass MVCC/constraint logic. `[verified-by-code]`
  `heap_force_kill` also clears the all-visible bit it would invalidate
  (`PageIsAllVisible` handling, `:239,258`). `[verified-by-code]`
- Because it skips constraint and MVCC checks, misuse can leave
  **heap/index inconsistencies**, violate UNIQUE/FOREIGN-KEY constraints, crash
  backends that later read a half-fixed page, and cause permanent data loss if
  the wrong TIDs are targeted. Identify TIDs first (pageinspect/amcheck), then
  cut. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/pageinspect.md]]` — find the bad line pointers /
  decode `t_infomask` before calling pg_surgery.
- `[[knowledge/docs-distilled/amcheck.md]]` — detect the heap/B-tree corruption
  that motivates surgery.
- `[[knowledge/docs-distilled/pgvisibility.md]]` — the VM all-visible/all-frozen
  bits `heap_force_kill`/`freeze` must keep consistent.
- `[[knowledge/subsystems/storage-buffer.md]]` — `MarkBufferDirty` /
  `log_newpage_buffer` page-modification path.
- Skills: `debugging` (corruption recovery), `wal-and-xlog` (the `log_newpage`
  records), `access-method-apis` (heap-AM TID semantics).
