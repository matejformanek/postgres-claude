---
path: src/test/modules/test_resowner/test_resowner_many.c
anchor_sha: e18b0cb7344
loc: 295
depth: read
---

# src/test/modules/test_resowner/test_resowner_many.c

## Purpose

Stress-tests `ResourceOwner` at scale — checks that arbitrarily many resources
across many kinds, with mixed release-phase / release-priority, are released
in the documented order (BEFORE_LOCKS phase before LOCKS phase before
AFTER_LOCKS phase; within a phase, lower `release_priority` first). Companion
to `test_resowner_basic.c` which covers the small-set + leak-detection
behaviours. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_resowner_many` | `test_resowner_many.c:201` | Driver: takes `(nkinds, nremember_bl, nforget_bl, nremember_al, nforget_al)` and exercises BEFORE_LOCKS + AFTER_LOCKS phases |
| `ReleaseManyTestResource` (static) | `:67` | Release callback; asserts monotonically non-decreasing `release_priority` |
| `PrintManyTest` (static) | `:82` | `DebugPrint` callback used for leak detection |
| `InitManyTestResourceKind` (static) | `:96` | Set up a `ResourceOwnerDesc` |
| `RememberManyTestResources` / `ForgetManyTestResources` (static) | `:116`, `:144` | Round-robin remember/forget across the `kinds` array |

## Internal landmarks

- `last_release_priority` static (`:50`) is reset to 0 at each phase
  boundary (`:276`, `:282`, `:287`) and the release callback asserts
  `last_release_priority <= mres->kind->desc.release_priority` (`:72`) —
  this is the invariant the test exists to verify.
- `current_release_phase` (`:49`) is purely informational; the assertion is
  about priority within a phase.
- Each `ManyTestResource` is tracked both in the `ResourceOwner` and in a
  local `dlist_head` per-kind so a bug in `ResourceOwnerForget` (e.g.
  releasing the wrong one) would desync the two and trip the leak check.

## Invariants & gotchas

- **Test module — never load in production.**
- Calling `pfree(mres)` inside the release callback (`:77`) is allowed
  because the resowner contract says ReleaseResource owns the resource at
  call time.
- `RELEASE_PRIO_FIRST + i` is used as the priority across `nkinds`, so all
  priorities are distinct and the strict-monotone assertion has teeth.
- The test deliberately uses **both** `RESOURCE_RELEASE_BEFORE_LOCKS` and
  `RESOURCE_RELEASE_AFTER_LOCKS` so a regression that releases
  AFTER_LOCKS-phase items during the BEFORE_LOCKS pass would trip the
  total-count assertions (`:278`, `:289-290`).

## Cross-refs

- `source/src/backend/utils/resowner/resowner.c` — the implementation.
- `source/src/include/utils/resowner.h` — `ResourceOwnerDesc`, the phases
  and `RELEASE_PRIO_*` constants.
- `knowledge/files/src/test/modules/test_resowner/test_resowner_basic.c.md`
  — sibling test.
