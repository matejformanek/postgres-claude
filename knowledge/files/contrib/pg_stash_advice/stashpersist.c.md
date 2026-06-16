# `contrib/pg_stash_advice/stashpersist.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 807
- **Source:** `source/contrib/pg_stash_advice/stashpersist.c`

The persistence background worker for `pg_stash_advice`. Contains
`pg_stash_advice_worker_main` (the bgworker entry point), the TSV
serializer (`pgsa_write_to_disk` + helpers), the TSV parser
(`pgsa_read_from_disk` + helpers), the slurp-buffer in-place
parsing strategy, and the on-disk file-format design. [verified-by-code]

## What the worker does

- On startup: claim `bgworker_pid` slot, install `pgsa_detach_shmem`
  on-exit hook, then if `stashes_ready` is unset, call
  `pgsa_read_from_disk` which parses the entire `pg_stash_advice.tsv`
  in private memory and only applies to shmem on success. Set
  `stashes_ready` to release the lockout. [verified-by-code]
- Then loop on `WaitLatch` with timeout `pg_stash_advice.persist_interval`.
  At each tick, if `change_count` differs from the previously-seen
  count, write a fresh dump file. [verified-by-code]
- On `SIGTERM`/shutdown request: do one final write before exiting. [verified-by-code]

## File format

```
stash\t<stash_name>
entry\t<stash_name>\t<query_id_int64>\t<advice_string_tsv_escaped>
```

Stash lines must precede their entry lines; parser enforces "entry
references unknown stash". TSV escapes: `\\`, `\t`, `\n`, `\r`. Any
other backslash sequence is a syntax error. CRLF line endings are
auto-stripped (`:345-346`). [verified-by-code]

## API / entry points

- `pg_stash_advice_worker_main(Datum)` `:93-215` — `PGDLLEXPORT`,
  the bgworker entry. Installs standard signal handlers, claims the
  bgworker slot, optionally reads from disk, then loops.
  [verified-by-code]
- `pgsa_detach_shmem(int code, Datum arg)` `:220-227` — `before_shmem_exit`
  callback that clears `bgworker_pid` if it matches `MyProcPid`.
  [verified-by-code]
- `pgsa_read_from_disk()` `:232-495` — slurp-and-parse with two-pass
  validation. Allocates a private `MemoryContext` ("pg_stash_advice
  load"), `palloc_extended(... MCXT_ALLOC_HUGE)`s the entire file,
  parses in-place by replacing tabs/newlines with NULs and growing a
  `pgsa_saved_entry` array. Applies stashes first, then entries.
  [verified-by-code]
- `pgsa_write_to_disk()` `:504-570` — writes to
  `pg_stash_advice.tsv.tmp`, then `durable_rename` into place.
  Special case: if zero stashes exist, deletes both tmp and final
  files rather than installing a zero-length file. [verified-by-code]
- `pgsa_append_tsv_escaped_string(StringInfo, const char *)`
  `:578-602` — backslash-escapes one of `\ \t \n \r` and passes
  everything else through verbatim. [verified-by-code]
- `pgsa_next_tsv_field(char **cursor)` `:610-627` — destructive tab
  tokeniser; replaces the next `\t` with `\0` and advances cursor.
  Returns NULL at end-of-line. [verified-by-code]
- `pgsa_restore_entries`, `pgsa_restore_stashes` `:632-667` — apply
  parsed structures to shared memory. Take SHARED resp EXCLUSIVE
  lock on `pgsa_state->lock`. [verified-by-code]
- `pgsa_unescape_tsv_field(char *, const char *, unsigned)` `:675-723` —
  in-place unescape. Trailing backslash or unknown escape →
  `ERRCODE_DATA_CORRUPTED`. [verified-by-code]
- `pgsa_write_entries`, `pgsa_write_stashes` `:728-807` — iterate
  the two dshashes and write file lines. `pgsa_write_stashes` also
  populates `wctx->nhash` so `pgsa_write_entries` can resolve
  `stash_id → name` cheaply. [verified-by-code]
- `pgsa_write_error(wctx)` `:766-777` — `pg_noreturn`. Cleans up the
  tmp file and ereport(ERROR)s with `%m`. [verified-by-code]

## Notable invariants / details

- **INV-1: At most one bgworker is alive at a time.** Worker entry
  checks `pgsa_state->bgworker_pid != InvalidPid` under EXCLUSIVE
  lock and exits silently if so (`:127-135`). Defends against double-
  starts via `pg_start_stash_advice_worker`. [from-comment]
- **INV-2: File parsing happens entirely in private memory; shmem is
  only mutated after validation succeeds.** Comment block `:286-322`
  spells out the rationale: a half-applied corrupted file would leave
  garbage in shmem, so we accept the 2x memory cost.
  [from-comment]
- **INV-3: Before re-applying from disk, `pgsa_reset_all_stashes` is
  called.** Even though the lockout should keep shmem empty, a
  previous worker may have died mid-apply (`:251-261`). So the
  reset is defense-in-depth. [from-comment]
- **INV-4: `pgsa_set_advice_string` is called under SHARED lock
  during restore.** Justified by the comment in `pg_stash_advice.c:656-671`
  — SHARED is enough because no one else can drop stashes during
  restore (lockout is active). [verified-by-code] `:635, 645`
- **INV-5: Empty dump → unlink, not zero-length write.** Otherwise
  a corrupted "no stashes" dump would be indistinguishable from
  "stashes were saved but somehow empty". [from-comment + verified-by-code]
  `:537-546`
- **INV-6: `stashes_ready` is set ONLY after `pgsa_read_from_disk`
  returns without erroring.** If it throws, the worker dies, postmaster
  restarts it (default restart interval), and we retry from the top.
  In the meantime, the lockout remains active. [from-comment]
- **INV-7: TSV escape vocabulary is fixed.** Only `\\ \t \n \r` are
  recognised. Notably, NUL bytes in advice strings are not handled
  — but advice strings are C strings already in shmem so they can't
  contain NUL anyway. [verified-by-code]
- **INV-8: `last_write_time` is recorded EVERY time we reach
  `next_write_time`, but `pgsa_write_to_disk` is called only if
  `change_count` actually changed** (`:189-200`). This avoids
  rewriting an unchanged file on every tick. [from-comment]

## Potential issues

- `:264-272` `AllocateFile(PGSA_DUMP_FILE, "r")` opens relative to
  cwd which is the data directory — not the cluster's `global/` or
  a subdir. A user with multiple clusters using
  shared_preload_libraries=`pg_stash_advice` is fine (each cluster has
  its own PGDATA), but if a future "multiple save files" feature is
  added (hinted at in comment `:297-299`), the bare filename will
  need rethinking. [from-comment] **[ISSUE-style: hardcoded basename
  blocks multi-file expansion (nit)]**
- `:311` `palloc_extended(statbuf.st_size + 1, MCXT_ALLOC_HUGE)`
  with a malicious dump file the size of available RAM (under user's
  control, since user-supplied advice strings get serialised) could
  DoS the bgworker by exhausting backend memory. Comment dismisses
  this with "if there's so much stashed advice that parsing runs us
  out of memory, something has gone terribly wrong" — true, but the
  worker dies and restarts in a loop. [from-comment]
  **[ISSUE-security: oversized dump file DoSes the bgworker (maybe)]**
- `:441-444` Query ID parse: `strtoi64`, with extra checks for
  trailing garbage and `queryId == 0`. Treating 0 as a syntax error is
  intentional but ugly — relies on the invariant that no live entry
  ever has queryId 0 (set in `pg_set_stashed_advice` at
  `stashfuncs.c:292-295`). [verified-by-code]
  **[ISSUE-undocumented-invariant: queryId == 0 sentinel cross-file (nit)]**
- `:745-746` "orphan entry, skip" silently drops entries whose
  stash_id isn't in `wctx->nhash`. Since `pgsa_write_stashes` ran
  first and populated `nhash` from the same dshash atomically (in the
  sense of the dshash iteration semantics), an orphan should be
  impossible — but if it happens (e.g. a future race), the entry is
  silently lost. [verified-by-code] **[ISSUE-correctness: silent
  drop of orphan entries during write (maybe)]**
- `:166-169` Infinite wait branch when `persist_interval <= 0`
  consumes 0 CPU but means the only writes happen at shutdown.
  Setting `persist_interval = 0` is therefore "save only at clean
  shutdown" — a SIGKILL of the postmaster loses all updates.
  Documented? Not in this file. [inferred] **[ISSUE-doc-drift:
  `persist_interval = 0` semantics not surfaced (nit)]**
- `:769-772` `pgsa_write_error` saves errno around `FreeFile`/`unlink`
  — correct. But if `FreeFile` itself sets errno to a "more
  interesting" value (e.g. EIO on flush), we lose the original write
  error. Probably fine. [inferred]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_stash_advice`](../../../issues/pg_stash_advice.md)
<!-- issues:auto:end -->
