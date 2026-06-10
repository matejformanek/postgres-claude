# Session — Phase D pitch roadmap synthesis (A → D bridge)

**Date:** 2026-06-10
**Phase:** A → D bridge (synthesis landmark)
**Source pin:** `e18b0cb7344` (post A18 refresh)
**Branch:** `ft_corpus_phase_d_pitch_roadmap`

## Why this session

After 17 foreground sweeps + 1 anchor refresh, the corpus held **~2,720 inline `[ISSUE-*]` tags across 38+ subsystem registers** but no consolidated view. Phase D pitch candidates were scattered across STATE.md narratives + per-register headlines. The next mechanical sweep would have padded coverage (ecpg, src/test, port subdir shims) without surfacing new high-value findings.

The right move was synthesis: consolidate the Phase D candidates into a single actionable roadmap.

## Output

**NEW:** `knowledge/phase-d-pitches.md` — 686 lines, ~32 KB. Structure:

1. **Mega-pitches MP1–MP10** — cross-corpus patch series (3+ findings each)
   - MP1 SecretBuf hosting site (10+ secret-scrub sites, closes A5's backlog)
   - MP2 StringInfo quoting helpers (A7+A13+A14 injection cluster)
   - MP3 pgcrypto modernization series (9 sub-patches)
   - MP4 PASSWORD redaction chokepoint (A4+A11+A17 3-header cluster)
   - MP5 Routine version+magic+selfcheck (closes "load arbitrary code" 5-primitive thread)
   - MP6 MCV-leak central chokepoint (CVE-2017-7484 class)
   - MP7 Monitoring-as-extraction per-relation gate (8+ site cluster)
   - MP8 Hardened readfuncs.h deserializer
   - MP9 heap_fetch_toast_slice toastrel cross-check (A12 anchor)
   - MP10 RLS leakproof/stable runtime cross-check

2. **Single-site pitches SP1–SP10** — focused patches (1-file or 1-mechanism)
   - SP1 SCRAM iter cap GUC
   - SP2 pg_str* MaxAllocSize cap
   - SP3 pg_get_viewdef security-clause round-trip
   - SP4 execParallel security-envelope documentation
   - SP5 lwlocklist CI cross-check
   - SP6 autoprewarm REVOKE-from-PUBLIC
   - SP7 tablefunc.connectby_text identifier quoting
   - SP8 per-process keying in hashfn
   - SP9 nodeCustom provider attestation
   - SP10 PS title password redaction

3. **Confirmed bugs CB1–CB10** — already-identified concrete bugs, patch shape sketched
   - CB1 pgcrypto decompression bomb
   - CB2 tablefunc SQL injection
   - CB3 sepgsql AVC cache widening (3 sub-issues)
   - CB4 pg_walinspect show_data RLS bypass
   - CB5 pg_prewarm autoprewarm PUBLIC
   - CB6 pg_surgery heap_force_freeze resurrects aborted tuples
   - CB7 ltree parse_lquery amplification
   - CB8 hstore forged HS_FLAG_NEWVERSION
   - CB9 pg_upgrade check_loadable_libraries RCE
   - CB10 pg_rewind zero O_NOFOLLOW

4. **Cross-corpus patterns P1–P9** — meta-findings catalog
   - P1 Load arbitrary code (5 primitives)
   - P2 NAME-vs-OID race (8+ sites)
   - P3 Secret-scrub gaps (10+ sites)
   - P4 Text-to-SPI injection sinks (5-sweep cluster)
   - P5 GiST signature-collision (5 modules)
   - P6 Monitoring-as-extraction (8+ sites)
   - P7 X-macro coordination (4 sites)
   - P8 Float NaN divergence (4 sites)
   - P9 A11 cleartext-password 3-header cluster

5. **Triage matrix** — 30+ rows with Severity / Effort / Sites / Cluster.

6. **Submission strategy** — 8 quick-win 1-day patches + 7 mid-term 1-month series + 10 long-term 2-3-month series.

## What this enables

- **Hackers-list filing:** 8 small, focused patches (SP6 autoprewarm REVOKE 1h, SP1 SCRAM cap 1d, SP2 MaxAllocSize cap 1d, SP3 pg_get_viewdef 2d, SP5 lwlocklist CI 1d, SP7 tablefunc 1d, SP10 PS-title redact 2d, CB7 ltree cap 3d) could ship as 8 CF entries in ~2 weeks. Establishes credibility on hackers-list before tackling the mega-pitches.
- **Three-phase planner pivot:** Each MP* has enough detail to feed into `pg-feature-plan` → `pg-implement` → `patch-submission`.
- **Cross-corpus rationale:** Every pitch carries its cross-sweep echoes (which A* sweeps surfaced it, which patterns it closes). Reviewers can verify the multi-sweep cluster claim.
- **Honest scope-down:** Phase A is essentially done for load-bearing areas. The remaining ~656 files are mechanical and best left to cloud routines. The corpus value is in the synthesis, not in chasing 100%.

## Position update

- **17 A-sweeps + 1 anchor refresh + 1 synthesis landmark** = the Phase A → D bridge is now built.
- Phase B (personas) remains unscheduled.
- Phase C (planner calibration) remains unscheduled.
- Phase D (hardening) is now actionable with concrete pitch backlog.

The user's discretion is needed to pick next:
- **Path A:** File first quick-win CF entries (start Phase D execution).
- **Path B:** Pivot to Phase B (developer personas from pgsql-hackers archives).
- **Path C:** Continue Phase A grinding (ecpg, src/test) via cloud routines while the user reviews the pitch roadmap.

This session's deliverable: the synthesis itself. The choice of what to do with it is human-pivot territory.

## Cross-references

- `knowledge/phase-d-pitches.md` — the roadmap (this session's main output)
- `progress/STATE.md` — Phase line updated to "A → D bridge"; Last activity updated
- `progress/anchor-refresh-2026-06-10.md` — A18 source pin refresh inventory
- `knowledge/issues/*.md` — 38+ subsystem registers with the source `[ISSUE-*]` entries
- `pg-claude-plan.md` (parent dir) — master 4-phase arc

## What this session did NOT do

- Did NOT add per-file docs (coverage unchanged at 74.4%).
- Did NOT update per-file doc anchors (per A18 soft-refresh policy).
- Did NOT file any CF entries (that's the next step).
- Did NOT update `knowledge/issues/*.md` registers — they remain the per-subsystem source of truth; the roadmap aggregates without duplicating.

## Suggested next steps (in order)

1. **Review** `knowledge/phase-d-pitches.md` with maintainer (Matej) for prioritization adjustment.
2. **Pick 2-3 quick wins** from the SP1–SP10 / CB1–CB10 lists. Likely starters:
   - SP6 autoprewarm REVOKE (lowest effort, clearest fix)
   - SP1 SCRAM iter cap GUC (small, defensible, defense-in-depth)
   - CB7 ltree amplification cap (high-severity, well-bounded fix)
3. **Build a pg-implement plan** for the chosen pitches using the three-phase planner suite.
4. **Cross-reference with pgsql-hackers ML** to verify no concurrent in-flight work.
5. **Update the roadmap** as pitches land or get superseded.
