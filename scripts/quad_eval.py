#!/usr/bin/env python
"""Headless evaluation script for quad-intent triangulation.

Generates two meshes (default vs quad_intent) on a given domain, computes
comprehensive quad-readiness metrics, and produces plots + JSON + markdown
summary.

Usage:
    python scripts/quad_eval.py --domain unit_disk --h 0.12 --outdir output/quad_eval

Outputs:
    - <domain>_metrics.json: raw metrics as JSON
    - <domain>_summary.md: markdown summary table
    - <domain>_mesh_overlay.png, <domain>_valence_hist.png, etc.: 7 PNG plots
"""

import sys
from pathlib import Path

# Ensure ADMESH can be imported
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import argparse
import json
import os
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import admesh
from admesh import quad_metrics
from admesh._stages.domains import UNIT_DISK, L_SHAPE, ANNULUS, UNIT_SQUARE, NOTCHED_RECTANGLE

# Map domain name to Domain object
DOMAIN_MAP = {
    "unit_disk": UNIT_DISK,
    "l_shape": L_SHAPE,
    "annulus": ANNULUS,
    "unit_square": UNIT_SQUARE,
    "notched_rectangle": NOTCHED_RECTANGLE,
}


def layer_metrics(mesh: "admesh.Mesh") -> dict:
    """Extract layer-based metrics via chilmesh if available.

    Returns a dict with:
    - "n_layers": int
    - "layer_imbalances": list of per-layer parity imbalances
    - "total_imbalance": sum of imbalances
    - "alternation_defects": proxy for OE-IE adjacency defects (placeholder)
    - "error": str (if chilmesh fails)

    Robust: returns empty dict if chilmesh unavailable or errors.
    """
    try:
        import chilmesh as c
        cm = c.CHILmesh(connectivity=mesh.elements, points=mesh.nodes, compute_layers=True)

        # Discover number of layers
        n_layers = None
        if isinstance(cm.Layers, int):
            n_layers = cm.Layers
        else:
            # Try to call get_layer in a loop
            try:
                i = 0
                while True:
                    _ = cm.get_layer(i)
                    i += 1
            except (IndexError, Exception):
                n_layers = i

        if n_layers is None or n_layers == 0:
            return {}

        # Per-layer imbalance: |len(OE) - len(IE)|
        layer_imbalances = []
        for i in range(n_layers):
            try:
                layer = cm.get_layer(i)
                oe = layer.get("OE", np.array([]))
                ie = layer.get("IE", np.array([]))
                imbalance = abs(len(oe) - len(ie))
                layer_imbalances.append(imbalance)
            except Exception:
                layer_imbalances.append(0)

        return {
            "n_layers": n_layers,
            "layer_imbalances": layer_imbalances,
            "total_imbalance": sum(layer_imbalances),
            "alternation_defects": 0,  # placeholder
        }
    except ImportError:
        return {}
    except Exception:
        return {}


def plot_mesh_overlay(m0: "admesh.Mesh", m1: "admesh.Mesh", outdir: Path, domain_name: str):
    """Plot 1x2 triplot of default vs quad_intent meshes."""
    try:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle(f"Mesh Overlay: {domain_name.upper()}", fontsize=14)

        for ax, mesh, title in zip(axes, [m0, m1], ["Default", "Quad-Intent"]):
            ax.triplot(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.elements, linewidth=0.5)
            ax.set_aspect("equal")
            ax.set_title(title)
            ax.set_xlabel("x")
            ax.set_ylabel("y")

        plt.tight_layout()
        out = outdir / f"{domain_name}_mesh_overlay.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Wrote {out}")
    except Exception as e:
        print(f"  ERROR: mesh_overlay plot failed: {e}")


def plot_valence_histogram(m0: "admesh.Mesh", m1: "admesh.Mesh", outdir: Path, domain_name: str):
    """Plot valence histograms for default vs quad_intent."""
    try:
        h0 = quad_metrics.interior_valence_histogram(m0)
        h1 = quad_metrics.interior_valence_histogram(m1)

        all_vals = sorted(set(list(h0.keys()) + list(h1.keys())))
        if not all_vals:
            return

        counts0 = [h0.get(v, 0) for v in all_vals]
        counts1 = [h1.get(v, 0) for v in all_vals]

        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(len(all_vals))
        width = 0.35
        ax.bar(x - width / 2, counts0, width, label="Default", alpha=0.7)
        ax.bar(x + width / 2, counts1, width, label="Quad-Intent", alpha=0.7)
        ax.axvline(7, color="red", linestyle="--", linewidth=1, label="Ideal (8)")
        ax.axvline(5, color="orange", linestyle="--", linewidth=1, label="Min (6)")
        ax.set_xlabel("Valence")
        ax.set_ylabel("Count")
        ax.set_title(f"Interior Valence Histogram: {domain_name.upper()}")
        ax.set_xticks(x)
        ax.set_xticklabels(all_vals)
        ax.legend()
        plt.tight_layout()
        out = outdir / f"{domain_name}_valence_hist.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Wrote {out}")
    except Exception as e:
        print(f"  ERROR: valence_hist plot failed: {e}")


def plot_valence_heatmap(m0: "admesh.Mesh", m1: "admesh.Mesh", outdir: Path, domain_name: str):
    """Plot 1x2 scatter of interior node valence."""
    try:
        from admesh.valence import compute_valence, _boundary_mask

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle(f"Interior Node Valence: {domain_name.upper()}", fontsize=14)

        for ax, mesh, title in zip(axes, [m0, m1], ["Default", "Quad-Intent"]):
            valence = compute_valence(mesh.elements)
            boundary = _boundary_mask(mesh)
            interior_mask = ~boundary
            interior_nodes = mesh.nodes[interior_mask]
            interior_valence = valence[interior_mask]

            if len(interior_nodes) > 0:
                sc = ax.scatter(interior_nodes[:, 0], interior_nodes[:, 1],
                              c=interior_valence, cmap="RdYlBu_r", s=20, alpha=0.6, edgecolors="none")
                plt.colorbar(sc, ax=ax, label="Valence")
            ax.set_aspect("equal")
            ax.set_title(title)
            ax.set_xlabel("x")
            ax.set_ylabel("y")

        plt.tight_layout()
        out = outdir / f"{domain_name}_valence_heatmap.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Wrote {out}")
    except Exception as e:
        print(f"  ERROR: valence_heatmap plot failed: {e}")


def plot_layers(m0: "admesh.Mesh", m1: "admesh.Mesh", outdir: Path, domain_name: str):
    """Plot 1x2 layers (onion-peel) via chilmesh or placeholder."""
    try:
        import chilmesh as c
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle(f"Layer Structure (Onion-Peel): {domain_name.upper()}", fontsize=14)

        for ax, mesh, title in zip(axes, [m0, m1], ["Default", "Quad-Intent"]):
            try:
                cm = c.CHILmesh(connectivity=mesh.elements, points=mesh.nodes, compute_layers=True)
                # Get layer count
                n_layers = cm.Layers if isinstance(cm.Layers, int) else 0
                if n_layers == 0:
                    try:
                        i = 0
                        while True:
                            cm.get_layer(i)
                            i += 1
                    except (IndexError, Exception):
                        n_layers = i

                if n_layers > 0:
                    # Assign each element to a layer color
                    elem_colors = np.zeros(mesh.n_elements)
                    for layer_idx in range(n_layers):
                        try:
                            layer = cm.get_layer(layer_idx)
                            elem_ids = layer.get("elements", np.array([], dtype=int))
                            for eid in elem_ids:
                                if 0 <= eid < mesh.n_elements:
                                    elem_colors[eid] = layer_idx
                        except Exception:
                            pass

                    tc = ax.tripcolor(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.elements,
                                    facecolors=elem_colors, cmap="viridis", edgecolors="none")
                    ax.set_aspect("equal")
                    ax.set_title(title)
                    ax.set_xlabel("x")
                    ax.set_ylabel("y")
                else:
                    ax.text(0.5, 0.5, "No layers found", ha="center", va="center", transform=ax.transAxes)
                    ax.set_title(title)
            except Exception:
                ax.text(0.5, 0.5, "chilmesh error", ha="center", va="center", transform=ax.transAxes)
                ax.set_title(title)

        plt.tight_layout()
        out = outdir / f"{domain_name}_layers.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Wrote {out}")
    except ImportError:
        # chilmesh not available; write placeholder
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle(f"Layer Structure (Onion-Peel): {domain_name.upper()}", fontsize=14)
        for ax in axes:
            ax.text(0.5, 0.5, "chilmesh unavailable", ha="center", va="center", transform=ax.transAxes)
        plt.tight_layout()
        out = outdir / f"{domain_name}_layers.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Wrote {out} (placeholder)")
    except Exception as e:
        print(f"  ERROR: layers plot failed: {e}")


def plot_iso_dev(m0: "admesh.Mesh", m1: "admesh.Mesh", outdir: Path, domain_name: str):
    """Plot 1x2 tripcolor of isotropy deviation."""
    try:
        iso0 = quad_metrics.iso_dev(m0.nodes, m0.elements)
        iso1 = quad_metrics.iso_dev(m1.nodes, m1.elements)

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle(f"Isotropy Deviation (degrees): {domain_name.upper()}", fontsize=14)

        for ax, mesh, iso, title in zip(axes, [m0, m1], [iso0, iso1], ["Default", "Quad-Intent"]):
            tc = ax.tripcolor(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.elements,
                            facecolors=iso, cmap="RdYlGn_r", edgecolors="none")
            ax.set_aspect("equal")
            ax.set_title(title)
            ax.set_xlabel("x")
            ax.set_ylabel("y")

        cbar = fig.colorbar(tc, ax=axes, label="Deviation (°)")
        plt.tight_layout()
        out = outdir / f"{domain_name}_iso_dev.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Wrote {out}")
    except Exception as e:
        print(f"  ERROR: iso_dev plot failed: {e}")


def plot_fidelity_histogram(m0: "admesh.Mesh", m1: "admesh.Mesh", outdir: Path, domain_name: str):
    """Plot overlaid histograms of edge fidelity ratio."""
    try:
        fid0 = quad_metrics.edge_fidelity(m0.nodes, m0.elements)
        fid1 = quad_metrics.edge_fidelity(m1.nodes, m1.elements)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(fid0["ratios"], bins=30, alpha=0.6, label="Default", edgecolor="black")
        ax.hist(fid1["ratios"], bins=30, alpha=0.6, label="Quad-Intent", edgecolor="black")
        ax.axvline(0.7, color="red", linestyle="--", linewidth=1, label="Band [0.7, 1.4]")
        ax.axvline(1.4, color="red", linestyle="--", linewidth=1)
        ax.set_xlabel("Edge Length Ratio (actual / target)")
        ax.set_ylabel("Count")
        ax.set_title(f"Edge Fidelity Histogram: {domain_name.upper()}")
        ax.legend()
        plt.tight_layout()
        out = outdir / f"{domain_name}_fidelity_hist.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Wrote {out}")
    except Exception as e:
        print(f"  ERROR: fidelity_hist plot failed: {e}")


def plot_quad_preview(m0: "admesh.Mesh", m1: "admesh.Mesh", outdir: Path, domain_name: str):
    """Plot 1x2 merged quads colored by quality, unpaired tris in light gray."""
    try:
        from admesh.quad_prep import _build_pairing_map

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle(f"Quad Preview (Merged Triangles): {domain_name.upper()}", fontsize=14)

        for ax, mesh, title in zip(axes, [m0, m1], ["Default", "Quad-Intent"]):
            pairs = _build_pairing_map(mesh.nodes, mesh.elements)
            paired = set()
            quad_list = []

            for k in range(len(pairs)):
                if pairs[k] >= 0 and k < pairs[k]:
                    j = int(pairs[k])
                    paired.add(k)
                    paired.add(j)
                    quad_list.append((k, j))

            # Draw all triangles first in light gray
            ax.triplot(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.elements,
                      color="lightgray", linewidth=0.3, alpha=0.5)

            # Draw paired quads as polygons (simplified: just outlines for now)
            for k, j in quad_list:
                tri_k = mesh.elements[k]
                tri_j = mesh.elements[j]
                # Find the shared edge
                shared = None
                remaining_k = None
                remaining_j = None
                for i in range(3):
                    v_a, v_b = tri_k[i], tri_k[(i + 1) % 3]
                    for jj in range(3):
                        v_c, v_d = tri_j[jj], tri_j[(jj + 1) % 3]
                        if {v_a, v_b} == {v_c, v_d}:
                            shared = (v_a, v_b)
                            remaining_k = tri_k[(i + 2) % 3]
                            remaining_j = tri_j[(jj + 2) % 3]
                            break
                    if shared:
                        break

                if shared:
                    quad_nodes = [remaining_k, shared[0], remaining_j, shared[1], remaining_k]
                    quad_coords = mesh.nodes[quad_nodes]
                    ax.plot(quad_coords[:, 0], quad_coords[:, 1], "b-", linewidth=1.5, alpha=0.7)

            ax.set_aspect("equal")
            ax.set_title(title)
            ax.set_xlabel("x")
            ax.set_ylabel("y")

        plt.tight_layout()
        out = outdir / f"{domain_name}_quad_preview.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Wrote {out}")
    except Exception as e:
        print(f"  ERROR: quad_preview plot failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate quad-intent triangulation on a domain."
    )
    parser.add_argument(
        "--domain",
        choices=list(DOMAIN_MAP.keys()),
        default="unit_disk",
        help="Domain to triangulate (default: unit_disk)",
    )
    parser.add_argument(
        "--h",
        type=float,
        default=0.12,
        help="Target max edge length h_max (default: 0.12)",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="output/quad_eval",
        help="Output directory for PNGs, JSON, and markdown (default: output/quad_eval)",
    )
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    domain = DOMAIN_MAP[args.domain]
    print(f"\n=== Quad-Intent Evaluation: {args.domain.upper()} ===")
    print(f"  h_max={args.h}, outdir={outdir}")

    # Generate meshes
    print(f"\nTriangulating (default)...", end=" ", flush=True)
    m0 = admesh.triangulate(domain, h_max=args.h, quad_intent=False, seed=42)
    print(f"OK ({m0.n_elements} elements)")

    print(f"Triangulating (quad_intent=True)...", end=" ", flush=True)
    m1 = admesh.triangulate(domain, h_max=args.h, quad_intent=True, seed=42)
    print(f"OK ({m1.n_elements} elements)")

    # Compute reports
    print(f"\nComputing reports...")
    r0 = quad_metrics.quadability_report(m0)
    r1 = quad_metrics.quadability_report(m1)

    # Layer metrics
    layer0 = layer_metrics(m0)
    layer1 = layer_metrics(m1)

    # Generate plots
    print(f"\nGenerating plots...")
    plot_mesh_overlay(m0, m1, outdir, args.domain)
    plot_valence_histogram(m0, m1, outdir, args.domain)
    plot_valence_heatmap(m0, m1, outdir, args.domain)
    plot_layers(m0, m1, outdir, args.domain)
    plot_iso_dev(m0, m1, outdir, args.domain)
    plot_fidelity_histogram(m0, m1, outdir, args.domain)
    plot_quad_preview(m0, m1, outdir, args.domain)

    # Write metrics JSON (serialize with care: ndarrays -> lists, drop big arrays)
    metrics_out = {
        "domain": args.domain,
        "h_max": args.h,
        "default": {
            "n_interior": r0["n_interior"],
            "n_boundary": r0["n_boundary"],
            "pct_even_interior": float(r0["pct_even_interior"]),
            "mean_abs_valence_dev": float(r0["mean_abs_valence_dev"]),
            "iso_dev_mean": float(r0["iso_dev_mean"]),
            "iso_dev_std": float(r0["iso_dev_std"]),
            "fidelity": {
                "in_band_fraction": float(r0["fidelity"]["in_band_fraction"]),
                "median": float(r0["fidelity"]["median"]),
                "band": r0["fidelity"]["band"],
                "n_edges": r0["fidelity"]["n_edges"],
            },
            "merged_quad": {
                "n_pairs": r0["merged_quad"]["n_pairs"],
                "n_unpaired_tris": r0["merged_quad"]["n_unpaired_tris"],
                "mean_quad_quality": float(r0["merged_quad"]["mean_quad_quality"])
                if not np.isnan(r0["merged_quad"]["mean_quad_quality"])
                else None,
            },
            "min_q": float(r0["min_q"]),
            "mean_q": float(r0["mean_q"]),
            "layer_metrics": layer0,
        },
        "quad_intent": {
            "n_interior": r1["n_interior"],
            "n_boundary": r1["n_boundary"],
            "pct_even_interior": float(r1["pct_even_interior"]),
            "mean_abs_valence_dev": float(r1["mean_abs_valence_dev"]),
            "iso_dev_mean": float(r1["iso_dev_mean"]),
            "iso_dev_std": float(r1["iso_dev_std"]),
            "fidelity": {
                "in_band_fraction": float(r1["fidelity"]["in_band_fraction"]),
                "median": float(r1["fidelity"]["median"]),
                "band": r1["fidelity"]["band"],
                "n_edges": r1["fidelity"]["n_edges"],
            },
            "merged_quad": {
                "n_pairs": r1["merged_quad"]["n_pairs"],
                "n_unpaired_tris": r1["merged_quad"]["n_unpaired_tris"],
                "mean_quad_quality": float(r1["merged_quad"]["mean_quad_quality"])
                if not np.isnan(r1["merged_quad"]["mean_quad_quality"])
                else None,
            },
            "min_q": float(r1["min_q"]),
            "mean_q": float(r1["mean_q"]),
            "layer_metrics": layer1,
        },
    }

    metrics_file = outdir / f"{args.domain}_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics_out, f, indent=2)
    print(f"\nWrote {metrics_file}")

    # Write markdown summary
    summary_lines = [
        f"# Quad-Intent Evaluation Summary: {args.domain.upper()}",
        f"\nh_max = {args.h}",
        "",
        "| Metric | Default | Quad-Intent |",
        "|--------|---------|-------------|",
    ]

    metrics_to_compare = [
        ("pct_even_interior", "Even Interior %", lambda v: f"{100*v:.1f}%"),
        ("mean_abs_valence_dev", "Mean Valence Dev", lambda v: f"{v:.2f}"),
        ("iso_dev_mean", "Isotropy Dev (°)", lambda v: f"{v:.2f}"),
        ("fidelity", "Fidelity In-Band", lambda v: f"{100*v['in_band_fraction']:.1f}%"),
        ("merged_quad", "Quad Quality", lambda v: f"{v['mean_quad_quality']:.4f}" if v['mean_quad_quality'] is not None else "N/A"),
        ("min_q", "Min Triangle Quality", lambda v: f"{v:.4f}"),
        ("mean_q", "Mean Triangle Quality", lambda v: f"{v:.4f}"),
    ]

    for key, label, fmt in metrics_to_compare:
        if key == "fidelity":
            v0 = r0[key]
            v1 = r1[key]
            s0 = fmt(v0)
            s1 = fmt(v1)
        elif key == "merged_quad":
            v0 = r0[key]
            v1 = r1[key]
            s0 = fmt(v0)
            s1 = fmt(v1)
        else:
            v0 = r0[key]
            v1 = r1[key]
            s0 = fmt(v0)
            s1 = fmt(v1)
        summary_lines.append(f"| {label} | {s0} | {s1} |")

    # Add layer imbalance if available
    if layer0 and "total_imbalance" in layer0:
        summary_lines.append(
            f"| Layer Imbalance | {layer0['total_imbalance']} | {layer1.get('total_imbalance', 'N/A')} |"
        )

    summary_file = outdir / f"{args.domain}_summary.md"
    with open(summary_file, "w") as f:
        f.write("\n".join(summary_lines))
    print(f"Wrote {summary_file}")

    # Print summary to stdout
    print("\n" + "=" * 80)
    print("\n".join(summary_lines))
    print("=" * 80)


if __name__ == "__main__":
    main()
