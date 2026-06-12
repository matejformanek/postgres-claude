---
path: src/interfaces/ecpg/ecpglib/memory.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 176
depth: deep
---

# `memory.c` — ecpglib allocation wrappers + per-thread auto-freed memory list

## Purpose
Provides ecpglib's thin allocation wrappers (`ecpg_alloc`, `ecpg_realloc`,
`ecpg_strdup`, `ecpg_free`) over libc `calloc`/`realloc`/`strdup`/`free`, and a
per-thread list of "auto-allocated" memory that ecpglib hands to the user (e.g.
buffers produced while fetching result data). The auto-mem list is keyed to a
pthread TLS slot so that each thread's user-handed allocations are tracked
independently and reclaimed at the next statement boundary (`ECPGfree_auto_mem`)
or at thread exit (TLS destructor). [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `void ecpg_free(void *ptr)` | memory.c:13 | bare `free()` wrapper [verified-by-code] |
| `char *ecpg_alloc(long size, int lineno)` | memory.c:19 | `calloc(1, size)`; on failure raises `ECPG_OUT_OF_MEMORY` then returns NULL [verified-by-code] |
| `char *ecpg_realloc(void *ptr, long size, int lineno)` | memory.c:33 | `realloc`; on failure raises then returns NULL [verified-by-code] |
| `char *ecpg_strdup(const char *string, int lineno, bool *alloc_failed)` | memory.c:54 | NULL input returns NULL (not an error); optional `alloc_failed` out-param set true on OOM; also raises [verified-by-code] |
| `char *ecpg_auto_alloc(long size, int lineno)` | memory.c:110 | alloc + register on auto-mem list; frees and returns NULL if registration fails [verified-by-code] |
| `bool ecpg_add_mem(void *ptr, int lineno)` | memory.c:126 | prepend `ptr` to the thread's auto-mem list; false on OOM [verified-by-code] |
| `void ECPGfree_auto_mem(void)` | memory.c:140 | free every user pointer AND its list node, reset slot to NULL [verified-by-code] |
| `void ecpg_clear_auto_mem(void)` | memory.c:160 | free only the list nodes, NOT the user pointers; reset slot [verified-by-code] |

## Internal landmarks
- `struct auto_mem` (memory.c:74): singly-linked `{pointer, next}` node.
- `auto_mem_key` / `auto_mem_once` (memory.c:80-81): pthread TLS key, lazily
  created once via `pthread_once`. [verified-by-code]
- `auto_mem_destructor` (memory.c:84): TLS destructor; calls `ECPGfree_auto_mem`
  so a thread's auto-allocated user memory is reclaimed at thread exit. [verified-by-code]
- `get_auto_allocs` / `set_auto_allocs` (memory.c:97, 104): TLS getter/setter;
  `get_auto_allocs` triggers the one-time key init. [verified-by-code]

## Invariants & gotchas
- OOM policy: `ecpg_alloc`/`ecpg_realloc` BOTH raise via `ecpg_raise(...,
  ECPG_OUT_OF_MEMORY, ...)` AND return NULL (memory.c:25-26, 39-40). Callers must
  still NULL-check; the raise records into sqlca rather than longjmp'ing. [verified-by-code]
- `ecpg_strdup(NULL, ...)` is a deliberate success path returning NULL — not an
  OOM (memory.c:58-59). The `alloc_failed` out-param is caller-initialized and
  may accumulate across multiple calls per the header comment (memory.c:49-51). [verified-by-code]
- Two distinct teardown semantics: `ECPGfree_auto_mem` frees the user payloads
  too (memory.c:152), whereas `ecpg_clear_auto_mem` frees only the bookkeeping
  nodes and leaves user pointers live (memory.c:172). Confusing the two
  double-frees or leaks. [verified-by-code]
- The auto-mem list is per-thread (TLS). A pointer added on one thread is not
  visible to `ECPGfree_auto_mem` on another. [inferred]

## Cross-refs
- [[ecpglib_extern.h]] — prototypes for all the above; `ecpg_raise`,
  `ECPG_SQLSTATE_ECPG_OUT_OF_MEMORY`.
- [[execute.c]] — primary consumer of `ecpg_auto_alloc` / `ecpg_alloc` for
  result buffers.
- [[data.c]] — `ecpg_get_data` auto-allocates user output buffers via this list. [inferred]
