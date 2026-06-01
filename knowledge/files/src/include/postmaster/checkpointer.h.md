# checkpointer.h

- **Source:** `source/src/include/postmaster/bgwriter.h` (historically — there
  may not be a separate `checkpointer.h`; checkpointer prototypes live in
  `bgwriter.h` and `access/xlog.h`).
- **Depth:** skim

## Symbols typically pulled from here / xlog.h

- `CheckpointerMain` (the `B_CHECKPOINTER` `main_fn`).
- `RequestCheckpoint(flags)` — backend-side request.
- `CheckpointWriteDelay` — internal pacing helper.
- `ForwardSyncRequest`, `AbsorbSyncRequests`,
  `CompactCheckpointerRequestQueue` — fsync-forwarding API.
- `CheckpointerShmemSize`, `CheckpointerShmemInit`.

The split between `checkpointer.h` / `bgwriter.h` / `xlog.h` is historical;
new code should follow whatever the current include lines show. The
checkpointer's source file (`postmaster/checkpointer.c`) lists the exact
includes.
