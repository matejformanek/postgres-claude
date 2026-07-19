# `src/include/executor/execdebug.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Compile-time debug printf macros for the executor — `EXEC_NESTLOOPDEBUG`,
`EXEC_SORTDEBUG`, `EXEC_MERGEJOINDEBUG`. Header notes the convention is
crufty and newer code prefers `elog()` [from-comment: lines 4-6].

## Public API

[verified-by-code: lines 33-127]

- `EXEC_NESTLOOPDEBUG` → `NL_printf` / `NL1_printf` /
  `ENL1_printf("ExecNestLoop: …")`.
- `EXEC_SORTDEBUG` → `SO_printf` / `SO1_printf` / `SO2_printf`.
- `EXEC_MERGEJOINDEBUG` → `MJ_*` family including `MJ_dump(state)`
  (`ExecMergeTupleDump`), `MJ_DEBUG_COMPARE`, `MJ_DEBUG_QUAL`,
  `MJ_DEBUG_PROC_NODE`.

When undefined (the default), each macro expands to nothing.

Helpers: `T_OR_F(b)`, `NULL_OR_TUPLE(slot)`.

## Invariants

None — these are dev-only compile-time toggles.

## Trust boundary

None.

## Cross-refs

- `executor/nodeNestloop.c`, `executor/nodeSort.c`,
  `executor/nodeMergejoin.c` — sole consumers.

## Issues

- [ISSUE-CRUFT: header is acknowledged crufty (lines 4-6); each
  macro family writes to `printf` (raw stdout), bypassing
  `elog`/log-line prefix. If someone builds with these defined in
  production by mistake, lines hit the postmaster's stdout (very
  low — defaults off)] — lines 4-6.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
