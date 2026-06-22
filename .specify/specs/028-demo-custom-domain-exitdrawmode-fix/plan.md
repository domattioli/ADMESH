# Plan: Spec 028 — demo custom-domain exitDrawMode ordering fix

**Issue:** [#133](https://github.com/domattioli/ADMESH/issues/133)
**Spec:** [spec.md](spec.md)
**Effort:** TINY — single-file reorder.

## Implementation steps

1. Open `docs/demo/index.html`.
2. Locate the compute function block around line 899.
3. Insert `const capturedVerts = (domainKey === "custom") ? drawVerts.slice() : null;` immediately before `if (drawMode) exitDrawMode();`.
4. Replace the `if (domainKey === "custom") { py.globals.set("_verts_json", ...) }` block (lines 919-921) with `if (capturedVerts !== null) { py.globals.set("_verts_json", JSON.stringify(capturedVerts)); }`.
5. Optional: add user-friendly error message in the outer catch (secondary hardening §4 of spec).

## Validation

- Manual browser test: draw ≥3 vertices, close polygon, click Compute — no ValueError.
- Inspect `_verts_json` in Python via `print(len(_json.loads(_verts_json)))` — should be ≥3.
- Confirm named domains (l_shape, annulus, seamount) still compute correctly.

## Commit message

```
fix: capture drawVerts before exitDrawMode in demo compute path (#133)
```
