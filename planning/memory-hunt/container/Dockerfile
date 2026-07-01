# PostgreSQL memory-hunt harness: Linux + Valgrind + LSan/ASan signal stack
# Builds PG with -DUSE_VALGRIND -DMEMORY_CONTEXT_CHECKING for proper Valgrind
# integration (~230-line upstream valgrind.supp + USE_VALGRIND annotations
# across src/backend/utils/mmgr/).

FROM ubuntu:24.04
# Note: Ubuntu 24.04 ships Valgrind 3.22+. Debian 12 ships 3.19 which trips
# `m_debuginfo/readdwarf.c:2761` (unhandled DW_OP_ 0x92) reading DWARF
# produced by GCC 12 on arm64. 3.20+ has the fix.

ENV DEBIAN_FRONTEND=noninteractive

# Build prerequisites + Valgrind + minimal locale (en_US.UTF-8 + C).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      meson \
      ninja-build \
      pkg-config \
      bison \
      flex \
      perl \
      libipc-run-perl \
      libtest-simple-perl \
      libreadline-dev \
      zlib1g-dev \
      libssl-dev \
      libicu-dev \
      libxml2-dev \
      libxml2-utils \
      xsltproc \
      python3-dev \
      libldap2-dev \
      libsystemd-dev \
      uuid-dev \
      liblz4-dev \
      libzstd-dev \
      valgrind \
      gdb \
      ca-certificates \
      locales \
      sudo \
      curl \
   && sed -i 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen \
   && locale-gen \
   && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# Run as non-root with UID matching host's matej (501) so bind-mount writes
# are owned by the host user.
RUN useradd -u 501 -m -s /bin/bash pg && \
    echo 'pg ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

USER pg
WORKDIR /home/pg

# Mount points used by run.sh:
#   /pg-source  (RO bind from host: ../postgresql-dev source tree)
#   /workloads  (RO bind: planning/memory-hunt/workloads)
#   /evidence   (RW bind: planning/memory-hunt/evidence/linux)
# Build dir is container-local at /home/pg/build, never leaks back to host.
