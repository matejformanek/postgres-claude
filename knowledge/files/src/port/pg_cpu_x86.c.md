---
path: src/port/pg_cpu_x86.c
anchor_sha: e18b0cb7344
loc: 296
depth: read
---

# src/port/pg_cpu_x86.c

## Purpose

Runtime CPUID-based feature probe for x86. Sits behind
`x86_feature_available(PG_*)`, which the SIMD dispatchers in
`pg_popcount_x86.c` and `pg_crc32c_sse42.c` consult on first call to pick
the best available implementation. Also exposes
`x86_tsc_frequency_khz()` for the TSC-based timing infrastructure
(`instr_time.h`). The whole file is gated by `defined(USE_SSE2) ||
defined(__i386__)` — on platforms where it doesn't compile, an empty
`pg_cpu_x86_dummy_variable` keeps the linker happy. `[verified-by-code]`
`[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `bool X86Features[X86FeaturesSize]` | `pg_cpu_x86.c:50` | Flat array of feature bits indexed by `enum X86FeatureId` |
| `void set_x86_features(void)` | `:104` | Populates `X86Features` from CPUID. Called once at process start |
| `uint32 x86_tsc_frequency_khz(char *source, size_t source_size)` | `:170` | Returns nominal TSC frequency, 0 if unknown; appends source description |

## Internal landmarks

- `pg_cpuid` (`:68`) / `pg_cpuid_subleaf` (`:84`) — thin wrappers over
  GCC/MSVC intrinsics (`__get_cpuid` vs `__cpuid`, `__get_cpuid_count` vs
  `__cpuidex`). Zero `reg[4]` on entry so missing-intrinsic branches still
  return well-defined data.
- `set_x86_features` (`:104`) — populates the array:
  - CPUID leaf 1 → PG_SSE4_2, PG_POPCNT, PG_HYPERVISOR, OSXSAVE bit
  - CPUID leaf 7 subleaf 0 → PG_TSC_ADJUST; gated on OSXSAVE, also AVX2
    (XMM|YMM XCR0), AVX-512 BW/VL/VPCLMULQDQ/VPOPCNTDQ (ZMM XCR0 bits too)
  - CPUID 0x80000001 → PG_RDTSCP
  - CPUID 0x80000007 → PG_TSC_INVARIANT
  - Sets `INIT_PG_X86 = true` last, sentinel that probe ran. `[verified-by-code]`
- `_xgetbv(0)` (`:127`) — reads XCR0, the OS-enabled XSAVE state mask.
  Required to know whether SIMD state is preserved across context switches
  (a CPU with AVX-512 wired to bypass OS XSAVE would crash on AVX-512 use).
  Wrapped by `HAVE_XSAVE_INTRINSICS`. `[from-comment]`
- TSC frequency (`:170-247`) — three sources tried in order:
  1. Hypervisor leaf `0x40000010` (VMware/KVM only — checked by signature
     match at `:260-261`). VM TSC reads from leaves 0x15/0x16 are documented
     unreliable. `[from-comment]`
  2. CPUID leaf 0x15 — `(ECX * EBX) / EAX` nominal TSC frequency.
  3. CPUID leaf 0x16 — processor base frequency (MHz, less precise).
  Appends a human-readable source description to the optional `source`
  buffer if non-NULL.

## Invariants & gotchas

- **XSAVE state mask gate.** Even when CPUID claims AVX-512 instructions
  are present, the OS may not preserve ZMM state across context switches
  (rare these days but possible in older kernels or sandboxes). The XCR0
  check at `:131-143` is what makes runtime SIMD safe on every kernel. Don't
  test for AVX-512 with CPUID alone. `[verified-by-code]`
- **`set_x86_features` must run before any `x86_feature_available` call.**
  PG calls it once during process startup. A library / extension calling
  `pg_comp_crc32c` from `_PG_init` runs early — but `set_x86_features` runs
  before that, so the order works.
- **Hypervisor TSC trust.** VMware and KVM are the only hypervisors whose
  `0x40000010.EAX` is trusted. Hyper-V hides TSC frequency in MSRs that
  unprivileged code can't read; that returns 0 here. `[from-comment]`
- The `INIT_PG_X86` sentinel exists because callers might check the array
  via a macro that asserts "did the probe run?". Don't read individual
  feature bits without checking the sentinel.

## Cross-refs

- `knowledge/files/src/port/pg_popcount_x86.c.md` — primary consumer via
  `x86_feature_available(PG_POPCNT)` etc.
- `knowledge/files/src/port/pg_crc32c_sse42.c.md` — primary consumer via
  `PG_SSE4_2`, `PG_AVX512_VL`, `PG_AVX512_VPCLMULQDQ`.
- `source/src/include/port/pg_cpu.h` — `enum X86FeatureId`, `X86Features` decl.
- `source/src/include/portability/instr_time.h` — TSC frequency consumer.
