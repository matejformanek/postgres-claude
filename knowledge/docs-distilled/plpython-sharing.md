---
source_url: https://www.postgresql.org/docs/current/plpython-sharing.html
chapter: "46.3 PL/Python Sharing Data (plpython-sharing)"
fetched_at: 2026-07-22
anchor_sha: d774576f6f0
---

# PL/Python sharing data — plpython-sharing

The `SD` / `GD` global dictionaries that let PL/Python functions keep state
between calls. Short chapter, but the scoping is non-obvious and a classic
footgun: both dictionaries are **per-backend-session**, so their lifetime is a
single database connection, and `GD` is *not* a cross-session cache.

## Non-obvious claims

- **`SD` is per-function, persists across calls within a session.** "The global
  dictionary `SD` is available to store private data between repeated calls to
  the same function." [from-docs] Each function has its own `SD`; it survives
  call-to-call but dies with the session.
- **`GD` is shared across ALL PL/Python functions in the session.** "The global
  dictionary `GD` is public data, that is available to all Python functions
  within a session." [from-docs] It is the single documented bridge across the
  per-function isolation.
- **Function execution environments are otherwise isolated.** "Each function
  gets its own execution environment in the Python interpreter, so that global
  data and function arguments from `myfunc` are not available to `myfunc2`. The
  exception is the data in the `GD` dictionary." [from-docs] So ordinary Python
  module-level globals set by one function are invisible to another — only `SD`
  (self) and `GD` (shared) cross call boundaries.
- **Both are per-backend-process, session-scoped — NOT shared between
  connections.** The fork-per-connection model means each backend has its own
  interpreter and its own `SD`/`GD`. `GD` is "global" only within one session;
  it is emphatically not a server-wide cache and vanishes at disconnect. The
  docs flag using it "with care" for exactly this reason. [from-docs, inferred
  from the per-session wording + PG's process model]

## Why it matters

Because `GD`/`SD` live in the backend's embedded Python interpreter, they are
free of locking concerns *across* sessions (each backend is single-threaded and
private) but offer **no** persistence: a connection pooler that recycles
backends will hand a new session a different `GD`. For cross-session shared
state you need a table, an unlogged table, or shared memory via an extension —
not `GD`. This mirrors the same "session-local, process-private" caveat that
applies to prepared statements and temp tables under the fork model.

## Links into corpus

- `[[knowledge/docs-distilled/plpython-funcs.md]]` — §46.2, the per-function
  execution environment `SD`/`GD` hang off.
- `[[knowledge/docs-distilled/plpython-database.md]]` — §46.4, `plpy.execute`
  plan objects are a common thing to cache in `SD`.
- `[[knowledge/docs-distilled/overview.md]]` — the fork-per-connection model
  that makes `GD` session-private.
- Skill `process-lifecycle` — the per-backend process boundary that scopes
  these dictionaries.

## Verification note

Two-quote behavioral chapter; both `SD`/`GD` scope claims are [from-docs] @
current. The "per-backend-process / not-cross-session" corollary is [inferred]
from PG's documented fork-per-connection model (`overview.md`) applied to the
embedded interpreter — not a single source line.
