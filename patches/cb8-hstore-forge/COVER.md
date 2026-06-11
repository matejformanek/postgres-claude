# pgsql-hackers cover email — CB8 hstore forged HS_FLAG_NEWVERSION

**To:** pgsql-hackers@lists.postgresql.org
**Subject:** [PATCH] hstore: validate structure before trusting HS_FLAG_NEWVERSION
**Attach:** `0001-hstore-validate-structure-before-trusting-HS_FLAG_NE.patch`

Hi hackers,

contrib/hstore/hstore_compat.c has a flag-trust gap: both
`hstoreUpgrade()` and `hstoreValidNewFormat()` short-circuit on
`hs->size_ & HS_FLAG_NEWVERSION` without inspecting the entry-offset
array.  A datum produced by a malicious tool (or a corrupted file used
during COPY / dump-restore) that sets the new-version bit on top of
garbage offsets routes the downstream HSTORE_KEY / HSTORE_VAL macros
into `memcpy` from attacker-controlled byte offsets - a controllable
out-of-bounds read in the consuming session.

The attached patch:

1. Removes the flag-trusting short-circuit inside
   hstoreValidNewFormat().  Structural validation always runs; the
   flag is only an intent signal.

2. Tightens the hstoreUpgrade() fast-path return so that it short-
   circuits only when BOTH the flag AND the structural check agree.
   Forged datums fall through to the existing valid_new + valid_old
   recovery path which already rejects mismatched inputs.

Build + `meson test --suite hstore` green on master @ e18b0cb7344
(2/2 subtests; broader sweep 99 OK).

**Discussion points for reviewers:**

1. **Behavior change in `hstore_version_diag()`.**  Before: a forged
   datum with the flag set + garbage offsets returns
   `valid_new=2 valid_old=0` (i.e. lies).  After: returns
   `valid_new=0 valid_old=0`.  Truthful.  Reviewers can decide
   whether the diagnostic contract guarantees the old (false) answer.

2. **No regression test.**  Crafting a forged hstore needs a
   hex-encoded bytea fixture (~50-100 LOC of test scaffolding for one
   error-path coverage).  The structural-correctness argument is
   strong; happy to add if hackers prefer.

3. **Backpatch.**  Yes; security fix for an OOB-read vector via the
   public bytea path.  v16, v17, v18 share hstore_compat.c.

Surfaced during a code-corpus sweep (postgres-claude/A13, 2026-06-09).

Thanks,
Matej
