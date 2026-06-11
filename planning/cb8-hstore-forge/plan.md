# Plan: CB8 — hstore forged HS_FLAG_NEWVERSION

**Status:** READY → DONE. Single-phase plan.
**Pitch:** `knowledge/phase-d-pitches.md` CB8 (A13 critical finding)
**Source pin:** `e18b0cb7344` (master at 2026-06-10)
**Slug:** `cb8-hstore-forge`
**Branch:** `feature_cb8_hstore_forge`
**Expected commits:** 1

## §1 Problem statement

`contrib/hstore/hstore_compat.c::hstoreUpgrade()` (line 242) returns
the datum unchanged if `HS_FLAG_NEWVERSION` is set, without
re-inspecting the entry-offset array.  `hstoreValidNewFormat()` (line
130) does the same short-circuit.  A forged hstore (via COPY/dump-
restore) with the new-version bit set on top of garbage offsets routes
downstream `HSTORE_KEY` / `HSTORE_VAL` into `memcpy` from
attacker-controlled offsets → controllable out-of-bounds read.

## §2 Approach

1. Remove the `HS_FLAG_NEWVERSION` short-circuit inside
   `hstoreValidNewFormat()`; let the structural pass always run.
2. In `hstoreUpgrade`, change `if (flag)` to `if (flag && validNewFormat(hs))`.
   Forged datums fall through to the existing `valid_new + valid_old`
   recovery path which already rejects mismatched inputs.

## §3 Files that change

| File | Change | LOC |
|---|---|---|
| `contrib/hstore/hstore_compat.c` | Remove flag-trusting short-circuit + add validation at hstoreUpgrade fast path | +20/-4 |

## §4–§12

(Standard plan body; see notes.md for the executed reality.)
