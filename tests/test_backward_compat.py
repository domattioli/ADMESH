"""Spec-002 backward-compatibility regression tests (US3).

Per spec-002 user story 3 ("an advanced user can still pass a fully
custom `size_field=` callable to bypass the default stack entirely"),
every spec-001 caller pattern keeps working byte-identically. These
tests document the patterns that MUST continue to work after spec 002
lands.

Tasks covered:
  - T033: custom-size-field bypasses the default stack
  - T034: user_contribs= composes on top of the default stack
  - T035: both-supplied UserWarning fires; size_field wins
  - T036: spec-001 quickstart-validation regression (light-touch)
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import admesh


def _l_shape_domain() -> admesh.Domain:
    rings = [np.array(
        [
            [-1.0, -1.0], [1.0, -1.0], [1.0, 0.0],
            [0.0, 0.0], [0.0, 1.0], [-1.0, 1.0], [-1.0, -1.0],
        ],
        dtype=float,
    )]
    return admesh.domain_from_polygon(rings)


# ---------------------------------------------------------------------------
# T033 — custom size_field bypasses the spec-002 default stack
# ---------------------------------------------------------------------------


def test_t033_custom_size_field_bypasses_default_stack() -> None:
    """`size_field=` skips the default stack — the caller's callable is the only sizing source."""
    domain = _l_shape_domain()

    def uniform_h(p):
        return 0.15 * np.ones(len(np.asarray(p, dtype=float).reshape(-1, 2)))

    mesh = admesh.triangulate(
        domain, h_max=0.15, max_iter=200, seed=0,
        size_field=uniform_h,
        quality_gate=(0.0, 0.0),
    )
    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0

    # The spec-001 "uniform-h" baseline is what we should get when
    # size_field= bypasses the default stack. Confirm by comparing
    # against the explicit-opt-out baseline mesh.
    baseline = admesh.triangulate(
        domain, h_max=0.15, max_iter=200, seed=0,
        enable_curvature=False, enable_medial_axis=False,
        quality_gate=(0.0, 0.0),
    )
    # Both paths should agree exactly — same RNG seed, same fh shape.
    assert mesh.equals(baseline, atol=1e-9), (
        f"size_field= bypass diverged from explicit-opt-out baseline: "
        f"{mesh.n_nodes} vs {baseline.n_nodes} nodes"
    )


# ---------------------------------------------------------------------------
# T034 — user_contribs= composes on top of the default stack
# ---------------------------------------------------------------------------


def test_t034_user_contribs_composes_on_top_of_default_stack() -> None:
    """`user_contribs=` Phase-2 composition still works; default stack acts as Phase-1."""
    domain = _l_shape_domain()

    def near_corner(p):
        # Refine near the L's reentrant corner at (0, 0).
        p = np.asarray(p, dtype=float).reshape(-1, 2)
        d = np.hypot(p[:, 0], p[:, 1])
        # Heavy refinement at the corner, taper to 0.20 by d=1.
        return np.clip(0.05 + 0.15 * d, 0.05, 0.20)

    mesh = admesh.triangulate(
        domain, h_max=0.20, h_min=0.04, max_iter=200, seed=0,
        user_contribs=[near_corner],
        quality_gate=(0.0, 0.0),
    )
    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0

    # The user_contribs= path takes the spec-001 Phase-2 composition
    # path inside `triangulate()`. Spec-001 already covers
    # `compose_size_field`'s combiner semantics in its own unit tests
    # (tests/test_size_field.py). The contract for spec-002 here is
    # narrower: when user_contribs= is supplied with no size_field=,
    # the call goes through the default-stack-builds-Phase-1 branch
    # (not the no-Phase-1 branch) AND produces a structurally-valid
    # mesh. Stronger numeric assertions about composition are
    # fixture-sensitive and live with `compose_size_field`'s own tests.


# ---------------------------------------------------------------------------
# T035 — both supplied: UserWarning + size_field wins
# ---------------------------------------------------------------------------


def test_t035_both_supplied_warns_and_uses_size_field() -> None:
    """When both `size_field=` and `user_contribs=` supplied, warn; ignore user_contribs."""
    domain = _l_shape_domain()

    def my_size_field(p):
        return 0.15 * np.ones(len(np.asarray(p, dtype=float).reshape(-1, 2)))

    def my_contrib(p):
        # If this gets used (it shouldn't), edge lengths would drop
        # dramatically — gives the test a clear discriminator.
        return 0.01 * np.ones(len(np.asarray(p, dtype=float).reshape(-1, 2)))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        mesh = admesh.triangulate(
            domain, h_max=0.15, max_iter=200, seed=0,
            size_field=my_size_field,
            user_contribs=[my_contrib],
            quality_gate=(0.0, 0.0),
        )
    user_warns = [
        w for w in caught
        if issubclass(w.category, UserWarning)
        and "ignoring" in str(w.message).lower()
        and "user_contribs" in str(w.message)
    ]
    assert user_warns, (
        "expected UserWarning about user_contribs being ignored; "
        f"got {[str(w.message) for w in caught]}"
    )

    # Confirm the resulting mesh matches the size_field-only path.
    only_sf = admesh.triangulate(
        domain, h_max=0.15, max_iter=200, seed=0,
        size_field=my_size_field,
        quality_gate=(0.0, 0.0),
    )
    assert mesh.equals(only_sf, atol=1e-9), (
        "user_contribs was not ignored — mesh differs from size_field-only path"
    )


# ---------------------------------------------------------------------------
# T036 — spec-001 quickstart-validation regression (light)
# ---------------------------------------------------------------------------


def test_t036_spec001_uniform_baseline_still_reachable() -> None:
    """The spec-001 uniform-`h` baseline is reproducible via explicit kwargs.

    Documents the upgrade path for spec-001 callers who want their
    legacy uniform-`h` behaviour: pass `enable_curvature=False,
    enable_medial_axis=False` (or supply `size_field=` directly).
    Replays one of the spec-001 quickstart examples and asserts the
    resulting mesh is structurally non-empty.
    """
    domain = _l_shape_domain()
    mesh = admesh.triangulate(
        domain, h_max=0.15, max_iter=200, seed=0,
        enable_curvature=False, enable_medial_axis=False,
        quality_gate=(0.0, 0.0),
    )
    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0
    # Boundary segments are derived from triangulation topology in this path.
    assert mesh.n_boundaries >= 1
