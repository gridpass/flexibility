#!/usr/bin/env bash
# Build only GridPass-owned code + pinned wheels; no Bosch binaries or credentials.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
OUT=${1:-"$ROOT/dist/ctrlx"}
PYTHON=${PYTHON:-python3}
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
STAGE=$(mktemp -d)
chmod 755 "$STAGE" # snap root must be readable; only public files are staged.
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE"/{meta,bin,examples,tests,src}
cp "$ROOT/deploy/ctrlx/meta/snap.yaml" "$STAGE/meta/"
install -m 755 "$ROOT/deploy/ctrlx/bin/replay" "$ROOT/deploy/ctrlx/bin/self-test" "$STAGE/bin/"
mkdir -p "$STAGE/src/gridpass_flexibility"
for file in __init__.py screening.py guard.py guard_demo.py; do
  cp "$ROOT/src/gridpass_flexibility/$file" "$STAGE/src/gridpass_flexibility/"
done
cp "$ROOT/examples/guard-site.json" "$STAGE/examples/"
cp "$ROOT/tests/test_guard.py" "$STAGE/tests/"
cp "$ROOT/LICENSE" "$STAGE/"
cp "$ROOT/deploy/ctrlx/requirements-amd64-py310.lock" "$STAGE/"
"$PYTHON" -m pip install --disable-pip-version-check --no-compile --require-hashes \
  --only-binary=:all: --platform manylinux_2_34_x86_64 \
  --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
  --platform manylinux_2_17_x86_64 --implementation cp --python-version 3.10 \
  --abi cp310 --target "$STAGE/vendor" \
  -r "$ROOT/deploy/ctrlx/requirements-amd64-py310.lock"
snap pack --check-skeleton "$STAGE"
snap pack "$STAGE" "$OUT"
sha256sum "$OUT/gridpass-guard_0.1.0_amd64.snap"
