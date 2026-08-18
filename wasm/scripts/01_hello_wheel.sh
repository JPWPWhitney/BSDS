#!/usr/bin/env bash
# Rung 1 verification: build a trivial C-extension wheel with pyodide-build and
# import it inside Pyodide-in-Node. Proves emsdk + xbuildenv + harness wiring.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/env.sh"

H="$ROOT/hello"
rm -rf "$H"; mkdir -p "$H/src"

cat > "$H/pyproject.toml" <<'EOF'
[build-system]
requires = ["setuptools>=64"]
build-backend = "setuptools.build_meta"
[project]
name = "hello-wasm"
version = "0.1.0"
EOF

cat > "$H/setup.py" <<'EOF'
from setuptools import setup, Extension
setup(ext_modules=[Extension("_hello", sources=["src/hello.c"])])
EOF

cat > "$H/src/hello.c" <<'EOF'
#define PY_SSIZE_T_CLEAN
#include <Python.h>
static PyObject *answer(PyObject *self, PyObject *args) { return PyLong_FromLong(42); }
static PyMethodDef m[] = {{"answer", answer, METH_NOARGS, ""}, {NULL, NULL, 0, NULL}};
static struct PyModuleDef mod = {PyModuleDef_HEAD_INIT, "_hello", NULL, -1, m};
PyMODINIT_FUNC PyInit__hello(void) { return PyModule_Create(&mod); }
EOF

cd "$H"
pyodide build
WHEEL="$(ls "$H"/dist/*.whl | head -1)"
echo "built: $WHEEL"

cat > "$H/test_hello.py" <<'EOF'
import _hello
assert _hello.answer() == 42
print("hello wheel OK: _hello.answer() ==", _hello.answer())
EOF

cd "$ROOT/harness"
"$NODE" run_in_pyodide.mjs "$H/test_hello.py" "$WHEEL"
