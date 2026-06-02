# Proposed edits for SKILL.md (iter-1 → iter-2)

The skill is already strong (21/21 across all 3 evals). The following
edits target small precision gaps observed when generating answers,
verified against real upstream commits.

## Edit 1 — Note that `http://postgr.es/m/` also appears in practice

Current text (§4 Notes):

> `Discussion:` URL uses the `postgr.es/m/...` shortener, **not** the
> raw archives URL.

Observed: commit `b1901e2895e` uses `http://postgr.es/m/...` (no `s`).
Both are accepted by the shortener. Update to say either scheme is
fine, but prefer `https://` for new commits (matches majority of
recent log).

## Edit 2 — Explicit guidance on when to OMIT `Author:`

Current §4 table says "Omit if the committer is sole author." but the
checklist (§9) and example slot don't make this prominent. Add an
inline note under §4 immediately after the table:

> If the committer is also the sole patch author, **omit `Author:`
> entirely** — don't write `Author: <self>`. Reviewed-by / Reported-by
> trailers still apply.

This matches `08127c641c0` (committer = author, no `Author:` line; only
Reported-by + Reviewed-by + Discussion + Backpatch-through).

## Edit 3 — Two-space sentence separator convention

PG body text uses two spaces after a sentence-ending period (visible
in `db5ed03217b`: "the default '$system' path is still assumed.  However,").
This is a real house-style detail. Add to §3:

> Two spaces follow a sentence-ending period inside the body paragraphs.
> (Inherited from the project's plain-text/emacs heritage; visible in
> nearly every recent commit body.)

## Edit 4 — Clarify the Backpatch-through value format with an inline example

Current text describes the format but a one-line "good vs bad" pair
helps. Add to §4 right after the Backpatch-through bullet:

> Good: `Backpatch-through: 16` (oldest branch as a bare major number).
> Bad: `Backpatch-through: 16-18`, `Backpatch-through: REL_16_STABLE`,
> `Backpatch from master`.

## Edit 5 — Tiny clarification on `Co-authored-by:` vs `Author:`

Reword the §4 row for `Co-authored-by:` to clarify when to use it:

> `Co-authored-by:`  Additional patch authors when there is more than
> one. The first author goes on `Author:`; subsequent humans on
> `Co-authored-by:`. (PG variant — lowercase `a` / `b`.)

No edits proposed for §1, §2, §5, §6, §7, §8 — those already test green.
