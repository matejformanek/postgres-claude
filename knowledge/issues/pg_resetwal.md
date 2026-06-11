# Issue register — `pg_resetwal`

Covers `src/bin/pg_resetwal/pg_resetwal.c`.

Sweep A20 bucket D, verified at `e18b0cb7344`.

This tool can silently corrupt a cluster. Most "issues" below are NOT
bugs but documented footguns; flagged so reviewers and downstream
auditors don't blindly trust pg_resetwal exit codes.

## Critical (data-loss footguns by design)

- **`--force` authorizes possible corruption** — `pg_resetwal.c:537-543`.
  Lets the user proceed past a dirty shutdown, which is the single
  largest data-loss footgun in the PG toolset. Error text mentions
  "data to be lost"; no dump-and-reload reminder. The user docs cover
  this but the tool itself doesn't repeat it. (likely)

- **postmaster.pid heuristic is the only concurrent-use guard** —
  `pg_resetwal.c:417-428`. An operator who has manually removed a stale
  pid file can then legally run pg_resetwal against a live cluster.
  No advisory file lock. (likely)

- **Synthesized system_identifier silently breaks replicas/basebackups** —
  `pg_resetwal.c:683-691`. On `GuessControlValues`, a fresh
  `gettimeofday() << 32 | getpid()` identifier is built. Every replica
  and pg_basebackup-derived clone now refuses to attach. Documented in
  user docs; not in the tool's own output. (likely)

- **GuessControlValues uses minimal defaults** — `pg_resetwal.c:740`.
  XXX-comment promises to grovel through old XLOG for better values;
  never implemented. After guess, NextXID = FirstNormalTransactionId,
  which guarantees XID reuse against any committed work. (maybe —
  XXX is old)

## Correctness

- **Half-deleted WAL on unlink failure** — `pg_resetwal.c:1032`.
  `unlink` failure during WAL deletion is fatal but control file is
  ALREADY rewritten. Cluster is now in a partial state with new
  control file pointing at a new segment but old WAL still present.
  Restart-time recovery would have surprising behaviour. (likely)

- **Control file written BEFORE WAL deletion** — `pg_resetwal.c:937` then
  `:1015`. If kernel crashes between, on restart the control file says
  "fresh start at new segno" but old WAL files are still there;
  recovery may try to replay them. Probably harmless via segno-mismatch
  rejection but worth a comment. (maybe)

- **Multixact sanity checks inadequate** — `pg_resetwal.c:286-289`.
  XXX-comment admits this. With `-m` you can set
  `nextMulti < oldestMulti` and wrap around immediately. (maybe — old XXX)

- **`-l` validates only lexical** — `pg_resetwal.c:309-322`. Only checks
  character set (hex) and length. Doesn't validate the resulting
  TLI/segno is sensible relative to existing data. (nit)

- **`-c` uses `strtoul`, not the strict variant** —
  `pg_resetwal.c:236-242`. Inconsistent with the other XID parsers
  (`strtouint32_strict`). Sign-checking is absent on the
  `newest_commit_ts_xid_val` parse. (nit)

## Style

- **`#define FRONTEND 1` + `#include "postgres.h"` "ugly hack"** —
  shared with `pg_controldata`. Header includes acknowledge it. (from-comment)

- **`update_controlfile` semantic split between fsync-yes/no** — fine
  but the tool always passes `true`; matches `pg_checksums`. (nit)
