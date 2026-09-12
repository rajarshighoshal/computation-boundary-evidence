#!/bin/sh
# Build the LD_PRELOAD shims for linux/x86_64 (glibc) inside a bullseye
# container so the artifacts load on every newer-glibc task image.
set -eu
cd "$(dirname "$0")"
mkdir -p out
docker run --rm --platform linux/amd64 -v "$PWD:/src" -w /src debian:bookworm bash -lc "
  apt-get update -qq && apt-get install -y -qq gcc libc6-dev >/dev/null
  gcc -O2 -shared -fPIC -o out/libscitrace_malloc.so scitrace_malloc.c -ldl
  gcc -O2 -shared -fPIC -o out/libscitrace_mpi.so scitrace_mpi.c -ldl
" 
sha256sum out/libscitrace_malloc.so out/libscitrace_mpi.so > out/sha256.txt
echo "built:"
cat out/sha256.txt
