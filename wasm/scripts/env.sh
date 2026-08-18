# Shared toolchain environment. `source scripts/env.sh` from any build script.
_ENV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WASM_PORT_ROOT="$_ENV_ROOT"
export NODE=/opt/node22/bin/node
export NPM=/opt/node22/bin/npm

# pyodide-build venv (python 3.13)
export PATH="$_ENV_ROOT/toolchain/venv313/bin:$PATH"

# emscripten (version pinned by the xbuildenv, see 00_setup_toolchain.sh)
source "$_ENV_ROOT/toolchain/emsdk/emsdk_env.sh" >/dev/null 2>&1

# pyodide-build 0.39 keeps the xbuildenv in a global cache:
#   /root/.cache/pyodide-build/.pyodide-xbuildenv-*/
# so `pyodide build` works from any cwd once 00_setup_toolchain.sh has run.
pyodide_xbuildenv_dir() { ls -d /root/.cache/pyodide-build/.pyodide-xbuildenv-* 2>/dev/null | head -1; }
