---
path: src/include/jit/llvmjit_backport.h
anchor_sha: e18b0cb7344
loc: 22
depth: read
---

# src/include/jit/llvmjit_backport.h

## Purpose

Tiny conditional-compilation switch shared by PostgreSQL and the in-tree
backported LLVM source files. Defines `USE_LLVM_BACKPORT_SECTION_MEMORY_MANAGER`
when running on AArch64 with `LLVM_VERSION_MAJOR < 22`. That macro turns on the
patched `llvm::backport::SectionMemoryManager` shipped in
`src/backend/jit/llvm/SectionMemoryManager.cpp` (mirror of the LLVM upstream
class but altered to allocate all JIT sections from a single reservation), as
a workaround for a bug where stock pre-LLVM-22 RuntimeDyld can emit code that
crashes on large-memory ARM64 systems because its multiple memory chunks land
too far apart to satisfy ARM relocations. `[from-comment][verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `USE_LLVM_BACKPORT_SECTION_MEMORY_MANAGER` (macro) | `:18-20` | Defined only when `defined(__aarch64__) && LLVM_VERSION_MAJOR < 22` |

## Internal landmarks

Single `#if defined(__aarch64__) && LLVM_VERSION_MAJOR < 22` block (`:18-20`)
sitting after `#include <llvm/Config/llvm-config.h>` (`:8`). No code, just the
gate.

## Invariants & gotchas

- **Architecture + version are *both* required.** x86_64 hits the same
  RuntimeDyld code paths but the ARM-only relocation reach is what triggers
  the crash, so the workaround stays off there. Don't loosen the guard.
- **Drop dead in LLVM 22+.** The fix landed upstream in LLVM 22; this header
  must keep gating *out* the backport on new LLVM to avoid double-defining
  the class. When PG bumps its minimum LLVM past 21, this file (and the
  backport .cpp) can be removed entirely.
- **Includable from both C and C++.** Only one LLVM header is pulled in
  (`<llvm/Config/llvm-config.h>`), which is plain macros — safe for both
  languages. The corresponding `SectionMemoryManager.h` next to this file is
  C++-only.

## Cross-refs

- `knowledge/files/src/include/jit/SectionMemoryManager.h.md` — the backported
  class declaration.
- `knowledge/files/src/include/jit/llvmjit.h.md` — gates
  `LLVMOrcCreateRTDyldObjectLinkingLayerWithSafeSectionMemoryManager` on this
  macro at `llvmjit.h:144-146`.
- `source/src/backend/jit/llvm/SectionMemoryManager.cpp` — the .cpp providing
  the backported class.
