---
path: src/test/modules/test_extensions/test_ext.c
anchor_sha: e18b0cb7344
loc: 22
depth: read
---

# src/test/modules/test_extensions/test_ext.c

## Purpose

Trivial C body for the `test_extensions` regression-test scaffolding. The
real testing here is in the `.control`/`.sql` files and the PG-side machinery
for `extension_control_path` (used to validate `pg_upgrade`'s extension
discovery). The C file exists only because some tests need the module to be
loadable as a `.so`. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_ext` | `test_ext.c:14` | Emits `NOTICE: running successful` and returns void |

## Internal landmarks

None beyond a single `PG_FUNCTION_INFO_V1` registration.

## Invariants & gotchas

- **Test module — never load in production.** It does nothing meaningful.
- The real interest is the surrounding `.control`/`.sql` files (extension
  manifests with various dependency / trust / relocatable combinations) and
  the TAP harness that exercises `pg_upgrade` against them.

## Cross-refs

- `source/src/backend/commands/extension.c` — `CREATE EXTENSION` machinery.
- `source/src/backend/utils/misc/guc_tables.c` — the
  `extension_control_path` GUC this test ultimately exercises.
