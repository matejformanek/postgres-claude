# SP6 implementation notes

## Phase 1 — implementation + tests (single phase per R3)

**Status:** done.
**Commit:** `acd8c00fb96 pg_prewarm: REVOKE autoprewarm_* from PUBLIC` (in `dev/` branch `feature_sp6_autoprewarm_revoke`)
**Test scope:** `meson test --suite pg_prewarm` — green (regress OK; TAP `001_basic` SKIP because local Perl lacks `IPC::Run`).
**Broader test:** `meson test --no-rebuild` — 99 OK, 1 fail (ecpg/ecpg pre-existing flake: `Could not open file ... dec_test.c for reading`, unrelated; same flake SP7 saw).

### What changed

Eight files in `dev/`, all under `contrib/pg_prewarm/`:

1. **`pg_prewarm.control`** — `default_version = '1.2'` → `'1.3'`.
2. **`pg_prewarm--1.1--1.2.sql`** — appended two `REVOKE EXECUTE ... FROM PUBLIC` lines for the two autoprewarm functions, so fresh installs at v1.2 already pick up the tightening.
3. **`pg_prewarm--1.2--1.3.sql`** — new upgrade script that re-applies the REVOKEs explicitly. This is the path existing 1.2 deployments follow via `ALTER EXTENSION pg_prewarm UPDATE TO '1.3'`.
4. **`Makefile`** — added new SQL file to `DATA`.
5. **`meson.build`** — added new SQL file to `install_data`.
6. **`sql/pg_prewarm.sql`** — new regress block: create `regress_prewarm_nopriv`, `SET ROLE`, exercise both functions (expect permission-denied), test that targeted `GRANT EXECUTE ON FUNCTION autoprewarm_dump_now()` unblocks one function without affecting the other.
7. **`expected/pg_prewarm.out`** — updated to match new regress output.
8. **`t/001_basic.pl`** — parallel TAP block using the existing `test_user` role (created at line 14 of the TAP test). Same shape as the regress test: verify denial, then GRANT, then verify access. Runs in CI where `IPC::Run` is present.

### Surprises / drift

1. **`tap_tests=enabled` is a hard gate, not an override.** First attempt enabled TAP via `meson configure -Dtap_tests=enabled` to force the new permission test to run. This failed at the configure stage because `config/check_modules.pl` couldn't find `IPC::Run`. Reverted to `tap_tests=auto`, which silently SKIPs TAP suites on a system that lacks the required Perl modules. Lesson: on this Mac the TAP test path is dormant; upstream CI is where the new `001_basic.pl` block actually executes.

2. **Pivot: added the test in two flavors.** The original plan called for a TAP test only. Because local validation needed the regress flavor too, the patch ended up with permission tests in BOTH `sql/pg_prewarm.sql` (covers local + upstream regress CI) and `t/001_basic.pl` (covers upstream TAP CI). This is more robust than the plan and the duplication is ~10 lines per side — acceptable.

3. **`tmp_install` cache trap again, same as SP7.** First test run after `ninja install` failed because `build-debug/tmp_install/initdb-template` was missing. Had to: `rm -rf build-debug/tmp_install` + `meson test --suite setup` to regenerate. Then `meson test --suite pg_prewarm` worked. This is the SAME pattern that bit SP7; should be canonized in the build-and-run skill: "after touching contrib install files, regenerate tmp_install before testing".

4. **Already-banked the right diff at first run, but expected output drift bit.** First attempt of the regress run produced exactly the correct security-fix behavior (permission-denied messages for both autoprewarm functions when called from `regress_prewarm_nopriv`), but the test framework flagged it because I hadn't updated `expected/pg_prewarm.out`. Updating expected was a copy-paste from the diffs file. No real surprise — standard pg_regress workflow.

### What this phase did NOT do

- Did NOT touch `autoprewarm.c`. No C-side permission check added (intentionally — contrib convention is SQL-level REVOKE, and a C check would shadow the GRANT pathway).
- Did NOT address the second half of CB5: the dumpfile-path validation issue + `<<N>>` signed-int parse → `dsm_create(20*N)` OOM. That requires a separate patch with its own threat model (filesystem-write attacker, not SQL-only attacker).
- Did NOT add a downgrade script (`pg_prewarm--1.3--1.2.sql`). Aligned with PG contrib convention: a tightening upgrade doesn't ship a downgrade. Operators who need pre-1.3 grants can manually `GRANT EXECUTE ... TO PUBLIC`.

### Submission readiness

- `format-patch` ready: `git format-patch e18b0cb7344..feature_sp6_autoprewarm_revoke --output-directory ../sp6-autoprewarm-revoke/`
- Patch subject candidate: `pg_prewarm: REVOKE autoprewarm_* from PUBLIC`
- Backpatch candidates: yes (security tightening on already-shipped code). v16, v17, v18 all run extension version 1.2 with the same default-grant exposure. Plan to ship a backpatch series if reviewers agree.
- CF target: 60 (January 2026).

### End-of-implementation gate (R12)

- [x] Full `meson test --no-rebuild` — 99 OK, 1 unrelated pre-existing flake (ecpg dec_test.c)
- [x] `git log --oneline e18b0cb7344..HEAD` shows exactly 1 commit (single-phase plan)
- [x] Commit message in upstream PG style (no Co-Authored-By, no Plan: trailer per R5's exemption for upstream-bound commits). Plan link captured here in `notes.md` + planning/sp6-autoprewarm-revoke/.
- [ ] Upstream-bound: needs `review-checklist` + `patch-submission` skills. NEXT STEP.
- [x] Local branch ready for review.

### Next step

Either:
1. **Open hackers-list thread** with the patch + the backpatch question — but SP7 hasn't been sent yet either, so this would queue behind it.
2. **Stage in a PR for user review** (same model as SP7's PR #118).
3. **Move on to the next quick-win pitch** (SP10 PS-title password redaction or SP1 SCRAM iter cap GUC).

Recommend (2) — keep the same review-gate cadence as SP7 so the user has a single, consistent surface to compare both patches before either goes upstream.
