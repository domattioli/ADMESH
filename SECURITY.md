# Security Policy

ADMESH is a Python library for automatic unstructured mesh generation for
2D shallow-water models. It is **currently distributed on PyPI** as
`admesh2D` (v0.5.1+). This policy describes our vulnerability reporting
process and security scope.

## Supported versions

| Version | Supported |
|---|---|
| `0.5.x` (current PyPI release) | ✅ — receives fixes |
| `0.4.x` and earlier | ❌ — best-effort only |

Versions prior to 0.5.0 receive fixes only for critical supply-chain
security issues (e.g., malicious dependency uploads); normal bug fixes are
not backported. For non-critical updates, upgrade to `0.5.x`.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub's
[private vulnerability reporting](https://github.com/domattioli/ADMESH/security/advisories/new)
for this repository. If that is unavailable to you, contact the maintainer
via their GitHub profile ([@domattioli](https://github.com/domattioli)) and
request a private channel.

When reporting, please include:

- A description of the issue and its impact.
- Steps to reproduce (a minimal proof of concept where practical).
- Affected paths / components (package, tests, dependencies).
- Any suggested remediation.

We aim to acknowledge a report within a reasonable window and will coordinate a
fix and disclosure timeline with you.

## Scope notes

- **Secrets.** No tokens, database URLs, API keys, or production credentials
  are committed. Dependencies and build artifacts read secrets from the
  environment only.
- **Input validation.** The library accepts domain files (TOML, JSON,
  fort.14) and polygons from user code. Malformed input that crashes the
  solver is a normal bug, not a security vulnerability, unless it enables
  arbitrary code execution or bypasses intended access controls.
- **Dependency security.** ADMESH depends on NumPy, SciPy, Numba, and Shapely.
  We monitor major dependency releases and patch versions for security issues.
  A malicious upload to PyPI or a supply-chain compromise of a dependency is
  in scope.
- **Numerical bugs.** Incorrect mesh generation, negative element areas, or
  convergence failures are correctness bugs, not security vulnerabilities. Report
  them as normal issues.

## Out of scope

- Findings that require a compromised maintainer machine or PyPI account.
- Denial of service against ephemeral test or demo surfaces (no public
  deployment exposed).
