"""ENPAC octree benchmark — three lineages + oracle-cost isolation.

Research instrumentation (spec-029). Not product code.
Loads ENPAC (272,913-node ADCIRC tidal DB) boundary as admesh Domain,
benchmarks octree background-grid build:
  - main lineage  (object pointer tree, src/admesh/_stages/octree_grid.py)
  - branch #132   (flat-list, /tmp/octree_branch.py)
  - vec prototype (struct-of-arrays, batched oracle, /tmp/octree_vec.py)

Two regimes:
  A. STRUCTURAL — cheap analytic oracle, isolates octree machinery.
  B. REALISTIC  — real ENPAC SDF oracle (2 ms/pt), build cost = oracle-bound.
Counts SDF/oracle evaluations per impl (the real cost lever).
"""
from __future__ import annotations
import sys, time, numpy as np
sys.path.insert(0, "/tmp")
import admesh
from admesh._stages import octree_grid as om
import octree_branch as ob
import octree_vec as ov

ENPAC = "/home/user/Valence/registry_data/meshes/EasternPacific_ENPAC2003.14"


class CountingSDF:
    """Wrap a domain SDF; count total points evaluated."""
    def __init__(self, sdf):
        self.sdf = sdf
        self.n_calls = 0
        self.n_pts = 0

    def __call__(self, pts):
        pts = np.atleast_2d(pts)
        self.n_calls += 1
        self.n_pts += len(pts)
        return self.sdf(pts)


def run(ratio, h_max, dom, do_main=True, do_branch=True):
    bb = dom.bbox
    h_min = h_max / ratio
    print(f"\n=== ratio {ratio}  h_max={h_max}  h_min={h_min:.4f} ===")

    # --- vec prototype: batched oracle ---
    cs = CountingSDF(dom.sdf)
    oracle_batch = lambda pts: np.clip(np.abs(cs(pts)), h_min, h_max)
    t0 = time.perf_counter()
    lv = ov.build_quadtree(bb, h_min, h_max, oracle_batch, max_depth=16, padding=0.0, balance=True)
    t1 = time.perf_counter()
    ov.leaf_graph(lv); t2 = time.perf_counter()
    print(f"  vec   : {len(lv['cx']):>8} leaves | build {t1-t0:7.3f}s graph {t2-t1:6.3f}s "
          f"| oracle calls {cs.n_calls:>5} pts {cs.n_pts:>8}")

    # --- branch #132: per-cell scalar oracle ---
    if do_branch:
        cb = CountingSDF(dom.sdf)
        oracle_scalar = lambda x, y: float(np.clip(abs(cb(np.array([[x, y]]))[0]), h_min, h_max))
        class BDom:
            bbox = bb
            @staticmethod
            def fd(p): return cb(p)
        t0 = time.perf_counter()
        grid = ob.build_octree(BDom, h_min=h_min, h_max=h_max,
                               size_oracle=oracle_scalar, padding=0.0)
        t1 = time.perf_counter()
        print(f"  branch: {len(grid.leaves):>8} leaves | build {t1-t0:7.3f}s "
              f"| oracle calls {cb.n_calls:>5} pts {cb.n_pts:>8}")

    # --- main lineage: per-leaf-center SDF (distance-proxy size) ---
    if do_main:
        cm = CountingSDF(dom.sdf)
        class MDom:
            bbox = bb
            sdf = cm
        t0 = time.perf_counter()
        tree = om.build_octree(MDom, h_min=h_min, h_max=h_max, max_depth=16)
        t1 = time.perf_counter()
        om.leaf_graph(tree); t2 = time.perf_counter()
        print(f"  main  : {len(tree.leaves):>8} leaves | build {t1-t0:7.3f}s graph {t2-t1:6.3f}s "
              f"| oracle calls {cm.n_calls:>5} pts {cm.n_pts:>8}")


def structural(ratio, h_max, bbox):
    """Cheap analytic oracle — isolate octree machinery, no SDF."""
    h_min = h_max / ratio
    cx0 = 0.5 * (bbox[0] + bbox[2]); cy0 = 0.5 * (bbox[1] + bbox[3])
    # refine toward a diagonal feature line through domain
    def ana(pts):
        pts = np.atleast_2d(pts)
        d = np.abs((pts[:, 0] - bbox[0]) - (pts[:, 1] - bbox[1]))
        return np.clip(0.3 * d, h_min, h_max)
    t0 = time.perf_counter()
    lv = ov.build_quadtree(bbox, h_min, h_max, ana, max_depth=16, padding=0.0, balance=True)
    t1 = time.perf_counter(); ov.leaf_graph(lv); t2 = time.perf_counter()
    print(f"  STRUCT ratio {ratio:>4}: {len(lv['cx']):>8} leaves | "
          f"build {t1-t0:7.4f}s graph {t2-t1:6.4f}s (cheap oracle, vec)")


if __name__ == "__main__":
    print("Loading ENPAC domain (272,913-node boundary)...")
    t0 = time.perf_counter()
    dom = admesh.load_domain_from_fort14(ENPAC)
    print(f"load_domain_from_fort14: {time.perf_counter()-t0:.2f}s  bbox={dom.bbox}")
    bb = dom.bbox

    print("\n--- Regime A: STRUCTURAL (octree machinery only, no SDF) ---")
    for r in (10, 100, 1000):
        structural(r, 8.0, bb)

    print("\n--- Regime B: REALISTIC (real ENPAC SDF oracle, 2 ms/pt) ---")
    # ratio kept modest so per-cell impls finish; vec scales fine either way
    run(10, 8.0, dom, do_main=True, do_branch=True)
    run(40, 8.0, dom, do_main=False, do_branch=False)  # vec-only, larger
