#!/usr/bin/env bash
# Runs inside the pg-memhunt container.
# Builds PG with USE_VALGRIND + MEMORY_CONTEXT_CHECKING + cassert + debug.
#
# Inputs:  /pg-source (RO source tree)
# Outputs: builds to /home/pg/build (container-local), installs to /home/pg/install,
#          builds Linux signature into /evidence/build-info.txt
set -euo pipefail

BUILD=/home/pg/build
INSTALL=/home/pg/install
SRC=/pg-source

mkdir -p "$BUILD" "$INSTALL"

if [[ ! -f "$BUILD/meson-info/intro-buildoptions.json" ]]; then
  echo "=== meson setup ==="
  cd /
  meson setup "$BUILD" "$SRC" \
    --buildtype=debug \
    -Dcassert=true \
    -Ddebug=true \
    -Doptimization=0 \
    -Dc_args="-DUSE_VALGRIND -DMEMORY_CONTEXT_CHECKING" \
    -Dprefix="$INSTALL"
fi

echo "=== ninja build ==="
cd "$BUILD"
ninja -j "$(nproc)" 2>&1 | tail -20

echo "=== ninja install ==="
ninja install 2>&1 | tail -10

echo "=== build info ==="
{
  echo "Build date: $(date -u +%FT%TZ)"
  echo "Source commit: $(cd /pg-source && git rev-parse HEAD 2>/dev/null || echo '(unknown — not a git tree)')"
  echo "Linux kernel: $(uname -r)"
  echo "Arch: $(uname -m)"
  echo "Valgrind: $(valgrind --version)"
  echo "Compiler: $(gcc --version | head -1)"
  echo "USE_VALGRIND: yes"
  echo "MEMORY_CONTEXT_CHECKING: yes"
  echo "cassert: yes"
} | tee /evidence/build-info.txt

echo "=== bin sanity ==="
"$INSTALL/bin/postgres" --version
"$INSTALL/bin/initdb" --version
"$INSTALL/bin/psql" --version
