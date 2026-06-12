# SP2 pg_str* MaxAllocSize cap — notes

**Patch:** `0001-Cap-input-size-for-pg_strlower-upper-title-fold-to-M.patch`
**Status:** **PARKED.** Sending requires explicit user re-auth.
**Calibration:** `knowledge/calibration/sp2-pgstr-maxalloc.md`

## Predicted lead committer
**Jeff Davis** (top committer in `pg_locale.c` 24mo by a wide
margin — 51 commits). **Jeff backpatches** (per Phase B
`committer-map.md`), so the persona-aware backpatch routing rule
does NOT fire here. Jeff is the right end-to-end committer.

## Gate checklist

### Gate 1 — `security@` embargo
**Answer:** **YES, ASK FIRST.** Confirmed DoS via `lower(text)` /
`upper(text)` etc., reachable by any role with EXECUTE. Pattern is
the most generic of the 5 (any role can `SELECT lower(big_text)`).

### Gate 2 — Test-omission skepticism
**COVER §3 says:** "No regression test. Exercising the cap requires
> 357 MB input, which would dominate buildfarm time + memory."
**Predicted Noah response:** push for a `PG_TEST_EXTRA=stress` gated
test (Daniel Gustafsson's online-checksums precedent).
**Action before send:** add a test gated under `PG_TEST_EXTRA=stress`
that asserts the new error on a 400 MB input. Daniel-style
PG_TEST_EXTRA gating is the documented escape hatch for expensive
correctness tests. ~40 LOC including the input generation.

### Gate 3 — Install-script immutability
Not applicable.

## Patch findings to address before send

| # | Finding | Source | Resolution |
|---|---|---|---|
| 1 | **3× expansion bound may NOT hold for non-UTF-8 encodings** | sp2 §Notes PATCH FINDING (Noah + Thomas + Jeff reflex confluence) | **MUST INVESTIGATE BEFORE SEND.** The 3× bound is documented for UTF-8 (Unicode SpecialCasing.txt). For GB18030, EUC_JP, EUC_KR, EUC_CN, EUC_TW the worst-case expansion is unverified. Two paths: (a) verify empirically + document per-encoding worst-cases in COVER, OR (b) keep the patch UTF-8/server-encoding-default-only and add a separate cap for non-UTF-8 paths. **Recommend (a)** — fetch a few SpecialCasing.txt equivalents for the East Asian encodings and document. If genuinely different worst-case, tighten the cap to the maximum-of-all-encodings bound. |
| 2 | Unicode TR / SpecialCasing.txt citation for the 3× claim | sp2 §3 (Jeff reflex) | Add to COVER: "ICU's documented 3× expansion is per Unicode TR #21 (case mappings) + SpecialCasing.txt entries (Greek final sigma, German sharp s, Lithuanian dotted i, Turkish dotless i). UTF-8: 3×. For non-UTF-8: [insert per-encoding analysis from finding #1]." |
| 3 | Helper-function refactor for 4-site symmetric checks | sp2 §3 (Peter style reflex) | Pre-empt: refactor the 4 inline cap-checks into a single static helper `pg_str_check_input_size(srclen, fname)`. Saves 30+ LOC, addresses Peter's predicted nit, makes the patch trivially symmetric. |
| 4 | Hot-path branch-prediction / micro-benchmark | sp2 §3 (Thomas + Heikki perf reflex) | Add to COVER: "`unlikely()` annotation added; measured overhead on 1 KB `lower()` input: <X ns/call vs baseline `Y` ns/call." Run pgbench `SELECT lower(short_string)` × N before + after the patch on a release build. Soft nit if missing, but Heikki will ask. |
| 5 | Cite ICU `ucasemap_utf8To*` docs in commit body | (Jeff style) | Include the ICU API URL/doc reference in the commit body — Jeff likes API citations spelled out. |

## Reviewer-style pre-emption

- **Address finding #1 first** — the non-UTF-8 worst-case is a real
  correctness gap that could push the patch to a v2 with per-
  encoding caps.
- Refactor to a single helper per finding #3.
- Add Unicode TR + SpecialCasing.txt citation per #2.
- Include micro-benchmark per #4.
- Cite ICU API per #5.
- Scrub "postgres-claude/A7+A15+A16 corpus sweep" (Tom rewrites).
- Submit with Jeff on To: + Peter + Tom + Noah + Thomas on CC
  (the full predicted-reviewer set).

## Send order recommendation

**1st in the pile.** Reasons:
1. Backpatch routing is clean (Jeff backpatches → no routing
   complication).
2. Reachability is the broadest of the 5 (`lower()` is in every
   query path), making the embargo case clearest.
3. Jeff is the most subsystem-deeply-engaged of the 5 lead
   committers — faster turnaround.

## Verdict
**INVESTIGATE finding #1 before GO.** The non-UTF-8 question is the
most substantive open issue across all 5 patches. Per-encoding
worst-case analysis is needed regardless of the path chosen.

## DO NOT SEND
1. Investigate non-UTF-8 worst-case per finding #1.
2. Refactor to helper per finding #3.
3. Add Unicode TR citation per #2.
4. Run + include micro-benchmark per #4.
5. Add `PG_TEST_EXTRA=stress` test per Gate 2.
6. `security@postgresql.org` notification.
7. Explicit user re-auth.
