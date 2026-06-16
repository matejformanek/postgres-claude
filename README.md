# pg-claude

> Turn Claude Code into a long-term collaborator on **PostgreSQL internals** —
> a cited knowledge corpus, agent skills, slash commands, and task-shaped
> scenarios for serious backend hacking.

![License: PostgreSQL](https://img.shields.io/badge/license-PostgreSQL-336791)
![PostgreSQL: master](https://img.shields.io/badge/PostgreSQL-master-336791)
![Built for: Claude Code](https://img.shields.io/badge/built%20for-Claude%20Code-cc785c)

pg-claude is a **meta repo** that sits next to an upstream PostgreSQL checkout
and gives Claude Code (Anthropic's CLI) the muscle memory of a long-time PG
hacker: where things live in the tree, which subsystem owns which invariant,
how to plan a patch, how to write a `pgsql-hackers`-ready commit message, and
which `file:line` to cite for every claim.

## What is pg-claude

A meta repo of skills, slash commands, scenarios, idioms, and a cited
knowledge corpus that turns Claude Code into a PostgreSQL-internals
collaborator. It does **not** fork PG — `source/` is a read-only reference
clone of upstream `master`, and `dev/` is a disposable scratch clone where
patches live.

## What's inside

The numbers below come from the current corpus on `master`:

- **2,580** per-file PostgreSQL source-tree notes under
  [`knowledge/files/`](knowledge/files/) — **100% strict coverage** of the
  in-scope tree
- **30** Claude Code [skills](.claude/skills/) — coding style, fmgr/SPI,
  locking, parser/nodes, WAL/xlog, memory contexts, patch submission, …
- **31** task-shaped [scenarios](knowledge/scenarios/) — add-new-data-type,
  add-new-sql-keyword, add-startup-hook, add-GUC, add-new-index-am,
  add-new-bgworker, … each with an authoritative file checklist the
  planner pins as §3.
- **155** PG-wide [idioms](knowledge/idioms/) (memory contexts, ereport,
  fmgr, SPI, lock-acquire-then-pin, …)
- **127** issue registers under [`knowledge/issues/`](knowledge/issues/)
  cross-referencing `pgsql-hackers` threads and CF entries
- **50+** [session logs](sessions/) capturing real working sessions
- **20** [slash commands](.claude/commands/) for the everyday loop:
  `/setup-pg`, `/pg-start`, `/pg-test`, `/pg-psql`, `/pg-plan`,
  `/pg-implement`, `/pg-review`, …

## Who it's for

- **PostgreSQL hackers** who want an LLM assistant that does not hallucinate
  locking order, fmgr conventions, or `RelationGetSmgr` semantics.
- **Database-internals learners** who want a guided, cited reading path
  through the backend — buffer manager, heap AM, WAL, planner, executor.
- **Claude Code power users** who want a working, non-trivial example of an
  agent surface built around skills, scenarios, idioms, and slash commands.

## Quickstart

```bash
# 1. Lay out the three side-by-side repos
mkdir -p ~/Work/postgres && cd ~/Work/postgres
git clone https://github.com/postgres/postgres                  postgresql
git clone --no-hardlinks postgresql                             postgresql-dev
git clone https://github.com/matejformanek/postgres-claude      postgres-claude

# 2. Open Claude Code in the meta repo
cd postgres-claude && claude

# 3. Inside Claude Code
> /setup-pg     # configure + build PG into dev/build-debug
> /pg-start     # boot the dev cluster
> /pg-psql      # connect
```

Symlinks `source/ -> ../postgresql/` (read-only reference) and
`dev/ -> ../postgresql-dev/` (mutable workspace) resolve automatically;
every `file:line` citation in the corpus points into `source/…` so links do
not rot.

## Why this exists

Most LLM-assisted PG work fails the same way: confident-sounding wrong
claims about locking order, smgr lifetime, or what a given subsystem
actually does. pg-claude attacks that head-on with three working rules
baked into every skill, scenario, and review checklist:

1. **Cite or don't claim.** Every concrete statement must point at
   `source/<path>:<line>` — or be tagged `[unverified]`.
2. **Confidence tags.** `[verified-by-code]`, `[from-README]`,
   `[from-comment]`, `[inferred]`, `[unverified]`. No bare assertions.
3. **Two-repo separation.** Patches to PG live in `dev/` on a feature
   branch; meta artifacts (knowledge, sessions, plans) live in
   `postgres-claude/`. They never mix in a single commit.

See [`CLAUDE.md`](CLAUDE.md) for the full project contract and
[`.claude/rules/pg-implement-discipline.md`](.claude/rules/pg-implement-discipline.md)
for the 12 implementation rules.

## Showcase

Real working sessions, end-to-end:

- [`sessions/2026-06-16-scenarios-layer.md`](sessions/2026-06-16-scenarios-layer.md)
  — designing the task-shaped scenarios layer (add-new-data-type,
  add-new-sql-keyword, …) on top of the existing knowledge corpus.
- [`sessions/2026-06-15-phase-a-close-100pct-coverage.md`](sessions/2026-06-15-phase-a-close-100pct-coverage.md)
  — closing Phase A at 100% strict coverage across the in-scope PG tree.
- The full [`sessions/`](sessions/) log captures 50+ working sessions:
  subsystem deep-dives, multi-day patch reviews, cloud-routine intake,
  and the experiment notes that shaped the current skill set.

For a quick map of how a Claude Code session is supposed to feel inside
this repo, start with
[`.claude/skills/pg-claude/SKILL.md`](.claude/skills/pg-claude/SKILL.md) —
the master navigator skill.

## Status

Active, single-maintainer, experimental. The knowledge corpus is at 100%
strict coverage of the in-scope tree; skills, scenarios, and idioms are
expanding. There is no release cadence yet — `master` is the trunk and
[`progress/STATE.md`](progress/STATE.md) is always the source of truth on
what is and isn't done.

## License

[PostgreSQL License](LICENSE) — same as upstream PG, so anything you
copy from here is compatible with sending it back to `pgsql-hackers`.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). In short: the meta repo and
upstream PG are two distinct contribution paths and it matters which one
your change belongs to. Upstream PG changes go through
[`pgsql-hackers`](knowledge/community/patch-workflow.md), not GitHub PRs.
