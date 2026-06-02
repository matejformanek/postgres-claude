# Proposed edits — iteration 1 (NOT applied)

The skill scored 21/21 on the assertions. Edits below are small refinements,
not corrections.

## 1. SRF_IS_FIRSTCALL collision with fn_extra cache — flag both ways

§1.9 says "fn_extra is therefore reserved by the SRF machinery and you
cannot co-opt it" — correct. But §1.12 ("fn_extra — per-call cache slot")
does not back-link to that restriction. A reader landing on §1.12 first and
then writing an SRF could get tripped.

Proposed: append one sentence to §1.12 saying "Do not use fn_extra in a
value-per-call SRF — it is owned by SRF_FIRSTCALL_INIT (§1.9)."

## 2. Strengthen the cross-reference from §2.3 to §1.12

The "Forgetting SPI_keepplan" pitfall in §2.8 is canonical: the user is
typically caching the plan on `flinfo->fn_extra`. The plan-cache pattern in
§2.3 shows `SPI_keepplan(plan)` but doesn't show the fn_extra + fn_mcxt
allocation idiom side-by-side. A reader can know both rules independently
and still write the "cache struct in CurrentMemoryContext, plan kept" bug.

Proposed: add a small example block to §2.3 — "Cached on fn_extra" — that
shows the full pattern (palloc cache in fn_mcxt + SPI_keepplan), with a
back-link to §1.12.

## 3. Document the "capture before rollback" diagnostic pattern

The aborted-subxact rule (§2.7) is well stated, but the natural follow-up —
"so how DO I capture diagnostics from a failed SPI call?" — is left
implicit. Most readers will reach for SPI_tuptable; the skill should pre-
empt that.

Proposed: add 4-6 lines at the end of §2.7 making explicit:

- ErrorData via CopyErrorData (before FlushErrorState) is the supported
  channel.
- To capture partial *result* rows, you must SPI_palloc / SPI_copytuple
  them out before ReleaseCurrentSubTransaction; you cannot recover them
  after rollback.

## 4. Surface MAT_SRF flag semantics in the bullet, not just a one-liner

§1.10 mentions MAT_SRF_USE_EXPECTED_DESC and MAT_SRF_BLESS in a trailing
sentence. For an LLM reader the flags are easy to miss. Consider promoting
to a two-row mini-table with one-line guidance:

| Flag | When to set |
|---|---|
| MAT_SRF_USE_EXPECTED_DESC | You want the tupdesc the caller already
expects (e.g. SELECT * FROM srf() AS (...)) |
| MAT_SRF_BLESS | Return type is RECORD and needs a typmod assigned |

## 5. Minor: name AtEOSubXact_SPI in §2.5 too

§2.7 names AtEOSubXact_SPI; §2.5 ("returning past SPI_finish") describes the
same memory-context machinery but talks about it in passing. Adding the
function name + a tiny pointer would tighten the cross-reference web.

## What NOT to change

- The "three things easy to get wrong" sections (§1.13, §2.8) are exactly
  the right shape — terse, actionable, mirrored across the two halves.
- DirectFunctionCall* NULL behavior is correctly flagged. Don't expand.
- The grep cheat-sheet in §3 is short and useful; resist the urge to grow.
