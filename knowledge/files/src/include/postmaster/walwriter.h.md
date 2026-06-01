# walwriter.h

- **Source:** `source/src/include/postmaster/walwriter.h`
- **Depth:** skim

Declares `WalWriterMain` and the `wal_writer_delay` / `wal_writer_flush_after`
GUC globals. Consumed by `postmaster.c`, `launch_backend.c`, and the
walwriter itself.
