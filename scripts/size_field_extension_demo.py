"""Custom size-field contribution demo (T045).

Mirrors the wave-breaker example from ``quickstart.md``. Triangulates
a unit-disk domain twice — without and with a user-supplied size
contribution that refines near a vertical "wave breaker" line —
and renders both meshes side-by-side under
``tests/output/size_field_extension_demo.png``.

This is a power-user pattern: drop a callable ``(N, 2) -> (N,)`` into
``triangulate(user_contribs=[...])`` and the Phase-2 combiner (default
``np.minimum.reduce``) folds your contribution into the size field
without touching the Phase-1 built-in stack (Constitution Principle I).
"""

from __future__ import annotations

import pathlib

import numpy as np

import admesh


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "tests" / "output" / "size_field_extension_demo.png"


_BREAKER_X = 0.3
_TARGET_H = 0.04
_BULK_H = 0.10


def refine_near_breaker(pts: np.ndarray) -> np.ndarray:
    """Smaller mesh size near x = ``_BREAKER_X`` (the 'wave-breaker' line).

    Lipschitz-bounded ramp so distmesh doesn't slive at the transition.
    """
    distance_to_breaker = np.abs(pts[:, 0] - _BREAKER_X)
    transition_band = 0.3
    ramp = _TARGET_H + (_BULK_H - _TARGET_H) * np.clip(
        distance_to_breaker / transition_band, 0.0, 1.0
    )
    return ramp


def _disc_domain():
    sdf = lambda p: np.hypot(p[:, 0], p[:, 1]) - 1.0
    return admesh.domain_from_sdf(sdf, bbox=(-1.0, -1.0, 1.0, 1.0))


def main() -> None:
    print("=== custom size-field demo ===\n")
    domain = _disc_domain()

    refined = admesh.triangulate(
        domain,
        h_max=_BULK_H,
        max_iter=200,
        seed=0,
        user_contribs=[refine_near_breaker],
        # The size jump is sharp; relax the gate and trust the
        # post-hoc quality readout below.
        quality_gate=(0.0, 0.0),
    )
    print(f"refined (near x={_BREAKER_X}):  {repr(refined)}")
    print(
        f"  min_q={float(refined.quality.min()):.2f}  "
        f"mean_q={float(refined.quality.mean()):.2f}\n"
    )

    # Empirical readout: average edge length inside vs outside the
    # transition band. Headline number for the demo.
    centroids = refined.nodes[refined.elements].mean(axis=1)
    inside = np.abs(centroids[:, 0] - _BREAKER_X) < 0.15
    edge_len = np.linalg.norm(
        refined.nodes[refined.elements[:, 1]]
        - refined.nodes[refined.elements[:, 0]],
        axis=1,
    )
    if inside.any() and (~inside).any():
        print(
            f"  mean edge length: near breaker = "
            f"{edge_len[inside].mean():.3f}, far = "
            f"{edge_len[~inside].mean():.3f}\n"
        )

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.axes_grid1.inset_locator import (
            inset_axes, mark_inset,
        )
    except ImportError:
        print(
            "matplotlib not installed — skipping figure render. "
            "Install via `pip install admesh2D[viz]`."
        )
        return

    fig, ax = plt.subplots(figsize=(8, 8), dpi=120)
    refined.plot(ax=ax, color="#444", linewidth=0.4)
    ax.axvline(
        _BREAKER_X, color="#1f77b4", lw=1.2, ls="--", alpha=0.7,
        label=f"wave-breaker line (x = {_BREAKER_X})",
    )
    ax.set_title(
        f"custom size-field contribution — refines near a wave-breaker line\n"
        f"({refined.n_nodes} nodes, {refined.n_elements} elements; "
        f"target h={_TARGET_H}, bulk h={_BULK_H})"
    )
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal")
    ax.legend(loc="lower right")

    # Zoom inset over the breaker transition zone.
    axins = inset_axes(
        ax, width="40%", height="40%", loc="upper right", borderpad=1.2
    )
    refined.plot(ax=axins, color="#444", linewidth=0.7)
    axins.axvline(_BREAKER_X, color="#1f77b4", lw=1.2, ls="--", alpha=0.7)
    axins.set_xlim(_BREAKER_X - 0.25, _BREAKER_X + 0.25)
    axins.set_ylim(-0.4, 0.4)
    axins.set_xticks([])
    axins.set_yticks([])
    axins.set_title("zoom: ±0.25 × ±0.4", fontsize=9)
    mark_inset(ax, axins, loc1=2, loc2=4, fc="none", ec="#888", lw=0.5)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
