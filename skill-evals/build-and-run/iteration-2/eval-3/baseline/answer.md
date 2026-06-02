# Eval 3 — baseline (no skill)

PostgreSQL uses a forking model — every client connection gets its own
backend process forked from the postmaster. If you attach to the postmaster
itself, your breakpoints won't hit because the postmaster only does process
management; it doesn't run queries or most of the backend logic.

The usual pattern:

1. Connect with `psql` and get the backend PID:

   ```sql
   SELECT pg_backend_pid();
   ```

2. Attach lldb (macOS) to *that* PID in another terminal:

   ```bash
   lldb -p <pid>
   ```

3. Set breakpoints and continue.

For code that runs early in backend startup (before you can attach), some
options:

- Add a `sleep()` or `pg_usleep()` early in the path you want to catch,
  rebuild, then attach within the window.
- Set the `PostAuthDelay` GUC to delay backend startup.
- Use `gdb`/`lldb`'s `follow-fork-mode child` to follow forked children
  automatically.

Make sure you compiled with debug symbols (`-O0 -g`, or for autoconf
`--enable-debug --enable-cassert`).

On macOS lldb is the path of least resistance — gdb requires codesigning.
