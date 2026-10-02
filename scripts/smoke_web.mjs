// Smoke test for the browser app: install the built wheel in Pyodide and mesh
// a small annulus.
//
// Usage: node scripts/smoke_web.mjs <path to pyodide module> <path to web_dist>
//          [<domain.json> <h_min> <h_max>]
//   e.g. node scripts/smoke_web.mjs node_modules/pyodide/pyodide.mjs web_dist
//        node scripts/smoke_web.mjs node_modules/pyodide/pyodide.mjs web_dist \
//          web/examples/wnat.json 0.3 0.5
//
// Without a domain the test meshes a small annulus. With a domain file it
// meshes that file with the given h_min and h_max and also prints the meshing
// time in seconds.
//
// Prints "nodes=<n> elements=<m> valid=<True|False>" and exits non-zero unless
// nodes > 0, elements > 0 and valid is True.
import { readFileSync } from "node:fs";
import { resolve, join } from "node:path";
import { pathToFileURL } from "node:url";

const [, , pyodidePath, distPath, domainPath, hMinArg, hMaxArg] = process.argv;
if (!pyodidePath || !distPath) {
  console.error("usage: node scripts/smoke_web.mjs <pyodide module path> <web_dist path> [<domain.json> <h_min> <h_max>]");
  process.exit(2);
}

const { loadPyodide } = await import(pathToFileURL(resolve(pyodidePath)).href);
const wheelsDir = resolve(distPath, "wheels");
const manifest = JSON.parse(readFileSync(join(wheelsDir, "manifest.json"), "utf8"));

// Annulus: outer circle radius 1, inner circle radius 0.4, 48 points each.
function ring(radius, n) {
  return Array.from({ length: n }, (_, i) => {
    const a = (2 * Math.PI * i) / n;
    return [Number((radius * Math.cos(a)).toFixed(6)), Number((radius * Math.sin(a)).toFixed(6))];
  });
}
const annulus = JSON.stringify({
  name: "annulus",
  bbox: [-1, -1, 1, 1],
  rings: [ring(1.0, 48), ring(0.4, 24).reverse()],
});

const pyodide = await loadPyodide();
await pyodide.loadPackage(["numpy", "scipy", "shapely", "micropip"]);
pyodide.FS.mkdir("/wheels");
pyodide.FS.writeFile("/wheels/" + manifest.wheel, readFileSync(join(wheelsDir, manifest.wheel)));
pyodide.FS.writeFile("/annulus.json", domainPath ? readFileSync(resolve(domainPath), "utf8") : annulus);
const hMin = domainPath ? Number(hMinArg) : undefined;
const hMax = domainPath ? Number(hMaxArg) : 0.2;
if (domainPath && !(hMin > 0 && hMax >= hMin)) {
  console.error("h_min and h_max must be positive numbers with h_min <= h_max");
  process.exit(2);
}
pyodide.globals.set("h_min", hMin);
pyodide.globals.set("h_max", hMax);

const micropip = pyodide.pyimport("micropip");
await micropip.install.callKwargs("emfs:/wheels/" + manifest.wheel, { deps: false });

const out = await pyodide.runPythonAsync(`
import numpy as np
import admesh
from admesh.loaders import load_domain_from_json

import time
domain = load_domain_from_json("/annulus.json")
kwargs = {"h_max": float(h_max), "quality_gate": (0.0, 0.0)}
if h_min is not None:
    kwargs["h_min"] = float(h_min)
t0 = time.perf_counter()
mesh = admesh.triangulate(domain, **kwargs)
seconds = time.perf_counter() - t0
p = mesh.nodes[mesh.elements]
area = 0.5 * ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
              - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))
inside = bool(np.all(np.asarray(domain.sdf(mesh.nodes)) < 1e-2))
valid = bool(np.all(area > 0)) and inside
print(f"seconds={seconds:.1f}")
f"nodes={mesh.n_nodes} elements={mesh.n_elements} valid={valid}"
`);
console.log(out);
const m = /nodes=(\d+) elements=(\d+) valid=(True|False)/.exec(out);
process.exit(m && Number(m[1]) > 0 && Number(m[2]) > 0 && m[3] === "True" ? 0 : 1);
