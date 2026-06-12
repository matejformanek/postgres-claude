# Issues — `jit`

Per-subsystem issue register. See `knowledge/issues/README.md` for the
tag convention, severity scale, and workflow.

**Parent subsystem doc:** `knowledge/subsystems/jit.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-12 | src/backend/jit/llvm/llvmjit.c:259-270 | undocumented-invariant | maybe | `llvm_release_context` decrements `llvm_jit_context_in_use_count` BEFORE the `proc_exit_inprogress` early return; correct today but a re-order would silently regress the PANIC at shutdown. Worth a header comment. | open | knowledge/files/src/backend/jit/llvm/llvmjit.c.md §Potential issues |
| 2026-06-12 | src/backend/jit/llvm/llvmjit_expr.c:1-13 | doc-drift | nit | Header comment does not mention the 121 `EEOP_*` cases or how they stay synced with `execExpr.c`. Future patch authors who add an opcode interpreter-side may forget the JIT case. | open | knowledge/files/src/backend/jit/llvm/llvmjit_expr.c.md §Potential issues |
| 2026-06-12 | src/backend/jit/llvm/llvmjit_deform.c:33-130 | undocumented-invariant | likely | `slot_compile_deform` callers must pass `natts <= desc->natts`; there is no defensive `Assert`. The per-column-block arrays are sized `natts` independently of `desc->natts`. | open | knowledge/files/src/backend/jit/llvm/llvmjit_deform.c.md §Potential issues |
| 2026-06-12 | src/backend/jit/llvm/llvmjit_deform.c:1-17 | doc-drift | maybe | Header comment does not call out the sign-extend-vs-zero-extend subtlety fixed in 6911f80379d. A half-sentence would prevent recurrence of the regression. | open | knowledge/files/src/backend/jit/llvm/llvmjit_deform.c.md §Potential issues |
| 2026-06-12 | src/backend/jit/llvm/llvmjit_types.c:137-185 | undocumented-invariant | nit | The contract is "every `ExecEval*` helper that may be called from JITed code MUST appear in `referenced_functions[]`." There is no compile-time check; the only catch is a runtime `elog(ERROR)` in `llvm_pg_func`. A reminder comment near `execExpr.c`'s ExecEval helpers would help. | open | knowledge/files/src/backend/jit/llvm/llvmjit_types.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

All five issues found in this sweep are documentation / invariant clarity nits, not behavioural bugs. The single recent real bug in this subsystem (`6911f80379d` — narrow-Datum sign-extension in JIT deform) is already fixed upstream and is referenced from the deform doc as a worked example of the "JIT deformer must produce bit-identical Datums to the interpreter" contract.
