#!/usr/bin/env python3
"""Assemble the bskcore project from a pristine Basilisk clone.

Steps (all idempotent; run with the toolchain venv python so libclang is available):
  1. copy the required C/C++/SWIG source subset  basilisk/src -> bskcore/bsk/
  2. apply patches/*.patch (sim_model no-threads, python wasm shims)
  3. generate per-payload messaging SWIG modules into bsk/autoSource/
     (same generators the CMake build uses: meta json via libclang -> equality
      header -> .i from template)
  4. run SWIG (host swig, 4.2.0) for every module -> swig/<name>_wrap.cxx and
     the proxy .py next to its package position under Basilisk/
  5. stage the pure-python package files (utilities etc.) under Basilisk/
  6. write ext_manifest.json consumed by setup.py

Usage: generate.py [--basilisk PATH] [--clean]
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BSK = HERE.parent / "basilisk" / "src"
PATCH_DIR = HERE.parent / "patches"
VENDOR_EIGEN = HERE.parent / "vendor" / "eigen3"

# ----------------------------------------------------------------------------
# What to copy out of basilisk/src (directories copied filtered by suffix)
COPY_DIRS = [
    "architecture/_GeneralModuleFiles",
    "architecture/system_model",
    "architecture/utilities",
    "architecture/utilities/moduleIdGenerator",
    "architecture/messaging",
    "architecture/messaging/msgAutoSource",
    "architecture/msgPayloadDefC",
    "simulation/dynamics/_GeneralModuleFiles",
    "simulation/dynamics/spacecraft",
    "simulation/dynamics/gravityEffector",
    "simulation/dynamics/reactionWheels",
    "simulation/dynamics/dragEffector",
    "simulation/environment/_GeneralModuleFiles",
    "simulation/environment/ExponentialAtmosphere",
    "fswAlgorithms/fswUtilities",
]
COPY_SUFFIXES = {".c", ".cpp", ".h", ".hpp", ".i", ".ih", ".swg", ".in", ".py"}

# ----------------------------------------------------------------------------
# Messaging payload modules to generate (C payload headers)
PAYLOADS = [
    "SCStatesMsgPayload",
    "SCMassPropsMsgPayload",
    "SCEnergyMomentumMsgPayload",
    "AttRefMsgPayload",
    "TransRefMsgPayload",
    "SpicePlanetStateMsgPayload",
    "EpochMsgPayload",
    "AtmoPropsMsgPayload",
]

# ----------------------------------------------------------------------------
# Source bundles (relative to bsk/)
ARCH_CORE = [
    "architecture/_GeneralModuleFiles/sys_model.cpp",
    "architecture/utilities/bskLogging.cpp",
    "architecture/utilities/moduleIdGenerator/moduleIdGenerator.cpp",
]
SIM_CORE = ARCH_CORE + [
    "architecture/system_model/sim_model.cpp",
    "architecture/system_model/sys_process.cpp",
    "architecture/_GeneralModuleFiles/sys_model_task.cpp",
]
C_UTILS = [
    "architecture/utilities/orbitalMotion.c",
    "architecture/utilities/linearAlgebra.c",
    "architecture/utilities/rigidBodyKinematics.c",
]
GRAV_MODELS = [
    "simulation/dynamics/_GeneralModuleFiles/pointMassGravityModel.cpp",
    "simulation/dynamics/gravityEffector/sphericalHarmonicsGravityModel.cpp",
    "simulation/dynamics/gravityEffector/polyhedralGravityModel.cpp",
]
DYN_CORE = ARCH_CORE + C_UTILS + GRAV_MODELS + [
    "architecture/utilities/avsEigenSupport.cpp",
    "simulation/dynamics/_GeneralModuleFiles/dynParamManager.cpp",
    "simulation/dynamics/_GeneralModuleFiles/stateData.cpp",
    "simulation/dynamics/_GeneralModuleFiles/dynamicEffector.cpp",
    "simulation/dynamics/_GeneralModuleFiles/stateEffector.cpp",
    "simulation/dynamics/_GeneralModuleFiles/gravityEffector.cpp",
]
SPACECRAFT_SRC = DYN_CORE + [
    "simulation/dynamics/_GeneralModuleFiles/dynamicObject.cpp",
    "simulation/dynamics/_GeneralModuleFiles/extendedStateVector.cpp",
    "simulation/dynamics/_GeneralModuleFiles/stateVecIntegrator.cpp",
    "simulation/dynamics/_GeneralModuleFiles/svIntegratorRK4.cpp",
    "simulation/dynamics/_GeneralModuleFiles/hubEffector.cpp",
    "simulation/dynamics/spacecraft/spacecraft.cpp",
]
ATMO_SRC = ARCH_CORE + C_UTILS + [
    "simulation/environment/_GeneralModuleFiles/atmosphereBase.cpp",
    "simulation/environment/ExponentialAtmosphere/exponentialAtmosphere.cpp",
]
DRAG_SRC = DYN_CORE + [
    "simulation/dynamics/dragEffector/dragDynamicEffector.cpp",
]

# ----------------------------------------------------------------------------
# SWIG module manifest: (ext name, .i path rel to bsk/ or 'interfaces', sources,
#                        needs numpy headers)
MODULES = [
    ("Basilisk.architecture._swig_common_model",
     "architecture/_GeneralModuleFiles/swig_common_model.i", [], False),
    ("Basilisk.architecture._bskLogging",
     "architecture/utilities/bskLogging.i",
     ["architecture/utilities/bskLogging.cpp"], False),
    ("Basilisk.architecture._astroConstants",
     "architecture/utilities/astroConstants.i", [], False),
    ("Basilisk.architecture._bskUtilities",
     "architecture/utilities/bskUtilities.i", [], False),
    ("Basilisk.architecture._sim_model",
     "architecture/system_model/sim_model.i", SIM_CORE, False),
    ("Basilisk.architecture._sys_model_task",
     "architecture/_GeneralModuleFiles/sys_model_task.i",
     ARCH_CORE + ["architecture/_GeneralModuleFiles/sys_model_task.cpp"], False),
    ("Basilisk.architecture._sysModel",
     "architecture/_GeneralModuleFiles/py_sys_model.i", ARCH_CORE, False),
    ("Basilisk.architecture._cutils",
     "INTERFACES/cutils.i", C_UTILS, False),
    ("Basilisk.simulation._gravityModel",
     "simulation/dynamics/_GeneralModuleFiles/gravityModel.i",
     ARCH_CORE + C_UTILS + GRAV_MODELS
     + ["architecture/utilities/avsEigenSupport.cpp"], False),
    ("Basilisk.simulation._pointMassGravityModel",
     "simulation/dynamics/gravityEffector/pointMassGravityModel.i",
     ARCH_CORE + C_UTILS + GRAV_MODELS
     + ["architecture/utilities/avsEigenSupport.cpp"], False),
    ("Basilisk.simulation._sphericalHarmonicsGravityModel",
     "simulation/dynamics/gravityEffector/sphericalHarmonicsGravityModel.i",
     ARCH_CORE + C_UTILS + GRAV_MODELS
     + ["architecture/utilities/avsEigenSupport.cpp"], False),
    ("Basilisk.simulation._polyhedralGravityModel",
     "simulation/dynamics/gravityEffector/polyhedralGravityModel.i",
     ARCH_CORE + C_UTILS + GRAV_MODELS
     + ["architecture/utilities/avsEigenSupport.cpp"], False),
    ("Basilisk.simulation._gravityEffector",
     "simulation/dynamics/gravityEffector/gravityEffector.i", DYN_CORE, False),
    ("Basilisk.simulation._spacecraft",
     "simulation/dynamics/spacecraft/spacecraft.i", SPACECRAFT_SRC, False),
    ("Basilisk.simulation._exponentialAtmosphere",
     "simulation/environment/ExponentialAtmosphere/exponentialAtmosphere.i",
     ATMO_SRC, False),
    ("Basilisk.simulation._dragDynamicEffector",
     "simulation/dynamics/dragEffector/dragDynamicEffector.i", DRAG_SRC, False),
] + [
    (f"Basilisk.architecture.messaging._{p}",
     f"AUTOSOURCE/{p}.i", ARCH_CORE, True)
    for p in PAYLOADS
]

# ----------------------------------------------------------------------------
# Pure-python files copied from basilisk/src (patched afterwards by patch files)
UTILITIES_PY = [
    "SimulationBaseClass.py", "macros.py", "orbitalMotion.py",
    "simIncludeGravBody.py", "RigidBodyKinematics.py", "simulationArchTypes.py",
    "pythonVariableLogger.py", "simulationProgessBar.py", "deprecated.py",
    "simHelpers.py", "unitTestSupport.py",
]


def run(cmd, cwd=None, env=None):
    printable = " ".join(Path(str(c)).name if "/" in str(c) else str(c) for c in cmd[:6])
    print(f"  $ {printable} ...")
    subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, check=True)


def copy_sources(src_root: Path, bsk: Path):
    print("== copying Basilisk sources ==")
    for rel in COPY_DIRS:
        src_dir = src_root / rel
        dst_dir = bsk / rel
        dst_dir.mkdir(parents=True, exist_ok=True)
        for f in src_dir.iterdir():
            if f.is_file() and f.suffix in COPY_SUFFIXES:
                shutil.copy2(f, dst_dir / f.name)


def apply_patches(bsk: Path, pkg: Path):
    print("== applying patches ==")
    run(["patch", "-p1", "-d", bsk, "-i", PATCH_DIR / "sim_model_nothreads.patch"])
    # python shims patch applies to the staged package (utilities/...)
    run(["patch", "-p1", "-d", pkg, "-i", PATCH_DIR / "python_wasm_shims.patch"])


def gen_payload_modules(bsk: Path):
    print("== generating messaging payload modules ==")
    msg = bsk / "architecture" / "messaging"
    auto = bsk / "autoSource"
    (auto / "cMsgMeta").mkdir(parents=True, exist_ok=True)
    for p in PAYLOADS:
        hdr = f"../msgPayloadDefC/{p}.h"
        meta = auto / "cMsgMeta" / f"{p}.json"
        run([sys.executable, "msgAutoSource/generatePayloadMetaJson.py",
             hdr, p, meta, "--", "-x", "c", "-I../", "-I../../"], cwd=msg)
        run([sys.executable, "msgAutoSource/generatePayloadEqualityHeader.py",
             auto / f"{p}_equality.h", meta, p, "msgPayloadDefC"], cwd=msg)
        run([sys.executable, "generateSWIGModules.py",
             auto / f"{p}.i", hdr, p, "msgPayloadDefC", "False", meta, "0"],
            cwd=msg / "msgAutoSource")


def run_swig(root: Path, bsk: Path, pkg: Path):
    print("== running SWIG ==")
    swig_out = root / "swig"
    swig_out.mkdir(exist_ok=True)
    wraps = {}
    for name, ifile, _srcs, _numpy in MODULES:
        modname = name.split(".")[-1]           # _spacecraft
        pkg_sub = pkg / Path(*name.split(".")[1:-1])  # Basilisk/simulation
        pkg_sub.mkdir(parents=True, exist_ok=True)
        if ifile.startswith("INTERFACES/"):
            ipath = root / "interfaces" / ifile.split("/", 1)[1]
        elif ifile.startswith("AUTOSOURCE/"):
            ipath = bsk / "autoSource" / ifile.split("/", 1)[1]
        else:
            ipath = bsk / ifile
        wrap = swig_out / f"{modname[1:]}_wrap.cxx"
        incs = ["-I" + str(bsk),
                "-I" + str(bsk / "architecture"),
                "-I" + str(bsk / "architecture" / "_GeneralModuleFiles"),
                "-I" + str(bsk / "architecture" / "utilities"),
                "-I" + str(bsk / "architecture" / "messaging"),
                "-I" + str(bsk / "simulation" / "dynamics" / "_GeneralModuleFiles"),
                "-I" + str(bsk / "autoSource"),
                "-I" + str(ipath.parent)]
        run(["swig", "-c++", "-python", *incs,
             "-outdir", pkg_sub, "-o", wrap, ipath])
        # the module's own directory must also be a C include dir (matches the
        # native CMake PARENT_DIR include), e.g. spacecraft.i does #include "spacecraft.h"
        wraps[name] = {
            "wrap": str(wrap.relative_to(root)),
            "incdirs": [str(ipath.parent.relative_to(root))],
        }
    return wraps


def stage_python(bsk_src: Path, pkg: Path):
    print("== staging python package files ==")
    (pkg / "utilities").mkdir(parents=True, exist_ok=True)
    for f in UTILITIES_PY:
        shutil.copy2(bsk_src / "utilities" / f, pkg / "utilities" / f)
    # package __init__ overlays
    overlay = HERE / "overlay"
    for rel in ["__init__.py", "architecture/__init__.py",
                "simulation/__init__.py", "utilities/__init__.py",
                "architecture/messaging/__init__.py"]:
        dst = pkg / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(overlay / rel, dst)


def write_manifest(root: Path, wraps: dict):
    manifest = {"modules": []}
    for name, _ifile, srcs, needs_numpy in MODULES:
        manifest["modules"].append({
            "name": name,
            "wrap": wraps[name]["wrap"],
            "incdirs": wraps[name]["incdirs"],
            "sources": sorted(set("bsk/" + s for s in srcs)),
            "numpy": needs_numpy,
        })
    (root / "ext_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"== wrote ext_manifest.json ({len(manifest['modules'])} modules) ==")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--basilisk", type=Path, default=DEFAULT_BSK)
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    bsk = HERE / "bsk"
    pkg = HERE / "Basilisk"
    if args.clean:
        for d in [bsk, pkg, HERE / "swig", HERE / "build", HERE / "dist",
                  HERE / "vendor_eigen3"]:
            shutil.rmtree(d, ignore_errors=True)

    if not (HERE / "vendor_eigen3" / "Eigen").exists():
        print("== vendoring Eigen ==")
        (HERE / "vendor_eigen3").mkdir(exist_ok=True)
        shutil.copytree(VENDOR_EIGEN / "Eigen", HERE / "vendor_eigen3" / "Eigen",
                        dirs_exist_ok=True)
        shutil.copytree(VENDOR_EIGEN / "unsupported",
                        HERE / "vendor_eigen3" / "unsupported", dirs_exist_ok=True)

    copy_sources(args.basilisk, bsk)
    stage_python(args.basilisk, pkg)
    apply_patches(bsk, pkg)
    gen_payload_modules(bsk)
    wraps = run_swig(HERE, bsk, pkg)
    write_manifest(HERE, wraps)
    print("generate.py done")


if __name__ == "__main__":
    main()
