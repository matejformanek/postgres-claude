# Iteration 2 — edits applied to `.claude/skills/testing/SKILL.md`

Source of edits: `iteration-1/proposed-edits.md`.

## E1 + E5 — isolation spec skeleton + injection-points path

Replaced the Step 1 item 1 paragraph with an expanded version that
(a) gives the explicit path `source/src/test/modules/injection_points/`
    instead of vague "use injection points",
(b) inlines an 8-line `session/step/permutation` grammar skeleton,
(c) calls out "explicit `permutation` is mandatory when steps block".

Verified path exists: `source/src/test/modules/injection_points/`
(has `expected/`, `specs/`, `sql/`, `Makefile`).

## E2 + E3 + E4 — LSN-sync recipe, no-WAL-assert caveat, done_testing

Inserted a perl-fenced block in Step 4 (just before the "Single TAP test"
bash block) covering:
- `wait_for_replay_catchup` (verified at
  `source/src/test/perl/PostgreSQL/Test/Cluster.pm:3543`)
- `poll_query_until` LSN form (verified idiom — same file defines `lsn`
  method, used pervasively across `src/test/recovery/t/`)
- `done_testing();` reminder
- "TAP verifies replicated state, not WAL-record identity" caveat with
  `pg_waldump` pointer.

## Not changed

No content corrections were needed — both attempts in iter-1 already
hit 21/22 and 22/22. These edits aim to make a future *baseline*
attempt (no skill) lose by a larger margin, i.e. to widen the skill's
value, not to fix bugs.
