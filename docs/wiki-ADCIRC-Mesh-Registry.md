# ADCIRC Mesh Registry (ADMESH-Domains)

## What is it?

A **federated, community-driven registry** for discovering, classifying, and managing ADCIRC-compatible coastal-simulation meshes (domains).

## Problem Solved

ADCIRC meshes are scattered across:
- GitHub repos (various formats)
- NOAA archives (limited discoverability)
- Academic supplementary data (hard to find)
- Local research collections (no standardization)

**Result**: No canonical way to discover, classify, or verify licensing.

## Solution

A unified registry with:
- **Standardized metadata** — license, geography, features, provenance
- **Discovery API** — search by region, features, license, size
- **Lineage tracking** — parent-child relationships with transformation history
- **PR-based contributions** — submit meshes via GitHub with automated validation
- **HuggingFace mirror** — web interface for browsing and downloading

## Quick Start

```python
from admesh_domains import find

# Find public-domain meshes in Gulf of Mexico with levees
meshes = find(
    bbox=(-97, 25, -88, 30),
    features=["levee"],
    license="public-domain"
)
```

## Repository

**[github.com/domattioli/ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)**

- Install: `pip install admesh-domains`
- Contribute: [CONTRIBUTING.md](https://github.com/domattioli/ADMESH-Domains/blob/main/docs/CONTRIBUTING.md)
- Report issues: [Issues](https://github.com/domattioli/ADMESH-Domains/issues)

## Status

v0.1.0 Alpha (2026-04-26)
- 43 passing tests
- 5 seed meshes
- Full Python API + CLI
- GitHub Actions CI/CD

## Relationship to ADMESH

Extracted from ADMESH on 2026-04-26 as a companion project. ADMESH remains focused on the faithful Python port of the MATLAB mesh generator; ADMESH-Domains handles discovery and lineage management.
