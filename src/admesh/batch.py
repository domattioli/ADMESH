"""Batch triangulation over a process pool (issue #99, phase P2).

Provides :func:`triangulate_batch` to run :func:`admesh.triangulate` over
multiple domains in parallel on a process pool. Strictly additive API layer —
no modifications to faithful-port :mod:`admesh._stages` modules.

The pool is an execution detail; it must never change a mesh result.
"""

from __future__ import annotations

import multiprocessing
import os
import pickle
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING

from admesh.api import Mesh, triangulate

if TYPE_CHECKING:
    from collections.abc import Sequence


def _worker_triangulate(domain, kwargs):
    """Worker function for process pool.

    Parameters
    ----------
    domain
        Domain object or path string (anything triangulate accepts).
    kwargs
        Keyword arguments to forward to triangulate.

    Returns
    -------
    Mesh
        Triangulated mesh.
    """
    return triangulate(domain, **kwargs)


def triangulate_batch(
    domains: Sequence,
    *,
    n_jobs: int | None = None,
    **kwargs,
) -> list[Mesh]:
    """Triangulate multiple domains on a process pool.

    Parameters
    ----------
    domains : sequence
        Sequence of Domain objects, file paths, or registry slugs — anything
        :func:`triangulate` accepts.
    n_jobs : int or None, optional
        Maximum number of worker processes. If None, defaults to
        ``min(len(domains), os.cpu_count() or 1)``.
        If 1, runs sequentially in-process without spawning workers.
        If < 1, raises ValueError.
    **kwargs
        Keyword arguments forwarded unchanged to every :func:`triangulate`
        call (h_max, h_min, size_field, seed, max_iter, quality_gate, etc.).

    Returns
    -------
    list of Mesh
        Meshes in input order. Results from sequential in-process
        execution (n_jobs=1) are numerically identical to pool results;
        the pool is an execution detail only.

    Raises
    ------
    ValueError
        If n_jobs is not None and < 1.
    TypeError
        If any domain or kwargs are not picklable (raised before pool
        creation to avoid silent serialization failures in workers).
        Message includes the domain index (for domains) or 'kwargs'.

    Notes
    -----
    When n_jobs=1 or ``len(domains) == 1``, the function runs a
    sequential loop without spawning a process pool. This avoids
    pickling overhead and permits unpicklable domains such as those
    with lambda SDF functions.

    For parallel execution (n_jobs > 1), each domain is pickled before
    the pool is created. Domains with lambda or local-scope SDF
    functions will raise TypeError. Use registry slugs, file paths,
    or module-level SDF callables instead, or set n_jobs=1.
    """
    domains_list = list(domains)

    # Resolve n_jobs
    if n_jobs is None:
        n_jobs = min(len(domains_list), os.cpu_count() or 1)
    if n_jobs < 1:
        raise ValueError(f"n_jobs must be >= 1, got {n_jobs}")

    # Empty input
    if not domains_list:
        return []

    # Sequential execution for n_jobs=1 or single domain
    if n_jobs == 1 or len(domains_list) == 1:
        return [triangulate(domain, **kwargs) for domain in domains_list]

    # Parallel execution: pickle-check all domains before pool creation
    for i, domain in enumerate(domains_list):
        try:
            pickle.dumps(domain)
        except (TypeError, AttributeError, pickle.PicklingError) as e:
            raise TypeError(
                f"Domain at index {i} is not picklable and cannot be sent to "
                f"worker processes. Suggestions:\n"
                f"  - Use a module-level SDF callable instead of a lambda\n"
                f"  - Use a file path (.toml, .json, .14) or registry slug\n"
                f"  - Set n_jobs=1 to run sequentially in-process"
            ) from e

    # Pickle-check kwargs once
    try:
        pickle.dumps(kwargs)
    except (TypeError, AttributeError, pickle.PicklingError) as e:
        raise TypeError(
            "kwargs are not picklable and cannot be sent to worker processes. "
            "Suggestions:\n"
            "  - Avoid callables with lambda or local scope\n"
            "  - Use module-level callables for size_field, bathymetry, etc.\n"
            "  - Set n_jobs=1 to run sequentially in-process"
        ) from e

    # Create pool and submit tasks
    mp_context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=n_jobs, mp_context=mp_context) as executor:
        futures = [
            executor.submit(_worker_triangulate, domain, kwargs)
            for domain in domains_list
        ]
        results = [future.result() for future in futures]

    return results
