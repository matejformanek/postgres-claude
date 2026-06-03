---
path: src/bin/psql/help.h
anchor_sha: 4b0bf0788b0
loc: 22
depth: shallow
---

# help.h

- **Source path:** `source/src/bin/psql/help.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 22

## Purpose

Five-symbol public face of `help.c`. [verified-by-code, help.h:11-19]

| Symbol | Driven by | Notes |
|---|---|---|
| `usage(pager)` | `psql --help` | command-line option list |
| `slashUsage(pager)` | `\?` (no arg) or `\? commands` | backslash-command list, includes some live `pset` state echoes |
| `helpVariables(pager)` | `\? variables` | env-var + psql variable list |
| `helpSQL(topic, pager)` | `\h [TOPIC]` | dispatches into the auto-generated `QL_HELP[]` table from `sql_help.h` |
| `print_copyright()` | `\copyright` | static BSD license text |

## Phase D notes

No SQL is built here — only text output to stdout or via `PageOutput`.
The only server interaction is `slashUsage` calling `PQdb(pset.db)` for
the "currently connected to" message. The only user-controlled input
is the `topic` argument to `helpSQL`, which is matched
case-insensitively against the compile-time `QL_HELP[]` table and used
in a `psprintf` URL for postgresql.org docs. No injection surface.
[verified-by-code, help.c:716-727]

## Confidence tag tally
`[verified-by-code]=2`
