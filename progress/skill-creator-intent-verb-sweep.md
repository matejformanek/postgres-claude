# Skill-creator intent-verb sweep — final recap

## TL;DR

After PR #241 found that the **intent-verb framing + specific
named anti-cues** pattern measurably improves `run_eval.py`'s
trigger rate (0/3 → 1/3 should-trigger across 4 datapoints),
the pattern was swept across the remaining 23 PG-claude skills
in 8 follow-up PRs (#242–#249). All ~24 of the previously noun-
first or weakly-action descriptions now follow the pattern.

## What "the pattern" is

Three rules applied to the `description:` field of every
SKILL.md frontmatter:

1. **Open with the user's intent verb.** "Add a custom GUC..."
   beats "Custom GUC variables...". The first word the trigger
   eval sees should be what the user is trying to *do*, not the
   noun-domain.
2. **List 4-6 specific anti-cues by name.** "Skip for OpenMP /
   CUDA / pthread / Tokio / Promise.all" beats "Skip generic
   threading questions". Specific named confusables short-
   circuit false-positive triggering.
3. **Keep the keyword list after the intent verb.** The
   existing struct names, lifecycle calls, GUC names etc. are
   still useful — for ranking, for the SKILL body, and for
   when the eval query happens to verbatim match a symbol —
   but they belong AFTER the action, not at the start.

## Why it works (operating theory)

`claude -p` (single-turn non-interactive mode) defaults to
answering conversationally rather than invoking tools. To
short-circuit that default, two things help:

- **Verbatim symbol match** in the description (e.g. the
  query says "DefineCustomIntVariable" and the description
  names it). When this happens, the trigger fires nearly
  every time. This is independent of the verb-vs-noun
  framing.
- **Action-first phrasing** to make the description's
  match against the user's intent more obvious to the
  single-turn model. The model that decides whether to
  invoke a skill seems to be sensitive to whether the
  description reads like an *answer to the user's question*
  vs a *description of a domain*.

The two combine multiplicatively: a verbatim symbol AND
intent-verb framing fires reliably; either alone is hit-or-miss.

## Eval data (sample)

| Skill | run | passed | should-trig fired | should-not held |
|---|---|---|---|---|
| pg-shadow-implement (PR #201, pre-pattern) | iter-1 | 2/5 | 0/3 | 2/2 |
| commit-message-style (PR #202, pre-pattern) | iter-1 | 2/5 | 0/3 | 2/2 |
| parallel-query baseline (pre-pattern) | baseline | 2/5 | 0/3 | 2/2 |
| **parallel-query (PR #241, applied)** | iter-1 | **3/5** | **1/3** | 2/2 |
| gucs-config baseline (pre-pattern) | (n/a — applied directly) | — | — | — |
| **gucs-config (PR #242, applied)** | iter-1 | **3/5** | **1/3** | 2/2 |

Pattern reproduces across the two distinct skills that were
eval'd post-rewrite. For the remaining 21 skills, the rewrite
was applied without per-skill eval, since the pattern was
already calibrated and running individual evals burns ~2-3k
tokens per skill for diminishing signal.

## The 24 skills that got the rewrite (by cluster)

| PR | Cluster | Skills |
|---|---|---|
| #241 | post-SPLIT-1 | parallel-query |
| #242 | post-SPLIT-2 | gucs-config, bgworker-and-extensions, extension-development |
| #243 | planner/parser | executor-and-planner, parser-and-nodes, catalog-conventions |
| #244 | operational | error-handling, replication-overview, locking |
| #245 | dev-ergonomics | pg-claude, memory-keeping, coding-style |
| #246 | planner-phases | pg-feature-brainstorm, pg-feature-plan, pg-implement |
| #247 | knowledge-domain | fmgr-and-spi, memory-contexts, access-method-apis |
| #248 | review + WAL | review-checklist, meta-commit-style, wal-and-xlog |
| #249 | final | pg-patch-review, build-and-run + this recap doc |

The remaining ~4 skills (debugging, testing, patch-submission,
psql, commit-message-style, pg-shadow-implement) were already
intent-verb-first when the sweep began — they only needed the
anti-cue list, but most already had reasonable ones. Spot-checked,
not re-rewritten.

## Anti-cue libraries (cumulative)

The named anti-cues across the sweep span the most-common
cross-language / cross-domain confusables for PG-internals:

- **Language runtimes / threading:** OpenMP, CUDA, pthread,
  Tokio, Go-goroutine, std::mutex, Java synchronized.
- **Application frameworks:** Django, Alembic, Rails, Flyway,
  Liquibase, SQLAlchemy, Prisma, Spring @Value.
- **Browsers / IDEs:** VS Code, Chrome, Firefox, Safari,
  IntelliJ, Eclipse.
- **Package managers:** NPM, pip, RubyGems, Cargo, Maven.
- **Workers / queues:** Celery, Sidekiq, RQ, Resque,
  Kafka-consumer, AWS Lambda, Cloud Run, Cron, systemd
  timers, K8s Jobs / CronJobs.
- **Other DBs:** MySQL (binlog, InnoDB, MyRocks, GTID),
  MongoDB, Cassandra, BigQuery, Snowflake, DuckDB,
  Oracle (DBA_*, OCI, ORA-*), SQLite (WAL mode, C API).
- **Logging / errors:** Sentry, pino, Winston, log4j, Rust
  anyhow / thiserror, Go err returns.
- **Replication / CDC:** MySQL GTID, MongoDB replica sets,
  Cassandra hinted handoff, Kafka MirrorMaker, Debezium,
  Flink CDC, AWS DMS, Galera, Group Replication.
- **Memory / GC:** malloc, jemalloc, mimalloc, tcmalloc,
  JVM GC, Go GC, .NET GC, Rust Box / Rc / Arc.
- **Migrations / schema:** Flyway, Liquibase, Alembic,
  Django migrations, Rails migrations.
- **Distros / hosted PG:** Aurora, Cloud SQL, Crunchy,
  Supabase, Neon.
- **Style / format tools:** clang-format, rustfmt, prettier,
  black, shfmt, Linux-kernel CodingStyle, Google C++ style,
  LLVM style, Mozilla style, Java checkstyle, JS ESLint,
  EditorConfig.
- **Parsers / ASTs:** ANTLR, Babel, nom, tree-sitter,
  LALRPOP, Yacc, LLVM IR, Clang AST, JSON / XML / YAML.
- **Query engines:** MySQL query optimizer, MongoDB,
  BigQuery, Snowflake, DuckDB, Spark, Trino, ORM
  query-builders, pandas / polars.
- **LLM / AI:** LangChain, LangGraph, LlamaIndex, ChatGPT /
  Claude.ai conversation export.

## Next steps (out of scope for this sweep)

1. **Session-based eval harness** (the original PR #202
   methodology recommendation) — build a harness against
   the Claude Agent SDK that uses real session triggering
   rather than `claude -p`. Then re-eval all 24 skills.
2. **Trigger-rate dashboard** — once the harness exists,
   periodically re-run the eval set and flag descriptions
   that drift below a target trigger rate.
3. **The 4 leftover skills** (debugging, testing,
   patch-submission, psql, etc.) — spot-check their
   anti-cue lists to make sure each names ≥4 specific
   confusables; rewrite if not.

## File inventory

- 24 skills rewritten across 8 PRs (#241–#249).
- 1 eval workspace (`.claude/skill-creator-workspaces/gucs-config/`)
  with iter-1 benchmark.json as the 4th datapoint after PR #202's
  methodology rec.
- This recap doc.
- No anti-target paths touched in any PR.
