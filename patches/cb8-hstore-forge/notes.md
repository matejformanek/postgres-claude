# CB8 hstore forged HS_FLAG_NEWVERSION — notes

**Patch:** `0001-hstore-validate-structure-before-trusting-HS_FLAG_NE.patch`
**Status:** **PARKED.** Sending requires explicit user re-auth.
**Calibration:** `knowledge/calibration/cb8-hstore-forge.md`

## Predicted lead committer
**Peter Eisentraut** (#1 hstore committer 24mo, 5 cleanup-class
commits). Same backpatch routing issue as CB7 — **CC Michael Paquier
+ Tom Lane** for the v16/v17/v18 backport.

## Gate checklist

### Gate 1 — `security@` embargo
**Answer:** **YES, ASK FIRST.** OOB read via `bytea::hstore` cast
(any role). Same pattern.

### Gate 2 — Test-omission skepticism
**COVER §2 says:** "No regression test. Crafting a forged hstore needs
a hex-encoded bytea fixture (~50-100 LOC of test scaffolding for one
error-path coverage)."
**Predicted Noah response (and triggered 3-for-3 across calibrations):**
push back on the self-justification. 50-100 LOC of base64-decoded
fixture is fine for asserting a security claim.
**Action before send:** add the regression test. Build a known-bad
fixture: a valid-looking hstore header with `HS_FLAG_NEWVERSION` set,
followed by garbage offsets, in a `bytea` literal. SQL:
```sql
SELECT '\x...'::bytea::hstore;
-- expected: ERROR: invalid hstore (forged HS_FLAG_NEWVERSION)
```

### Gate 3 — Install-script immutability
Not applicable.

## Patch findings to address before send

| # | Finding | Source | Resolution |
|---|---|---|---|
| 1 | **`hstore_version_diag()` behavior change may push to deprecation cycle vs unified backpatch** | cb8 §Notes PATCH FINDING (Tom contract-probing reflex) | **DECISION POINT.** The function now returns `valid_new=0` (truthful) where before it returned `valid_new=2` (the flag-claimed lie). Two options: (a) ship as unified v16/v17/v18 backpatch arguing the prior return was incorrect, OR (b) introduce a deprecation cycle (add a new function `hstore_version_diag_v2()`, deprecate the old, ship the fix to master only). **Recommend (a) — argue the prior answer was a lie, not a contract.** Tom may push for (b); have the argument ready in COVER. |
| 2 | "Third state" cross-check | cb8 §3 Heikki reflex | Add to COVER: "Three states enumerated: (i) flag set + structure valid → fast-path (unchanged), (ii) flag set + structure invalid → forged datum, now caught by tightened check (NEW), (iii) flag unset + structure valid → old-format datum, runs `hstoreValidNewFormat` already (unchanged), (iv) flag unset + structure invalid → error path (unchanged). No fifth state." |
| 3 | Test fixture (resolves Gate 2) | cb8 §3 Noah reflex | See Gate 2 action above. |
| 4 | Performance micro-benchmark | cb8 §6 Heikki perf reflex | Optional. Removing the flag-trust short-circuit forces structural validation on every call. For typical 1 KB hstores the cost is O(small-n). Include a sentence: "structural-check overhead measured at <X ns/call on 1 KB hstore; negligible against the ~150 ns hstore_in baseline." If you can't measure, drop the claim. |

## Reviewer-style pre-emption

- Add the regression test (Gate 2 + finding #3).
- Add the third-state enumeration to COVER (finding #2).
- Decision on finding #1 — recommend documenting the "diagnostic
  was a lie, fix it" argument in COVER body.
- Cite Michael Paquier's similar `pgcrypto: Fix buffer overflow in
  pgp_pub_decrypt_bytea()` as the contrib-security-fix precedent.
- Scrub "postgres-claude/A13 corpus sweep".
- Submit with Peter on To: + Tom + Michael on CC + Heikki on CC
  (binary-format reflex routing).

## Send order recommendation

**4th in the pile** (after CB1 + CB7 set the embargo + contrib-security
patch-shape precedents). CB8 is the trickiest because of the
behavior-contract question — going later means Tom Lane will already
have seen the embargo-path shape, easier ack.

## Verdict
**REFINE before GO.** Finding #1 needs a decision; finding #2 is a
clear add-to-COVER; the regression test (#3) is mandatory.

## DO NOT SEND
1. Decide finding #1 (recommend option a — argue prior return was lie).
2. Add regression test per Gate 2 + finding #3.
3. Add third-state enumeration per finding #2.
4. Cite Michael Paquier precedent commit.
5. `security@postgresql.org` notification.
6. Explicit user re-auth.
