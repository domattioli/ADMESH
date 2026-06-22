# Spec 028 — Fix demo custom-domain vertex loss on compute (exitDrawMode ordering)

**Status:** Planning. No code shipped in this commit (ADMESH planning profile).
**Issue:** [#133](https://github.com/domattioli/ADMESH/issues/133) — `type: bug`, `priority: normal`
**Branch:** `daily-maintenance` (plan) → implementation session
**Token budget:** TINY — single-file, single-block reorder in `docs/demo/index.html`.

---

## 1. Problem statement

When a user draws a custom polygon and clicks **Compute**, the browser demo raises:

```
ValueError: Custom domain needs at least 3 vertices
```

even though the polygon was fully drawn and properly closed (≥3 vertices, `drawClosed = true`).

---

## 2. Root cause

`docs/demo/index.html` — compute path (inside `async function` around line 856):

```
line 861:  if (domainKey === "custom" && !drawClosed) { /* early return */ }
           ...
line 899:  if (drawMode) exitDrawMode();   // ← clears drawVerts = []
           ...
line 919:  if (domainKey === "custom") {
line 920:    py.globals.set("_verts_json", JSON.stringify(drawVerts));  // now []
           }
```

`exitDrawMode()` (line 506) sets `drawVerts = []; drawClosed = false;` — its purpose is to clean the draw canvas and disable draw UI. When the user draws a polygon and then clicks Compute while still in draw mode (`drawMode === true`), `exitDrawMode()` runs first and empties `drawVerts`. The subsequent `JSON.stringify(drawVerts)` sends `"[]"` to Python, which then raises `ValueError: Custom domain needs at least 3 vertices` (line 757).

The guard at line 861 only checks `drawClosed` — which is `true` at that point — so the early-return does not fire, and the ordering bug reaches Python.

**Reproducible scenario:**
1. Select "Custom — draw your own domain" from domain selector.
2. Draw ≥3 vertices, close the polygon (snap-to-first or double-click).
3. `drawClosed = true`, `drawMode = true`, `drawVerts.length >= 3`.
4. Click **Compute**.
5. `exitDrawMode()` fires → `drawVerts = []`.
6. Python receives `_verts_json = "[]"` → ValueError.

---

## 3. Fix

Capture vertex data before `exitDrawMode()` clears `drawVerts`:

**Option A — capture before exit (minimal, preferred):**

```javascript
// line ~899 block — reorder: capture THEN exit
const capturedVerts = (domainKey === "custom") ? drawVerts.slice() : null;
if (drawMode) exitDrawMode();
// ... existing live-player seeding ...
if (capturedVerts !== null) {
  py.globals.set("_verts_json", JSON.stringify(capturedVerts));
}
// Remove the existing lines 919-921 block (now handled above)
```

**Option B — move the py.globals.set call before exitDrawMode:**

Move lines 919-921 (`py.globals.set("_verts_json", ...)`) to before line 899. Simpler diff, same fix.

Option A is preferred because it makes the intent explicit: `capturedVerts` is the snapshot at click time; `exitDrawMode()` can safely clear `drawVerts` afterwards.

---

## 4. Secondary hardening (same PR)

Two optional improvements to add in the same HTML edit:

1. **User-facing error UX**: catch `ValueError` in Python error handler and surface it as `setComputeStatus("Draw at least 3 vertices to define a domain")` instead of a bare Python traceback. The demo already has a try/catch in the outer compute block — add a message check there.

2. **Degenerate vertex guard (Python side)**: after line 757, also check for collinear or duplicate vertices that would produce a zero-area polygon. Raise a descriptive error if detected (e.g. `"Custom domain has zero area — ensure vertices are not collinear"`). Low priority; the SDF will produce a degenerate distance field before reaching distmesh.

Both are optional. The ordering fix (§3) is the mandatory acceptance criterion.

---

## 5. Files touched

| File | Change |
|---|---|
| `docs/demo/index.html` | Reorder `py.globals.set("_verts_json", ...)` before `exitDrawMode()` call (~2–5 line change) |

No Python package files change. No spec-kit sub-specs. No MATLAB parity concern.

---

## 6. Acceptance criteria

- [ ] Drawing a polygon (≥3 vertices, closed), clicking Compute: no `ValueError`.
- [ ] Drawing a partial polygon (< 3 vertices) and attempting to compute: demo shows "Draw and close a polygon first" (existing guard at line 861, unchanged).
- [ ] Navigating away and back, then drawing + computing: no regression.
- [ ] The fix does not affect the l_shape, annulus, or seamount domain paths.

---

## 7. Out of scope

- Refactoring the demo Python worker into a separate `.py` file (tracked separately).
- Adding automated tests for the demo HTML (no test harness exists for the in-browser Pyodide environment).
- Fixing any other demo issues (issue #23 animation demo, etc.).
