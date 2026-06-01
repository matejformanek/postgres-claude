# 2026-06-01 — leaf-subsystems wave 3 (libpq-backend / port / main / foreign / jit / partitioning)

## What was read
- libpq backend: deep `be-secure.c`, `auth.c`, `hba.c`; read
  `be-secure-common.c`, `crypt.c`, `auth-sasl.c`, `pqsignal.c`,
  `pqmq.c`, `pqcomm.c` top, `pqformat.c` top, `ifaddr.c` top,
  `be-secure-openssl.c` top, `be-secure-gssapi.c` top,
  `be-fsstubs.c` top, `README.SSL`. Headers: `libpq.h`,
  `libpq-be.h`, `hba.h`, `auth.h`, plus skims of the remaining
  libpq headers.
- port: `atomics.c`, `posix_sema.c` top, `sysv_sema.c` top,
  `sysv_shmem.c` top, `win32_shmem.c` top, `include/port/atomics.h`
  top.
- main: full `main.c`.
- foreign: full `foreign.c`, `foreign.h`, `fdwapi.h`.
- jit: full `jit.c`, `README`; tops of `llvmjit.c`,
  `llvmjit_deform.c`, `llvmjit_expr.c`, `llvmjit_inline.cpp`;
  full `llvmjit_error.cpp`, `llvmjit_wrap.cpp`; headers
  `jit.h`, `llvmjit.h`.
- partitioning: tops of `partbounds.c`, `partprune.c`, `partdesc.c`;
  deep on the three bsearch functions in `partbounds.c:3592-3763`;
  headers `partbounds.h`, `partprune.h`, `partdesc.h`.

## Docs produced
- `knowledge/subsystems/libpq-backend.md`
- `knowledge/subsystems/port.md`
- `knowledge/subsystems/main.md`
- `knowledge/subsystems/foreign.md`
- `knowledge/subsystems/jit.md`
- `knowledge/subsystems/partitioning.md`
- `knowledge/subsystems/headers-wave3.md`

## Key facts locked
- **`check_hba` is linear-first-match**, no priority, no second
  pass; implicit-reject is a synthetic last entry
  ([verified-by-code] `hba.c:2338-2438`).
- **JIT load is sticky-fail**: `provider_failed_loading` is set
  *before* `load_external_function` and only cleared on success
  ([verified-by-code] `jit.c:78-120`).
- **Partition bsearches all share the same invariant**: return
  greatest index with bound ≤ probe, or -1. `lo=-1`,
  `hi=ndatums-1`, `mid=(lo+hi+1)/2`; early-break when cmp==0
  ([verified-by-code] `partbounds.c:3599-3763`).
- **`FdwRoutine` is a 30+ field vtable** ([verified-by-code]
  `fdwapi.h:208-286`); `GetFdwRoutineForRelation` caches it in
  `rd_fdwroutine` and `restrict_nonsystem_relation_kind` is the
  only choke point.

## Flagged uncertain (carried into §9 of each doc)
- libpq: full OAuth + SCRAM channel-binding traces; SSPI; pg_hosts.conf reload semantics.
- port: Win32 bodies; aix/, tas/ subdirs.
- foreign: deep planner walk through `GetExistingLocalJoinPath` merge path.
- jit: LLVMJitContext handle lifecycle vs resowner; inliner index format.
- partitioning: `partition_bounds_merge` algorithm; `last_found_count` parallel COPY behavior; step interpreter walkthrough.

## Tag tallies (per-doc, approximate)
| Doc | verified | from-README | from-comment |
|---|---|---|---|
| libpq-backend | 21 | 0 | 14 |
| port | 4 | 0 | 8 |
| main | 8 | 0 | 9 |
| foreign | 8 | 0 | 4 |
| jit | 11 | 10 | 4 |
| partitioning | 8 | 0 | 10 |

## Registry
- 63 new rows appended to `progress/files-examined.md`,
  `By = leaf-subsystems-wave3`.
