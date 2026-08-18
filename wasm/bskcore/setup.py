"""bskcore: Basilisk astrodynamics core cross-compiled to wasm32 (Pyodide).

Reads ext_manifest.json produced by generate.py. Run generate.py before
building; then `pyodide build` from this directory.
"""

import json
import os
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext as _build_ext


class build_ext(_build_ext):
    """Parallel compile; shared sources produce shared objects across exts."""

    def finalize_options(self):
        super().finalize_options()
        if not self.parallel:
            self.parallel = int(os.environ.get("BSKCORE_PARALLEL", "4"))

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / "ext_manifest.json").read_text())

COMMON_INC = [
    "bsk",
    "bsk/architecture",
    "bsk/architecture/_GeneralModuleFiles",
    "bsk/autoSource",
    "vendor_eigen3",
]

NUMPY_INC = None
try:
    import numpy

    NUMPY_INC = numpy.get_include()
except ImportError:
    pass

ext_modules = []
for m in manifest["modules"]:
    include_dirs = list(COMMON_INC) + m.get("incdirs", [])
    if m.get("numpy"):
        if NUMPY_INC is None:
            raise RuntimeError(f"module {m['name']} needs numpy headers")
        include_dirs.append(NUMPY_INC)
    ext_modules.append(
        Extension(
            m["name"],
            sources=[m["wrap"]] + m["sources"],
            include_dirs=include_dirs,
            language="c++",
            # NDEBUG matches the native Release build; basilisk asserts are dev-only
            define_macros=[("NDEBUG", None)],
        )
    )


def find_bsk_packages():
    pkgs = []
    for init in (HERE / "Basilisk").rglob("__init__.py"):
        rel = init.parent.relative_to(HERE)
        pkgs.append(".".join(rel.parts))
    return sorted(pkgs)


setup(
    packages=find_bsk_packages(),
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
