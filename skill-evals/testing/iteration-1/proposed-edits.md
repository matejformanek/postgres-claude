# Proposed edits for `.claude/skills/testing/SKILL.md` (iteration 1)

Status: **proposed, not applied.**

The skill performed very well — 22/22 and 21/22 across the two attempts on three
realistic prompts. Edits below are small refinements, not corrections.

## E1. Add a one-line isolation-spec skeleton inline

Currently the SKILL has skeletons-ish content only via the long-form
`knowledge/conventions/testing.md`. Attempt B in eval 3 got the right answer
but didn't reproduce the grammar — adding 8 lines of `session "s1" { step
"s1a" { ... } }` + `permutation "s1a" "s2a"` to the SKILL would make a one-shot
correct answer more reliable.

Suggested placement: under "Step 1, item 1 (isolation)", as a fenced block.

## E2. Add a one-line LSN-sync recipe to the TAP section

For replication-verification prompts (eval 2), the SKILL implies but doesn't
spell out the standard "wait for replay" pattern:

```perl
$primary->wait_for_replay_catchup($standby);
# or, explicitly:
my $lsn = $primary->lsn('insert');
$standby->poll_query_until('postgres',
    "SELECT pg_last_wal_replay_lsn() >= '$lsn'::pg_lsn");
```

This is the single most common idiom in `src/test/recovery/t/` and worth one
line in the SKILL itself.

## E3. Make the "no direct WAL-record assertion" caveat explicit

Eval 2 prompt asked specifically "verify it catches a specific WAL record."
Both attempts correctly answered "you assert on observable effects, not on the
WAL record itself." A one-line note in the TAP section — *"TAP tests verify
replicated state, not WAL-record identity; use `pg_waldump` from a separate
shell step if you really need the latter"* — would prevent a future user from
hunting for a nonexistent API.

## E4. Add `done_testing();` to the run-and-debug checklist

Currently mentioned only in the long-form companion. Easy footgun.

## E5. (Nit) Cross-link the injection-points module by path

In Step 1 item 1's LWLock caveat, replace "use injection points or a C test
module instead" with "use `source/src/test/modules/injection_points/` (or a
custom C test module) instead." Saves a search.

---

None of these change behavior or fix wrong content — they would just shave
one re-read off harder prompts.
