# Plan: SP6 — `autoprewarm` REVOKE-from-PUBLIC

**Status:** READY. Single-phase plan.
**Pitch:** `knowledge/phase-d-pitches.md` SP6 + CB5
**Source pin:** `e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa` (master at 2026-06-10)
**Slug:** `sp6-autoprewarm-revoke`
**Branch:** `feature_sp6_autoprewarm_revoke` (in `dev/`)
**Expected commits:** 1 (single phase per R3 + R5)

## §1 Problem statement

`contrib/pg_prewarm` exposes two SQL-callable functions added in extension version 1.2
(`pg_prewarm--1.1--1.2.sql:6-13`):

- `autoprewarm_start_worker()` — launches the autoprewarm bgworker; iterates over all
  shared-buffer headers (`autoprewarm.c:665-665+` apw_dump_now), contending for
  `BufferDescriptorGetContentLock` spinlocks.
- `autoprewarm_dump_now()` — performs an immediate buffer-state dump; same scan cost.

Neither has a `REVOKE EXECUTE ... FROM PUBLIC` in any install or upgrade script. The PG
default for `CREATE FUNCTION` is `EXECUTE` to `PUBLIC`. Consequence: **any logged-in
user**, including unprivileged ones, can:

1. Trigger an O(NBuffers) scan + spinlock acquisition pattern on demand — a denial-of-
   service vector on busy systems.
2. Force a dumpfile write via `apw_dump_now(false, true)` (`autoprewarm.c:852-855`), with
   no rate limiting.

The C-side functions have NO `pg_has_role` / `superuser()` / `pg_read_all_settings`
membership check (`autoprewarm.c:813-859`). Access control is **entirely** the missing
SQL-level REVOKE.

A14 surfaced this in the sweep that produced `knowledge/issues/pg_prewarm.md`. Catalogued
as **CB5** + **SP6** in `knowledge/phase-d-pitches.md`.

## §2 Approach

Standard PG contrib pattern for tightening permissions on already-shipped extension
functions: introduce a new extension version with the REVOKE, and also write the REVOKE
into the existing fresh-install path.

1. **Bump `default_version`** in `pg_prewarm.control` from `1.2` to `1.3`.
2. **Add `pg_prewarm--1.1--1.2.sql` REVOKEs** for the two autoprewarm functions, so
   fresh installs at version 1.2 (via the upgrade chain `1.1 → 1.2`) get the locked-
   down grants. This catches anyone explicitly pinning to `--with-version 1.2`.
3. **Create `pg_prewarm--1.2--1.3.sql`** containing `REVOKE EXECUTE ON FUNCTION
   autoprewarm_start_worker(), autoprewarm_dump_now() FROM PUBLIC;` — this is the
   upgrade DBAs run on existing installs. The fact that we bump 1.2 → 1.3 specifically
   to deliver a REVOKE makes the security-fix nature explicit.
4. **Extend the TAP test** `t/001_basic.pl` to verify that `test_user` (the
   already-existing unprivileged role) gets `permission denied` when calling both
   autoprewarm functions, and succeeds after explicit `GRANT EXECUTE`.

No C-side changes. No new GUC. No catalog bumps.

## §3 Files that change

| File | Change | LOC |
|---|---|---|
| `contrib/pg_prewarm/pg_prewarm.control` | `default_version = '1.3'` | 1 |
| `contrib/pg_prewarm/pg_prewarm--1.1--1.2.sql` | Add REVOKEs after the two CREATEs | +2 |
| `contrib/pg_prewarm/pg_prewarm--1.2--1.3.sql` (NEW) | REVOKE upgrade script | +6 |
| `contrib/pg_prewarm/Makefile` | Add the new SQL file to `DATA` | +1 |
| `contrib/pg_prewarm/meson.build` | Add the new SQL file to `install_data` sources | +1 |
| `contrib/pg_prewarm/t/001_basic.pl` | Append permission tests for autoprewarm fns | +~15 |

**Sites verified against current source (pin `e18b0cb7344`):**
- `source/contrib/pg_prewarm/pg_prewarm.control:4` — `default_version = '1.2'`
- `source/contrib/pg_prewarm/pg_prewarm--1.1--1.2.sql:6-13` — two CREATE FUNCTION blocks
- `source/contrib/pg_prewarm/autoprewarm.c:813-859` — neither function has C-side ACL check
- `source/contrib/pg_prewarm/t/001_basic.pl:48-72` — existing test_user permission-test pattern
- `source/contrib/pg_prewarm/Makefile` and `meson.build` — DATA / install_data lists

## §4 Catalog impact

None to system catalogs. Extension version bump 1.2 → 1.3. `pg_extension.extversion`
moves to `1.3` after the user runs `ALTER EXTENSION pg_prewarm UPDATE`.

## §5 Behavior changes

- **Fresh installs of pg_prewarm at 1.3 (or 1.2 from a fresh master build):** non-
  superusers can no longer call `autoprewarm_start_worker()` or `autoprewarm_dump_now()`
  without explicit `GRANT EXECUTE`. This is the intended security tightening.
- **Existing 1.2 installs:** unchanged until DBA runs `ALTER EXTENSION pg_prewarm UPDATE
  TO '1.3'`. This is intentional; we cannot retroactively REVOKE without an upgrade
  action.
- **No downgrade script** (1.3 → 1.2): not generally provided by PG contrib; if a user
  needs to undo, they can manually `GRANT EXECUTE ... TO PUBLIC`. Aligned with how
  pg_walinspect / adminpack handled similar tightenings.

## §6 Test plan

Extend `t/001_basic.pl` (`autoprewarm.c` already exercises `test_user` for `pg_prewarm`).
After the existing `autoprewarm_dump_now()` invocation in the superuser path (~line 75),
add a `test_user` block:

```perl
# test_user should be unable to call autoprewarm_* without explicit GRANT
($cmdret, $stdout, $stderr) = $node->psql(
    "postgres",
    "SELECT autoprewarm_dump_now();",
    extra_params => [ '--username' => 'test_user' ]);
ok($stderr =~ /permission denied for function autoprewarm_dump_now/,
    'autoprewarm_dump_now blocked by REVOKE');

($cmdret, $stdout, $stderr) = $node->psql(
    "postgres",
    "SELECT autoprewarm_start_worker();",
    extra_params => [ '--username' => 'test_user' ]);
ok($stderr =~ /permission denied for function autoprewarm_start_worker/,
    'autoprewarm_start_worker blocked by REVOKE');

# explicit GRANT should re-enable
$node->safe_psql("postgres",
    "GRANT EXECUTE ON FUNCTION autoprewarm_dump_now() TO test_user;");
$result = $node->safe_psql(
    "postgres",
    "SELECT autoprewarm_dump_now();",
    extra_params => [ '--username' => 'test_user' ]);
like($result, qr/^[0-9]+$/, 'autoprewarm_dump_now succeeds after GRANT');
```

**Phase-end check:** `meson test --suite pg_prewarm` must pass (existing 001_basic.pl
checks PLUS the new test_user blocks).

## §7 Implementation sketch

`pg_prewarm.control`:
```
-default_version = '1.2'
+default_version = '1.3'
```

`pg_prewarm--1.1--1.2.sql` (append after the two CREATE FUNCTION blocks):
```sql
REVOKE EXECUTE ON FUNCTION autoprewarm_start_worker() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION autoprewarm_dump_now() FROM PUBLIC;
```

`pg_prewarm--1.2--1.3.sql` (NEW):
```sql
/* contrib/pg_prewarm/pg_prewarm--1.2--1.3.sql */

-- complain if script is sourced in psql, rather than via ALTER EXTENSION
\echo Use "ALTER EXTENSION pg_prewarm UPDATE TO '1.3'" to load this file. \quit

REVOKE EXECUTE ON FUNCTION autoprewarm_start_worker() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION autoprewarm_dump_now() FROM PUBLIC;
```

`Makefile` — add `pg_prewarm--1.2--1.3.sql` to the `DATA` list.
`meson.build` — add the new file to `install_data` `sources`.

## §8 Phase-end check

```bash
cd dev
ninja -C build-debug install
rm -rf build-debug/tmp_install   # bust the cached install (SP7 lesson)
meson test -C build-debug --suite pg_prewarm
```

Expected: green; existing 7 tests + 3 new tests pass.

## §9 Risk + reviewer concerns

**Anticipated reviewer pushback:**

1. *"Why bump default_version instead of just adding REVOKE to --1.1--1.2.sql?"* — Two
   reasons: (a) existing 1.2 installs in the field don't get re-protected without an
   upgrade trigger; bumping forces the migration to be visible in `ALTER EXTENSION`
   output. (b) Consistent with how pg_walinspect tightened (added 1.1 with REVOKE on
   `pg_get_wal_block_info` show_data restrictions).
2. *"Should the C functions also check role membership?"* — Arguable. The pattern in
   `pg_read_all_settings` is "default-allow at SQL, REVOKE in install" rather than
   "default-deny in C". Sticking to the lighter SQL-only REVOKE matches contrib
   convention; a C-side check would be redundant with the REVOKE for the common case
   and would complicate `GRANT EXECUTE ... TO admin_role` flows.
3. *"Backpatch?"* — Yes, this is a security tightening for code already shipped. v16 +
   v17 + v18 are all running 1.2. Backpatch via the same SQL changes (bump default
   to 1.3 on those branches, add the upgrade script). Master gets it first.
4. *"What about `pg_prewarm()` itself?"* — Out of scope. `pg_prewarm(regclass, ...)`
   already does relation-level permission checks via `ReadBufferExtended` → catalog
   ACL. The TAP test exercises this (lines 48-72).

**Known limitations after this patch:**
- The dumpfile path validation issue ("autoprewarm dump-file path is unvalidated +
  `<<N>>` signed-int parse → `dsm_create(20*N)` OOM" — CB5's second half) is **not
  addressed** by this patch. That's a corruption-of-dumpfile attack requiring
  filesystem write access, which has its own threat model. Tracked as separate
  follow-up.

## §10 Cross-corpus echoes (this fix touches)

- A14 sweep finding (`knowledge/issues/pg_prewarm.md`)
- CB5 confirmed bug in `knowledge/phase-d-pitches.md`
- Pattern P6 "Monitoring-as-extraction": autoprewarm joins the cluster of
  monitoring/maintenance functions defaulting to PUBLIC. SP6 is the first to actually
  ship a REVOKE.

## §11 Submission package

After implementation lands and tests pass:
- `git format-patch e18b0cb7344..feature_sp6_autoprewarm_revoke --output-directory ../sp6-autoprewarm-revoke/`
- Patch subject: `pg_prewarm: REVOKE autoprewarm_* from PUBLIC`
- Commit message body: cite the security implication (any logged-in user can trigger
  NBuffers scan + dump file write); explain default_version bump + the two-file REVOKE
  approach; reference the new TAP test.
- Target: pgsql-hackers mailing list + commitfest 60 (January 2026).
- Backpatch candidate: yes (security tightening on shipped code).

## §12 Notes / surprises

(Empty at plan time. Populate in `notes.md` during implementation per R8.)
