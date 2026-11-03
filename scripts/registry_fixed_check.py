"""One-off check: registry domains mesh with boundary="fixed".

Needs VALENCE_TOKEN in the environment. Prints counts only, never the token.

    python scripts/registry_fixed_check.py [slug ...]
"""

import sys
import time

import numpy as np

import admesh
from admesh.registry import list_available_domains, load_domain_from_registry

names = sys.argv[1:] or list(list_available_domains())[:3]
print("domains:", names)
for name in names:
    t = time.time()
    try:
        dom = load_domain_from_registry(name)
        ring = len(dom.pts) if dom.pts is not None else 0
        m = admesh.triangulate(dom, boundary="fixed", quality_gate=(0, 0))
        q = m.quality
        print(f"{name}: ring={ring} holes={len(dom.holes)} nodes={len(m.nodes)} "
              f"tris={len(m.elements)} qmin={q.min():.3f} qmean={q.mean():.2f} "
              f"bad={(q < 0.3).sum()} t={time.time() - t:.1f}s")
    except Exception as e:  # report and continue
        print(f"{name}: FAIL {type(e).__name__}: {str(e)[:200]}")
    sys.stdout.flush()
_ = np
