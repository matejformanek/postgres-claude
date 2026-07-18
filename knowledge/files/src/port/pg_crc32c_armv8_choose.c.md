---
path: src/port/pg_crc32c_armv8_choose.c
anchor_sha: e18b0cb7344
loc: 162
depth: read
---

# src/port/pg_crc32c_armv8_choose.c

## Purpose

The runtime CPU-feature dispatcher for ARM CRC32C. On first call to
`pg_comp_crc32c`, this file's `pg_comp_crc32c_choose` probes for the
ARMv8 CRC Extension (and optionally the PMULL crypto extension), then
patches the global function pointer to the best available implementation:
sb8 software fallback, scalar ARMv8 `__crc32c*` intrinsics, or PMULL-folded
vectorized CRC. The ARM equivalent of the choose-code embedded in
`pg_crc32c_sse42.c`. `[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `pg_crc32c (*pg_comp_crc32c)(...)` | `pg_crc32c_armv8_choose.c:162` | Global function pointer initially set to `pg_comp_crc32c_choose` |

## Internal landmarks

- `pg_crc32c_armv8_available` (`:45`) — three platform arms:
  - `HAVE_ELF_AUX_INFO` (FreeBSD) — `elf_aux_info(AT_HWCAP, ...)`, bit
    `HWCAP_CRC32`. On 32-bit ARM the bit lives in HWCAP2 not HWCAP, hence
    the `#ifdef __aarch64__` split (`:50-56`).
  - `HAVE_GETAUXVAL` (Linux) — same idea via `getauxval(AT_HWCAP)` (or
    `AT_HWCAP2` on 32-bit).
  - `__NetBSD__` (`:63-105`) — reads the ISAR0 register via
    `sysctl machdep.cpu0.cpu_id` (aarch64) or `machdep.id_isar` (32-bit ARM),
    extracts a 4-bit CRC32 field at bit position 16, and accepts any nonzero
    value. `[from-comment]`
- `pg_pmull_available` (`:113`) — gated by both
  `USE_PMULL_CRC32C_WITH_RUNTIME_CHECK` and `__aarch64__`. Checks
  `HWCAP_PMULL` via the same auxv probes. 32-bit ARM doesn't get PMULL.
- `pg_comp_crc32c_choose` (`:139`) — set fallback first: if
  `USE_ARMV8_CRC32C` is hardcoded (e.g., macOS, where runtime detection
  doesn't work) use armv8; else use sb8 software. Then probe; if armv8
  available, install it; if PMULL also, upgrade to that. `[from-comment]`

## Invariants & gotchas

- **macOS shortcut: skip runtime detection.** The comment at `:143-144`
  flags that on macOS the auxv probes don't work, so the build hardcodes
  `USE_ARMV8_CRC32C` and the choose function unconditionally selects
  `pg_comp_crc32c_armv8`. Apple Silicon and Macs with M-series CPUs all
  have CRC Extension so this is safe. `[from-comment]`
- **NetBSD's `sysctl` interface differs by bitness.** The path and struct
  layout for ISAR0 changes between 32-bit and 64-bit kernels. The comment
  at `:65-69` calls this out as "doubtless-historical". `[from-comment]`
- This is **only the chooser** — the actual implementations are in
  `pg_crc32c_armv8.c`. Splitting the chooser into its own TU lets the
  implementation file carry `pg_attribute_target` directives without
  affecting the dispatch code's calling convention.

## Cross-refs

- `knowledge/files/src/port/pg_crc32c_armv8.c.md` — the implementations
  this file picks between.
- `knowledge/files/src/port/pg_crc32c_sb8.c.md` — the software fallback.
- `knowledge/files/src/port/pg_crc32c_sse42.c.md` — x86 sibling that
  embeds its choose code inline rather than splitting it out.
- `knowledge/files/src/port/pg_popcount_aarch64.c.md` — sibling SIMD file
  using the same HWCAP_SVE probe pattern.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
