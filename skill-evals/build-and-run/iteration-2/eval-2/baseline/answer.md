# Eval 2 — baseline (no skill)

That error suggests the temporary install tree (`tmp_install`) wasn't built
before the test ran. With meson PG tests, the framework needs to install
into a temporary prefix before it can spin up test clusters.

A few things to try:

1. Build the install target first:

   ```bash
   ninja -C dev/build-debug install
   meson test -C dev/build-debug --suite isolation
   ```

2. Or run the full test target once so meson populates everything:

   ```bash
   meson test -C dev/build-debug
   ```

3. Make sure your meson setup completed cleanly — re-run
   `meson setup --reconfigure dev/build-debug` if in doubt.

4. Check `dev/build-debug/meson-logs/testlog.txt` for the underlying error
   message.

If those don't work, you may need to wipe the build directory and reconfigure
from scratch:

```bash
rm -rf dev/build-debug
meson setup dev/build-debug ...
ninja -C dev/build-debug
meson test -C dev/build-debug --suite isolation
```
