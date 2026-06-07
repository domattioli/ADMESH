"""Backward-compatibility shim for spec 009 R3 reorg.

The canonical source lives at `admesh._stages.inpaint`. This stub re-exports
the full module surface (including underscore-prefixed helpers used by
existing tests) so legacy imports `from admesh.inpaint import <name>`
continue to work until ADMESH 1.0.0.

New code SHOULD import from `admesh._stages.inpaint` directly.
"""
from admesh._stages.inpaint import *  # noqa: F401,F403

# Also expose underscore-prefixed names (private helpers) for legacy
# imports. 1.0.0 will drop this stub; canonical path is admesh._stages.inpaint.
from admesh._stages import inpaint as _src
globals().update({k: v for k, v in vars(_src).items() if not k.startswith('__')})
del _src
