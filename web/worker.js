/* ADMESH browser worker. Runs Python (Pyodide) off the main thread.
   Messages in:  {type: "mesh", name, text, hMin, hMax}
   Messages out: {type: "status" | "ready" | "result" | "error" | "frame", ...} */

const PYODIDE_VERSION = "0.29.5";
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";
const DOMAIN_EXTENSIONS = [".json", ".toml", ".14"];

importScripts(PYODIDE_URL + "pyodide.js");

const PY_RUN = `
import json, os, time
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import admesh
from admesh.loaders import (
    load_domain_from_fort14, load_domain_from_json, load_domain_from_toml,
)

LOADERS = {".json": load_domain_from_json, ".toml": load_domain_from_toml,
           ".14": load_domain_from_fort14}
GRADING = 0.2  # growth of the target edge length per unit distance from the boundary (ADMESH default g)


def _checks(domain, nodes, tris):
    p = nodes[tris]
    area = 0.5 * ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
                  - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))
    bad_area = int(np.sum(area <= 0.0))
    xmin, ymin, xmax, ymax = domain.bbox
    tol = 1e-3 * float(np.hypot(xmax - xmin, ymax - ymin))
    outside = int(np.sum(np.asarray(domain.sdf(nodes)) > tol))
    edges = np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), axis=1)
    uniq, counts = np.unique(edges, axis=0, return_counts=True)
    over_shared = int(np.sum(counts > 2))
    boundary = uniq[counts == 1]
    degree = np.bincount(boundary.ravel(), minlength=len(nodes))
    open_nodes = int(np.sum((degree != 0) & (degree != 2)))
    return {
        "positive_area": {"ok": bad_area == 0, "count": bad_area},
        "inside_domain": {"ok": outside == 0, "count": outside},
        "watertight": {"ok": over_shared == 0 and open_nodes == 0,
                       "count": over_shared + open_nodes,
                       "boundary_edges": int(len(boundary))},
    }


def run(path, h_min, h_max, on_frame):
    ext = "." + path.rsplit(".", 1)[-1].lower()
    domain = LOADERS[ext](path)
    xmin, ymin, xmax, ymax = domain.bbox
    if h_max is None:
        h_max = max(float(np.hypot(xmax - xmin, ymax - ymin)) / 20.0, 1e-6)
    else:
        h_max = float(h_max)
    if h_min is None:
        h_min = h_max / 10.0
    else:
        h_min = float(h_min)

    # Sample the boundary distance once on a grid of spacing about h_min, because evaluating the signed distance at every size-field call doubles the meshing time.
    step = max(h_min, max(xmax - xmin, ymax - ymin) / 2000.0)
    pad = 2 * step
    gx = np.arange(xmin - pad, xmax + pad + step, step)
    gy = np.arange(ymin - pad, ymax + pad + step, step)
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    dist = np.abs(np.asarray(domain.sdf(np.c_[X.ravel(), Y.ravel()]), dtype=float)).reshape(X.shape)
    interp = RegularGridInterpolator((gx, gy), dist, bounds_error=False, fill_value=None)
    def coast(pts):
        return np.minimum(h_min + GRADING * interp(np.asarray(pts, dtype=float)), h_max)

    # Target edge length grows from h_min at the boundary by GRADING per unit distance, capped at h_max.
    # medial_method="grid" also refines narrow channels and lets the generator place points closer than h_max.
    kwargs = {"quality_gate": (0.0, 0.0), "h_min": h_min, "h_max": h_max, "user_contribs": (coast,), "medial_method": "grid"}

    if on_frame is not None:
        last_frame_time = time.monotonic()

        def on_iter(k, p, t):
            nonlocal last_frame_time
            now = time.monotonic()
            if k == 0 or (now - last_frame_time) >= 0.25:
                last_frame_time = now
                frame_json = json.dumps({
                    "nodes": p.ravel().round(6).tolist(),
                    "elements": t.ravel().tolist()
                })
                on_frame(k, frame_json)

        kwargs["on_iter"] = on_iter

    mesh = admesh.triangulate(domain, **kwargs)
    os.makedirs("/tmp/out", exist_ok=True)
    mesh.to_fort14("/tmp/out/mesh.14")
    mesh.to_msh("/tmp/out/mesh.msh")
    nodes = np.asarray(mesh.nodes, dtype=float)
    tris = np.asarray(mesh.elements, dtype=int)
    q = np.asarray(mesh.quality, dtype=float)
    with open("/tmp/out/mesh.14") as f:
        fort14 = f.read()
    with open("/tmp/out/mesh.msh") as f:
        msh = f.read()
    return json.dumps({
        "nodes": nodes.ravel().tolist(),
        "elements": tris.ravel().tolist(),
        "quality": q.tolist(),
        "stats": {"nodes": int(len(nodes)), "elements": int(len(tris)),
                  "minQuality": float(q.min()), "meanQuality": float(q.mean())},
        "checks": _checks(domain, nodes, tris),
        "fort14": fort14,
        "msh": msh,
    })
`;

let pyodide = null;
const ready = init();

function post(type, extra) {
  self.postMessage(Object.assign({ type }, extra));
}

async function init() {
  post("status", { text: "Loading Python runtime" });
  pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  post("status", { text: "Loading numpy, scipy and shapely" });
  await pyodide.loadPackage(["numpy", "scipy", "shapely", "micropip"]);
  post("status", { text: "Installing ADMESH" });
  const manifestUrl = new URL("wheels/manifest.json", self.location.href);
  const manifest = await (await fetch(manifestUrl)).json();
  const wheelUrl = new URL("wheels/" + manifest.wheel, self.location.href).href;
  const micropip = pyodide.pyimport("micropip");
  await micropip.install.callKwargs(wheelUrl, { deps: false });
  micropip.destroy();
  pyodide.runPython(PY_RUN);
  post("ready", { version: manifest.version });
}

function lastLine(text) {
  const lines = String(text).trim().split("\n").filter(Boolean);
  return lines.length ? lines[lines.length - 1] : "Unknown error";
}

function domainExtension(name) {
  const lower = String(name).toLowerCase();
  return DOMAIN_EXTENSIONS.find((ext) => lower.endsWith(ext)) || null;
}

async function mesh(msg) {
  if (!domainExtension(msg.name)) {
    post("error", {
      message:
        "'" + msg.name + "' is not a domain file. Upload a .json, .toml or fort.14 file. " +
        "Registry names are not looked up in the browser.",
    });
    return;
  }
  await ready;
  post("status", { text: "Computing element sizes" });
  const dir = "/tmp/domain";
  if (!pyodide.FS.analyzePath(dir).exists) pyodide.FS.mkdir(dir);
  const path = dir + "/" + msg.name.replace(/[^A-Za-z0-9._-]/g, "_");
  pyodide.FS.writeFile(path, msg.text);
  const run = pyodide.globals.get("run");
  const onFrame = (k, json) => post("frame", { iter: k, frame: JSON.parse(json) });
  try {
    const json = run(path, msg.hMin ?? undefined, msg.hMax ?? undefined, onFrame);
    post("result", { result: JSON.parse(json) });
  } finally {
    run.destroy();
  }
}

self.onmessage = async (event) => {
  if (event.data.type !== "mesh") return;
  try {
    await mesh(event.data);
  } catch (err) {
    post("error", { message: lastLine(err && err.message ? err.message : err) });
  }
};

ready.catch((err) => {
  post("error", { fatal: true, message: "Could not start Python: " + lastLine(err.message || err) });
});
