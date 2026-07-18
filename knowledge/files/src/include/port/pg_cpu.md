# `src/include/port/pg_cpu.h`

## Role

Runtime CPU feature detection for x86 (SSE 4.2, POPCNT, AVX2, AVX-512,
TSC variants, hypervisor presence). Defines an `X86FeatureId` enum and
the `X86Features[]` array; lookup is `x86_feature_available(feature)`,
which lazily initializes via `set_x86_features()` on first miss
`[verified-by-code]` `source/src/include/port/pg_cpu.h:50-57`.

Header is **only compiled on x86 / x86_64** (gated by
`USE_SSE2 || __i386__`) — ARM, POWER, etc. don't get a `pg_cpu.h`
backed surface; they use compile-time `#ifdef`s for feature gating.

## Public API

`[verified-by-code]` `source/src/include/port/pg_cpu.h:18-60`:

- `enum X86FeatureId { INIT_PG_X86, PG_SSE4_2, PG_POPCNT, PG_AVX2,
   PG_AVX512_BW, PG_AVX512_VL, PG_AVX512_VPCLMULQDQ,
   PG_AVX512_VPOPCNTDQ, PG_HYPERVISOR, PG_RDTSCP,
   PG_TSC_INVARIANT, PG_TSC_ADJUST }`
- `X86FeaturesSize` = enum-count.
- `extern PGDLLIMPORT bool X86Features[]`.
- `extern void set_x86_features(void)`.
- `static inline bool x86_feature_available(X86FeatureId feature)`.
- `extern uint32 x86_tsc_frequency_khz(char *source, size_t source_size)`.

## Invariants

1. **`INIT_PG_X86` is the sentinel** — set to true after
   `set_x86_features` populates the table. The inline check
   `if (X86Features[INIT_PG_X86] == false) set_x86_features();`
   makes the dispatch idempotent and lazy `[verified-by-code]`
   `source/src/include/port/pg_cpu.h:53-54`.
2. **`X86FeaturesSize` enumerates max ID + 1**, used to size the
   array externally `[verified-by-code]`
   `source/src/include/port/pg_cpu.h:44`.
3. **Non-x86 builds get nothing from this header** — the entire
   contents are wrapped in `#if defined(USE_SSE2) || defined(__i386__)`
   `[verified-by-code]` `source/src/include/port/pg_cpu.h:16,61`.
4. **TSC features are exposed for measurement, not for "fast time"**
   — PG's clock_gettime / gettimeofday usage is separate. The TSC
   readout is for `x86_tsc_frequency_khz` to inform tools about
   timer precision.

## Notable internals

The lazy-init pattern means **every consumer that calls
`x86_feature_available` pays a one-time CPUID probe**. After init,
it's a single load + a comparison. Used by:

- `pg_crc32c` runtime-check paths (test PG_SSE4_2, PG_AVX512_*).
- `pg_popcount` runtime-check (PG_POPCNT, PG_AVX512_VPOPCNTDQ).
- Future: any new SIMD codepath wanting runtime dispatch.

`set_x86_features` lives in `src/port/pg_x86_features.c` `[unverified
— not in scope here but the natural .c file]`.

## Trust-boundary / Phase D surface

- **Hypervisor-detection (`PG_HYPERVISOR`) is informational only.**
  PG doesn't gate behavior on whether we're in a VM. The bit comes
  from CPUID leaf 1 ECX bit 31. It's there for observability tools.
- **`PG_TSC_INVARIANT` controls clock-source choice in some
  benchmarks.** TSC without invariance (older AMD, certain VMs) can
  drift between cores; PG doesn't currently use TSC for timestamps
  but tooling that does (perf_event, dtrace) cares.
- **Lazy-init means concurrent first-callers all call CPUID**
  redundantly until one wins the store to `X86Features[INIT_PG_X86]`.
  The probe is idempotent (CPUID is pure), so the worst case is "two
  threads do the work, last writer wins". Not a correctness issue.
- **Adversarial CPUID is not a concern in-process** — but if a VM
  emulator reports lies about feature support, PG would
  generate-and-trap on `SIGILL`. Unlikely failure mode in practice.

## Cross-refs

- `source/src/port/pg_x86_features.c` `[unverified path]` — the
  `set_x86_features` implementation.
- `source/src/include/port/pg_crc32c.h`,
  `source/src/include/port/pg_bitutils.h` — consumers.
- A16-other (this slice): `simd.h`, `pg_lfind.h` indirectly.

## Issues / unresolved

- **ISSUE-portability**: no equivalent header for ARM (`pg_cpu_arm.h`)
  — ARMv8 feature detection (CRC32 ext, SVE) is currently done via
  separate `_choose.c` files per-feature, scattered. Could be
  unified. (severity: low)
- **ISSUE-doc**: the header doesn't say WHERE the lazy init happens
  (the consumer of `x86_feature_available` triggers it); a comment
  pointing at `set_x86_features` would help. (severity: trivial)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
