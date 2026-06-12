# CB7 ltree parse_lquery amplification — notes

**Patch:** `0001-ltree-cap-total-variant-allocations-in-parse_lquery.patch`
**Status:** **PARKED.** Sending requires explicit user re-auth.
**Calibration:** `knowledge/calibration/cb7-ltree-amplification.md`

## Predicted lead committer
**Peter Eisentraut** (top contrib/ltree/ committer 24mo, 6 commits —
all cleanup-class). **But Peter zero-backpatches in 24mo** (per
`committer-map.md` Peter row + Phase B finding). For the v16/v17/v18
backport, the realistic landing committer is **Michael Paquier** or
**Tom Lane** (both backpatch DoS fixes regularly). **CC both** on
the thread.

## Gate checklist

### Gate 1 — `security@` embargo
**Answer:** **YES, ASK FIRST.** Confirmed DoS via `text::lquery` cast,
reachable by any role. Pattern identical to CB1.

### Gate 2 — Test-omission skepticism
**COVER §3 says:** regression test IS included (~21 KB input that
would otherwise drive ~10M nodeitems). ✓ pre-empted.

### Gate 3 — Install-script immutability
Not applicable.

## Patch findings to address before send

| # | Finding | Source | Resolution |
|---|---|---|---|
| 1 | **Cap-value arithmetic doesn't match COVER's "~3 MB scratch" claim** | cb7 §6 PATCH FINDING (Tom predicted concern + own arithmetic check) | **MUST REFINE BEFORE SEND.** At cap 131072 in a 365×360 shape, per-level scratch sums to hundreds of MB. Either tighten the cap (e.g. 32768 = ~12 MB worst case) OR rewrite COVER §3 with honest worst-case math + justification for accepting it. |
| 2 | Multibyte/UTF-8 interaction in byte-walking parser | cb7 §3 (Jeff Davis + Noah Misch reflex) | Add to COVER: "The cap applies to level/variant counts (parsed AFTER multibyte boundary handling in `parse_lquery`); confirm by inspecting `ltree_io.c:206` level-counting loop which uses `pg_mblen`-aware step. The cap is encoding-agnostic — UTF-8 inputs trigger it at the same `num × (numOR+1)` product." |
| 3 | Move `LQUERY_MAX_TOTAL_VARIANTS` `#define` to `ltree.h` | cb7 §3 (Peter style reflex) | Move to `contrib/ltree/ltree.h` next to existing `LQUERY_MAX_LEVELS` constant. Soft nit, easy to pre-empt. |
| 4 | `injection_points` reproducer | cb7 §3 (Noah reflex) | Optional — the regression test already exercises the cap. If Noah pushes back, point at the regression test as the answer. |
| 5 | Cite predecessor cap-constant SHA | (general convention) | Find the commit that added `LQUERY_MAX_LEVELS = PG_UINT16_MAX` and cite it in the COVER as the precedent. |

## Reviewer-style pre-emption

- **Address finding #1 first** — the arithmetic disagreement is a real
  concern that any careful reviewer will catch.
- Move the `#define` per finding #3.
- Add the multibyte sentence per #2.
- Scrub "postgres-claude/A13 corpus sweep" (Tom rewrites).
- Submit with Peter on To: + Michael + Tom on CC (per backpatch
  routing rule).

## Send order recommendation

**2nd in the pile** (after CB1's embargo path sets the pattern).
Same security@ embargo path.

## Verdict
**REFINE before GO.** Finding #1 (cap-value arithmetic) is a real
patch-content issue, not a process item. Either tighten the cap
or honestly document the worst-case. Recommend tightening to
`(1 << 15) = 32768` for a ~12 MB worst-case scratch — still 5×
larger than the legitimate 65535-variant test from the existing
ltree regression suite, but well below the "100 GB attack" surface.

## DO NOT SEND
1. Tighten cap value (or rewrite COVER §3) per finding #1.
2. Move `#define` per finding #3.
3. Add multibyte clarifying sentence per #2.
4. Cite predecessor SHA per #5.
5. `security@postgresql.org` notification.
6. Explicit user re-auth.
