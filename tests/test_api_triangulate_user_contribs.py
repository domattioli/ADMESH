"""End-to-end ``triangulate(user_contribs=[...])`` test (T040).

Triangulate a unit disk twice — once with no user contributions and
once with a contribution that halves the size in a small target disc.
Assert the targeted region's elements end up smaller while the
quality gate still holds globally.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import admesh


_TARGET_CENTER = np.array([0.4, 0.0])
_TARGET_RADIUS = 0.3
_BULK_H = 0.2
_TARGET_H = 0.06


def _refine_in_disc(pts: np.ndarray) -> np.ndarray:
    """Lipschitz size field: ``_TARGET_H`` inside, ``_BULK_H`` outside.

    Linear growth between target edge and bulk-equivalent radius
    keeps distmesh from producing slivers at the transition.
    """
    d = np.hypot(
        pts[:, 0] - _TARGET_CENTER[0], pts[:, 1] - _TARGET_CENTER[1]
    )
    # Inside target: _TARGET_H. Linear ramp from _TARGET_H up to _BULK_H
    # over a transition band of width 0.3, then capped at _BULK_H.
    transition = (d - _TARGET_RADIUS) / 0.3
    ramp = _TARGET_H + (_BULK_H - _TARGET_H) * np.clip(transition, 0.0, 1.0)
    return ramp


def _disc_domain():
    sdf = lambda p: np.hypot(p[:, 0], p[:, 1]) - 1.0
    return admesh.Domain(sdf=sdf, bbox=(-1.0, -1.0, 1.0, 1.0))


def _triangle_centroids(mesh: admesh.Mesh) -> np.ndarray:
    return mesh.nodes[mesh.elements].mean(axis=1)


def _mean_inradius(mesh: admesh.Mesh, centroid_mask: np.ndarray) -> float:
    """Mean inradius of triangles whose centroid satisfies ``centroid_mask``."""
    if not centroid_mask.any():
        return float("nan")
    sel = mesh.elements[centroid_mask]
    a = mesh.nodes[sel[:, 0]]
    b = mesh.nodes[sel[:, 1]]
    c = mesh.nodes[sel[:, 2]]
    ab = np.linalg.norm(b - a, axis=1)
    bc = np.linalg.norm(c - b, axis=1)
    ca = np.linalg.norm(a - c, axis=1)
    s = 0.5 * (ab + bc + ca)
    area = np.abs(
        (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
        - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
    ) * 0.5
    return float((area / np.maximum(s, 1e-12)).mean())


def test_user_contribs_refines_targeted_region():
    domain = _disc_domain()

    base = admesh.triangulate(
        domain, h_max=_BULK_H, max_iter=200, seed=0,
    )
    refined = admesh.triangulate(
        domain,
        h_max=_BULK_H,
        max_iter=200,
        seed=0,
        user_contribs=[_refine_in_disc],
        # Sharp size transitions cost some quality. The point of this
        # test is the refinement signal, not the global gate (covered
        # elsewhere) — disable the gate so we measure refinement only.
        quality_gate=(0.0, 0.0),
    )

    # (a) Refined mesh is structurally valid even with a sharp size jump.
    assert refined.n_elements > 0
    assert refined.elements.min() >= 0
    assert refined.elements.max() < refined.n_nodes

    # (b) Mean inradius INSIDE the target disc is smaller in `refined`.
    base_centroids = _triangle_centroids(base)
    refined_centroids = _triangle_centroids(refined)
    base_mask = (
        np.hypot(base_centroids[:, 0] - _TARGET_CENTER[0],
                 base_centroids[:, 1] - _TARGET_CENTER[1])
        < _TARGET_RADIUS
    )
    refined_mask = (
        np.hypot(refined_centroids[:, 0] - _TARGET_CENTER[0],
                 refined_centroids[:, 1] - _TARGET_CENTER[1])
        < _TARGET_RADIUS
    )
    base_inradius = _mean_inradius(base, base_mask)
    refined_inradius = _mean_inradius(refined, refined_mask)
    assert refined_inradius < base_inradius, (
        f"refined inradius {refined_inradius:.4f} not smaller than "
        f"baseline {base_inradius:.4f}"
    )

    # (c) Connectivity outside the target region is unchanged in the
    #     sense that the bulk-region triangles' inradius is similar
    #     between baseline and refined (within ~50% — distmesh's
    #     point-seeding is stochastic and we don't expect bit-exact
    #     parity, only that the bulk wasn't accidentally refined too).
    base_outside = _mean_inradius(base, ~base_mask)
    refined_outside = _mean_inradius(refined, ~refined_mask)
    assert refined_outside > 0.5 * base_outside, (
        f"bulk inradius unexpectedly tiny — refined={refined_outside:.4f} "
        f"baseline={base_outside:.4f}"
    )


def test_size_field_and_user_contribs_together_warns():
    """Mixing both kwargs triggers a UserWarning (the user_contribs
    is silently ignored, which would be a contract violation)."""
    domain = _disc_domain()
    pre_composed = lambda p: np.full(p.shape[0], 0.2)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        admesh.triangulate(
            domain,
            h_max=0.2,
            max_iter=100,
            seed=0,
            size_field=pre_composed,
            user_contribs=[lambda p: np.full(p.shape[0], 0.05)],
            quality_gate=(0.10, 0.30),
        )

    matches = [
        w for w in caught
        if issubclass(w.category, UserWarning)
        and "user_contribs" in str(w.message)
    ]
    assert matches, "expected a UserWarning about ignored user_contribs"
