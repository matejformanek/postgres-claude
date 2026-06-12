# SP6 pg_prewarm autoprewarm REVOKE — notes

**Patch:** `0001-pg_prewarm-REVOKE-autoprewarm_-from-PUBLIC.patch`
**Status:** **PARKED.** Sending requires explicit user re-auth.
**Calibration:** `knowledge/calibration/sp6-autoprewarm-revoke.md`

## Predicted lead committer
**Tom Lane** (top install-script committer cross-contrib 24mo — 11
commits on `contrib/*/*--*.sql`). Tom backpatches; routing is clean.

## Gate checklist

### Gate 1 — `security@` embargo
**Answer:** **NO — EXEMPTION ARGUED.** This is the calibration's
exemption-pattern example. COVER §2 already makes the argument:
"defense-in-depth, not an emergency CVE; logged-in user required;
DoS-class not data disclosure." Acceptable per the exemption
protocol in `review-checklist` Phase 0 Gate 1.

### Gate 2 — Test-omission skepticism
**Pre-empted.** COVER includes both SQL regress + TAP test coverage.
✓.

### Gate 3 — Install-script immutability
**THE KEY GATE FOR THIS PATCH.** This is the install-script
reviewer reflex the methodology asked about — and it FIRED on Tom
Lane's predicted comment per the calibration §3.

**Predicted Tom concern:** "Editing the shipped `--1.1--1.2.sql`
script is unusual. Shipped `--*.sql` scripts are immutable
post-release; installations that already ran the 1.2 upgrade have
a different post-state than a fresh install with the edited
script."

**Patch's current shape:** edits BOTH the shipped 1.1→1.2 (so fresh
installs of 1.2 already see the tightening) AND adds a new 1.2→1.3
(so existing 1.2 deployments can upgrade).

**Recommendation:** **change the shape** to ONLY ship 1.2→1.3.
Leave the shipped 1.1→1.2 alone. Fresh installs cascade through
all upgrade scripts on `CREATE EXTENSION` so they'll get the
REVOKE via 1.2→1.3 just like existing 1.2 deployments do. This
removes the install-script-immutability concern entirely.

## Patch findings to address before send

| # | Finding | Source | Resolution |
|---|---|---|---|
| 1 | **Don't edit shipped 1.1→1.2 — only ship 1.2→1.3** | sp6 §3 (Tom install-script reflex; Gate 3 above) | **MUST CHANGE PATCH SHAPE.** Drop the 1.1→1.2 edit. Keep the new 1.2→1.3 + the `default_version` bump + the regression + TAP tests. This is a 3-line patch removal. |
| 2 | Confirm postmaster-side autoprewarm bgworker unchanged | sp6 §3 (Nathan area-owner reflex) | Add to COVER: "REVOKE only affects manual SQL triggering of `autoprewarm_start_worker()` and `autoprewarm_dump_now()`. The postmaster-launched autoprewarm bgworker at server startup is unaffected." |
| 3 | `default_version` bump idempotency across 1.0/1.1/1.2 | sp6 §3 (Michael upgrade-path reflex) | Add to COVER: "Cascade behavior — `CREATE EXTENSION pg_prewarm` (no version) installs 1.3. `ALTER EXTENSION pg_prewarm UPDATE` from any of {1.0, 1.1, 1.2} runs the appropriate scripts in sequence and ends at 1.3 with the REVOKE in place. Confirmed by inspection of extension.c's cascade logic." |
| 4 | `PG_TEST_EXTRA` gating question on new TAP | sp6 §3 (Daniel reflex) | Probably **NO**. The TAP test is short (single role + REVOKE + GRANT check). Not buildfarm-expensive. Leave unconditional. If Daniel asks, the answer is "not expensive enough to gate". |

## Reviewer-style pre-emption

- **Address finding #1 first** — change the patch shape to 1.2→1.3
  only. This is the substantive change.
- Add findings #2 + #3 sentences to COVER body.
- Add a "convention precedent" cite: pg_walinspect's recent
  tightenings used the same 1.2→1.3-only shape.
- Scrub "postgres-claude/A14 corpus sweep" (Tom rewrites).
- Submit with Tom on To: + Nathan + Michael + Melanie on CC
  (the area + install-script reviewer set).

## Send order recommendation

**5th (last) in the pile.** Reasons:
1. Distinct shape (install-script not code-path) — sending it last
   lets reviewers calibrate to your patch style on CB1/CB7/CB8/SP2
   first.
2. The security@ exemption argument is most credible on a
   privilege-tightening patch rather than a code-path DoS fix —
   sending it after the embargo-path patches lets Tom see the
   pattern.
3. Risk-of-rejection is lowest (this is a clean defense-in-depth
   patch with no behavior change for non-superusers).

## Verdict
**REFINE before GO.** Finding #1 (drop the 1.1→1.2 edit) is the
critical change. Otherwise patch is in good shape.

## DO NOT SEND
1. Drop the 1.1→1.2 edit per finding #1 (3-line patch change).
2. Add findings #2 + #3 to COVER body.
3. Cite pg_walinspect precedent.
4. NO `security@` notification — exemption is on file in COVER §2.
5. Explicit user re-auth.
