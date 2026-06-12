# Calibration — SP2 pg_str* MaxAllocSize cap

**Patch:** `patches/sp2-pgstr-maxalloc/0001-Cap-input-size-for-pg_strlower-upper-title-fold-to-M.patch`
**Cover:** `patches/sp2-pgstr-maxalloc/COVER.md`
**Methodology:** `knowledge/calibration/README.md`
**Calibrated at:** 2026-06-12 against `source` @ `e18b0cb7344`.
**Sequence:** fourth per-patch run after CB1+CB7+CB8. First non-contrib patch — touches `src/backend/utils/adt/pg_locale.c`, the core case-mapping primitive.

## 1. Patch summary

Adds an early input-size cap of `(MaxAllocSize - 1) / 3` (~357 MB) inside
each of the four pg_str* case-mapping entry points in
`src/backend/utils/adt/pg_locale.c`:

- `pg_strlower()`, `pg_strupper()`, `pg_strtitle()`, `pg_strfold()`

All four dispatch to ICU's `ucasemap_utf8To*` or libc, which can expand
the result up to **3× input length** (German sharp s → "SS", Greek final
sigma). The documented two-call "size and grow" pattern in
`formatting.c` (`str_tolower`, `str_toupper`, `str_initcap`,
`str_casefold`) trips MaxAllocSize on the `repalloc(3*srclen+1)` after
the initial walk has already happened — resulting in the opaque
`"invalid memory alloc request size 2148532223"` message with ~700 MB
live palloc + the ICU walk cost burned.

The cap fires before dispatch. Above it, `ereport
ERRCODE_PROGRAM_LIMIT_EXCEEDED` with a specific message naming the
SQL-visible function: `"input string is too long for lower()"` +
`DETAIL: Input length N exceeds the case-mapping limit of 357913940 bytes.`

Files touched: 1 (`pg_locale.c`, +~12 LOC per primitive × 4 = ~50 LOC).
No header changes. **Also fixes the same class of bug in `contrib/ltree`
for free** (lquery_op.c, crc32.c call pg_strfold — COVER §1 calls this
out as a design feature).

No regression test (COVER §3 self-admission — input >357 MB would
dominate buildfarm time + memory; documented ICU contract is the
structural argument).

## 2. Predicted reviewers

Mined from 24mo commit + trailer history of
`src/backend/utils/adt/pg_locale.c`, `src/include/utils/pg_locale.h`,
and `src/backend/utils/adt/formatting.c`:

| Rank | Reviewer | Why they would review | Persona |
|---|---|---|---|
| 1 | Jeff Davis | **Top committer by a wide margin: 51 commits 24mo** in `pg_locale.c`. He owns this subsystem. Will land it, will probe Unicode-fidelity, will request specific codepoint test cases. **The lead reviewer for sure.** | `knowledge/personas/jeff-davis.md` |
| 2 | Peter Eisentraut | #2 committer (26 commits 24mo). Co-owner of `pg_locale.c` cleanup; style + include discipline reviewer. | `knowledge/personas/peter-eisentraut.md` |
| 3 | Tom Lane | #3 committer (6 commits). ABI + error-message-style reviewer. Will probe the cap value choice + errmsg wording. | `knowledge/personas/tom-lane.md` |
| 4 | Noah Misch | Strong reflex for "DoS via allocation on a public SQL API" + multibyte interaction. SP2 specifically resolves the multibyte 3× expansion attack — directly his wheelhouse (see his `9f4fd11` "Fix SUBSTRING() for toasted multibyte characters" + `627acc3` "GB18030 SIGSEGV"). | `knowledge/personas/noah-misch.md` (#152) |
| 5 | Thomas Munro | #4 committer (4 commits — encoding-table removal `MULE_INTERNAL`). Encoding/charset reflex. | `knowledge/personas/thomas-munro.md` |
| 6 | Michael Paquier | #4 tie (4 commits). Likely backpatch landing committer if Jeff routes the backport. | `knowledge/personas/michael-paquier.md` |
| 7 | Chao Li | **Top R-by reviewer: 17 R-bys 24mo on this area.** Per `chao-li.md` (#155): trailer multiplier, attends widely. Expect his R-by to land. | `knowledge/personas/chao-li.md` (#155) |
| 8 | Heikki Linnakangas | #2 R-by reviewer (4 R-bys). Performance-on-hot-paths reflex — `pg_strlower` is in the query path. | `knowledge/personas/heikki-linnakangas.md` |

## 3. Predicted review feedback, per reviewer

### Jeff Davis (LEAD reviewer + likely landing committer)

Driven by `jeff-davis.md` "What to expect":

- **Unicode standard fidelity. CONFIDENCE: VERY HIGH.** This is exactly the cap that ICU's documented 3× expansion makes structurally correct, and Jeff has the deepest Unicode reflex in the project. Expect:
  - *"Cite the Unicode TR or RFC behind the 3× claim."* The COVER §1 names "German sharp s → SS, Greek final sigma"; Jeff will want the precise Unicode reference (likely UAX #29 + the SpecialCasing.txt entries).
  - *"What's the worst case for `pg_strtitle()`? Title-casing has different expansion behavior than upper/lower; confirm 3× is the bound for ALL four primitives, not just upper/lower."* This is the concrete-failure-example reflex turned on the patch's correctness claim.
- **`length=-1` and "magic" API value reflex.** Patch uses `MaxAllocSize / 3` as a derived constant. Expect: *"Why `(MaxAllocSize - 1) / 3` and not a named constant like `PG_CASE_MAP_MAX_INPUT_BYTES`?"* Soft nit; aligned with his `length=-1` pattern.
- **Method-table dispatch.** Patches that branch on `locale->provider == COLLPROVIDER_LIBC` get pushed back. SP2 puts the cap BEFORE the dispatch — so the cap applies uniformly to ICU + libc + C/POSIX. ✓ Aligned with Jeff's preferred shape. He'll like this.
- **C11 char16/char32 typedefs.** Not applicable — patch doesn't touch codepoint types.
- **Concrete failure example.** Expect: *"Add a SQL-level test that triggers the cap with a specific input. ~357 MB is too large for the regression suite, but a `PG_TEST_EXTRA=stress` gated test would settle the question."* High confidence — matches Jeff's "concrete failure example" reflex AND Noah's "where's the test" reflex AND the COVER §3 self-admission. **The test will be asked for.**
- **Short body is fine.** Don't pad. COVER body is already appropriately terse. ✓.

### Peter Eisentraut

- **Style/cleanup reflex.** Cap implementation is mechanical and uniform across the 4 primitives — Peter will appreciate the symmetry. Expect: *"Could the cap-check be a single inlined helper `pg_str_check_input_size(srclen, fname)`?"* Soft nit — reduces 4 sites to 1 + 4 thin wrappers.
- **Include discipline.** Patch likely adds no new includes (`MaxAllocSize` from `utils/memutils.h` is already pulled by `pg_locale.c`'s existing `palloc` usage — verify in the patch diff).
- **Zero backpatch reflex.** Per `peter-eisentraut.md`: zero backpatches in 24mo. COVER §4 says yes to v16/v17/v18 — expect Peter to **review + ack**, then route to Jeff or Michael for the actual backport.
- **`uint64`/`Size` width fussiness.** SP2 uses `Size` (the `srclen` parameter is `Size`); cap comparison is `srclen > (MaxAllocSize - 1) / 3`. Both sides `Size`. ✓.

### Tom Lane

- **Will rewrite the commit message.** Scrubbing the "postgres-claude/A7+A15+A16" reference; requiring `Discussion:` URL.
- **Error-message wording.** *"DETAIL: Input length N exceeds the case-mapping limit of 357913940 bytes."* — Tom is fussy about error-message style. Expect: *"The 'case-mapping limit' phrase is unusual. Either reuse 'maximum allowed string length' or define why this is its own concept."* Soft nit.
- **ABI back-compatibility on `pg_locale.h`.** No header changes in SP2 (cap is in `.c`). ✓.
- **Backpatch implications.** COVER §4 says yes. Tom will agree on a DoS fix. **He may co-commit the unified back-patch with Jeff if Jeff routes the backport.**
- **Hashability / typecache.** N/A.

### Noah Misch

Driven by `noah-misch.md` (#152):

- **#1 "Where's the test?"** — COVER §3 self-admits, cites buildfarm cost. **Noah will push back exactly like he did on CB1+CB8.** *"`PG_TEST_EXTRA=stress` is a long-standing pattern (Daniel Gustafsson's online-checksums work uses it). Add the test there."* Three patches in a row now where Noah will override the "no test" self-justification.
- **#2 "Has security@ been notified?"** — **FOUR for four.** The 4th calibration of a DoS-on-public-SQL-API patch triggers Noah's embargo reflex. SP2 is reachable via `lower(text)`, `upper(text)`, etc. — every role has EXECUTE. Embargo question is real here.
- **#3 backpatch story.** COVER §4 says yes; Noah will agree.
- **#4 multibyte/encoding interaction.** **THIS IS HIS PATCH.** Noah's GB18030 SIGSEGV + multibyte SUBSTRING fix are exactly the upstream commits SP2 generalizes. Expect:
  - *"What's the expansion behavior under GB18030 specifically? UTF-8's 3× bound is documented; GB18030 may have a different worst case."* Genuine concern — needs investigation before SP2 sends.
  - *"What about EUC_JP / EUC_KR — these have specific case-mapping quirks?"* Medium-high confidence — Noah recently committed `0163951` "EUC_CN, EUC_JP, EUC_KR, EUC_TW: Skip U+00A0 tests instead of failing" so he's tracking these encodings.
- **#5 reproducer.** Same as #1 — push for `PG_TEST_EXTRA=stress` test.
- **#6 inplace update.** N/A.

### Thomas Munro

Driven by `thomas-munro.md`:

- **Encoding-table awareness.** Recent commit `77645d4` "Remove MULE_INTERNAL encoding" — Thomas tracks encoding-table cleanup. Expect: *"After MULE_INTERNAL removal, are there any other encodings whose case-mapping might exceed 3×? The Cyrillic encodings have 1:1 maps, the East Asian ones are punted to ICU. Confirm the bound."*
- **Performance reflex on hot paths.** Adding 4 entry-point checks on every case-mapping call. *"Branch-prediction-friendly? Likely yes — input >357 MB is the unlikely branch. Confirm via micro-benchmark on `pg_strlower` with a 1 KB input."* Soft nit.
- **JIT touch.** N/A.

### Michael Paquier

- **Likely backpatch landing committer.** Jeff usually pushes his own, but Michael often handles backports of correctness fixes that span 4 versions.
- **`Discussion:` URL.** Required.
- **Subject re-tag.** *"Why not `pg_locale:` prefix?"* COVER subject is `Cap input size for pg_strlower/upper/title/fold to MaxAllocSize/3` — Michael may prefer `pg_locale: cap input size for case-mapping primitives at MaxAllocSize/3`. Soft re-tag.
- **Test coverage.** Will agree with Jeff + Noah's PG_TEST_EXTRA=stress push.

### Chao Li

Per `chao-li.md` (#155): trailer multiplier. Expect his `Reviewed-by:` to land on the merge commit if there are 2+ other R-bys. No specific shape prediction.

### Heikki Linnakangas

- **Performance reflex on hot paths.** Same concern as Thomas above. *"`pg_strlower` is on the query path for `WHERE col = lower($1)`. Confirm the new check is in the unlikely branch and the compiler hoists the comparison out of any loop."* Medium-high confidence.
- **Will not flag the cap value.** Heikki's signature concern is binary format + performance, not constant-choice debate (per `heikki-linnakangas.md`).

## 4. Generic pipeline output (what `pg-patch-review` would catch unaided)

1. **`Discussion:` trailer missing.** (Tom + Michael.)
2. **Test coverage gap — explicit self-admission.** (Matches Jeff + Noah + Michael.) The COVER §3 admission is at face value here; pipeline doesn't push back.
3. **Commit-message hygiene** — scrub "A7+A15+A16" reference. (Tom.)
4. **Backpatch question** — verify v16/v17/v18 file identity for `pg_locale.c`. (Tom + Noah + Michael.)
5. **Error-message wording** — "case-mapping limit" is unusual phrasing. (Tom.)
6. **Cap-value choice** — `(MaxAllocSize - 1) / 3` is derived; consider a named constant. (Peter style nit.)
7. **Coverage of all 4 primitives** — verify each entry point has the cap; symmetric application. (Mechanical check.)

The generic pipeline does NOT catch:

- **`security@` embargo** (Noah #2) — **4-for-4 now.**
- **Unicode TR / SpecialCasing.txt citation requirement on the 3× claim** (Jeff Unicode-fidelity reflex). Subsystem-local; even `domain-ownership.md` doesn't encode this.
- **Per-encoding worst-case verification** (Noah #4 + Thomas encoding reflex). The 3× bound is documented for UTF-8/ICU; GB18030 + EUC_* may differ. **This is a genuine pre-send investigation item.**
- **Push-back on COVER's self-justified test omission with `PG_TEST_EXTRA=stress` precedent** (Noah override pattern; 3rd time triggered).
- **Hot-path branch-prediction / micro-benchmark check** (Thomas + Heikki performance reflex).
- **Helper-function refactor of the 4-site symmetric check** (Peter style reflex).
- **Persona-aware backpatch routing** (Jeff is the area owner BUT pushes his own backports too — actually Jeff DOES backpatch unlike Peter; the routing rule needs nuance).

## 5. Gap analysis

| Predicted comment | Covered by §4? | Why missed |
|---|---|---|
| security@ embargo, 4-for-4 pattern | ❌ | This is now overwhelming — the most reproduced gap in the calibration set. |
| Unicode TR citation for 3× expansion claim | ❌ | Jeff-specific reflex; no skill encodes "cite the Unicode TR" requirement. |
| Per-encoding worst-case (GB18030, EUC_*) | ❌ | Noah + Thomas reflex; the patch may have a real GAP here — pre-send investigation needed. |
| Noah test-omission override (PG_TEST_EXTRA=stress) | ❌ | Three-for-three now. |
| Hot-path branch-prediction check | ❌ | Heikki + Thomas; subsystem-local. |
| Helper-function refactor for 4-site symmetric checks | ❌ | Peter style reflex; subsystem-local. |
| Persona-aware backpatch routing (Jeff backpatches; Peter doesn't) | ❌ | The rule from CB7/CB8 needs nuance — it's about "is the predicted top committer a backpatcher", not just a binary check. |

The pattern is now four-for-four on security@. **This calibration is the
one where the catalog's flagship recommendation has the most data.**

**SP2-specific PATCH FINDING (most important from this calibration)**: the
3× expansion bound is documented for **UTF-8** specifically (Unicode case
mapping). It may not hold for non-Unicode encodings — GB18030 and the
EUC_* family have different case-mapping conventions, and `pg_strfold` /
`pg_strlower` in libc mode (not ICU mode) may have different worst-case
bounds. Pre-send investigation: enumerate the bound per-encoding, OR
restrict the cap to UTF-8-only paths and use a different cap for non-UTF-8.
Log in `patches/sp2-pgstr-maxalloc/notes.md`.

## 6. Recommended skill edits

Consolidating gap-catalog after four calibrations:

1. **(CB1+CB7+CB8+SP2 confirm; 4-for-4) `security@` embargo HARD GATE.**
   This is now overwhelmingly evidence-backed. Promote unconditionally.
   No more "consider" — checklist phase fails until the author confirms
   security@ notification or argues why this isn't embargo-warranted.
2. **(CB7+CB8+SP2 confirm — 3-for-3 if Jeff doesn't backpatch the cap;
   actually 2-for-3 because Jeff DOES backpatch — needs nuance)
   Persona-aware backpatch routing.** Refine the rule: when the
   predicted top committer's 24mo backpatch rate is <5%, surface the
   alternative landing committer. Jeff Davis's rate is ~15-20% (need
   to compute), so for SP2 Jeff IS the right person — the rule
   shouldn't fire here.
3. **(CB1+CB8+SP2 confirm — 3-for-3) Noah override of COVER's
   self-justified test omission on security patches.** Three patches
   in a row. Add to `review-checklist`: when COVER acknowledges "no
   test, the fixture would dominate buildfarm time / would need N LOC
   of scaffolding", surface the `PG_TEST_EXTRA=stress` precedent
   (Daniel Gustafsson's online-checksums work) and push for the test
   anyway.
4. **(NEW for SP2) Unicode TR citation requirement for case-mapping /
   normalization claims.** When a patch claims a Unicode-derived
   expansion factor or normalization bound, surface "cite the
   Unicode TR / annex / SpecialCasing.txt entry that documents this".
   Driver: Jeff "Unicode standard fidelity" persona bullet.
5. **(NEW for SP2) Per-encoding worst-case verification.** When a
   patch caps input/output size on a text-processing primitive,
   surface "enumerate the worst-case expansion per encoding:
   UTF-8 (documented), GB18030, EUC_JP, EUC_KR, EUC_CN, EUC_TW. The
   bound may differ per-encoding." Driver: Noah #4 + Thomas
   encoding-removal reflex.
6. **(NEW for SP2) Hot-path branch-prediction / micro-benchmark
   check.** When a patch adds a guard check on a function that's
   reachable from `WHERE` / `JOIN` / `GROUP BY` predicates (i.e.
   query-path-hot), surface "include micro-benchmark numbers
   confirming the guard is in the unlikely branch and adds <1%
   overhead to typical-size inputs." Driver: Thomas + Heikki
   performance reflex.
7. **(NEW for SP2) Symmetric-check refactor when N entry points
   need the same guard.** When a patch adds the SAME guard logic
   to 3+ entry points of the same module, surface "consider a
   shared inline helper to keep the entry points symmetric".
   Driver: Peter style reflex on symmetric primitives.

## Notes

- **One remaining calibration:** SP6 autoprewarm REVOKE. Different
  shape — install-script privilege fix, not code path. Will test
  whether the methodology surfaces the "install-script reviewer
  reflex" the calibration plan in `README.md` flagged.
- **Methodology is now battle-tested.** Four patches, six-section
  shape held throughout, gap catalog converged to seven concrete
  edits. Phase C's remaining work after SP6 is the consolidated
  gap-catalog PR that lands the seven skill edits.
- **PATCH FINDING (SP2-specific, log for Phase D):** the 3× bound
  may not hold for non-UTF-8 encodings. Pre-send investigation
  required. Log in `patches/sp2-pgstr-maxalloc/notes.md` when
  Phase D resumes.

## Cross-references

- `patches/sp2-pgstr-maxalloc/COVER.md`.
- `knowledge/personas/jeff-davis.md`, `peter-eisentraut.md`,
  `tom-lane.md`, `noah-misch.md` (#152), `thomas-munro.md`,
  `michael-paquier.md`, `chao-li.md` (#155),
  `heikki-linnakangas.md` — driver personas (all 8 exist now).
- `knowledge/calibration/README.md`, sibling docs (CB1/CB7/CB8) —
  gap-catalog convergence.
