# pgsql-hackers cover email — SP6 pg_prewarm autoprewarm REVOKE

**To:** pgsql-hackers@lists.postgresql.org
**Subject:** [PATCH] pg_prewarm: REVOKE autoprewarm_* from PUBLIC
**Attach:** `0001-pg_prewarm-REVOKE-autoprewarm_-from-PUBLIC.patch`

---

Hi hackers,

contrib/pg_prewarm ships two SQL-callable maintenance functions that
have been EXECUTE-grantable to PUBLIC since they were added in
extension version 1.2:

  * autoprewarm_start_worker()  - launches the autoprewarm bgworker
  * autoprewarm_dump_now()      - performs an immediate buffer dump

Neither has a C-side privilege check (autoprewarm.c:813-859), and
neither has a REVOKE in any install or upgrade script.  The PG default
for CREATE FUNCTION is EXECUTE to PUBLIC, so any logged-in user can
trigger the underlying O(NBuffers) scan + buffer-header spinlock
contention + a dumpfile write -- with no rate limiting.

These are clearly maintenance entry points for a DBA, not general-user
APIs.  Patch attached.

The patch:

  1. Adds REVOKE EXECUTE ... FROM PUBLIC for both functions to
     pg_prewarm--1.1--1.2.sql, so fresh installs of v1.2 already get
     the tightening.
  2. Adds a new pg_prewarm--1.2--1.3.sql upgrade script that
     re-applies the same REVOKEs explicitly, so existing 1.2
     deployments can run ALTER EXTENSION ... UPDATE TO '1.3' and pick
     up the change.
  3. Bumps default_version in pg_prewarm.control from 1.2 to 1.3.
  4. Adds regression-test coverage in both the SQL regress suite
     (sql/pg_prewarm.sql) and the TAP test (t/001_basic.pl), in each
     case asserting permission-denied for a non-superuser and verifying
     that a targeted GRANT EXECUTE unblocks one function without
     affecting the other.

Build + `meson test --suite pg_prewarm` green on master @ e18b0cb7344.

**Discussion points for reviewers:**

1. **No C-side privilege check.** Sticking to the SQL-level REVOKE
   matches existing contrib convention (pg_visibility, adminpack); a
   C-side check would shadow GRANT EXECUTE flows and complicate the
   "GRANT ... TO admin_role" pattern.  Happy to revisit if hackers
   prefer C-side, but I think SQL-level is the right granularity here.

2. **Backpatch.** This is defense-in-depth, not an emergency CVE: a
   logged-in user is required, and the impact is DoS-class (buffer
   scan + dumpfile write) rather than data disclosure.  But the
   functions have been default-PUBLIC since v11 (extension 1.2 was
   added in 5fb5b6cf), and the threat model is well-defined.  I'd
   suggest backpatching to v16/v17/v18 with the same diff
   (default_version bump + new upgrade script).  Older branches are
   out of scope.

3. **No downgrade script.** Aligned with how pg_walinspect /
   pg_visibility tightenings have shipped: a tightening upgrade
   doesn't ship a downgrade.  Operators who need the prior behavior
   can manually GRANT EXECUTE ... TO PUBLIC.

4. **Out of scope.** The autoprewarm dumpfile path is unvalidated and
   the `<<N>>` block-count parse uses `atoi`, which signed-overflows
   into a `dsm_create(20*N)` allocation request.  That's a separate
   threat (filesystem-write attacker) and a separate patch.  Tracked
   in our corpus as CB5b.

Surfaced during a code-corpus sweep (postgres-claude/A14, 2026-06-09).

Thanks,
Matej

---

## After sending

1. Wait for the message to hit the archive: https://www.postgresql.org/list/pgsql-hackers/
2. Capture the archive message-id.
3. Open a CF entry at https://commitfest.postgresql.org/ targeting CF #60:
   - Topic: Security  (or System Administration, hackers' call)
   - Patch: archive URL
   - Reviewers: open
4. Add the CF link back to `postgres-claude/planning/sp6-autoprewarm-revoke/notes.md`.
