# bskcore: wasm32 build of the Basilisk astrodynamics core (v2.11.1 sources).
# Import messaging first so recorder/message SWIG types register before any
# module hands them out (mirrors upstream Basilisk/__init__.py).
from Basilisk.architecture import messaging  # noqa: F401

__version__ = "2.11.1+wasm"
