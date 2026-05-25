# Contract: Per-Stage Parity Gate

The test contract every ported stage must satisfy (FR-003, US3, Principle I).
The MATLAB `.npz` fixtures are the authoritative oracle (Constitution Art V.2).

## Gate

For each stage, a test loads the fixture **input**, runs the **C++** stage, and
asserts the output against the fixture **expected** at the stage's tolerance.
A stage is "ported" only when this is green.

```python
# tests/test_<stage>.py — augmented, not replaced
@pytest.mark.parametrize("backend", ["python", "cpp"])
def test_<stage>_matches_matlab_fixture(backend, fixture):
    inp, expected = load_npz(fixture)            # MATLAB oracle
    got = run_stage("<stage>", inp, backend=backend)
    assert_parity(got, expected, mode=PARITY_MODE["<stage>"])
```

- `python` param: existing locked Numba fallback (must stay green — Art VI.6).
- `cpp` param: the new native stage. Mid-port, **both** are checked against the
  same fixture (US3 scenario 2).

## Parity modes

| Mode | Assertion | Build constraint |
|---|---|---|
| `bit_parity` | `np.allclose(got, expected, atol=1e-8, rtol=1e-6)` | no `-ffast-math`, `-ffp-contract=off`, pinned reduction order (FR-005), fixed-baseline ISA (R3) |
| `relaxed` | documented per-stage assertion (e.g. count match + quality within tol) | rationale recorded in the test docstring (FR-003) |

Mode per stage: see [research.md R8](../research.md). Bit-parity is default;
`relaxed` requires a written rationale or the gate rejects it.

## Relaxed-stage rule

A `relaxed` stage MUST document, in its test docstring:
1. **why** bit-parity is costly (e.g. Triangle replaces scipy Delaunay → different
   node counts; transcendental/order-sensitive SDF eval),
2. the **exact** tolerance / metric used (counts within X%, `min_q`/`mean_q`
   within Y),
3. that the divergence is **algorithmic, not a port bug** (Art IV.6).

Widening tolerance to make a bit-parity stage pass is forbidden (Art IV.6) —
divergence is a bug until proven structural.

## Standalone C++ gate (no Python)

Independent of pytest: `admesh-cpp/tests/` (ctest) meshes the MVP domains + WNAT
and asserts node/element counts + quality within tolerance — **no Python in the
process** (SC-002).
