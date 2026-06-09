# Issues — `contrib/tsm_system_time`

TABLESAMPLE method — system sampling with time budget. 1 source file / ~356 LOC.

**Parent docs:** `knowledge/files/contrib/tsm_system_time/tsm_system_time.c.md`.

**Source:** 3 entries surfaced 2026-06-09 by A14-2.

## Headlines

1. **Time budget enforced at block boundary** — can overshoot user-supplied limit.
2. Asymmetry with sister module — pagemode NOT forced (different from `tsm_system_rows`).
3. No `CHECK_FOR_INTERRUPTS` in inner block-stepping loop.

## Entries — `tsm_system_time.c`

- [ISSUE-correctness: time budget enforced at block boundary, can overshoot (maybe)] — `:260-264`
- [ISSUE-api-shape: asymmetry with sister module — pagemode NOT forced (nit)] — `:188-210`
- [ISSUE-correctness: no `CHECK_FOR_INTERRUPTS` in inner block-stepping loop (maybe)] — `:217-279`
