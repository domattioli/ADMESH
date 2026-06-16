# Tasks: Spec 028 — Fix demo custom-domain exitDrawMode ordering (#133)

**Spec:** [spec.md](spec.md) | **Plan:** [plan.md](plan.md)
**Issue:** [#133](https://github.com/domattioli/ADMESH/issues/133)

---

## Phase 1: Fix (single task)

- [x] T001 In `docs/demo/index.html`, before `if (drawMode) exitDrawMode()` (~line 899): add `const capturedVerts = (domainKey === "custom") ? drawVerts.slice() : null;`. Replace the `if (domainKey === "custom") { py.globals.set("_verts_json", ...) }` block (~line 919) with `if (capturedVerts !== null) { py.globals.set("_verts_json", JSON.stringify(capturedVerts)); }`.

## Phase 2: Optional hardening

- [x] T002 (optional) In the outer catch block, detect `ValueError` from Python and call `setComputeStatus("Draw at least 3 vertices to define a domain")` for better UX.

## Acceptance

- T001 done → draw ≥3 vertices, close, Compute → no ValueError.
- Named domains (l_shape, annulus, seamount) unaffected.

**Commit:** `fix: capture drawVerts before exitDrawMode in demo compute path (#133)`
