# `src/include/port/pg_iovec.h`

## Role

Scatter-gather I/O abstraction over `preadv(2)`/`pwritev(2)` with a
Windows shim. Provides:

- `struct iovec` (typedef on POSIX, defined here on Windows).
- `IOV_MAX` (minimum 16 per X/Open) and `PG_IOV_MAX` (clamped to 128).
- `pg_preadv(fd, iov, iovcnt, offset)` and `pg_pwritev` static-inline
  wrappers.

Used heavily by the storage layer (`md.c` `mdreadv`, `mdwritev`) and by
storage-AIO (`smgrreadv`, `smgrwritev`) for vectored reads/writes that
gather multiple buffer-manager pages into one syscall
`[verified-by-code]` `source/src/include/port/pg_iovec.h:1-12`.

## Public API

`[verified-by-code]` `source/src/include/port/pg_iovec.h:25-125`:

- `struct iovec { void *iov_base; size_t iov_len; }` — Windows local
  definition; on POSIX, the system's `<sys/uio.h>` provides it.
- `IOV_MAX` — fallback to 16 if system doesn't define it.
- `PG_IOV_MAX` = `Min(IOV_MAX, 128)`.
- `ssize_t pg_preadv(fd, iov, iovcnt, offset)`.
- `ssize_t pg_pwritev(fd, iov, iovcnt, offset)`.

Both wrappers are `static inline`. On platforms with native preadv/
pwritev (`HAVE_DECL_PREADV` / `HAVE_DECL_PWRITEV`), they:

- For `iovcnt == 1`, call `pread`/`pwrite` directly — avoiding "a
  small amount of argument copying overhead in the kernel"
  `[from-comment]` `source/src/include/port/pg_iovec.h:55-63`.
- Otherwise call the native syscall.

On platforms without (notably older macOS, Solaris), they implement a
loop calling `pg_pread`/`pg_pwrite` per iovec, accumulating returned
bytes, and short-circuiting on partial returns
`[verified-by-code]` `source/src/include/port/pg_iovec.h:66-86`.

## Invariants

1. **Side-effect on Windows: file position changes.** Both `pg_preadv`
   and `pg_pwritev` carry a `pg` prefix specifically to flag this
   `[from-comment]` `source/src/include/port/pg_iovec.h:49-52,89-91`.
   Reading from a backend that shares an fd with another thread (rare
   but possible via `dup`) on Windows would see a moved cursor.
2. **`PG_IOV_MAX = Min(IOV_MAX, 128)`.** The 128 is "a reasonable
   maximum that is safe to use on the stack in arrays of struct iovec"
   `[from-comment]` `source/src/include/port/pg_iovec.h:43-46`.
   Stack-allocated `iovec[PG_IOV_MAX]` is ~2 KiB on 64-bit (16 bytes
   per iovec). Used as a hard cap.
3. **Default `IOV_MAX = 16`.** Set if `<limits.h>` didn't define it,
   notably on GNU Hurd `[from-comment]`
   `source/src/include/port/pg_iovec.h:33-37`.
4. **Partial-read short-circuit.** In the fallback loop, on
   `pg_pread(...) < (size_t) iov[i].iov_len`, the function returns
   `sum` immediately without trying further iovecs
   `[verified-by-code]` `source/src/include/port/pg_iovec.h:81-83`.
   Mimics the kernel's preadv semantics (short read).
5. **First-iovec error returns -1, subsequent errors return partial
   sum.** `i == 0 → return -1`; `i > 0 → return sum` so the caller
   sees the bytes that did succeed `[verified-by-code]`
   `source/src/include/port/pg_iovec.h:72-78`.

## Notable internals

The `iovcnt == 1` fast path is a real optimization — on macOS pre-11
and on older Linux kernels, the `preadv` syscall does an extra round
of iovec copy-in even for a single element. The wrapper bypasses that.

On Windows the typedef of `struct iovec` is local and the preadv/
pwritev fallback paths above are never used because the `#ifndef
WIN32` guard at line 16 keeps the whole syscall-aware section out;
the Windows port likely implements scatter-gather via `ReadFileScatter`
elsewhere `[inferred]` (this header doesn't define `pg_preadv` on
Windows).

Wait — checking line 16: `#ifndef WIN32 / #include <sys/uio.h> /
#else / struct iovec {...} / #endif`. The struct iovec define is
**inside** the `#else` (Win32). Then the rest of the file (IOV_MAX,
PG_IOV_MAX, pg_preadv, pg_pwritev) is **outside** the conditional, so
Windows DOES get the pg_preadv inline. But Windows doesn't define
`HAVE_DECL_PREADV` (no preadv on Windows), so the loop fallback runs,
calling `pg_pread`/`pg_pwrite` — which are themselves emulated in
`src/port/pread.c`/`pwrite.c`. The "changes file position" warning is
exactly about the emulated `pg_pread` on Windows using
`SetFilePointer`-style logic. `[inferred from header-only reading;
verify with src/port/pread.c]`

## Trust-boundary / Phase D surface

- **The partial-read-loops-don't-retry contract.** This is correct
  POSIX behavior but easy to misuse from the caller side. Callers in
  smgr handle short reads by retrying or padding with zeros (page-
  aligned reads in PG should never short-read except at EOF). Any new
  caller of `pg_preadv` outside the relfile path must understand the
  semantics. **Phase-D-review-pattern:** new `pg_preadv` callers
  outside `smgr/`/`xlog/` need scrutiny.
- **`PG_IOV_MAX = 128` is a stack-size assumption** that can be wrong
  on platforms with smaller default stacks. PG sets
  `max_stack_depth=2MB` by default; 128 iovecs is 2KB so no risk in
  practice. But if a future patch raises `PG_IOV_MAX` to e.g. 1024,
  callers stack-allocating `iovec[PG_IOV_MAX]` for it would suddenly
  bump.
- **Windows file-position side-effect** is the only truly portable
  trust boundary. Any caller that shares an fd between threads on
  Windows must serialize the call.
- **The `iovcnt == 1` short-circuit silently changes the syscall
  observed.** A strace/dtrace user looking for `preadv` calls won't
  see them when `iovcnt == 1`; they'll see `pread`. Documented gotcha
  for performance investigation.
- **A14 storage-AIO interaction.** When AIO routes I/O through
  `io_method=worker` (synchronous worker pool), the worker invokes
  this wrapper. When `io_method=io_uring`, this header is bypassed —
  io_uring submits its own `IORING_OP_READV`/`WRITEV`. Document this
  asymmetry: the wrapper isn't on the AIO hot path with io_uring.

## Cross-refs

- `source/src/backend/storage/smgr/md.c` (`mdreadv`, `mdwritev`) —
  primary callers.
- `source/src/backend/storage/aio/method_worker.c` — AIO worker path.
- `source/src/include/storage/aio.h` — A14 storage-aio surface.
- `source/src/port/pread.c`, `source/src/port/pwrite.c` — emulated
  fallbacks for platforms without preadv/pwritev.

## Issues / unresolved

- **ISSUE-doc**: the side-effect warning is only on the two wrappers;
  the struct `iovec`/`IOV_MAX` constants don't mention that on
  Windows the whole feature is emulated. (severity: low)
- **ISSUE-portability**: `PG_IOV_MAX = 128` is a magic number; the
  rationale (stack-safe) is in a comment but the actual upper bound
  isn't tied to a documented stack-size assumption. (severity: low)
- **ISSUE-observability**: `iovcnt == 1` becoming `pread`/`pwrite`
  syscall changes what tracing tools see; not documented at call
  sites. (severity: low, doc-only)
