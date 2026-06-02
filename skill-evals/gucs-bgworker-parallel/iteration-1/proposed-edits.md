# Proposed SKILL.md edits — iteration 1

The skill scored 22/22 on the with-skill side. All baseline misses are
genuine value-adds the skill already provides (placeholder removal,
PARALLEL_KEY range, `bgw_notify_pid` mechanics, dynamic vs static
registration, `proc_exit(0)` overriding restart, signature exactness).
So the structural shape is right; the proposed edits are small polish
items I noticed while answering.

## 1. Hoist the "proc_exit(0) overrides bgw_restart_time" rule

§2.5 has the rule but it's buried mid-list. A worker author scanning
the section for "how do I prevent restart" reads §2.5 top-to-bottom and
may stop at `BGW_NEVER_RESTART`. Suggest reorganising §2.5 as a tiny
table so both interacting knobs are visible at a glance:

```
### 2.5 Restart policy

Two knobs decide restart; both must allow it.

| bgw_restart_time | Worker exit | Restarted? |
|---|---|---|
| BGW_NEVER_RESTART | any | No |
| N seconds | proc_exit(0) | No (clean exit retires the slot) |
| N seconds | proc_exit(1) | Yes, after N seconds |
| N seconds | crash / signal | Yes, after N seconds |
```

## 2. Add "dynamic vs static — where you call it from" warning to §2.1

§2.1's table has a "Where to call" column but the *implication* — that
a backend at runtime simply cannot use `RegisterBackgroundWorker` —
isn't spelled out. One sentence under the table:

> `RegisterBackgroundWorker` errors out unless called from `_PG_init`
> during shared-library preload. From any other site, use
> `RegisterDynamicBackgroundWorker`.

## 3. Add an explicit `shmem_request_hook` cross-link to §1

§1.3 shows `PGC_POSTMASTER` + `GUC_UNIT_KB` but doesn't mention the
adjacent reality that a GUC sizing shmem implies you'll be in
`shmem_request_hook`. A one-line pointer at the end of §1.3:

> If the GUC sizes a shared-memory allocation, request it from
> `shmem_request_hook` (PG ≥ 15) using `RequestAddinShmemSpace` —
> the hook runs after GUCs are loaded but before postmaster sizes
> the main shmem segment.

## 4. Make §3.3 "estimate-then-allocate symmetry" a numbered gotcha

§3.6 checklist has it; §3.3 walks through the lifecycle but doesn't
flag *why* the estimate calls matter. A boxed warning right above the
`shm_toc_estimate_chunk` lines:

> ⚠ Every `shm_toc_allocate` you'll do after init must have a matching
> `shm_toc_estimate_chunk` + bump of `shm_toc_estimate_keys` *before*
> `InitializeParallelDSM`. Mismatch trips an assert in debug; in
> release builds it silently overruns the segment.

## 5. Tiny correction — §1.4's claim about parallel workers

§1.4 says `MarkGUCPrefixReserved` is needed because "without removal,
parallel-worker startup later trips over them." Worth verifying — the
mechanism is real (parallel workers reload GUC state and a stale
placeholder of the wrong type would fail), but tagging this as
`[verified-by-code]` would require a specific cite into
`parallel.c` / `ParallelWorkerMain`. Currently presented without a
cite; either add one or downgrade to `[inferred]`.

## Non-issues

- Coverage of §1, §2, §3 against the three realistic prompts was full;
  no missing concepts surfaced.
- The cross-cutting §4 on "GUCs inside workers" answered eval 3's
  GUC-propagation sub-question exactly.
- §5 (greps) and §6 (open questions) are scope-appropriate.
