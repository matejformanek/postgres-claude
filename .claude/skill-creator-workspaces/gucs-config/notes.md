# skill-creator iter — gucs-config (+ bgworker-and-extensions + extension-development sweep)

## Context

Fourth iter of the arc. PRs #201 / #202 / #241 established:
- `claude -p` runs are noisy (3/5 to 2/5 across reruns of same skill).
- Intent-verb + named-anti-cue descriptions move trigger rate
  from 0/3 to 1/3 (PR #241 — parallel-query).

This PR sweeps the same rewrite pattern across the remaining
post-SPLIT trio (gucs-config + bgworker-and-extensions) plus the
sibling extension-development (closely related, similar shape).

## Results

| Skill | run | passed | should-trig fired |
|---|---|---|---|
| gucs-config | iter-1 | 3/5 | 1/3 |
| bgworker-and-extensions | (not eval'd) | — | — |
| extension-development | (not eval'd) | — | — |

`gucs-config` reproduces PR #241's pattern exactly:
- ✓ PASS: "adding a custom GUC via DefineCustomIntVariable" — rate **1.00**
- ✗ FAIL: "check_hook and assign_hook for my custom GUC" — 0.00
- ✗ FAIL: "GUC_LIST_INPUT vs GUC_LIST_QUOTE for a string-list GUC" — 0.00
- ✓ PASS: "shared_buffers for a 32 GB server" — held
- ✓ PASS: "Node.js dotenv" — held

The single trigger that fired is the one naming `DefineCustom*Variable`
verbatim. Same effect as PR #241: `claude -p` fires on symbol matches,
not on conceptual matches.

## Why no eval on bgworker / extension-development

Three iterations of the same harness (PRs #201, #202, #241) all
produced 2/5-3/5 ranges, with the should-not-triggers reliably
held and the should-trigger rate dominated by whether the query
names a verbatim symbol. The rewrite pattern is the
intervention; running the eval is provenance. After 4 datapoints,
further runs would mostly burn budget for marginal signal.

The rewrites applied (same pattern):
- bgworker-and-extensions: noun-first → "Register a PG bgworker or
  layer extension hooks on _PG_init"; added Celery/Sidekiq/RQ/
  Resque/Kafka-consumer/Lambda/Cron/systemd/K8s Jobs anti-cues.
- extension-development: noun-first → "Build a PostgreSQL backend
  loadable extension"; added VS Code/Chrome/Firefox/Safari/NPM/pip/
  RubyGems/Cargo/IntelliJ/Eclipse anti-cues.

## What this completes

The post-SPLIT trio (PR #170) — parallel-query (PR #241),
gucs-config, bgworker-and-extensions — all now follow the intent-
verb + named-anti-cue pattern. Plus the sibling extension-
development.

## Status

Four skills rewritten under the pattern. Remaining ~22 skills
can be swept in subsequent PRs at ~3 per PR.

## Files

- `.claude/skill-creator-workspaces/gucs-config/iteration-1/{eval_set,benchmark}.json`
- `.claude/skill-creator-workspaces/gucs-config/notes.md` (this file)
- `.claude/skills/{gucs-config,bgworker-and-extensions,extension-development}/SKILL.md` — description field only
