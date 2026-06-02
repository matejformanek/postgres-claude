# Eval 1 — baseline (no skill)

After editing a backend C file, the fastest cycle is:

```bash
# Rebuild
cd postgres
make -j$(sysctl -n hw.ncpu)
make install

# Or with meson (PG 16+)
ninja -C build
ninja -C build install

# Restart your cluster so the postmaster picks up the new binary
pg_ctl -D /usr/local/pgsql/data restart

# Run regression tests
make check
# Or just the core regression suite
cd src/test/regress && make check
```

If you only changed one C file under `access/heap`, you can often get away
with rebuilding just that subdir:

```bash
cd src/backend/access/heap && make
cd ../../../.. && make install
```

For meson:

```bash
ninja -C build src/backend/postgres
ninja -C build install
```

Then `psql` against your running cluster to smoke-test.
