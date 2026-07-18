---
source_url: https://www.postgresql.org/docs/current/app-postgres.html
fetched_at: 2026-07-18
anchor_sha: 03480907e9ff
app: src/backend/main + src/backend/tcop/postgres.c
---

# postgres — the server backend binary

`postgres` is the multiuser server (the process `pg_ctl start` launches as the
postmaster). `postmaster` survives only as a deprecated alias. Two special
launch modes and a set of developer-only flags make this page the reference for
single-user recovery and backend debugging.

## Non-obvious claims

- **Single-user mode** (`postgres --single -D <datadir> [opts] <dbname>`) runs
  one interactive backend with **no postmaster, no background processes, no real
  IPC/locking**, and the session user is uid 1 with implicit superuser powers.
  Its uses are exactly the three where a postmaster can't help: initdb bootstrap,
  system-catalog repair, and disaster recovery. It is explicitly *not* a tool for
  debugging a live server (no concurrency). `[from-docs]`
- Single-user input terminators are unusual: by default a **newline** submits the
  query (backslash-newline continues a line); with `-j`, submission requires
  `;`+newline+empty-line, which lets you type semicolons inside literals. `EOF`
  (Ctrl-D) exits; if text is pending, the first EOF acts as a terminator and the
  second exits. `[from-docs]`
- **Bootstrap mode** `--boot` is the mode `initdb` drives to build `template1`
  from the BKI script; it's internal-use and not meant to be run by hand.
  `[from-docs]`
- `-O` (**allow system-table structure changes**) and `-P` (**ignore system
  indexes** on read, still update on write) are the recovery levers: `-O` lets DDL
  touch catalog structure, and `-P` is how you get in when a *system index* is
  corrupt. Both are used by initdb / recovery, not normal operation. `[from-docs]`
- `-f {s|i|o|b|t|n|m|h}` **forbids planner methods** for testing —
  **s**eqscan / **i**ndexscan / index-**o**nly / **b**itmap / **t**idscan /
  **n**estloop / **m**ergejoin / **h**ashjoin — the backend-global equivalent of
  the `enable_*` GUCs, handy for forcing a plan shape in tests. `[from-docs]`
- Timing/introspection dev flags: `-s` prints per-command time+memory stats;
  `-t {pa|pl|e}` times parser/planner/executor separately (mutually exclusive
  with `-s`); `-S <kB>` sets the sort/hash work memory; `-d {1..5}` sets debug
  verbosity. `[from-docs]`
- **Debugger-attach helpers**: `-W <seconds>` makes a starting backend sleep that
  long after authentication so you can attach a debugger before it does work; and
  the abnormal-termination signal can be switched from `SIGQUIT` to a
  core-dumping signal for post-mortem analysis. Under the per-connection fork
  model these are how you catch a *specific* fresh backend. `[from-docs]`
- Any GUC can be set at launch as `-c name=value` or `--name=value` (underscores
  may be written as dashes on the command line), repeatable — this is the same
  mechanism `pg_ctl -o` forwards. `[from-docs]`
- Core server flags of note: `-D datadir` (or `PGDATA`), `-p port` (default 5432
  / `PGPORT`), `-k <dir>` unix-socket dir, `-B nbuffers` (shared buffers),
  `-N maxconn`, `-F` disable fsync (dangerous), `-e` European (DMY) dates.
  `[from-docs]`

## Links into corpus

- Postmaster fork model, backend startup, `ProcessInterrupts`, aux processes:
  the `process-lifecycle` skill, `[[knowledge/docs-distilled/server-start.md]]`,
  `[[knowledge/docs-distilled/connect-estab.md]]`.
- The main message loop (`PostgresMain` in `tcop/postgres.c`) these flags tune:
  `[[knowledge/docs-distilled/query-path.md]]`, the `wire-protocol` skill.
- `--boot` bootstrap driven by initdb: `[[knowledge/docs-distilled/app-initdb.md]]`,
  `[[knowledge/docs-distilled/bki.md]]`.
- Attaching a debugger to a forked backend (the `-W` window): the `debugging`
  skill.
- `-f`/`-S` planner-shaping equivalents at the SQL level:
  `[[knowledge/docs-distilled/runtime-config-query.md]]`, the `executor-and-planner` skill.
