"""Backward-compatibility shim for spec 009 R3 reorg.

The canonical source lives at `admesh._stages.in_polygon`. This stub re-exports
the full module surface (including underscore-prefixed helpers used by
existing tests) so legacy imports `from admesh.in_polygon import <name>`
continue to work until ADMESH 1.0.0.

New code SHOULD import from `admesh._stages.in_polygon` directly.
"""
from admesh._stages.in_polygon import *  # noqa: F401,F403

# Also expose underscore-prefixed names (private helpers) for legacy
# imports. 1.0.0 will drop this stub; canonical path is admesh._stages.in_polygon.
from admesh._stages import in_polygon as _src
globals().update({k: v for k, v in vars(_src).items() if not k.startswith('__')})
del _src
