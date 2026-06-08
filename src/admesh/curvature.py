"""Backward-compatibility shim for spec 009 R3 reorg.

The canonical source lives at `admesh._stages.curvature`. This stub re-exports
the full module surface (including underscore-prefixed helpers used by
existing tests) so legacy imports `from admesh.curvature import <name>`
continue to work until ADMESH 1.0.0.

New code SHOULD import from `admesh._stages.curvature` directly.
"""
from admesh._stages.curvature import *  # noqa: F401,F403

# Also expose underscore-prefixed names (private helpers) for legacy
# imports. 1.0.0 will drop this stub; canonical path is admesh._stages.curvature.
from admesh._stages import curvature as _src
globals().update({k: v for k, v in vars(_src).items() if not k.startswith('__')})
del _src
