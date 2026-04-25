"""Tests for ``admesh.size_field.compose_size_field`` (T036–T039)."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from admesh.size_field import compose_size_field


# ---------------------------------------------------------------------------
# Test point set
# ---------------------------------------------------------------------------


@pytest.fixture
def pts() -> np.ndarray:
    return np.array(
        [[0.0, 0.0], [0.5, 0.0], [1.0, 0.0], [1.5, 0.0], [2.0, 0.0]],
        dtype=np.float64,
    )


# ---------------------------------------------------------------------------
# T036 — Phase-1 isolation: builtins-only path is pure min-stack
# ---------------------------------------------------------------------------


def test_phase1_min_stack_two_builtins(pts):
    f1 = lambda p: np.full(p.shape[0], 0.5)
    f2 = lambda p: 0.1 + 0.2 * np.abs(p[:, 0])
    sf = compose_size_field(builtins=[f1, f2])
    expected = np.minimum(f1(pts), f2(pts))
    np.testing.assert_allclose(sf(pts), expected, atol=1e-12)


def test_phase1_min_stack_ignores_combine(pts):
    """`combine` does NOT leak into Phase 1 — Constitution Principle I."""
    f1 = lambda p: np.full(p.shape[0], 0.5)
    f2 = lambda p: np.full(p.shape[0], 0.2)
    # Even with a max combiner, the builtins-only result is the min.
    sf = compose_size_field(
        builtins=[f1, f2], user_contribs=[], combine=np.maximum.reduce
    )
    np.testing.assert_allclose(sf(pts), np.full(pts.shape[0], 0.2), atol=1e-12)


def test_phase1_no_builtins_returns_inf(pts):
    sf = compose_size_field(builtins=[])
    result = sf(pts)
    assert np.all(np.isinf(result))


# ---------------------------------------------------------------------------
# T037 — Phase-2 default combiner is elementwise min
# ---------------------------------------------------------------------------


def test_phase2_default_min(pts):
    builtin = lambda p: np.full(p.shape[0], 0.5)
    user = lambda p: np.full(p.shape[0], 0.2)
    sf = compose_size_field(builtins=[builtin], user_contribs=[user])
    np.testing.assert_allclose(sf(pts), np.full(pts.shape[0], 0.2), atol=1e-12)


def test_phase2_user_can_only_refine_with_default_combiner(pts):
    """User contribs combined via min => never coarser than Phase 1."""
    builtin = lambda p: np.full(p.shape[0], 0.3)
    user_coarse = lambda p: np.full(p.shape[0], 0.9)  # tries to be coarser
    sf = compose_size_field(builtins=[builtin], user_contribs=[user_coarse])
    np.testing.assert_allclose(sf(pts), np.full(pts.shape[0], 0.3), atol=1e-12)


# ---------------------------------------------------------------------------
# T038 — Phase-2 custom combiner
# ---------------------------------------------------------------------------


def test_phase2_max_combiner(pts):
    builtin = lambda p: np.full(p.shape[0], 0.3)
    user = lambda p: np.full(p.shape[0], 0.9)
    sf = compose_size_field(
        builtins=[builtin], user_contribs=[user], combine=np.maximum.reduce
    )
    # max(0.3, 0.9) = 0.9 elementwise.
    np.testing.assert_allclose(sf(pts), np.full(pts.shape[0], 0.9), atol=1e-12)


def test_phase2_custom_combiner_does_not_leak_into_phase1(pts):
    """Two builtins min-stack first; user contrib then maxes against that."""
    f1 = lambda p: np.full(p.shape[0], 0.3)
    f2 = lambda p: np.full(p.shape[0], 0.6)  # min(0.3, 0.6) = 0.3
    user = lambda p: np.full(p.shape[0], 0.9)
    sf = compose_size_field(
        builtins=[f1, f2], user_contribs=[user], combine=np.maximum.reduce
    )
    # Phase-1 result is 0.3 (min); Phase-2 max with 0.9 is 0.9.
    np.testing.assert_allclose(sf(pts), np.full(pts.shape[0], 0.9), atol=1e-12)


# ---------------------------------------------------------------------------
# T039 — invalid user values: clamp + UserWarning
# ---------------------------------------------------------------------------


def test_user_contrib_nan_clamped_with_warning(pts):
    def naughty(p: np.ndarray) -> np.ndarray:
        out = np.full(p.shape[0], 0.2)
        out[0] = np.nan
        return out

    sf = compose_size_field(
        builtins=[lambda p: np.full(p.shape[0], 0.5)],
        user_contribs=[naughty],
        hmin=0.05,
        hmax=1.0,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = sf(pts)

    user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
    assert user_warnings, "expected a UserWarning naming the contribution"
    msg = str(user_warnings[0].message)
    assert "naughty" in msg
    assert "1" in msg  # affected count
    # Output remains finite within bounds.
    assert np.all(np.isfinite(result))


def test_user_contrib_negative_clamped_with_warning(pts):
    def negative(p: np.ndarray) -> np.ndarray:
        out = np.full(p.shape[0], 0.2)
        out[0] = -0.5
        out[1] = 0.0
        return out

    sf = compose_size_field(
        builtins=[lambda p: np.full(p.shape[0], 0.5)],
        user_contribs=[negative],
        hmin=0.05,
        hmax=1.0,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sf(pts)

    user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
    assert user_warnings
    msg = str(user_warnings[0].message)
    assert "negative" in msg
    assert "2" in msg  # two clamps


def test_clean_user_contrib_does_not_warn(pts):
    sf = compose_size_field(
        builtins=[lambda p: np.full(p.shape[0], 0.5)],
        user_contribs=[lambda p: np.full(p.shape[0], 0.2)],
        hmin=0.05,
        hmax=1.0,
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sf(pts)
    assert not [w for w in caught if issubclass(w.category, UserWarning)]


def test_user_contrib_above_hmax_clamped(pts):
    def too_big(p: np.ndarray) -> np.ndarray:
        return np.full(p.shape[0], 5.0)  # above hmax=1.0

    sf = compose_size_field(
        builtins=[lambda p: np.full(p.shape[0], 0.5)],
        user_contribs=[too_big],
        hmin=0.05,
        hmax=1.0,
        combine=np.maximum.reduce,
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = sf(pts)
    user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
    assert user_warnings
    # After clamping, value is hmax=1.0; max(0.5, 1.0) = 1.0.
    np.testing.assert_allclose(result, np.full(pts.shape[0], 1.0))


# ---------------------------------------------------------------------------
# Shape validation
# ---------------------------------------------------------------------------


def test_input_shape_validation():
    sf = compose_size_field(builtins=[lambda p: np.zeros(p.shape[0])])
    with pytest.raises(ValueError, match=r"\(N, 2\)"):
        sf(np.array([1.0, 2.0, 3.0]))


def test_output_shape_validation_from_contribution(pts):
    sf = compose_size_field(
        builtins=[lambda p: np.zeros(p.shape[0] + 1)],  # wrong length
    )
    with pytest.raises(ValueError, match="returned shape"):
        sf(pts)
