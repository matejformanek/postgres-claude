# `src/include/utils/pg_rusage.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Tiny resource-usage measurement helper used in VACUUM/ANALYZE/CREATE
INDEX verbose output. Wraps `getrusage(2)` and gettimeofday(2).

## Public API

[verified-by-code: lines 22-30]
```c
typedef struct PGRUsage {
    struct timeval tv;
    struct rusage  ru;
} PGRUsage;

extern void        pg_rusage_init(PGRUsage *ru0);
extern const char *pg_rusage_show(const PGRUsage *ru0);
```

`pg_rusage_init` captures a baseline; `pg_rusage_show` returns a
statically-allocated, human-readable diff string (CPU sec, elapsed sec,
I/O blocks).

## Invariants

- **INV** [inferred] Return value of `pg_rusage_show` points to a
  static buffer — not re-entrant, not thread-safe (PG is process-per-
  connection so this is fine).

## Trust boundary

None. Output only goes to backend log / NOTICE messages addressed to
the issuer of the command.

## Cross-refs

- Callers: `commands/vacuum.c`, `commands/analyze.c`,
  `commands/cluster.c`, `commands/indexcmds.c`.

## Issues

None.
