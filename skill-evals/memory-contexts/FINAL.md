# memory-contexts skill — eval FINAL

## Pass rates

|              | iter-1        | iter-2        | delta |
|--------------|---------------|---------------|-------|
| with_skill   | 22/22 (100%)  | 22/22 (100%)  |  0    |
| baseline     | 16/22 (72.7%) | 17/22 (77.3%) | +1    |
| skill lift   | +27.3 pp      | +22.7 pp      | -4.6  |

## Per-eval

| Eval | iter-1 ws | iter-1 base | iter-2 ws | iter-2 base |
|------|-----------|-------------|-----------|-------------|
| 1    | 7/7       | 4/7         | 7/7       | 5/7         |
| 2    | 7/7       | 5/7         | 7/7       | 5/7         |
| 3    | 8/8       | 7/8         | 8/8       | 7/8         |

## Edits applied vs skipped

All three proposed edits were applied verbatim (see
`iteration-2/edits-applied.md`):

1. Lifetime table extended with SRF value-per-call, SRF materialize,
   aggregate-trans rows, plus "reset at start" and "delete is recursive"
   inline notes.
2. `MaxAllocSize` bullet expanded with the exact error string,
   `MemoryContextAllocHuge`, `repalloc_huge`, `MaxAllocHugeSize` cap,
   and the per-context-type matrix.
3. Concrete cache-entry pattern added under "Creating a context"
   with `CacheMemoryContext` parent, `ALLOCSET_SMALL_SIZES`, and the
   `rd_rulescxt` precedent pointer.

## Did with_skill improve?

**No measurable improvement** — both iterations score 22/22. The skill
was already at ceiling on this assertion set. The edits did make the
SKILL.md more self-contained: information that previously required
synthesizing from multiple sections (e.g. "what context for an SRF",
"what error string does 1 GB cap produce") is now directly callout-able
without inference. That hardens the answer against regressions but
doesn't show up in a binary pass/fail rubric.

## Did baseline move?

**Slight drift up: 16 → 17 / 22.** This is honest noise from
re-answering the same question fresh — my iter-2 baseline for eval-1
happened to include `MemoryContextSwitchTo(oldcxt)` save/restore in
the materialize snippet, which it didn't in iter-1. The skill content
genuinely cannot leak into the baseline (separate context), but my own
generation variance can. So the baseline sanity check is "approximately
stable" rather than "identical", which is the most we can ask without
templated answers.

## Remaining gaps

1. **Ceiling at 22/22 means the assertion set is exhausted.** Future
   iterations need *new* and harder questions:
   - PG_TRY + volatile correctness on memory contexts (the skill
     mentions it but no eval covers it).
   - MemoryContextRegisterResetCallback for non-PG-owned resource
     teardown (skill mentions, eval set doesn't probe).
   - Cross-(sub)transaction lifetimes — `CurTransactionContext` vs
     `TopTransactionContext` discipline under subtransactions.
   - `allowInCritSection` + the assert-build-only failure mode.

2. **Cite-discipline is doing most of the lift.** 4 of the 5
   skill-only assertions baseline misses are cite-style ("cites
   file:line"). The skill genuinely owns this, but a future eval
   should also test correctness-only assertions where the skill must
   contribute substantive content the base model lacks, not just
   citation form.

3. **No negative test.** No eval probes whether the skill *fails to*
   trigger on out-of-scope prompts (Java GC, jemalloc, shared_buffers).
   The description has the explicit "Do NOT trigger on…" list — that's
   worth verifying with adversarial prompts.

## Recommendation

Skill is at the practical ceiling for the current 3-eval set; further
SKILL.md churn risks bloat without measurable lift. Next iteration
should grow the eval set (negative triggers + 3-4 new question shapes)
before tuning copy again.
