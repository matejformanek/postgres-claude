---
source_url: https://www.postgresql.org/docs/current/datetime-invalid-input.html
fetched_at: 2026-07-12T19:52:30Z
anchor_sha: eed6c0d33e09
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "B.2 Handling of Invalid or Ambiguous Timestamps"
---

# Docs distilled — Invalid / Ambiguous Timestamps (datetime-invalid-input)

What `timestamptz` input does when a local wall-clock time either **never
existed** (spring-forward gap) or **existed twice** (fall-back overlap). The
user-facing face of `DetermineTimeZoneOffset()` /
`DetermineTimeZoneOffsetInternal()` in `datetime.c`. This page carries a
**code-vs-docs nuance** worth flagging (see last bullet).

## Non-obvious claims

- **Neither case is rejected — PG always resolves to a concrete instant.** DST
  gaps/overlaps never raise an error; only genuinely out-of-range fields
  (Feb 31) error. "Such cases are not rejected; the ambiguity is resolved by
  determining which UTC offset to apply." [from-docs]
- **Spring-forward (nonexistent) time → use the offset in effect *before* the
  transition.** `'2018-03-11 02:30'::timestamptz` in America/New_York (2AM EST
  jumped straight to 3AM EDT) is read as if it were standard time (UTC-5),
  rendering as `2018-03-11 03:30:00-04`. [from-docs]
- **Fall-back (doubled) time → use the offset in effect *after* the
  transition.** `'2018-11-04 01:30'::timestamptz` (1:30AM occurred twice) yields
  `01:30:00-05` (the standard-time, post-transition side). To force the other
  reading, name the offset explicitly: `'2018-11-04 01:30 EDT'` →
  `01:30:00-04`. [from-docs]
- **The docs' summary rule is "standard-time interpretation preferred when in
  doubt" — but the actual implemented rule is subtly different and is the more
  correct one.** [verified-by-code] `DetermineTimeZoneOffsetInternal`
  `src/backend/utils/adt/datetime.c:1631`. When `beforetime` and `aftertime`
  straddle the boundary, the code does **not** test "which side is standard";
  it compares the two candidate instants directly: spring-forward prefers the
  *before* interpretation, fall-back prefers *after*, decided by
  `if (beforetime > aftertime)` at `:1737`. The source comment (`:1726-1734`)
  is explicit that they **removed** the old "prefer standard-time" rule because
  it fails when both candidates report as standard time (cited example:
  Europe/Moscow, Oct 2014) and because zones like Europe/Dublin disagree about
  which offset is even "standard". So "standard-time preferred" is a *docs
  approximation*, true "in most time zones" but not the algorithm. [from-docs]
  for the approximation, [verified-by-code] for the real rule.
- **The unambiguous fast paths short-circuit first.** If both candidate instants
  land on the same side of the boundary, that side is used directly; the
  boundary instant itself counts as *after* the transition
  (`aftertime == boundary` accepted). [verified-by-code] `datetime.c:1713`
  (both-before) / `:1719` (both-after).

## Links into corpus

- [[knowledge/files/src/backend/utils/adt/datetime.c.md]] — hosts
  `DetermineTimeZoneOffset` / `DetermineTimeZoneOffsetInternal`, the exact
  functions this page describes.
- [[knowledge/docs-distilled/datetime-config-files.md]] — how the abbreviation
  → offset that feeds this resolution is configured.
- [[knowledge/docs-distilled/datetime-posix-timezone-specs.md]] — the POSIX
  transition-rule grammar that defines where these spring/fall boundaries fall
  for non-IANA zones.

## Confidence

Behavior + examples are [from-docs]. The corrected before/after rule and its
rationale are [verified-by-code] against `datetime.c` @ `eed6c0d33e09` (lines
1631/1713/1719/1737 + the `:1726-1734` rationale comment). This is a genuine
code-improves-on-docs finding, not a contradiction — the outcomes match in the
zones the docs example uses.
