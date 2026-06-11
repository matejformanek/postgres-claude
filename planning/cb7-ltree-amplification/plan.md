# Plan: CB7 — ltree `parse_lquery` memory amplification cap

**Status:** READY. Single-phase plan.
**Pitch:** `knowledge/phase-d-pitches.md` CB7 (A13 critical finding)
**Source pin:** `e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa` (master at 2026-06-10)
**Slug:** `cb7-ltree-amplification`
**Branch:** `feature_cb7_ltree_amplification` (in `dev/`)
**Expected commits:** 1 (single phase per R3 + R5)

## §1 Problem statement

`contrib/ltree/ltree_io.c::parse_lquery` (`source/contrib/ltree/ltree_io.c:268-`) makes
two passes over the input.  Pass 1 counts:

- `num`   — number of `.` separators + 1 (level count)
- `numOR` — number of `|` characters anywhere in the query (variants count)

Pass 2 walks the input again and, **at every level**, allocates an array sized for
the GLOBAL `numOR` count:

```c
GETVAR(curqlevel) = lptr = palloc0_array(nodeitem, numOR + 1);  /* line 322 and 329 */
```

With `LQUERY_MAX_LEVELS = PG_UINT16_MAX = 65535` (`source/contrib/ltree/ltree.h:125`)
and `sizeof(nodeitem) = 24` (`ltree_io.c:17-23`), a hostile query of the shape
`a|b|c.a|b|c.a|b|c.…` with N levels each containing K variants gives:

- `num   ≈ N`     (one per `.`)
- `numOR ≈ N·K`   (one per `|`, summed globally)
- per-level alloc ≈ `(N·K + 1) · 24` bytes
- total scratch  ≈ `N · (N·K + 1) · 24` bytes

For N=65535, K=2 (so input is ~256 KB), total ≈ 65535 · 131072 · 24 ≈ **205 GB**.
Even for N=65535, K=1 (~131 KB input), total ≈ 65535 · 65536 · 24 ≈ **103 GB**.

Each individual palloc is well under `MaxAllocSize`, so the existing cap doesn't
trigger.  The cumulative cross-level allocation is the bug.  PG's CurrentMemoryContext
limit (if set) might catch it eventually but only after substantial damage.

Surfaced 2026-06-09 by A13 sweep (foreground); catalogued as **CB7** in
`knowledge/phase-d-pitches.md`.

## §2 Approach

Add a hardcoded cap on total nodeitem allocation during lquery parsing.  Compute the
product `(uint64) num * (uint64) (numOR + 1)` after the existing pass-1 counters are
finalized, and ereport `ERRCODE_PROGRAM_LIMIT_EXCEEDED` if it exceeds a conservative
limit.

Limit choice: **1 MB worth of nodeitems = `(1 << 20) / sizeof(nodeitem)` ≈ 43,690
entries.**  That covers any sensible legitimate lquery (tens of levels × tens of
variants = hundreds of nodeitems) with a wide safety margin while bounding worst-case
scratch to ~1 MB per nodeitem-buffer plus the same again in fixed overhead.

Why hardcoded, not a GUC:

- Security fix needs to land in back-branches; adding a GUC complicates backpatch.
- The limit is structural (PG's design assumption was that per-level allocations
  stay small); operators don't have a workflow that benefits from tuning it.
- Reviewers in the past (e.g., `LQUERY_MAX_LEVELS`) have preferred hardcoded
  per-input constants for ltree.

Why total variants × levels, not input size:

- Catches pathological `|`-density even in short inputs (the actual attack shape).
- An input-size GUC would either be too generous (still allows the amp) or break
  legitimate large queries.

## §3 Files that change

| File | Change | LOC |
|---|---|---|
| `contrib/ltree/ltree_io.c` | Add `LQUERY_MAX_TOTAL_VARIANTS` constant + cap check after the pass-1 counters | +13 |
| `contrib/ltree/expected/ltree.out` | Regenerate to match the new error path (only if a regression test is added) | +N |
| `contrib/ltree/sql/ltree.sql` | Optional regression test exercising the cap | +N |

**Sites verified against current source (pin `e18b0cb7344`):**
- `source/contrib/ltree/ltree_io.c:268-310` — `parse_lquery` pass-1 + existing `num > LQUERY_MAX_LEVELS` cap
- `source/contrib/ltree/ltree_io.c:322,329` — the two `palloc0_array(nodeitem, numOR + 1)` sites
- `source/contrib/ltree/ltree.h:125` — `LQUERY_MAX_LEVELS = PG_UINT16_MAX`

## §4 Catalog impact

None.

## §5 Behavior changes

- Inputs producing total variants × levels ≤ 43690: unchanged.
- Inputs above that: previously could allocate up to ~100 GB scratch (or hit
  MemoryContext limit / process OOM); now error with a specific message before
  any per-level palloc fires.
- No change for non-hostile lqueries (typical: < 100 levels × < 100 variants).

## §6 Test plan

Add a focused regression test that exercises the cap with a small-but-pathological
query.  Aim for an input that produces total >43690 variants × levels but is small
enough not to dominate the regression run.  Example:

```sql
-- CB7: pathological lquery rejected before allocating ~MB of nodeitems
SELECT 'a'::ltree ~ repeat('a|b|c|d|e|f|g|h|i|j.', 1000)::lquery;
-- Expected: ERROR with the specific message about variant amplification
```

That input is ~21 KB and would produce num=1001, numOR=10000 → total = 1001 × 10001
= 10M+ entries.  Well above the 43690 threshold, well below catastrophic.

**Phase-end check:** `meson test --suite ltree` must pass.

## §7 Implementation sketch

```c
/*
 * Cap on the total variant slots allocated across all lquery levels.
 *
 * parse_lquery allocates palloc0_array(nodeitem, numOR + 1) at every
 * level, so the cumulative allocation is num * (numOR + 1) entries.
 * With LQUERY_MAX_LEVELS = 65535 and sizeof(nodeitem) = 24, an input
 * with N levels and N |s globally can reach N * (N+1) * 24 bytes -
 * ~100 GB for N near LQUERY_MAX_LEVELS.  Cap the product to keep the
 * total scratch under ~1 MB worth of nodeitems regardless of input.
 */
#define LQUERY_MAX_TOTAL_VARIANTS ((1 << 20) / (int) sizeof(nodeitem))

...

if ((uint64) num * (uint64) (numOR + 1) > LQUERY_MAX_TOTAL_VARIANTS)
    ereturn(escontext, NULL,
            (errcode(ERRCODE_PROGRAM_LIMIT_EXCEEDED),
             errmsg("lquery is too complex"),
             errdetail("Total of %llu variant slots across %d levels exceeds "
                       "the maximum allowed (%d).",
                       (unsigned long long) num * (numOR + 1),
                       num, LQUERY_MAX_TOTAL_VARIANTS)));
```

Place this check immediately after the existing `num > LQUERY_MAX_LEVELS` block,
before the first palloc.

## §8 Phase-end check

```bash
cd dev
ninja -C build-debug install
rm -rf build-debug/tmp_install
meson test -C build-debug --suite setup
meson test -C build-debug --suite ltree
```

Expected: existing tests green; new regression test passes (produces the expected
ERROR).  Broader `meson test --no-rebuild` ≤ 1 pre-existing flake (ecpg).

## §9 Risk + reviewer concerns

**Anticipated reviewer pushback:**

1. *"Why hardcoded and not a GUC?"* — Backpatch friendliness (no GUC introduces
   complexity on stable branches); the cap is a structural property of the
   parser, not an operator-tunable knob.  Happy to convert to a GUC if hackers
   prefer.
2. *"Why total variants × levels and not input length?"* — Input-length caps
   either accept the pathological short inputs that trigger this OR break legitimate
   large queries.  The product directly bounds the allocation amount we care
   about.
3. *"Will this break existing queries?"* — A typical lquery has tens of levels
   × tens of variants per level (≪ 1000).  The cap of 43690 leaves a ~40x
   safety margin.  An exhaustive search over `ltree` documentation examples shows
   nothing close to the cap.
4. *"Backpatch?"* — Yes, this is a confirmed DoS bug in already-released code.
   v16, v17, v18 share the same parser.

**Known limitations after this patch:**
- `parse_ltree` (separate function for ltree literal parsing) does NOT have the
  same amplification (it palloc's only once based on level count).  Out of scope.
- Other ltree operators (`lquery_op`, `nodeitem` matching) inherit the size of
  whatever the parser produced, so they're bounded by this cap.

## §10 Cross-corpus echoes (this fix touches)

- A13 sweep finding (`knowledge/issues/ltree.md`)
- CB7 confirmed bug in `knowledge/phase-d-pitches.md`
- P2 NAME-vs-OID race cluster: unrelated.
- The `LQUERY_MAX_LEVELS` cap (already present) is the precedent for hardcoded
  ltree limits.

## §11 Submission package

After implementation lands and tests pass:
- `git format-patch e18b0cb7344..feature_cb7_ltree_amplification --output-directory ../cb7-ltree-amplification/`
- Patch subject: `ltree: cap total variant allocations in parse_lquery`
- Commit message body: cite the cross-level amplification, the 100 GB worst case,
  the 1 MB cap rationale, the absence of legitimate queries near the cap.
- Target: pgsql-hackers mailing list + commitfest 60 (January 2026).
- Backpatch candidate: yes (DoS bug in released code).

## §12 Notes / surprises

(Empty at plan time. Populate in `notes.md` during implementation per R8.)
