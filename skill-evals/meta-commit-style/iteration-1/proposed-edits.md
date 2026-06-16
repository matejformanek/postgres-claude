# Proposed edits for meta-commit-style SKILL.md (iter-1 → iter-2)

Iter-1 caught one real spelling bug and three smaller drifts between
the SKILL.md text and what `git log` of the meta repo actually
contains. All proposed edits are verified against the real log of
this worktree (`git log --oneline -300`) and recent full-body commits.

## Edit 1 — Fix `Co-Authored-By:` casing (highest leverage)

**Bug:** SKILL.md uses `Co-Authored-By:` (GitHub uppercase) in every
example and in the §"Trailers" body text. The real meta-repo log
uses lowercase `Co-authored-by:` 45 times in the last 50 commits with
a co-author trailer; uppercase appears only 11 times (older commits).
The lowercase form is also what upstream PG uses (`commit-message-style`),
and what git itself canonicalizes to.

**Verification:**
```
$ git log --format='%B' -50 | grep -i 'co-author' | sort | uniq -c
  11 Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   8 Co-authored-by: Claude <noreply@anthropic.com>
  45 Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

**Fix:** Replace all `Co-Authored-By:` → `Co-authored-by:` in
SKILL.md (description frontmatter line, table row in §contrast,
§Trailers list item, all three canonical examples, §Forbidden — 7
occurrences total).

## Edit 2 — Use plural scope `ft(skills):` in example, not `ft(skill):`

**Drift:** SKILL.md example "Planner suite, multi-file new skill set"
opens with `ft(skill): add two-phase planner ...` (singular). Real
log has 23 uses of `ft(skills):` and 0 uses of `ft(skill):`. The
real "ft(scope)" vocabulary in last 200 commits, by frequency:

```
122 ft(corpus):
 23 ft(skills):
  6 hf(corpus):
  5 ft(cloud):
  2 ft(meta):
  8 docs(cloud):
  2 docs(community):
  1 docs(state):
  1 ft(patches):
  1 ft(ideologies):
```

**Fix:**
- Change the §"Prefix vocabulary" row from `ft(skill):` → `ft(skills):` (plural).
- Change the example title `ft(skill): add two-phase planner ...` →
  `ft(skills): add two-phase planner ...` (and update the matching
  reference in the §"Cross-skill notes" if any).

## Edit 3 — Expand the prefix vocabulary table with real-log scopes

**Gap:** Current table lists `ft(corpus|dev|skill|cloud|plan)` and
`hf(scope)` and `docs(scope)`. Real log uses additional scopes that
the table doesn't enumerate:

- `ft(meta):` — repo-wide metadata changes (README, CONTRIBUTING,
  llms.txt, .github/). Seen 2x in last 200.
- `docs(state):` / `docs(cloud):` / `docs(community):` / `docs(queue):` —
  STATE.md / cloud / community / queue narrative updates. Seen 12x.
- `ft(patches):` — for `patches/` directory work.

**Fix:** Add an "Also seen in the wild" subsection right after the
canonical-set table, listing `ft(meta):` and the `docs(<doc-dir>):`
variants, so the agent knows these are real and not coinage. Anchor
to an example commit SHA each:

```
ft(meta): discoverability quick wins                  (82ebf2e)
docs(state): prepend 2026-06-16 entry                 (b707ab2)
docs(cloud): pg-evening-merger 2026-06-16             (5a39b7d)
```

## Edit 4 — Acknowledge looser `Plan:` usage and clarify the strict form

**Drift:** §"Trailers" defines `Plan: planning/<slug>/plan.md (phase <N>:
<title>)` as the only form. Real log uses `Plan:` more loosely:

```
Plan: cloud routine pg-quality-auditor (AUDIT mode, 2026-06-14)
Plan: catalog trio "trigger system depth" from ...
Plan: cross-ref-audit fixup on PR 4/4.
Plan: .claude/cloud/pg-extension-anthropologist.md
```

**Fix:** Reword the `Plan:` trailer spec to distinguish:

> 1. `Plan:` — link back to whatever drove this commit.
>    - **Phased plan (canonical):** `Plan: planning/<slug>/plan.md
>      (phase <N>: <title>)`. Required when this commit implements a
>      phase of a `planning/<slug>/plan.md` per R5 of
>      `pg-implement-discipline.md`.
>    - **Loose form (recipe / trio / one-off):** `Plan: <freeform
>      pointer>` — e.g. `Plan: cloud routine .claude/cloud/X.md`,
>      `Plan: catalog trio "<name>"`. Use the canonical form whenever
>      a `planning/<slug>/plan.md` exists; the loose form is for
>      commits where the "plan" is a recipe or thread, not a planner
>      artifact.

## Edit 5 — Anchor each canonical example to a real commit SHA

**Gap:** The three canonical examples in §"Examples" are
plausible-but-fictional. Adding a real-SHA anchor lets a future
reader see a live commit that matches the style without having to
trust the example.

**Fix:** Replace or supplement examples with real SHAs from `git log
--oneline -200`:

- `ft(corpus):` synthesize example → cross-link to `4925200`
  (`ft(corpus): memory contexts depth trio …`).
- `ft(skills):` multi-file planner suite example → cross-link to
  `62da1c2` (`ft(skills): skill-creator heavy pass round 1 …`).
- `[cloud:<routine>]` example → cross-link to `aecd8e3`
  (`[cloud:pg-upstream-watcher] 5 commits · 8 bf failures (#312)`).

Concrete edit: add a line `(anchor: <SHA>)` under each example block.

## Edit 6 — Explicit contrast block: meta vs upstream side by side

**Gap:** The contrast table at the top is good but a side-by-side
*concrete example* would land harder. Eval 3 specifically tested
whether the agent can tell the user "your title `Add new skill` is
right for upstream PG / dev/, but wrong for the meta repo — here
both styles for the same notional change".

**Fix:** Add a short §"Side-by-side: same change, two styles" block
between the contrast table and §"When to use":

```
Same conceptual change ("add a knowledge doc on lock acquire order"),
two different homes:

dev/ patch (commit-message-style):
    Document lock acquire-before-pin invariant

    The lock-then-pin sequence is not stated in lmgr.h, …

    Author: …
    Reviewed-by: …
    Discussion: https://postgr.es/m/...

postgres-claude meta repo (this skill):
    ft(corpus): synthesize lock-acquire-then-pin idiom (148 lines, 22 cites)

    Distill the lock-then-pin sequencing pattern from …

    Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## Edit 7 — Tighten the description to surface the lowercase casing

**Gap:** The frontmatter `description:` field currently says "the
global `Co-Authored-By: Claude Opus 4.7 (1M context)
<noreply@anthropic.com>` footer". This is the exact place where the
casing bug is most visible to the dispatcher / model — it'll see this
even before opening SKILL.md body.

**Fix:** Change to `Co-authored-by:` (lowercase) in the description
line as well. Folded into Edit 1's global replace.

---

## Edits NOT proposed

- No edit to the cross-references block — every link still
  resolves.
- No edit to the §"Forbidden" list — already accurate; just needs the
  casing fix from Edit 1.
- No edit to the §"When to use" / §"When NOT to use" lists — both
  match real-log usage.
