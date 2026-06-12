# Calibration — SP6 pg_prewarm autoprewarm REVOKE

**Patch:** `patches/sp6-autoprewarm-revoke/0001-pg_prewarm-REVOKE-autoprewarm_-from-PUBLIC.patch`
**Cover:** `patches/sp6-autoprewarm-revoke/COVER.md`
**Methodology:** `knowledge/calibration/README.md`
**Calibrated at:** 2026-06-12 against `source` @ `e18b0cb7344`.
**Sequence:** fifth (final) per-patch run. **Distinct shape**: this is the only patch that's an install-script privilege fix rather than a code-path patch — tests whether the methodology surfaces the install-script reviewer reflex flagged in `README.md` §Calibration-order.

## 1. Patch summary

Revokes `EXECUTE` permission from `PUBLIC` on the two
`autoprewarm_*` SQL-callable maintenance functions in
`contrib/pg_prewarm`:

- `autoprewarm_start_worker()` — launches the autoprewarm bgworker
- `autoprewarm_dump_now()` — immediate buffer dump

Neither has a C-side privilege check (`autoprewarm.c:813-859`);
both have been EXECUTE-grantable to PUBLIC since extension version
1.2 (added via commit `5fb5b6cf` in v11). Patch:

1. **`pg_prewarm--1.1--1.2.sql`**: adds REVOKE in the original 1.2
   upgrade script — so fresh installs already see the tightening.
2. **`pg_prewarm--1.2--1.3.sql`** (NEW): re-applies the REVOKEs so
   existing 1.2 deployments can `ALTER EXTENSION ... UPDATE TO '1.3'`
   to pick up the change.
3. **`pg_prewarm.control`**: bumps `default_version` from 1.2 to 1.3.
4. **Regression test coverage in both `sql/pg_prewarm.sql` AND
   `t/001_basic.pl`**: a non-superuser is denied; a targeted
   `GRANT EXECUTE` unblocks one function without affecting the other.

The shape is **install-script + .control + tests** — five files
touched, no `.c` changes. Convention precedent: pg_visibility,
adminpack, pg_walinspect tightenings have shipped this way.

## 2. Predicted reviewers

The 24mo `contrib/pg_prewarm/` history shows the directory's REAL
churn is the autoprewarm bgworker / buffer-stream integration
(Melanie Plageman 5 commits, Andres Freund 4 — Phase B-confirmed AIO
cluster), not the SQL install scripts. The install-script REFLEX
lives with the cross-contrib `--*.sql` reviewer pool (Tom Lane 11
commits 24mo, Michael Paquier 9, Peter Eisentraut 4).

| Rank | Reviewer | Why they would review | Persona |
|---|---|---|---|
| 1 | Tom Lane | **#1 install-script committer cross-contrib** (11 commits on `contrib/*/*--*.sql` in 24mo). Will land the privilege fix, will rewrite the commit message, will probe the `default_version` bump + downgrade question. | `knowledge/personas/tom-lane.md` |
| 2 | Nathan Bossart | #2 pg_prewarm committer (3 commits 24mo). Has done multiple pg_prewarm-class autoprewarm fixes. Specifically reviews this directory. | `knowledge/personas/nathan-bossart.md` |
| 3 | Michael Paquier | **#2 install-script committer cross-contrib** (9 commits 24mo). Likely backpatch landing committer for the v16/v17/v18 spread. | `knowledge/personas/michael-paquier.md` |
| 4 | Melanie Plageman | **#1 pg_prewarm committer 24mo** (5 commits — autoprewarm + read-stream integration). She owns this directory's code path. May or may not engage on the install-script side, but should be CC'd as the area owner. | `knowledge/personas/melanie-plageman.md` |
| 5 | Andres Freund | #3 pg_prewarm committer (4 commits, AIO worker pool tuning). Likely defers to Melanie/Nathan on the install-script question. | `knowledge/personas/andres-freund.md` |
| 6 | Peter Eisentraut | #3 install-script committer (4 commits 24mo). Style/discipline reflex on `--*.sql` files. | `knowledge/personas/peter-eisentraut.md` |
| 7 | Noah Misch | Privilege fixes are his explicit beat (`46b4f5c` "Fix SQL injection in logical replication origin checks"). DoS-on-public-API → his embargo reflex. | `knowledge/personas/noah-misch.md` |
| 8 | Heikki Linnakangas | Top R-by reviewer on pg_prewarm (2 trailers 24mo). Likely adds R-by. | `knowledge/personas/heikki-linnakangas.md` |
| 9 | Daniel Gustafsson | Joint #2 R-by reviewer (2 trailers 24mo). Test-module + install-script discipline reflex. | `knowledge/personas/daniel-gustafsson.md` |

## 3. Predicted review feedback, per reviewer

### Tom Lane (LEAD reviewer + likely landing committer)

Driven by `tom-lane.md`:

- **Will rewrite the commit message.** Scrub "postgres-claude/A14"; require `Discussion:` URL; shorten the body. The 4 enumerated discussion points are sensible — Tom may consolidate them into 2 paragraphs.
- **`default_version` bump question.** Confidence very high. Expect:
  *"Bumping `default_version` to 1.3 means `CREATE EXTENSION pg_prewarm;` (no version specified) installs 1.3. Existing 1.2 deployments need `ALTER EXTENSION UPDATE`. Is the upgrade script idempotent if run twice? What if 1.2 was already manually tightened?"* Tom routinely probes upgrade-path correctness on extension version bumps.
- **No downgrade script — COVER §3 self-justifies.** Tom will agree with the precedent (pg_walinspect, pg_visibility) but may ask: *"Add a comment in the 1.2→1.3 script saying 'no downgrade by design — operators who want PUBLIC access can manually GRANT'."*
- **REVOKE in the 1.1→1.2 script is a real edit to a SHIPPED script.** Confidence very high. Expect: *"We don't normally edit shipped --*.sql scripts after the version is out. The 1.1→1.2 script is in v11, v12, ..., v18. If we backpatch the REVOKE into that script, existing installations that already ran the 1.2 upgrade will see a different post-state on a fresh install vs an upgrade-from-1.1."* **This is the killer concern.** The right shape might be: leave 1.1→1.2 alone, just ship 1.2→1.3 with the REVOKE. COVER §point-1 needs an answer for this.
- **`Discussion:` URL.** Required.
- **Backpatch.** Tom will agree COVER §2's framing: defense-in-depth, DoS-class, logged-in user required → reasonable to back-patch to v16/v17/v18.
- **API/ABI back-compat on `pg_prewarm.h`.** N/A — no header changes.
- **Hashability / typecache.** N/A.

### Nathan Bossart

- **He owns autoprewarm internals.** Per `committer-map.md`, Nathan is #2 on the `bgworker` infrastructure cluster. Will check whether the REVOKE actually prevents the worker from running for legitimate use cases (the bgworker itself doesn't go through SQL — only `autoprewarm_start_worker()` does).
- **DBA-vs-user audience.** Expect: *"Confirm that the autoprewarm bgworker still starts at server startup without anyone needing to call the SQL function. The REVOKE only affects manual triggering."* True — the patch leaves the postmaster-side worker launch alone. Pre-empt by including this clarification in COVER.
- **Test coverage.** Will agree with the SQL+TAP test addition — Nathan likes both regression and TAP coverage on privilege changes.

### Michael Paquier

- **He may commit the backpatch.** Given Tom's queue depth and the install-script focus, Michael is a strong candidate to land the v16/v17/v18 spread.
- **`Discussion:` URL.** Required.
- **Subject re-tag.** Expect landed subject `pg_prewarm:` prefix — COVER already uses it. ✓.
- **Test coverage.** Will agree.
- **Extension upgrade-path correctness.** Michael is fastidious about extension version bumps. Expect: *"Walk through what happens for each starting version (1.0, 1.1, 1.2) under `ALTER EXTENSION ... UPDATE TO '1.3'`. The default cascading upgrade should produce the same end state."* Detailed inspection, but resolvable.

### Melanie Plageman

- **Area-owner CC, may not engage on the install-script side.** Per
  `melanie-plageman.md`: her recent pg_prewarm work is read-stream
  integration (buffer-scan modernization, not the SQL surface).
- **If she engages**, expect: *"Confirm that the worker still
  triggers autoprewarm on demand for a DBA via the function call —
  the regression test for that case was added, ✓ pre-empted."* Mostly
  she signs off with a `Reviewed-by:` trailer.

### Andres Freund

- **Defers to Melanie/Nathan.** Likely adds a `Reviewed-by:` trailer
  without engagement on the install-script side. Per `andres-freund.md`:
  his current focus is AIO + storage infrastructure, not contrib
  privileges.
- **If he engages on TAP test**, expect: *"Does `t/001_basic.pl`
  exercise the regress role correctly under `--with-extra-version`?"*
  Soft nit on TAP test discipline.

### Peter Eisentraut

- **Style on `--*.sql` scripts.** Confidence high — he has 4 commits
  in 24mo specifically on contrib `--*.sql` files (cleanup, casting,
  `pg_noreturn` follow-ups). Expect: *"Format the REVOKE statements
  on multiple lines for readability"* or *"Confirm tab-vs-space
  consistency with neighbor scripts."* Soft style nit.
- **`pg_prewarm.control` bump.** Standard. ✓.
- **Zero backpatch reflex.** Reviews-and-routes, doesn't backpatch.

### Noah Misch

Driven by `noah-misch.md`:

- **#1 "Where's the test?"** — **COVER §regression test names BOTH a
  SQL regress AND a TAP test.** Pre-empted. ✓. (First time in the 5
  calibrations the test wasn't a flag.)
- **#2 "Has security@ been notified?"** — **5-for-5 now if it
  triggers; but SP6 is the edge case.** SP6 is *not* a code-path DoS
  — it's a privilege-tightening defense-in-depth. COVER §2 explicitly
  argues "defense-in-depth, not an emergency CVE; logged-in user
  required; DoS-class not data disclosure." This is the argued
  exemption from the security@ gate the methodology's recommendation
  #1 anticipates. **The skill edit should support this: the gate is
  about asking the question, not auto-blocking; SP6 has the question
  answered in COVER §2.** Noah will agree with the
  pgsql-hackers-not-security@ routing once the argument is on record.
- **#3 backpatch story.** COVER §2 argues v16/v17/v18; Noah will
  agree.
- **#4 multibyte/encoding.** N/A (SQL-level only).
- **#5 reproducer.** Pre-empted by the test. ✓.
- **#6 inplace update.** N/A.

### Heikki Linnakangas

- **Likely adds `Reviewed-by:` trailer.** No specific engagement
  predicted on the install-script side.

### Daniel Gustafsson

- **Test-module + install-script discipline.** Per `daniel-gustafsson.md`
  "test module expected for new infra" reflex. SP6 already adds a
  TAP test; expect ack.
- **PG_TEST_EXTRA gating reflex.** The TAP test is unconditional —
  Daniel will check whether it should be gated under
  `PG_TEST_EXTRA`. Unlikely to require gating since the test is
  short, but he'll ask.
- **errorhandling discipline.** N/A (no code-path changes).

## 4. Generic pipeline output

1. **`Discussion:` trailer missing.** ✓ (Tom + Michael.)
2. **Test coverage** — SQL + TAP both present. **Mark green.** First
   patch in the set where test-coverage is pre-empted.
3. **Commit-message hygiene** — scrub A14 reference. (Tom.)
4. **Backpatch question** — verify v16/v17/v18 install-script
   identity. (Tom + Michael + Noah.)
5. **`default_version` bump** — standard extension upgrade pattern.
   The pipeline catches this as a mechanical check. (Matches Tom +
   Michael.)
6. **REVOKE syntax / SQL style** — standard checks. (Matches Peter.)
7. **Convention precedent named** — COVER names pg_visibility +
   adminpack. ✓ flagged as positive.

The generic pipeline does NOT catch:

- **`security@` embargo question + the EXEMPTION argument**
  (Noah #2 with twist). The SP6 case is "should this go to
  security@?" answered with "no, defense-in-depth + DoS-class + auth
  required". The pipeline needs to support both the gate AND the
  exemption path.
- **Editing-a-shipped-`--1.1--1.2.sql`-script is unusual** (Tom
  reflex). The install-script reflex from `README.md`'s
  Calibration-order plan turned out to live here. **This is the
  install-script reviewer reflex the methodology asked about.** No
  current skill encodes "don't modify shipped extension upgrade
  scripts; ship a new version instead".
- **Autoprewarm-via-postmaster path unchanged confirmation**
  (Nathan-area-owner reflex). The pipeline doesn't know to ask "the
  REVOKE only affects manual SQL triggering — confirm the
  postmaster-launched worker still runs unchanged".
- **`default_version` bump idempotency across starting versions 1.0,
  1.1, 1.2** (Michael upgrade-path reflex). Subsystem-local.
- **`PG_TEST_EXTRA` gating question on new TAP tests** (Daniel
  reflex). Already in `daniel-gustafsson.md`; no skill encodes it.
- **Persona-aware backpatch routing.** Tom backpatches at ~25% rate,
  so he's a fine landing committer. Rule doesn't fire here.

## 5. Gap analysis

| Predicted comment | Covered by §4? | Why missed |
|---|---|---|
| security@ embargo EXEMPTION path (defense-in-depth + auth-required) | ❌ | Edge case to the 4-for-4 pattern — needs the skill edit to support BOTH gate AND exemption argumentation. |
| "Don't edit shipped `--1.1--1.2.sql`; ship new version" install-script reviewer reflex | ❌ | **The install-script reflex the methodology flagged.** Tom's primary concern here; not in any skill. |
| Confirm postmaster-side autoprewarm unchanged | ❌ | Subsystem-area-owner reflex (Nathan). |
| `default_version` bump idempotency across 1.0/1.1/1.2 starting points | ❌ | Subsystem-local extension-upgrade reflex (Michael). |
| `PG_TEST_EXTRA` gating on new TAP tests | ❌ | Daniel persona reflex. |

**Pattern after 5 calibrations:**

- **security@ embargo:** **4-for-4 hard hit + 1 EXEMPTION (5/5
  triggered the question)**. Lift to checklist hard-gate with
  exemption support.
- **Noah test-omission override:** 3-for-3 with one exemption (SP6
  pre-empted with both SQL+TAP tests).
- **Persona-aware backpatch routing:** 2-for-3 (CB7+CB8 → yes;
  SP2 Jeff backpatches → no; SP6 Tom backpatches → no).
- **Subsystem-local invariants (cleanup-on-error, multibyte, third-
  state, install-script reflex):** EACH ONE was triggered by EXACTLY
  ONE patch. Confirms the "subsystem-local reflexes don't generalize
  — encode them per-subsystem" hypothesis.

## 6. Recommended skill edits (FINAL consolidated catalog)

Five calibrations, seven gap-catalog items, ready for the consolidated
PR that ends Phase C:

1. **`security@` embargo HARD GATE with exemption support.**
   Trigger: any patch description mentioning `(DoS|denial.of.service|
   decompression bomb|amplification|integer overflow|buffer overflow|
   injection|TOCTOU|privilege|REVOKE|GRANT)` AND any path callable from
   a public SQL API. Fail the design-fit phase until the author has
   either confirmed security@ notification OR provided an explicit
   exemption argument (the COVER §X "defense-in-depth + auth-required
   + DoS-class" shape is the model). **Calibration support: 5-for-5
   triggered.**

2. **Noah-style override of self-justified test omission on security
   patches.** Trigger: COVER acknowledges "no test, fixture would
   dominate buildfarm / would need scaffolding". Surface the
   `PG_TEST_EXTRA=stress` precedent (Gustafsson online-checksums
   work) and push for the test. **Calibration support: 3-for-3
   triggered, 1 pre-empted.**

3. **Persona-aware backpatch routing with backpatch-rate nuance.**
   Trigger: patch claims back-patching AND predicted top committer's
   24mo backpatch rate < 5%. Surface the realistic landing
   committer's name (from `committer-map.md` rate column +
   `domain-ownership.md` reviewer column). **Calibration support:
   2-for-2 (CB7 Peter, CB8 Peter); SP2/SP6 didn't fire because the
   area owners DO backpatch.**

4. **Cleanup-on-early-return tracing on resource-handle paths.**
   Trigger: patch adds an early `return` inside a function that owns
   a `z_stream`, `BufFile`, `FileFd`, `MemoryContext`, similar
   resource handle. Surface "trace the cleanup path under the new
   error return". **Calibration support: CB1 (compression filter).**

5. **Multibyte/encoding interaction check for byte-walking parsers
   AND text-processing primitives.** Trigger: patch walks input
   byte-by-byte OR caps input/output size on a text primitive.
   Surface "enumerate worst-case per encoding (UTF-8, GB18030,
   EUC_JP, EUC_KR, EUC_CN, EUC_TW); cite the Unicode TR /
   SpecialCasing.txt entry for any UTF-8-specific bound". **Calibration
   support: CB7 (parser) + SP2 (text primitive).**

6. **Subsystem-local-cap discoverability.** Trigger: patch adds a
   `#define` to a contrib `.c` file. Surface "move to
   `<subsystem>.h` if a public-style cap; cite the precedent
   constant in the same area". **Calibration support: CB7.**

7. **"Third state" cross-check for binary-format changes.** Trigger:
   patch changes how a flag-bit / version-bit / layout-bit is
   interpreted. Surface "enumerate the third state — bit set but
   structure invalid, OR bit unset but structure looks valid".
   **Calibration support: CB8.**

8. **`injection_points` reproducer for DoS / scratch-allocation
   claims.** Trigger: patch claims "prevents N MB/GB scratch
   allocation" or "fixes a race". Surface "include a
   `src/test/modules/injection_points` measurement of the boundary".
   **Calibration support: CB7 + CB8.**

9. **Hot-path branch-prediction / micro-benchmark check.** Trigger:
   patch adds a guard check on a function reachable from `WHERE` /
   `JOIN` / `GROUP BY` predicates (query-path-hot). Surface
   "include micro-benchmark confirming guard is unlikely-branch
   and adds <1% overhead". **Calibration support: SP2.**

10. **Symmetric-check refactor when N entry points need the same
    guard.** Trigger: patch adds same guard logic to 3+ entry points
    of the same module. Surface "consider a shared inline helper".
    **Calibration support: SP2 (Peter style on 4 pg_str* sites).**

11. **Install-script discipline — don't edit shipped `--A--B.sql`
    upgrade scripts; ship a new version instead.** Trigger: patch
    modifies `contrib/*/*--*.sql` where the file is from a
    previously-released version. Surface "shipped install-scripts
    are immutable post-release; ship `--B--C.sql` with the new
    behavior instead". **Calibration support: SP6 (Tom install-script
    reviewer reflex).**

11 catalog items total. **5 are persona-driven cross-cutting (1, 2,
3, 5, 9). 6 are subsystem-local reflexes (4, 6, 7, 8, 10, 11).** This
split is the right shape — generic skill edits do the persona-driven
ones; per-subsystem-doc edits hold the local-reflex ones.

## Notes

- **Methodology validated.** Five patches, six-section structure
  held throughout. Gap catalog converged from "looks like CB1
  produced something" to "two-for-two pattern" to "the catalog is
  saturated" with each successive run.
- **Phase C remaining work**: ONE consolidated PR that lands the 11
  catalog items as concrete edits to:
  - `.claude/skills/review-checklist/SKILL.md` (catalog items 1, 2,
    3, 9, 10)
  - `.claude/skills/pg-patch-review/SKILL.md` (4, 5, 6, 7, 8, 11)
  - `knowledge/subsystems/<x>.md` per-subsystem "Local reviewer
    reflexes" sections (6, 7, 11 specifically).
- **Phase D ready** after Phase C closes. Per-patch PATCH FINDINGS
  logged in calibration docs need to graduate into
  `patches/<slug>/notes.md` files when Phase D resumes.

## Cross-references

- `patches/sp6-autoprewarm-revoke/COVER.md`.
- `knowledge/personas/tom-lane.md`, `nathan-bossart.md`,
  `michael-paquier.md`, `melanie-plageman.md`, `andres-freund.md`,
  `peter-eisentraut.md`, `noah-misch.md` (#152),
  `heikki-linnakangas.md`, `daniel-gustafsson.md` — driver personas.
- `knowledge/calibration/{cb1,cb7,cb8,sp2,sp6}*.md` — full set of
  per-patch calibrations.
- `knowledge/calibration/README.md` — methodology.
