# Calibration — CB7 ltree parse_lquery amplification cap

**Patch:** `patches/cb7-ltree-amplification/0001-ltree-cap-total-variant-allocations-in-parse_lquery.patch`
**Cover:** `patches/cb7-ltree-amplification/COVER.md`
**Methodology:** `knowledge/calibration/README.md`
**Calibrated at:** 2026-06-12 against `source` @ `e18b0cb7344`.
**Sequence:** second per-patch run after CB1 (the methodology shake-down).

## 1. Patch summary

Adds a hardcoded cap `LQUERY_MAX_TOTAL_VARIANTS = 131072` (2^17) on the
*product* of `num` (levels) × `numOR + 1` (variants per level) in
`contrib/ltree/ltree_io.c::parse_lquery`. The per-level allocation at
`ltree_io.c:322` and `:329` (`palloc0_array(nodeitem, numOR + 1)`) sizes
its array against the GLOBAL count of `|` characters in the input —
making a `a|b|c.a|b|c. ...` 256 KB input drive scratch to
`N × (N+1) × 24` bytes ≈ 100 GB without any single call tripping
`MaxAllocSize`.

Touches 1 file in `contrib/ltree/`:
- `ltree_io.c` (+8 LOC including the new constant + check + new
  `ereturn` with `errmsg("lquery is too complex")`).

Includes a regression test (`expected/ltree.out` + `sql/ltree.sql`): a
~21 KB input that would otherwise drive ~10M nodeitems of scratch. New
error class string `"lquery is too complex"` joins the existing four
(`"syntax error"`, `"too many items"`, `"too large"`, `"too many
variants"`).

Behavior: `ERRCODE_PROGRAM_LIMIT_EXCEEDED` raised before any oversized
palloc. No change for inputs under the cap.

## 2. Predicted reviewers

Mined from 24-month commit + trailer history of `contrib/ltree/`:

| Rank | Reviewer | Why they would review | Persona |
|---|---|---|---|
| 1 | Peter Eisentraut | Top committer in `contrib/ltree/` 24mo (6 commits, mostly cleanup: `Use fallthrough attribute`, `Remove useless casting`, `pg_noreturn`, `Remove unused #include's`). Will land it if it's a clean patch — but cleanup-style, not security-instinct. | `knowledge/personas/peter-eisentraut.md` |
| 2 | Tom Lane | #2 committer 24mo (5 commits), parser-style + ABI reviewer. Will probe error-message convention + ERRCODE choice + the cap value. | `knowledge/personas/tom-lane.md` |
| 3 | Noah Misch | Not a committer of ltree in 24mo, but the strongest project-wide reflex for "DoS via allocation amplification on a public SQL API" + multibyte interaction (the input is a multibyte text string; `parse_lquery` does its own byte-walking — encoding-fidelity concerns apply). | `knowledge/personas/noah-misch.md` (NEW — landed in #152) |
| 4 | Michael Paquier | #3 committer 24mo (4 commits — small ltree cleanups + `palloc_array`/`palloc_object` conversions). Will check error-message style + commit body. May commit it if Peter punts. | `knowledge/personas/michael-paquier.md` |
| 5 | Jeff Davis | #4 committer 24mo (3 commits). Recent ltree work + Unicode standard reflex. Will ask whether the cap interacts with multibyte/Unicode input handling. | `knowledge/personas/jeff-davis.md` |
| 6 | Chao Li | Top trailer-only reviewer for ltree in 24mo (3 `Reviewed-by`s). Per `domain-ownership.md`: in top-4 reviewers of 11/20 subsystems despite ~10 months active. Will likely add a `Reviewed-by:` line; no strong shape prediction yet. | (no persona; mentioned in `contributor-map.md`) |

## 3. Predicted review feedback, per reviewer

### Peter Eisentraut (most-likely landing committer)

Driven by `peter-eisentraut.md`:

- **Include discipline reflex.** `ltree_io.c` already includes `ltree.h`, which transitively pulls `c.h`/`fmgr.h`. The new `LQUERY_MAX_TOTAL_VARIANTS` constant adds no new includes — clean. *No comment expected here.*
- **Style/cleanup reflex (his most consistent 24mo ltree theme).** Expect: *"Move the new `#define` to `ltree.h` next to `LQUERY_MAX_LEVELS` for discoverability."* Soft nit. The COVER §1 already cites `LQUERY_MAX_LEVELS` as precedent so this nit can be pre-empted.
- **`uint64` cast.** Patch uses `(uint64) num * (uint64) (numOR + 1) > LQUERY_MAX_TOTAL_VARIANTS`. Peter's style is conservative on int widths but the cast is correct — `num` and `numOR` are `uint16` per ltree's existing conventions. *No comment.*
- **Will not flag the cap value itself.** Peter's reviews are style-focused, not invariant-focused. The "131072 vs 65536 vs 1M" debate (see Tom below) is not his.
- **Zero backpatch reflex.** Per `committer-map.md`, Peter has **zero backpatches in 24mo** across 719 commits. If this needs back-patching (it does — DoS in released code per COVER §5), expect Peter to push it to someone else for the landing. Likely outcome: **Michael Paquier lands the back-patched version, Peter is happy to review.**

### Tom Lane

Driven by `tom-lane.md`:

- **Will rewrite the commit message.** Likely outcome: the "Reported in postgres-claude corpus sweep A13" reference will be scrubbed; the body shortened; a `Discussion:` URL required.
- **ERRCODE choice.** `ERRCODE_PROGRAM_LIMIT_EXCEEDED` is correct for "input too complex for a hard cap" — Tom will check this. Same code used by the existing 4 ltree limits → consistent. *Expected verdict: OK on errcode.*
- **The cap value (131072).** Tom is fussy about arbitrary constants. Expect: *"Why 2^17 specifically? The 'far more than any legitimate lquery needs' claim needs more support. Worst case at 131072 is still N × (N+1) × 24 = 131072 × 365 × 24 ≈ 1.1 GB scratch if `num=365` — that's not 'a few MB'. Did you account for `numOR ≈ sqrt(LQUERY_MAX_TOTAL_VARIANTS)`?"* This is a real arithmetic concern the cover glosses over. **Flag as a calibration finding to feed back to the patch.**
- **`(uint64)` cast safety.** Tom is fussy about width promotion. The cast is correct (both `num` and `numOR` are `uint16` so the product fits in `uint32`, but the cast to `uint64` is defensive and right). *No comment expected.*
- **Backpatch implications.** Tom backpatches roughly 25% of his commits. He will agree with COVER §5 and likely commit a unified v16/v17/v18 backpatch. *Expected: he'd land it if Peter punts.*
- **Hashability / typecache / cache-invalidation.** Not applicable — parser-side fix, no operator-class touch.

### Noah Misch (now per `knowledge/personas/noah-misch.md`)

Driven by his persona's "What to expect" §1-7:

- **#1 "Where's the test?"** — COVER §3 already names a regression test in the patch. Pre-empted. ✓
- **#2 "Has security@ been notified?"** — **This is the killer comment.** CB7 is a confirmed DoS via a public SQL API (`text::lquery` is invokable by any role with `EXECUTE` on the cast). Noah will flag pgsql-hackers as the wrong forum. Same gap as CB1 §6.2 in the methodology — feeds the same skill-edit recommendation.
- **#3 "What's the back-patch story?"** — COVER §5 says yes to v16/v17/v18 — Noah will agree.
- **#4 "Did you check the multibyte / encoding interaction?"** — Confidence medium-high. `parse_lquery` walks the input byte-by-byte (`ltree_io.c:206` `level`-counting loop). The cap is on level/variant counts, not on byte count, so multibyte interactions are bounded — but Noah will *ask*. Expect: *"Confirm the cap works for UTF-8 inputs that decompose into more code points than bytes."*
- **#5 "Show the failure-mode reproducer."** — COVER §3 cites a "~21 KB regression test" but doesn't include a public PoC link. Expect: *"Can you confirm the 256 KB worst-case input drives the 100 GB scratch you claim? `injection_points` would let us measure scratch at the palloc boundary."* Medium confidence.
- **#6 "What about inplace update?"** — Not applicable, parser code.
- **#7 "Don't `--amend` upstream commits."** — Not applicable.

### Michael Paquier

Driven by `michael-paquier.md`:

- **He may commit it (high baseline rate).** With Peter unlikely to backpatch and Tom's queue often deeper, Michael is the realistic backpatch-landing committer for this kind of small contrib DoS fix.
- **`Discussion:` URL.** Required — 98% of his commits cite one.
- **Subject re-tag.** Expect landed subject `ltree: cap total variant allocations in parse_lquery` — COVER already uses this prefix. ✓
- **Test coverage.** COVER §3 names a regression test — expect Michael to verify it's actually included in the patch's `expected/ltree.out` diff.
- **Trailer hygiene.** Submit with proposed `Reviewed-by:` lines once they accumulate.

### Jeff Davis

Driven by `jeff-davis.md`:

- **Unicode standard fidelity.** This is parser code that walks input by byte. Jeff will ask: *"Does the byte-walking in `parse_lquery` respect UTF-8 multibyte boundaries? An input where each visible `.` is preceded by a continuation byte that the parser misinterprets as a separator could shift the level count."* Medium-high confidence — this is exactly his reflex.
- **Concrete failure example.** Expect: *"Show me the specific codepoint that triggers the cap differently for ASCII vs UTF-8 input."* If you can't, he'll suggest adding such a test.
- **Method-table dispatch reflex.** Not applicable — ltree doesn't use a provider abstraction.
- **`length=-1` reflex.** The patch doesn't introduce a sentinel int. *No comment.*

### Chao Li

No persona file yet; he's mentioned in `contributor-map.md` as a high-volume cross-subsystem reviewer (top-4 in 11/20 subsystems despite ~10mo active). Specific shape unknown — flag as a future Phase B follow-up if his review patterns stabilize.

## 4. Generic pipeline output (what `pg-patch-review` would catch unaided)

Synthesized from the current skills applied to this patch:

1. **`Discussion:` trailer missing.** (Matches Tom + Michael.)
2. **Test coverage.** "Patch includes a regression test — verify it exercises both branches of the new check." (Matches expected reviewer reaction.)
3. **Commit-message hygiene.** "Body cites postgres-claude/A13; scrub or footnote." (Matches Tom.)
4. **Backpatch question.** "Confirm v16/v17/v18 file identity for parser." (Matches Tom + Noah.)
5. **Cap-value justification.** "COVER §3 says '131072 = ~3 MB worst case' — verify arithmetic: at 131072 / 365 ≈ 359 levels × 365 variants → ~1.1 GB scratch, not a few MB." (This DOES land — the generic pipeline catches arithmetic claims that don't add up. Matches Tom's predicted concern.)
6. **New errmsg string.** "'lquery is too complex' is a new error class — consider whether to reuse 'too large' or 'too many variants' for consistency." (Matches Peter cleanup reflex partially.)

The generic pipeline does NOT catch:

- **`security@` embargo** (Noah #2). Same gap as CB1.
- **Multibyte/UTF-8 interaction with byte-walking parser** (Noah #4 + Jeff). Subsystem-specific reflex.
- **`injection_points` reproducer for the bomb claim** (Noah #5). Subsystem-specific.
- **Peter's "zero backpatch" routing implication** — generic pipeline doesn't know Peter doesn't backpatch in 24mo.
- **Move new `#define` to `ltree.h` next to `LQUERY_MAX_LEVELS`** (Peter style nit). Subsystem-local.

## 5. Gap analysis

| Predicted comment | Covered by §4? | Why missed |
|---|---|---|
| security@ embargo for DoS-on-public-API | ❌ | Same gap as CB1 §5. **Two-for-two now**; this is the highest-impact skill edit. |
| UTF-8/multibyte boundary in byte-walking parser | ❌ | Jeff+Noah-shared reflex; no skill knows to ask. |
| `injection_points` measurement of scratch at allocation boundary | ❌ | Subsystem-specific verification convention. |
| Peter's zero-backpatch routing | ❌ | Phase B persona signal not wired into the pipeline yet — the pipeline should route a back-patch-needed correctness fix to a committer who actually back-patches. |
| Move `#define` to `ltree.h` next to existing caps | ❌ | Subsystem-local discoverability convention. |

Compared to CB1, the gap shape **rhymes**: the generic pipeline catches the
docs-hygiene/test-coverage/cap-value-arithmetic class (mechanical
review-checklist items) but misses the four reflex-driven concerns
(security disclosure, subsystem-specific invariants, persona-aware
routing). **One sample is a hypothesis; two samples is a pattern.**

## 6. Recommended skill edits

Proposals added to the consolidating gap catalog (CB1 already raised
1-4; this calibration upgrades and adds):

1. **(UPGRADE from CB1 #2) Security@ embargo gate** — now backed by
   two patches (CB1 pgcrypto bomb, CB7 ltree amplification). Lift to
   `review-checklist` as a hard gate, not a soft hint: when the patch
   description matches `(DoS|denial.of.service|decompression bomb|
   amplification|integer overflow|buffer overflow|injection|TOCTOU)`
   AND the patch touches a path callable via a public SQL API (any
   `contrib/*/` `.c` exporting a `Datum *` function, any
   `src/backend/utils/adt/`, etc.), **fail** the checklist phase
   asking the author to confirm `security@postgresql.org` notification.
2. **(NEW) Persona-aware backpatch routing.** When the patch's
   `Backpatch:` claim ≠ master-only AND the predicted top committer
   (per `domain-ownership.md`) has zero or near-zero backpatches in
   24mo (per `committer-map.md`), surface a hint: "Top committer X
   doesn't backpatch in 24mo; the realistic landing committer for a
   v16/v17/v18 backport is Y. CC them on the thread." Drives off the
   committer-map + domain-ownership tables — pure corpus data, no
   external lookups needed.
3. **(NEW) Multibyte/encoding interaction check for byte-walking
   parsers.** When the patch touches a path that walks input
   byte-by-byte (`*p++`, `*input++`, manual `for` loops over
   characters in `varlena`/`text`/`cstring`), surface "confirm
   multibyte boundary handling — name the UTF-8 / GB18030 /
   EUC-* test case that exercises this". Driver: Noah #4 + Jeff
   "Unicode standard fidelity" persona bullets.
4. **(NEW) `injection_points` reproducer for DoS / scratch-allocation
   claims.** When a patch claims "this prevents N MB / N GB of scratch
   allocation", surface "consider measuring it at the allocation
   boundary via `src/test/modules/injection_points`". Driver: Noah #5.
5. **(NEW) Subsystem-local-cap discoverability.** When a patch adds a
   `#define` to a contrib `.c` file (not the header), surface "move
   to `<subsystem>.h` if a public-style cap, or to a static-scope
   block if private; cite the precedent constant in the same area".
   Driver: Peter Eisentraut style reflex.
6. **(UPGRADE from CB1 #1) Cleanup-on-early-return tracing** — still
   relevant: this patch is parser-side so no resource handle
   ownership, but the rule generalizes.

### Findings about the PATCH (not skill edits — log for Phase D)

- **Cap-value arithmetic doesn't match the cover's claim.** At the
  cap of 131072 total variants, the worst case is NOT "a few MB". A
  product of `num × (numOR + 1) = 131072` can be achieved as
  `365 × 360` giving ~131k variants and ~1.1 GB of scratch
  (`131072 × 24 = 3.1 MB` if ALL scratch were a single allocation;
  but the allocation is per-level, sized by `numOR + 1` — so the
  total scratch is `Σ num × (numOR + 1) × sizeof(nodeitem)` where
  the per-level sum can still reach hundreds of MB depending on
  shape). Phase D should refine the COVER §3 arithmetic or tighten
  the cap. Log in `patches/cb7-ltree-amplification/notes.md` (file
  doesn't exist yet; create on Phase D resume).
- **Multibyte interaction unaddressed.** The COVER doesn't mention
  whether the cap applies pre- or post-encoding-validation. Jeff
  will ask; have an answer ready.

## Notes

- **Phase B hole noted:** Chao Li persona missing. He's reviewing
  ltree directly (3 trailers in 24mo) and appears in many other
  subsystems' top reviewers. If he turns out to be a regular reviewer
  for Phase D candidates, write the persona before SP2/SP6.
- **Methodology working as intended:** two patches in, the consolidated
  gap catalog is producing five concrete, testable skill edits with
  clear persona drivers. The methodology is calibrated; CB8/SP2/SP6
  should reuse without restructure.

## Cross-references

- `patches/cb7-ltree-amplification/COVER.md` — patch description.
- `knowledge/issues/contrib-ltree.md` (does it exist?) — TODO check;
  if absent, the A13-sweep finding lives somewhere in `knowledge/issues/`.
- `knowledge/personas/peter-eisentraut.md`, `tom-lane.md`, `noah-misch.md`
  (#152), `michael-paquier.md`, `jeff-davis.md` — driver personas.
- `knowledge/personas/domain-ownership.md` — owner lookup for §2.
- `knowledge/personas/committer-map.md` — backpatch-rate input for
  recommendation #2.
- `knowledge/calibration/README.md` — methodology.
- `knowledge/calibration/cb1-pgcrypto-bomb.md` — sibling calibration;
  recommendation #1 is the upgrade of CB1 §6.2.
