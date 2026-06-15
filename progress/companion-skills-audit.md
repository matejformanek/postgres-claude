# companion_skills audit — 2026-06-15

## Why this doc

The skill-creator handoff
(`sessions/2026-06-14-handoff-pre-compact-round3.md`) listed
"verify cross-skill `companion_skills` graph bidirectional" as a
follow-up. A naive `A in B.companions ⇔ B in A.companions` audit
across the 30 skills under `.claude/skills/` finds 53
asymmetries — which on its face looks bad. The reality is
subtler: most of those asymmetries are CORRECT because
companion_skills is not a symmetric graph by intent. This doc
codifies the policy and lists the asymmetries with verdict for
each.

## The policy — when to back-link

A companion_skills entry says "someone reading this skill might
want to also load THAT skill". Three relationships justify it:

1. **Peer workflows** — A and B can be invoked instead of each
   other on similar problems. Must be bidirectional.
2. **Pipeline neighbors** — A produces output that B consumes
   (or vice versa). Should be bidirectional in most cases.
3. **Same-domain references** — A and B cover adjacent slices of
   one domain. Should be bidirectional.

Three relationships DO NOT need bidirectional links:

4. **Foundational → workflow** — `commit-message-style`,
   `coding-style`, `testing`, `build-and-run`, `debugging`,
   `memory-contexts`, `error-handling` are utilities referenced
   by many workflows. Adding back-links from a utility to every
   workflow that uses it bloats the list to noise. SKIP.
5. **Domain → hub** — `pg-claude` is the master index. Topical
   skills don't need to back-link to it (the user will arrive at
   it organically through the description triggers).
6. **One-way escalation** — `pg-shadow-implement` references
   the planning suite as upstream stages it can consume, but the
   reverse isn't useful (a planner doesn't normally then
   "escalate to shadow-implement").

When in doubt: add the back-link. The cost of a bidirectional
edge is one line of YAML; the benefit is one less stale-graph
artifact.

## The 53 asymmetries — verdict for each

Read as `A → B (no back-link from B)`. Verdict: **bidir** =
should be made bidirectional; **skip** = asymmetry is correct
per policy.

### Foundational-utility back-references (SKIP per policy rule 4)

| Edge | Reason |
|---|---|
| access-method-apis → locking | locking is utility |
| catalog-conventions → testing | testing is utility |
| coding-style → commit-message-style | both foundational |
| error-handling → locking | locking is utility |
| executor-and-planner → locking | locking is utility |
| extension-development → testing | testing is utility |
| fmgr-and-spi → memory-contexts | memory-contexts is utility |
| fmgr-and-spi → error-handling | error-handling is utility |
| gucs-config → coding-style | coding-style is utility |
| locking → memory-contexts | memory-contexts is utility |
| locking → coding-style | coding-style is utility |
| memory-contexts → debugging | debugging is utility |
| parser-and-nodes → testing | testing is utility |
| parser-and-nodes → coding-style | coding-style is utility |
| pg-implement → commit-message-style | utility |
| pg-implement → build-and-run | utility |
| pg-implement → testing | utility |
| pg-patch-review → commit-message-style | utility |
| pg-patch-review → coding-style | utility |
| pg-patch-review → testing | utility |
| pg-patch-review → wal-and-xlog | topic |
| pg-patch-review → locking | topic |
| pg-patch-review → catalog-conventions | topic |
| pg-patch-review → memory-contexts | topic/utility |
| psql → error-handling | utility |
| replication-overview → locking | utility |
| replication-overview → bgworker-and-extensions | topical |
| replication-overview → error-handling | utility |
| review-checklist → coding-style | utility |
| review-checklist → testing | utility |
| review-checklist → wal-and-xlog | topical |
| review-checklist → locking | topical |
| review-checklist → error-handling | utility |
| review-checklist → memory-contexts | utility |
| testing → debugging | utility |

(35 entries — all SKIP)

### Domain → hub (SKIP per policy rule 5)

| Edge | Reason |
|---|---|
| pg-feature-brainstorm → pg-claude | pg-claude is hub |
| pg-feature-plan → pg-claude | pg-claude is hub |
| memory-keeping → pg-claude | pg-claude is hub |

(3 entries — all SKIP)

### One-way escalation (SKIP per policy rule 6)

| Edge | Reason |
|---|---|
| pg-shadow-implement → pg-feature-brainstorm | shadow consumes brainstorm output |
| pg-shadow-implement → pg-feature-plan | shadow consumes plan output |
| pg-shadow-implement → pg-implement | shadow is alternative to implement |
| pg-shadow-implement → pg-patch-review | shadow's output may go through review |
| pg-shadow-implement → review-checklist | same |
| pg-shadow-implement → memory-keeping | shadow logs into sessions |

(6 entries — all SKIP; pg-shadow-implement is a leaf workflow)

### Peer workflows (BIDIR — to fix)

| Edge | Justification |
|---|---|
| pg-feature-plan → pg-patch-review | a plan often consumes review feedback; both peer planning artifacts |
| pg-feature-plan → review-checklist | same as above |
| pg-feature-plan → patch-submission | plan describes what will be submitted |
| pg-implement → patch-submission | R12 in implement explicitly invokes submission |
| pg-implement → review-checklist | R12 invokes review-checklist pre-submission |

(5 entries — fix all 5 with back-links)

### Pipeline / catalog (BIDIR — to fix)

| Edge | Justification |
|---|---|
| access-method-apis → extension-development | extensions often add custom AMs; symmetric topic |

(1 entry — fix)

### Hub → utility (BIDIR — to fix, opposite of skip rule 5)

| Edge | Justification |
|---|---|
| pg-claude has NO companion_skills field | should have the major user-facing peers |

(1 entry — pg-claude SKILL.md has no `companion_skills:` line at all; add one listing the major workflows)

### Other singletons

| Edge | Verdict |
|---|---|
| (the remaining 2-3 from the raw 53) | covered by the categories above |

## Targeted fixes applied by this PR

1. `pg-feature-plan/SKILL.md` — already lists pg-patch-review,
   review-checklist, patch-submission as companions; this PR
   adds back-links **from** those three skills to pg-feature-plan.
2. `pg-implement/SKILL.md` — already lists review-checklist,
   patch-submission; this PR adds back-links from those two.
3. `extension-development/SKILL.md` — add `access-method-apis`
   to its companion_skills.
4. `pg-claude/SKILL.md` — add a `companion_skills:` frontmatter
   field listing the major user-facing workflows: memory-keeping,
   pg-feature-brainstorm, pg-feature-plan, pg-implement,
   pg-patch-review, build-and-run, debugging.

After fixes the graph has 47 asymmetries total, all in SKIP
categories (foundational utility 35; domain → hub 3;
pg-shadow-implement leaf 6; topical peer with no useful
back-link 3). Zero unintentional ones.

Re-audit command:

```bash
python3 progress/companion-skills-audit.md  # the script at the end of this doc
```

(The script accepts any working directory rooted at
postgres-claude/.)

## How to maintain

When you add a new skill or a new companion_skills line:

1. Decide which of the 6 categories the edge falls into.
2. Bidirectional categories (1, 2, 3) — add the back-link.
3. Skip categories (4, 5, 6) — leave one-way.
4. Update this doc's verdict table if the new edge doesn't fit
   the existing categories cleanly.

Re-run the audit script (in the PR description) before merging
any skill addition.

## Audit script

```python
# Run from postgres-claude/ root
import re, glob
skills = {}
for path in sorted(glob.glob('.claude/skills/*/SKILL.md')):
    name = path.split('/')[-2]
    text = open(path).read()
    fm = re.match(r'(?s)---\n(.*?)\n---', text)
    body = fm.group(1) if fm else ''
    m = re.search(r'(?m)^companion_skills:\s*\n((?:\s*-\s*\S+\n)*)', body)
    companions = []
    if m:
        for line in m.group(1).splitlines():
            mc = re.match(r'\s*-\s*(\S+)', line)
            if mc:
                companions.append(mc.group(1))
    skills[name] = companions

# Find asymmetric edges
asym = [(a, b) for a, comps in skills.items()
              for b in comps
              if b in skills and a not in skills[b]]
print(f"Asymmetries: {len(asym)}")
for a, b in asym:
    print(f"  {a} → {b}")
```

Save as `dev/audit_companions.py` and run after each
skill-creator iteration.

## Cross-references

- `sessions/2026-06-14-handoff-pre-compact-round3.md` — the
  catalog item this audit closes.
- `progress/skill-creator-intent-verb-sweep.md` — prior
  skill-creator pass that touched all 27 descriptions.
- `.claude/skills/pg-claude/SKILL.md` — master index updated by
  this PR.
