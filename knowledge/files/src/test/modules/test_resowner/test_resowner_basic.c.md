---
path: src/test/modules/test_resowner/test_resowner_basic.c
anchor_sha: e18b0cb7344
loc: 209
depth: read
---

# src/test/modules/test_resowner/test_resowner_basic.c

## Purpose

Smoke-tests the `ResourceOwner` API. Verifies the parent/child release
ordering (children released before parents within a phase, priorities respected),
exercises the leak-detection path (`isCommit=true` in `ResourceOwnerRelease`
triggers the `DebugPrint` callback), and confirms that
`ResourceOwnerRemember` / `ResourceOwnerForget` correctly error out when
called between release phases. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_resowner_priorities` | `test_resowner_basic.c:48` | Builds a parent+child pair with `nkinds * 2` priority bands across two phases |
| `test_resowner_leak` | `:138` | Remembers a string but never forgets it — triggers `DebugPrint` warning |
| `test_resowner_remember_between_phases` | `:161` | Confirms `ResourceOwnerEnlarge` errors after the first phase has been released |
| `test_resowner_forget_between_phases` | `:184` | Same for `ResourceOwnerForget` |
| `ReleaseString` / `PrintString` (static) | `:35`, `:41` | Test callbacks that NOTICE the released string |

## Internal landmarks

- `string_desc` (`:27`) is a const `ResourceOwnerDesc` reused by the leak +
  between-phases tests; it lives in `RESOURCE_RELEASE_AFTER_LOCKS` with
  `RELEASE_PRIO_FIRST`.
- `test_resowner_leak` passes `isCommit=true` in every phase release
  (`:152-154`), which is the trigger for `DebugPrint` to fire (and the
  leak-detection WARNING to be emitted).

## Invariants & gotchas

- **Test module — never load in production.**
- The two "_between_phases" tests are designed to ereport(ERROR) — the
  trailing `elog(ERROR, "... should have errored out")` (`:179`, `:206`)
  is the "unreachable" guard.
- `CStringGetDatum(psprintf(...))` builds the per-resource string in
  `CurrentMemoryContext`; the release callback only NOTICEs it, doesn't free.

## Cross-refs

- `source/src/backend/utils/resowner/resowner.c` — implementation under test.
- `knowledge/files/src/test/modules/test_resowner/test_resowner_many.c.md`
  — sibling.
