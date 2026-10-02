"""Backward-compatibility shim for spec 009 R3 reorg.

The canonical source lives at `admesh._stages.routine`. This stub re-exports
the full module surface (including underscore-prefixed helpers used by
existing tests) so legacy imports `from admesh.routine import <name>`
continue to work. The shim is kept for 1.x; removal no earlier than 2.0.

New code SHOULD import from `admesh._stages.routine` directly.
"""
from admesh._stages.routine import *  # noqa: F401,F403

# Also expose underscore-prefixed names (private helpers) for legacy
# imports. Kept for 1.x; removal no earlier than 2.0. Canonical path is admesh._stages.routine.
from admesh._stages import routine as _src
globals().update({k: v for k, v in vars(_src).items() if not k.startswith('__')})
del _src
