# connect.h

A single-macro header providing the canonical "lock down the
search_path" SQL for FE/BE tools that establish a libpq
connection. (`source/src/include/common/connect.h:1-28`)
[verified-by-code]

## Purpose

Avoid the classic SECURITY-DEFINER / `CREATE` confused-deputy
attack by clearing `search_path` immediately after connecting. Every
maintenance tool (`pg_dump`, `pg_restore`, `vacuumdb`, `reindexdb`,
`clusterdb`, `pg_amcheck`, …) executes this query right after
authentication.

## Key declarations

- `ALWAYS_SECURE_SEARCH_PATH_SQL` =
  `"SELECT pg_catalog.set_config('search_path', '', false);"`
  Header comment notes:
  - Unqualified `CREATE` will fail because no creation schema is
    selected — desirable hardening for utility connections.
  - Does *not* demote `pg_temp`, so unsuitable for SECURITY
    DEFINER bodies (use `pg_catalog, pg_temp` there instead).
  - Portable back to PostgreSQL 7.3.

## Phase D notes

[ISSUE-undocumented-invariant: callers must run this AFTER auth
but BEFORE any other query — header doesn't spell that out (low)]
The wrong ordering (running a query first, then setting the
search_path) defeats the protection. All in-tree callers do it
correctly, but a new caller copying the macro name without reading
the comment could get it wrong.
