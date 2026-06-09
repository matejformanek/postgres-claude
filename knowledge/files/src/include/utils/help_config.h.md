# `utils/help_config.h` — `postgres --describe-config` entry point

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/help_config.h`)

## Role

17-line header exposing one function: `GucInfoMain`. Called by
`src/backend/main/main.c` when the user runs `postgres --describe-config`,
which dumps the full GUC table as tab-separated text for documentation
tooling.

## Public API

- `pg_noreturn extern void GucInfoMain(void)` —
  `source/src/include/utils/help_config.h:15`.

## Invariants

- The function is `pg_noreturn` — it exits the process after writing
  output, never returns. [verified-by-attribute, `:15`]
- Runs before any catalog access; reads only the static
  `ConfigureNames[]` table. [inferred from `--describe-config` semantics]
- Output format is one GUC per line with tab-separated fields (name,
  context, group, vartype, ...). [inferred; matches PG docs build]

## Notable internals

Trivial header. The only thing worth noting is that `--describe-config`
runs outside a backend lifecycle — no shared memory, no transaction.

## Trust-boundary / Phase D surface

- `pg_noreturn` means the caller never recovers; if `GucInfoMain` ever
  reaches an error path that wasn't `_exit`, the absence of return is
  a contract violation. [ISSUE-error-handling: pg_noreturn contract
  must be upheld inside; header gives no recovery (nit)]
- The output is consumed by docs/scripting; a future change in the
  field order or escaping rules silently breaks downstream tooling.
  No format-version is exposed. [ISSUE-api-shape: --describe-config
  output format has no version marker (nit)]
- Built-in GUC names are exposed including any that are
  `GUC_NO_SHOW_ALL` flagged. In normal SHOW, those are hidden; in
  --describe-config they appear because the goal is full documentation.
  [ISSUE-audit-gap: --describe-config may print GUC_NO_SHOW_ALL names,
  potentially revealing internal-only settings to anyone who can run
  the binary (nit; running the binary already implies file-system
  access)]

## Cross-refs

- `knowledge/files/src/include/utils/guc.h.md` — `ConfigureNames[]` and
  `config_generic`.
- `knowledge/files/src/include/utils/guc_tables.h.md` —
  `config_group`, `config_type` enums printed by GucInfoMain.

## Issues

1. [ISSUE-api-shape: `--describe-config` output format has no version
   marker; downstream tooling fragile (nit)] —
   `source/src/include/utils/help_config.h:15`.
2. [ISSUE-audit-gap: --describe-config may print `GUC_NO_SHOW_ALL`
   names (nit)] —
   `source/src/include/utils/help_config.h:15`.
