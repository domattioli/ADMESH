"""
Setup configuration for ADMESH with optional C++ distmesh extension.

Build:
    pip install -e . --no-build-isolation

If pybind11 or Eigen unavailable, the build skips the C++ extension and
falls back to pure-Python Numba distmesh. The admesh API is unchanged.
"""

from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext
import subprocess
import sys
from pathlib import Path


def _find_eigen3():
    """Return Eigen3 include directory or None if not found."""
    try:
        flags = subprocess.check_output(
            ["pkg-config", "--cflags-only-I", "eigen3"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        # flags may be "-I/usr/include/eigen3" or empty
        for token in flags.split():
            path = token.lstrip("-I").strip()
            if path and (Path(path) / "Eigen" / "Dense").exists():
                return path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    candidates = [
        "/usr/include/eigen3",
        "/usr/local/include/eigen3",
        "/opt/homebrew/include/eigen3",
        "/opt/homebrew/include",
        "/usr/include",
    ]
    for c in candidates:
        if (Path(c) / "Eigen" / "Dense").exists():
            return c
    return None


# Optional: try to include C++ extension
try:
    import pybind11
    from pybind11.setup_helpers import Pybind11Extension, build_ext
    HAS_PYBIND11 = True
except ImportError:
    HAS_PYBIND11 = False
    print("[setup.py] pybind11 not found; C++ distmesh extension will be skipped")

eigen_path = _find_eigen3() if HAS_PYBIND11 else None
if HAS_PYBIND11 and eigen_path is None:
    print("[setup.py] Eigen3 not found; C++ distmesh extension will be skipped")

ext_modules = []

if HAS_PYBIND11 and eigen_path is not None:
    include_dirs = [str(Path(__file__).parent), str(Path(__file__).parent / "src"), eigen_path]
    ext_modules = [
        Pybind11Extension(
            "admesh._cpp._distmesh_cpp",
            [
                "src/admesh/_cpp/distmesh_module.cpp",
                "src/admesh/_cpp/distmesh_cpp.cpp",
            ],
            include_dirs=include_dirs,
            language='c++',
            extra_compile_args=['-O3', '-march=native'] if sys.platform != 'win32' else ['/O2'],
        ),
    ]


setup(
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext} if HAS_PYBIND11 else {},
    packages=find_packages(),
)
