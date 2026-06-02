# Edits applied — iteration 2

Compared `proposed-edits.md` against current SKILL.md. Of the five
suggestions in iter-1:

## Applied by previous agent

**#1 — §2.5 restart policy as a table** ✓ Applied at SKILL.md:226-236.
The table renders both knobs (`bgw_restart_time` × exit code) explicitly,
with `BGW_NEVER_RESTART (-1)` and the `proc_exit(0) → no restart` row.
Verified `-1` value against `source/src/include/postmaster/bgworker.h:92`.

**#2 — Dynamic vs static "where you call it from" warning** ✓ Applied at
SKILL.md:177-180. One-sentence prose under the §2.1 table spells out that
`RegisterBackgroundWorker` errors out unless `process_shared_preload_libraries_in_progress`
is true, so backends at runtime must use the dynamic API.

## Not applied (low value or already implicit)

**#3 — `shmem_request_hook` cross-link in §1.3** Not applied. §1.3 is
already scoped to "GUC definition" and the eval-1 question explicitly
mentions `shmem_request_hook` as a given, so the cross-link does not
move any assertion outcome. Skipping keeps §1 tighter.

**#4 — Boxed `estimate-then-allocate` warning in §3.3** Not applied.
The checklist item at §3.6 already calls out the symmetry requirement,
and the §3.3 prose right above the estimate calls (lines 361-364) says
"call shm_toc_estimate_chunk / _keys for every piece of shared state you'll
insert later" — so the gotcha is present, just not boxed. Keeping the
flatter prose layout.

**#5 — Tighten §1.4 cite for the "parallel-worker startup trips on
placeholders" claim** Not applied. The claim is verified in
`source/src/backend/utils/misc/guc.c:5193-5195` (comment block inside
`MarkGUCPrefixReserved`: "We must actually remove invalid placeholders,
else future parallel worker startups will fail"). The existing cite of
`5178-5228` already covers those lines, so the `[verified-by-code]` tag
is accurate. Could be narrowed to `5193-5195` but the full-function
range stays useful for readers wanting context. Leaving as-is.

## Values verified against source

- `BGW_NEVER_RESTART = -1` → `source/src/include/postmaster/bgworker.h:92` ✓
- TOC reserved range `0xFFFFFFFFFFFF0001..0xFFFFFFFFFFFF000F`
  → `source/src/backend/access/transam/parallel.c:67-81` ✓
- `MarkGUCPrefixReserved` placeholder-removal + parallel-worker-startup
  comment → `source/src/backend/utils/misc/guc.c:5193-5195` ✓
- `proc_exit(0)` retires the slot regardless of `bgw_restart_time`
  → `source/src/include/postmaster/bgworker.h:14-27` ✓ (comment block)

No corrections required.
