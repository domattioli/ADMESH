"""One-time, opt-out hint that invites users to share meshes."""

from __future__ import annotations

import os
import sys

# TODO: the valence-intake repo does not exist yet. Update this URL once it does.
SHARE_URL = "https://github.com/domattioli/valence-intake/issues/new?template=share-mesh.yml"
ENV_VAR = "ADMESH_NO_SHARE_HINT"

_hint_shown = False


def maybe_log_share_hint() -> None:
    """Print the share-your-mesh hint to stderr once per process.

    Set ADMESH_NO_SHARE_HINT to any non-empty value to silence it.
    """
    global _hint_shown
    if _hint_shown or os.environ.get(ENV_VAR):
        return
    _hint_shown = True
    print(
        "Mesh written. If you can share it, we would be glad to add it to a "
        "public test collection: %s (set ADMESH_NO_SHARE_HINT to silence this message)."
        % SHARE_URL,
        file=sys.stderr,
    )
