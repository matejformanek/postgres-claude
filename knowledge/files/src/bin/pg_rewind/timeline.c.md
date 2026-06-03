# timeline.c

## Purpose

A frontend copy of the backend's `readTimeLineHistory` (`src/backend/access/transam/timeline.c`),
adapted to take an already-slurped `char *buffer` (so callers can use `slurpFile`)
and return a `pg_malloc`'d array of `TimeLineHistoryEntry`.

## Role in pg_rewind

Called from `pg_rewind.c` to parse the `.history` files of both source
and target timelines. The resulting arrays are compared to find the
divergence point — the LSN at which target and source last shared a
common WAL position. The target's history array is also exposed as
`targetHistory[]` to `parsexlog.c::SimpleXLogPageRead` so it can
choose which timeline's WAL files to read.

## Key functions

- `rewind_parseTimeLineHistory(buffer, targetTLI, *nentries)`
  (`source/src/bin/pg_rewind/timeline.c:27-129`). Tokenises the buffer
  line by line (in place — writes `'\0'` over each newline at `:58`),
  skips blank lines and `#` comments, `sscanf`s `"%u\t%X/%08X"` for
  `(tli, switchpoint_hi, switchpoint_lo)`. Each row produces one
  `TimeLineHistoryEntry { tli, begin=prev_end, end=switchpoint }`.
  Validates that TLI is strictly increasing (`:84-89`) and that
  the target TLI is greater than the last historical TLI (`:105-110`).
  Appends a final "tip" entry for `targetTLI` itself with
  `end = InvalidXLogRecPtr`.

## State / globals

None. Pure function over the input buffer.

## Phase D notes

### Path safety

`timeline.c` itself doesn't touch the filesystem. Its caller
(`pg_rewind.c`) reads the `.history` file via `slurpFile`, which uses
`<datadir>/<path>` concatenation. The history filename is constructed
from a TLI (`XX.history` for some `XX`) — not from operator input, so
no path-traversal vector here.

### Buffer trust

The buffer is whatever bytes were in `pg_wal/XXXX.history`. The
operator owns that file, so this is not an external trust boundary.
That said:

- **In-place null-termination** (`:58`) mutates the caller's buffer.
  `slurpFile` returns a `pg_malloc`'d buffer that the caller never
  reuses, so this is fine — but anyone refactoring to share buffers
  would be surprised.
- **No line-length cap.** `sscanf` of `%u\t%X/%08X` stops at the
  first non-matching char, so a line of arbitrary length doesn't
  overrun anything. A line with no `\n` and no parse-able prefix
  triggers the "syntax error" branch and exits.
- **Comments must start at column 0 after optional whitespace**
  (`:60-67`). A `#` mid-line is ignored — but `sscanf` will still
  match the leading numeric fields. Behaviour matches the backend
  copy.
- **`pg_realloc_array` per line** (`:94`) is O(n²) for an n-line
  history. Histories are at most a few thousand lines in practice,
  so fine, but pathological.

### Drift from backend

The header comment says "copy-pasted from the backend readTimeLineHistory,
modified to return a malloc'd array and to work without backend functions".
Any future change to the backend parser (e.g. accepting a new field) would
silently drift from this copy.

## Potential issues

- `[ISSUE-dos: pg_realloc_array per parsed line is O(n²) in line
  count (low)]` (`:94`). Practical histories are tiny so this
  doesn't matter, but it's an unstated assumption.
- `[ISSUE-correctness: timeline.c is a hand-maintained copy of the
  backend's readTimeLineHistory and can silently drift (maybe)]`
  (`:17-18`). Comment explicitly flags this. No mechanism prevents
  the two from diverging.
- `[ISSUE-correctness: line termination handling drops the final
  line silently if it has no newline AND no parseable content (low)]`
  (`:53-58`). `lastline = true` is set and the empty line is then
  skipped by the comment-skip loop. Probably intentional but
  undocumented.
- `[ISSUE-undocumented-invariant: in-place mutation of caller's
  buffer at :58 (low)]`. Caller must not reuse the buffer expecting
  its original newlines.
