"""
Setup configuration for ADMESH with optional C++ distmesh extension.

Build:
    pip install -e . --no-build-isolation

If pybind11 or Eigen unavailable, the build skips the C++ extension and
falls back to pure-Python Numba distmesh. The admesh API is unchanged.
"""

from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext
import sys
from pathlib import Path

# Optional: try to include C++ extension
try:
    import pybind11
    from pybind11.setup_helpers import Pybind11Extension, build_ext
    HAS_PYBIND11 = True
except ImportError:
    HAS_PYBIND11 = False
    print("[setup.py] pybind11 not found; C++ distmesh extension will be skipped")


ext_modules = []

if HAS_PYBIND11:
    ext_modules = [
        Pybind11Extension(
            "admesh._cpp._distmesh_cpp",
            [
                "admesh/_cpp/distmesh_module.cpp",
                "admesh/_cpp/distmesh_cpp.cpp",
            ],
            include_dirs=[str(Path(__file__).parent)],
            language='c++',
            extra_compile_args=['-O3', '-march=native'] if sys.platform != 'win32' else ['/O2'],
        ),
    ]


setup(
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext} if HAS_PYBIND11 else {},
    packages=find_packages(),
)
