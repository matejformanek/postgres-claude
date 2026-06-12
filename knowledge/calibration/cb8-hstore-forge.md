# Calibration — CB8 hstore forged HS_FLAG_NEWVERSION

**Patch:** `patches/cb8-hstore-forge/0001-hstore-validate-structure-before-trusting-HS_FLAG_NE.patch`
**Cover:** `patches/cb8-hstore-forge/COVER.md`
**Methodology:** `knowledge/calibration/README.md`
**Calibrated at:** 2026-06-12 against `source` @ `e18b0cb7344`.
**Sequence:** third per-patch run after CB1 + CB7. Methodology unchanged.

## 1. Patch summary

`contrib/hstore/hstore_compat.c` had two flag-trust short-circuits —
`hstoreUpgrade()` and `hstoreValidNewFormat()` — that returned early
when `hs->size_ & HS_FLAG_NEWVERSION` without inspecting the actual
entry-offset array. A datum with the new-version bit set on top of
garbage offsets routes the downstream `HSTORE_KEY` / `HSTORE_VAL` macros
into `memcpy` from attacker-controlled byte offsets — an out-of-bounds
read in the consuming session, reachable via the public `bytea::hstore`
cast or any COPY restore of a corrupted dump.

Touches 1 file:
- `hstore_compat.c` (+~15 LOC across the two short-circuits — flag
  becomes intent-only; structural validation always runs;
  fast-path return requires BOTH flag AND structural agreement).

**Behavior change worth flagging**: `hstore_version_diag()` on a forged
datum now returns `valid_new=0 valid_old=0` (truthful), where before
it returned `valid_new=2 valid_old=0` (the flag-trust lie). COVER §1
already calls this out; reviewers may or may not consider this an
exposed contract.

No regression test (COVER §2 self-admission — building a fixture would
need ~50-100 LOC of hex-bytea scaffolding for one error-path test).

## 2. Predicted reviewers

Mined from 24mo commit + trailer history of `contrib/hstore/` (a
small, low-churn directory).

| Rank | Reviewer | Why they would review | Persona |
|---|---|---|---|
| 1 | Peter Eisentraut | Top committer (5 commits, all cleanup-class: `pg_noreturn`, `Use fallthrough attribute`, `Remove useless casting`, `Remove unused #include's`, anonymous-unions). Will land it if clean — won't backpatch (Phase B: zero backpatches in 24mo across 719 commits). | `knowledge/personas/peter-eisentraut.md` |
| 2 | Tom Lane | #2 committer (3 commits 24mo), the universal reviewer. Will look hard at the behavior change in `hstore_version_diag()` — contract concerns are his bread and butter. | `knowledge/personas/tom-lane.md` |
| 3 | Noah Misch | Not an hstore committer in 24mo, but the precise reflex for "OOB read via public SQL API + bytea path" + "did you add a fixture for the security claim". Same routing as CB1/CB7. | `knowledge/personas/noah-misch.md` |
| 4 | Michael Paquier | #3 committer (2 commits). Likely backpatch-landing committer (Peter punts; Tom backpatches but his queue is deeper). Recently has been doing pgcrypto/contrib security fixes, will recognize the shape. | `knowledge/personas/michael-paquier.md` |
| 5 | Heikki Linnakangas | Top trailer-only reviewer for hstore (2 R-bys in 24mo). Strong on-disk format / binary layout reflex — exactly this patch's invariant. | `knowledge/personas/heikki-linnakangas.md` |
| 6 | Chao Li | Joint #2 trailer reviewer (2 R-bys). Same Phase B follow-up flag as CB7. | (no persona) |

## 3. Predicted review feedback, per reviewer

### Peter Eisentraut (most-likely landing committer for master)

- **Style / include discipline.** Patch adds no new includes — `hstore.h` already pulls `hstore_compat.c`'s needs. ✓ Clean.
- **`#define HS_FLAG_NEWVERSION` redefinition?** No — patch doesn't change the macro. ✓.
- **Zero backpatch reflex.** Per `committer-map.md`, Peter has zero backpatches in 24mo across 719 commits. COVER §3 names v16/v17/v18 — expect Peter to **review + ack**, then **route to Michael or Tom for the actual backpatch**.
- **Soft nit on the new helper structure.** The flag-vs-structural duality (now requiring BOTH for fast-path) introduces a logically-and condition where there was a single check. Expect: *"Could the fast-path stay readable as `flag_says_new && structural_check(buf) == HS_VALID_NEW`? Same logic, named intent."* Low confidence.

### Tom Lane

- **The behavior-contract question is HIS.** Confidence very high.
  COVER §1 explicitly flags `hstore_version_diag()` returning
  `valid_new=2` before and `valid_new=0` after for forged inputs.
  Expect: *"Does any extension or test rely on the diagnostic
  returning the flag-claimed answer rather than the truth? It's a
  public function; the contract is at minimum 'what the bits say'.
  Argue this is the right change because the flag-claimed answer is
  the lie."* This is the kind of contract probing Tom is known for
  (per `tom-lane.md` "API/ABI back-compatibility" bullet).
- **Will rewrite the commit message.** Scrubbing the
  "postgres-claude/A13" reference; requiring `Discussion:` URL.
- **Backpatch implications.** Tom backpatches DoS / OOB-read fixes
  aggressively. Expect: *"v16/v17/v18 share `hstore_compat.c` — I'll
  push the unified backpatch."* High confidence he lands the actual
  backport even if Peter does the master push.
- **Width-type fussiness.** No width changes in the diff. ✓.

### Noah Misch

- **#1 "Where's the test?"** — COVER §2 self-admits no test, cites
  scaffolding cost. **Noah will not accept the self-justification
  on a security patch.** Expect: *"50-100 LOC of hex-bytea
  scaffolding is fine; this is the test we need because the OOB read
  is the entire point. Add it."* High confidence — Noah landed
  exactly this kind of fixture for the pgcrypto encoding-validation
  patch (`c5dc7547`).
- **#2 "Has security@ been notified?"** — **Third patch in a row
  triggering this gate.** CB1 + CB7 + CB8 all reach the rule.
  This is now overwhelmingly the highest-leverage skill edit; lift
  it from soft hint to hard gate in `review-checklist`.
- **#3 backpatch story** — COVER §3 says yes; Noah will agree.
- **#4 multibyte/encoding** — Not directly applicable; hstore is
  binary-format, not text. But the bytea-cast path means the input
  arrives byte-aligned regardless of encoding. ✓ no comment expected.
- **#5 reproducer.** **Will request a fixture.** Same as #1; Noah
  treats DoS / OOB-read claims as "show me the reproducer that
  triggers it, ideally via `injection_points` or as a SQL test".
- **#6 inplace update** — N/A.

### Michael Paquier

- **He may commit the backpatch.** Given Peter's zero-backpatch
  pattern and Tom's queue depth, Michael is the backpatch-landing
  committer to bet on. He has recent contrib-security commits
  (`pgcrypto: Fix buffer overflow in pgp_pub_decrypt_bytea`,
  similar shape).
- **`Discussion:` URL.** Required.
- **Subject re-tag.** COVER subject already uses `hstore:` prefix ✓.
- **Test coverage.** Will agree with Noah's "add the fixture" push;
  unlikely to land without one.
- **Trailer hygiene.** Will collect Tom + Noah + Heikki R-bys before
  pushing.

### Heikki Linnakangas

- **Binary-format reflex.** `hstore_compat.c` is exactly the kind of
  on-disk-format compatibility code Heikki has deep instincts for.
  Per `heikki-linnakangas.md` (Phase B persona — storage / shmem
  rework area). Expect: *"Walk through what HS_FLAG_NEWVERSION means
  vs what the structural check verifies. The flag is supposed to
  mark 'we wrote this with the new code path'; structural-check
  verifies 'the bytes still parse as new format'. What's the third
  state — bytes parse as new but were written by an old client that
  accidentally set the flag? Confirm that case is handled."* Medium-high
  confidence — Heikki has a reflex for "what's the third state I'm
  not seeing".
- **Performance reflex.** Removing a flag-trust short-circuit forces
  structural validation on every call. Expect: *"What's the
  benchmark on `hstore_in` for a typical 1-KB hstore? Is the
  structural check O(n)?"* Soft nit; the answer is yes O(n) but n
  is small for typical hstores. Pre-empt by including a
  micro-benchmark.

### Chao Li

No persona file yet (same flag as CB7 §6). Specific prediction
unavailable; likely contributes a `Reviewed-by:` after Tom/Noah
land theirs.

## 4. Generic pipeline output (what `pg-patch-review` would catch unaided)

Synthesized:

1. **`Discussion:` trailer missing.** (Tom + Michael ✓.)
2. **Test coverage gap — explicit self-admission.** "COVER §2
   acknowledges no test; security patches need one." (Matches Noah
   strongly; Peter, Tom, Michael also agree on this baseline.)
3. **Commit-message hygiene** — scrub "A13" reference; need 
   `Discussion:` URL. (Tom-shaped.)
4. **Backpatch question** — verify v16/v17/v18 file identity.
   (Matches Tom + Noah.)
5. **Behavior change in `hstore_version_diag()`.** This is a flagged
   contract change. (Matches Tom's predicted concern.) The generic
   pipeline catches "this changes return values of a public function"
   when the COVER says so.
6. **Style: the new helper structure is logically AND, was logically
   OR before.** (Matches Peter's soft nit.)

The generic pipeline does NOT catch:

- **`security@` embargo** (Noah #2). **Now three-for-three.**
- **`injection_points` / hex-fixture reproducer push-back when the
  COVER pre-emptively self-justifies skipping the test** (Noah #5).
  The pipeline accepts COVER §2's self-justification at face value;
  Noah does not.
- **"Third state" question — bytes parse as new but flag was set by
  an old client accidentally** (Heikki binary-format reflex). No
  skill encodes the "find the unaccounted state" cross-check.
- **Persona-aware backpatch routing** (Peter punts → Michael lands).
  Same gap as CB7 §6.2.
- **Micro-benchmark for newly-mandatory structural check** (Heikki
  performance reflex). Subsystem-local.

## 5. Gap analysis

| Predicted comment | Covered by §4? | Why missed |
|---|---|---|
| security@ embargo, three-patch pattern now | ❌ | Three-for-three. **Promote to checklist hard-gate; this is the catalog's flagship recommendation.** |
| Noah override of COVER's "no test, would need scaffolding" self-justification | ❌ | The pipeline reads COVER as truth; Noah reads COVER as a starting position to push back on. |
| "Third state" / unaccounted-state binary-format question | ❌ | Heikki reflex; no skill encodes the meta-check. |
| Persona-aware backpatch routing | ❌ | Same as CB7. |
| Micro-benchmark on newly-mandatory check | ❌ | Subsystem-local. |

The pattern is now solid across three patches:
- **5/5 of the security-class patches calibrated so far would have
  benefited from the `security@` embargo gate.**
- **2/2 of the back-patch-bearing patches (CB7, CB8) route through
  the zero-backpatch-committer hand-off pattern (Peter → Michael
  or Tom).**
- **2/2 of the contrib bomb/OOB-read patches got pushback on the
  "self-justified test omission" pattern.** Noah has the strongest
  voice on this.

## 6. Recommended skill edits

Consolidating gap-catalog status after three calibrations:

1. **(CB1+CB7+CB8 confirm) `security@` embargo HARD GATE.** Lift
   from soft hint to `review-checklist` hard gate; cite all three
   calibrations as motivation. Block at the design-fit phase: the
   patch's first decision is which forum to send to, and the
   pipeline should not let a clear DoS / OOB-read / injection patch
   default to pgsql-hackers without explicit author confirmation
   that security@ has been notified or that the issue is
   public-enough not to warrant embargo.
2. **(CB7+CB8 confirm) Persona-aware backpatch routing.** Now two
   patches in a row; promote from "new" to "confirmed". The rule:
   when the patch's predicted top committer has zero/near-zero
   backpatches in 24mo AND the patch claims back-patching, surface
   the realistic landing committer.
3. **(NEW for CB8) Skepticism of self-justified test omission on
   security patches.** When the COVER acknowledges "no test, the
   fixture would need N LOC of scaffolding", surface "is N LOC
   acceptable cost for asserting the security claim? Don't let the
   self-justification settle the question; expect Noah-class
   reviewers to push back." Driver: Noah persona "Where's the test?"
   reflex applied to the specific COVER §X pattern.
4. **(NEW for CB8) "Third state" cross-check for binary-format
   changes.** When the patch changes how a flag-bit / version-bit /
   layout-bit is interpreted, surface "enumerate the third state —
   the bit is set but doesn't mean what it claims, OR the bit is
   unset but the structure looks valid. What handles each?" Driver:
   Heikki binary-format reflex.
5. **(NEW for CB8) Micro-benchmark check when removing a
   short-circuit.** When the patch turns a flag-trust fast-path into
   a structural validation, surface "include a micro-benchmark
   confirming the new per-call cost is acceptable on a typical
   input". Driver: Heikki performance reflex on hot paths.
6. **(Carry from CB1+CB7) Multibyte/encoding check** — not
   triggered by CB8 (binary path, no encoding). No upgrade.
7. **(Carry from CB7) Subsystem-local cap discoverability** — not
   triggered by CB8 (no new `#define`). No upgrade.

## Notes

- **Methodology stable.** Three patches in, the six-section structure
  is producing convergent gap-catalog items. SP2 + SP6 should reuse
  without restructure.
- **Chao Li persona** still missing; he's appearing in every contrib
  calibration's predicted-reviewer set. Decision: write him before
  SP2 unless you (user) tell me to skip.
- **PATCH FINDING (logged here, will move to
  `patches/cb8-hstore-forge/notes.md` on Phase D resume)**: the
  `hstore_version_diag()` behavior change is a real contract
  question — could be enough to push CB8 to a deprecation-of-old-
  behavior cycle (1 release of warning, then enforce) instead of a
  unified backpatch. Have an answer ready.

## Cross-references

- `patches/cb8-hstore-forge/COVER.md`.
- `knowledge/personas/peter-eisentraut.md`, `tom-lane.md`,
  `noah-misch.md` (#152), `michael-paquier.md`,
  `heikki-linnakangas.md` — driver personas.
- `knowledge/calibration/README.md`,
  `knowledge/calibration/cb1-pgcrypto-bomb.md`,
  `knowledge/calibration/cb7-ltree-amplification.md` — sibling
  calibrations; gap catalog converges.
