---
path: src/include/jit/SectionMemoryManager.h
anchor_sha: e18b0cb7344
loc: 226
depth: read
---

# src/include/jit/SectionMemoryManager.h

## Purpose

In-tree fork of LLVM's `llvm::SectionMemoryManager` class declaration, lifted
verbatim from the upstream Apache-2.0-with-LLVM-Exception sources and modified
to support **single-block allocation** for the RuntimeDyld-based JIT. Used
only on AArch64 with `LLVM_VERSION_MAJOR < 22` (see
`knowledge/files/src/include/jit/llvmjit_backport.h.md`) because stock pre-22
`SectionMemoryManager` hands out separate mappings for code / rodata / rwdata
that can land too far apart to satisfy ARM64 relocation reach, producing
crashes on large-memory systems. The fork forces all sections into one
reserved region. `[from-comment]`

The class lives in namespace `llvm::backport` to avoid clashing with
upstream's `llvm::SectionMemoryManager`. C++-only — the rest of the JIT C API
reaches it through the `LLVMOrcCreateRTDyldObjectLinkingLayerWithSafeSectionMemoryManager`
shim declared in `llvmjit.h`.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `class llvm::backport::SectionMemoryManager` | `:46-221` | Derives `RTDyldMemoryManager`; non-copyable |
| `enum class AllocationPurpose { Code, ROData, RWData }` | `:50-54` | Tags for the underlying `MemoryMapper::allocateMappedMemory` |
| `class SectionMemoryManager::MemoryMapper` | `:58-109` | Pluggable allocator interface: `allocateMappedMemory`, `protectMappedMemory`, `releaseMappedMemory` |
| `SectionMemoryManager(MemoryMapper *MM = nullptr, bool ReserveAlloc = false)` | `:117` | Ctor; if `MM == nullptr` falls back to default OS mapper |
| `needsToReserveAllocationSpace()` | `:123` | Returns `ReserveAllocation` so RuntimeDyld will pre-call `reserveAllocationSpace` |
| `reserveAllocationSpace(...)` | `:128-138` | LLVM <16 takes `uint32_t` aligns, LLVM ≥16 takes `Align` — both overloads declared |
| `allocateCodeSection`, `allocateDataSection` | `:145-156` | RuntimeDyld memory grants |
| `finalizeMemory(std::string *ErrMsg = nullptr)` | `:169` | Applies page permissions; **must be called before executing JIT code** |
| `invalidateInstructionCache()` | `:178` | Called by `finalizeMemory` on icache/dcache-split targets |

## Internal landmarks

- **`MemoryGroup`** (`:191-203`) — three of these (`CodeMem`, `RWDataMem`,
  `RODataMem` at `:215-217`). Each holds `PendingMem` (handed out but not
  yet protected), `FreeMem` (reserved but not handed out), and `AllocatedMem`
  (raw system reservations). The `Near` member anchors subsequent allocations
  geographically — the ARM-reach fix.
- **`FreeMemBlock.PendingPrefixIndex`** (`:188`) — if the block immediately
  follows a pending allocation, this index lets `allocateSection` extend that
  pending region in place instead of creating a new one. Important for the
  "one reservation" guarantee on ARM.
- **`reserveAllocationSpace` is the single-allocation hook.** RuntimeDyld
  calls it once before laying down code+rodata+rwdata; the backported
  implementation reserves a single block big enough for all three with the
  worst-case alignment and slices from it. Stock LLVM <22 reserved per
  section.
- **Dual overload of `reserveAllocationSpace`** (`:128-138`) — LLVM 15 used
  `uint32_t` for alignment, LLVM 16+ moved to `llvm::Align`. The `#if
  LLVM_VERSION_MAJOR < 16` gate keeps both source compatibilities.
- **`anchor()` virtual** (`:213`) — LLVM RTTI/devirt artifact: needed so the
  vtable lands in this translation unit, not duplicated in every TU that
  instantiates the type.

## Invariants & gotchas

- **Pages start as RW**; only `finalizeMemory` applies the final permissions
  (`[from-comment]` at `:41-45`). Calling JIT code before `finalizeMemory`
  is undefined — on most platforms it traps because code pages aren't yet
  executable. The ORC layer wired in by the LLVM JIT provider takes care of
  this; direct users must not.
- **`SectionMemoryManager(const &) = delete`** (`:118-119`) — the manager
  owns large OS reservations; copying is not just inefficient, it would
  double-free.
- **`OwnedMMapper`** (`:219`) — when the caller passes `nullptr` for `MM`,
  the constructor instantiates a default mapper and stores it here so the
  unique_ptr destroys it. When the caller passes a mapper, ownership stays
  with the caller and `OwnedMMapper` stays null.
- **Drop-dead in LLVM 22.** Stock upstream `llvm::SectionMemoryManager` from
  LLVM 22 onward incorporated this fix, so once PG's minimum LLVM passes 21
  this entire file (and the .cpp implementation) must be removed. The
  matching gate in `llvmjit_backport.h` is the canonical kill switch.
- **License header retained** (`:6-12`) — Apache-2.0 with LLVM exception.
  PG ships this verbatim; modifications must preserve attribution.

## Cross-refs

- `knowledge/files/src/include/jit/llvmjit_backport.h.md` — the
  `USE_LLVM_BACKPORT_SECTION_MEMORY_MANAGER` gate.
- `knowledge/files/src/include/jit/llvmjit.h.md` — declares the C-API shim
  `LLVMOrcCreateRTDyldObjectLinkingLayerWithSafeSectionMemoryManager`.
- `source/src/backend/jit/llvm/SectionMemoryManager.cpp` — definitions for
  the methods declared here.
