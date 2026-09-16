#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD_DIR=${STAGEFORGE_BUILD_DIR:-"$ROOT/build"}
cmake -S "$ROOT" -B "$BUILD_DIR"
cmake --build "$BUILD_DIR"
ctest --test-dir "$BUILD_DIR" --output-on-failure
printf '\nNative engine: %s\n' "$BUILD_DIR/native/stageforge_engine"
