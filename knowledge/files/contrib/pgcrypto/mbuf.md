# mbuf.c / mbuf.h

## One-line summary

Internal byte-buffer (`MBuf`) and streaming push/pull filter
abstractions (`PushFilter`, `PullFilter`) used by pgcrypto's PGP
machinery (`pgp-encrypt.c`, `pgp-decrypt.c`, `pgp-armor.c`,
`pgp-compress.c`, `pgp-cfb.c`). Not used by the core PX
encrypt/decrypt path — those work on flat bytea buffers via the
PX_Combo combo_encrypt/decrypt API.

Covers `source/contrib/pgcrypto/mbuf.c` (547 lines) and
`source/contrib/pgcrypto/mbuf.h` (122 lines).

## Public API / entry points

### `MBuf` — growable byte buffer

- `MBuf *mbuf_create(int len)` — `mbuf.c:110-128`. Default 8192
  if `len == 0`. Marks `own_data = true`.
- `MBuf *mbuf_create_from_data(uint8 *data, int len)` —
  `mbuf.c:130-145`. Read-only view over caller-provided memory.
  Marks `no_write = true`, `own_data = false`.
- `int mbuf_avail(MBuf *)` — bytes available to read.
- `int mbuf_size(MBuf *)` — total bytes in buffer.
- `int mbuf_grab(MBuf *, int len, uint8 **data_p)` — `mbuf.c:148-159`.
  Hand out a pointer into the buffer (zero-copy), advance read_pos,
  mark `no_write = true` (subsequent appends become an error).
- `int mbuf_steal_data(MBuf *, uint8 **data_p)` — `mbuf.c:161-174`.
  Caller takes ownership of the underlying allocation; MBuf is
  reset.
- `int mbuf_append(MBuf *dst, const uint8 *buf, int len)` —
  `mbuf.c:93-108`. Calls `prepare_room` (which `repalloc`s in
  16KB-step chunks); returns `PXE_BUG` if `no_write`.
- `int mbuf_free(MBuf *)` — `mbuf.c:61-71`. Scrubs owned data with
  `px_memset(0)` before pfree, then pfree's the MBuf.

### `PullFilter` — streaming read with filter stack

- `pullf_create(PullFilter **, const PullFilterOps *, void *init_arg,
  PullFilter *src)` — `mbuf.c:190-226`. Init callback may return a
  buffer-size hint; pullf allocates that much working space.
- `pullf_read(PullFilter *, int len, uint8 **data_p)` —
  `mbuf.c:245-260`. May return less than asked, 0 = EOF.
- `pullf_read_max(PullFilter *, int len, uint8 **data_p, uint8 *tmpbuf)`
  — `mbuf.c:262-295`. Reads until len bytes accumulated, copying
  into tmpbuf if needed.
- `pullf_read_fixed(PullFilter *src, int len, uint8 *dst)` —
  `mbuf.c:300-317`. Caller wants exactly `len` bytes; short read →
  `PXE_PGP_CORRUPT_DATA`.
- `pullf_free(PullFilter *)` — `mbuf.c:228-242`. Scrubs working
  buffer.
- `pullf_create_mbuf_reader(PullFilter **, MBuf *src)` —
  `mbuf.c:335-339`.

### `PushFilter` — streaming write with filter stack

- `pushf_create(PushFilter **, const PushFilterOps *, void *init_arg,
  PushFilter *next)` — `mbuf.c:356-392`.
- `pushf_write(PushFilter *, const uint8 *, int len)` —
  `mbuf.c:438-496`. Buffers up to `block_size`, flushes when full,
  pushes complete blocks straight through.
- `pushf_flush(PushFilter *)` — `mbuf.c:498-522`. Recursive flush
  down the chain.
- `pushf_free` / `pushf_free_all` — `mbuf.c:394-421`. Scrub +
  pfree.
- `pushf_create_mbuf_writer(PushFilter **, MBuf *dst)` —
  `mbuf.c:543-547`.

### Convenience macro

- `GETBYTE(pf, dst)` — `mbuf.h:113-120`. Read one byte via
  `pullf_read_fixed`; auto-returns the error code on failure.

## Key invariants

- **`no_write` is a one-way latch**. Once `mbuf_grab` or
  `mbuf_steal_data` is called, the buffer cannot be appended to
  again. Subsequent `mbuf_append` returns `PXE_BUG`
  (`mbuf.c:96-100`).
- **`own_data` distinguishes owned heap memory from a borrowed
  pointer**. `mbuf_create` owns; `mbuf_create_from_data` does not.
  `mbuf_free` only scrubs/pfree's if `own_data` is true. `mbuf_steal_data`
  transfers ownership out (sets own_data=false on the MBuf, returns
  the buffer to the caller).
- **`prepare_room` rounds up to 16KB STEP** (`mbuf.c:73-91`).
  Reduces realloc churn for streaming use.
- **Filter chains form a singly-linked list via `next`** for push,
  `src` for pull. `pushf_free_all` walks the chain; pull filters are
  freed one at a time by the caller.
- **All filter wrappers scrub their working buffer on free** —
  `pushf_free` at `mbuf.c:400-404`, `pullf_free` at `:234-238`.
  Uses `px_memset`.
- **The MBuf data itself is scrubbed on `mbuf_free`** — `mbuf.c:66`.

## Notable internals

### Filter ops semantics

`PullFilterOps` / `PushFilterOps` are defined in `mbuf.h:41-74`.
The `init` callback returns:
- `> 0`: needs N bytes of working buffer; pullf/pushf allocates it.
- `0`: no buffering, priv = init_arg.
- `< 0`: error code; init fails.

The `push` callback for push filters must consume ALL input (or
return error). It returns 0 on success, < 0 on error.
`wrap_process` at `mbuf.c:423-435` enforces: if `push` returns > 0,
that's a `PXE_BUG`.

The `pull` callback for pull filters returns the number of bytes
delivered (may be less than asked, 0 = EOF, < 0 = error). It may
return a zero-copy pointer (`*data_p` points into upstream buffer)
OR a copy into the caller-provided `buf`.

### MBuf-backed reader/writer

`pull_from_mbuf` (`mbuf.c:322-329`) and `push_into_mbuf`
(`mbuf.c:528-537`) are the trivial adapters that bridge MBuf
storage to the filter pipeline.

### Memory zeroing on free

This is the consistent pattern: every free path scrubs.
- `mbuf_free` → `px_memset(mbuf->data, 0, buf_end - data)` at
  `mbuf.c:66`.
- `pullf_free` → scrubs `pf->buf` and the PullFilter struct itself
  (`mbuf.c:234-241`).
- `pushf_free` → scrubs `mp->buf` and the PushFilter struct itself
  (`mbuf.c:400-407`).

This is consistent with the PGP-data threat model: encrypted
plaintext flows through MBuf, and on cleanup the bytes are zeroed.
**Subject to the same `px_memset` LTO-elision caveat from `px.md`.**
[ISSUE-security: px_memset elision risk applies (likely)]

## Crypto trust boundary / Phase D surface

- **Plaintext flows through `MBuf`**: in `pgp-decrypt.c`, the decrypted
  message body accumulates in an MBuf until returned to the caller.
  Scrub-on-free is the only mitigation; `px_memset` LTO-elision risk
  is the bound. [ISSUE-security: ptxt-bearing MBuf scrubbed only via
  px_memset (likely)]
- **`mbuf_steal_data` transfers ownership without scrubbing** —
  `mbuf.c:161-174`. Caller is responsible for the memory's lifetime.
  Used to hand decrypted bytea back to the SQL caller. The bytea
  detoasting path then pfree's it; the bytes are not scrubbed.
- **`mbuf_grab` hands out a pointer into the internal buffer**.
  After the grab, `no_write` is set, but the bytes remain readable
  until `mbuf_free`. Standard zero-copy pattern.
- **PushFilter `op->free` is called BEFORE the buf is scrubbed**
  (`mbuf.c:397-403`). If the filter's free callback fails to scrub
  its own state, the working buffer is still scrubbed afterwards.
  Defense-in-depth.
- **No size limit on MBuf growth** — `prepare_room` will `repalloc`
  in 16KB steps without an upper bound. Malicious PGP input could in
  principle drive arbitrary memory pressure; mitigated only by
  `work_mem`/the process's memory context tracking.
  [ISSUE-defense-in-depth: no max-size cap on MBuf (maybe)]

## Cross-references

- `pgp-decrypt.c` — primary consumer of `pullf_*`.
- `pgp-encrypt.c` — primary consumer of `pushf_*`.
- `pgp-armor.c` — uses MBuf for ascii-armor decode.
- `pgp-compress.c` — wraps zlib in PushFilter/PullFilter.
- `pgp-cfb.c` — wraps the PX_Cipher in CFB-mode filter.
- `px.c:px_memset` — the scrub primitive.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: ptxt in MBuf scrubbed via `px_memset` only,
  LTO-elision risk (likely)] — `mbuf.c:66, 236, 240, 285, 402, 406`.
- [ISSUE-defense-in-depth: no max-size cap on MBuf growth (maybe)] —
  `mbuf.c:73-91`. Malicious PGP could OOM the backend.
- [ISSUE-api-shape: `mbuf_steal_data` does not document the
  scrub-responsibility transfer (nit)] — comment at `mbuf.c:161`
  is silent about who scrubs.
- [ISSUE-correctness: `pullf_read_max` scrubs tmpbuf on error path
  but NOT on partial-success path (likely-fine, just worth noting)]
  — `mbuf.c:285`. The caller is expected to scrub on their own use.
- [ISSUE-api-shape: `PushFilterOps.init`'s return value tri-state
  (size / 0 / error) is overloaded (nit)] — works but is awkward.
