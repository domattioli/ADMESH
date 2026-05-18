"""Backward-compatibility shim for spec 009 R3 reorg.

The canonical source lives at `admesh._stages.distmesh`. This stub re-exports
the full module surface (including underscore-prefixed helpers used by
existing tests) so legacy imports `from admesh.distmesh import <name>`
continue to work until ADMESH 1.0.0.

New code SHOULD import from `admesh._stages.distmesh` directly.
"""
from admesh._stages.distmesh import *  # noqa: F401,F403

# Also expose underscore-prefixed names (private helpers) for legacy
# imports. 1.0.0 will drop this stub; canonical path is admesh._stages.distmesh.
from admesh._stages import distmesh as _src
globals().update({k: v for k, v in vars(_src).items() if not k.startswith('__')})
del _src
