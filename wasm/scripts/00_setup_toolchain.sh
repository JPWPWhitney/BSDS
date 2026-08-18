#!/usr/bin/env bash
# Rung 1: recreate the wasm toolchain non-interactively.
# Re-runnable: every step is guarded; safe to re-invoke after partial failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TC="$ROOT/toolchain"
DL="$ROOT/downloads"
PYODIDE_VERSION=0.29.4
PYODIDE_BUILD_VERSION=0.39.0
HTTP_PORT=8765

mkdir -p "$TC" "$DL" "$ROOT/vendor" "$ROOT/harness"

echo "== [1/6] Python 3.13 venv + pyodide-build =="
if [ ! -x "$TC/venv313/bin/python" ]; then
    python3.13 -m venv "$TC/venv313"
fi
# pypi.org / files.pythonhosted.org are proxy-exempt (no_proxy) -> direct TLS works on 3.13
"$TC/venv313/bin/pip" install --quiet "pyodide-build==$PYODIDE_BUILD_VERSION"
"$TC/venv313/bin/pyodide" --version

echo "== [2/6] Pyodide xbuildenv $PYODIDE_VERSION =="
# BLOCKER workaround: pyodide-build fetches from pyodide.github.io / github.com which
# Python 3.13 TLS rejects behind the MITM proxy (VERIFY_X509_STRICT). curl trusts the
# proxy CA, and 127.0.0.1 is proxy-exempt, so: curl the tarball, then serve it to the
# tool over local http. Never disable TLS verification.
XB="$DL/xbuildenv-$PYODIDE_VERSION.tar.bz2"
if [ ! -f "$XB" ]; then
    curl -L --fail -o "$XB" \
      "https://github.com/pyodide/pyodide/releases/download/$PYODIDE_VERSION/xbuildenv-$PYODIDE_VERSION.tar.bz2"
fi
# xbuildenv lands in $PWD/.pyodide-xbuildenv-*/ — run all pyodide cmds from $ROOT.
cd "$ROOT"
if ! "$TC/venv313/bin/pyodide" config get emscripten_version >/dev/null 2>&1; then
    python3 -m http.server "$HTTP_PORT" --bind 127.0.0.1 --directory "$DL" >/dev/null 2>&1 &
    HTTPD_PID=$!
    trap 'kill $HTTPD_PID 2>/dev/null || true' EXIT
    sleep 1
    "$TC/venv313/bin/pyodide" xbuildenv install \
        --url "http://127.0.0.1:$HTTP_PORT/xbuildenv-$PYODIDE_VERSION.tar.bz2"
    kill $HTTPD_PID 2>/dev/null || true
    trap - EXIT
fi
EMSCRIPTEN_VERSION="$(cd "$ROOT" && "$TC/venv313/bin/pyodide" config get emscripten_version)"
echo "xbuildenv OK; wants emscripten $EMSCRIPTEN_VERSION"

echo "== [3/6] emsdk / emscripten $EMSCRIPTEN_VERSION =="
if [ ! -d "$TC/emsdk" ]; then
    git clone --depth 1 https://github.com/emscripten-core/emsdk "$TC/emsdk"
fi
if [ ! -f "$TC/emsdk/upstream/emscripten/emcc" ]; then
    "$TC/emsdk/emsdk" install "$EMSCRIPTEN_VERSION"   # storage.googleapis.com is allowed
fi
"$TC/emsdk/emsdk" activate "$EMSCRIPTEN_VERSION" >/dev/null
source "$TC/emsdk/emsdk_env.sh" >/dev/null 2>&1
emcc --version | head -1

echo "== [4/6] SWIG =="
if ! command -v swig >/dev/null; then
    apt-get install -y swig
fi
swig -version | grep Version   # 4.2.0 from apt works on v2.11.1 .i files

echo "== [5/6] Node harness (pyodide npm package) =="
cd "$ROOT/harness"
if [ ! -d node_modules/pyodide ]; then
    /opt/node22/bin/npm install --no-fund --no-audit "pyodide@$PYODIDE_VERSION"
fi
/opt/node22/bin/node -e "const{version}=require('pyodide/package.json');console.log('pyodide npm', version)"

echo "== [6/6] Vendored Eigen (pywasmcross filters -I/usr/include) =="
if [ ! -d "$ROOT/vendor/eigen3/Eigen" ]; then
    mkdir -p "$ROOT/vendor/eigen3"
    cp -r /usr/include/eigen3/Eigen /usr/include/eigen3/unsupported "$ROOT/vendor/eigen3/"
fi
grep -rE "#define EIGEN_(WORLD|MAJOR|MINOR)_VERSION" "$ROOT/vendor/eigen3/Eigen/src/Core/util/Macros.h" | head -3

echo "== [7/7] Runtime numpy wheel (CDN is blocked; PyPI has no pyodide wheels) =="
# The full pyodide release bundle carries every packaged wheel; extract numpy only.
NPWHEEL="$(ls "$ROOT/downloads/wasm-wheels"/numpy-*.whl 2>/dev/null | head -1 || true)"
if [ -z "$NPWHEEL" ]; then
    PB="$DL/pyodide-$PYODIDE_VERSION.tar.bz2"
    [ -f "$PB" ] || curl -L --fail -o "$PB" \
      "https://github.com/pyodide/pyodide/releases/download/$PYODIDE_VERSION/pyodide-$PYODIDE_VERSION.tar.bz2"
    mkdir -p "$ROOT/downloads/wasm-wheels"
    tar -xjf "$PB" -C "$ROOT/downloads/wasm-wheels" --strip-components=1 \
        --wildcards "pyodide/numpy-*.whl"
fi
ls "$ROOT/downloads/wasm-wheels"/numpy-*.whl

echo "== toolchain ready =="
