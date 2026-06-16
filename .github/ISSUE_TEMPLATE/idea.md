---
name: Idea
about: Propose a new skill, scenario, knowledge doc, slash command, or rule
title: "idea: "
labels: idea
---

## Which layer

Tick the layer this belongs to (one is fine; cross-layer ideas usually
split into multiple issues):

- [ ] **Skill** — `.claude/skills/<name>/SKILL.md`
- [ ] **Slash command** — `.claude/commands/<name>.md`
- [ ] **Scenario** — `knowledge/scenarios/<name>.md`
- [ ] **Knowledge doc** — `knowledge/{subsystems,data-structures,idioms,architecture}/<name>.md`
- [ ] **Rule** — `.claude/rules/<name>.md`

## What

One or two sentences describing the proposed addition.

## Why now

What concrete task or session has surfaced this gap? A pointer to a
session log, a `pgsql-hackers` thread, or a CF entry is ideal.

## Sketch

Bullet list of the rough structure you have in mind (headings, key
citations, scope boundaries). It's OK to leave this blank if you just
want to flag the gap.
