# Spec 015 — CHILmesh Overlap Analysis (resolves #81)

**Status:** Planning-phase only. No code shipping.
**Issue:** [#81 overlap with chilmesh](https://github.com/domattioli/ADMESH/issues/81)
**Branch:** `daily-maintenance`
**Token budget:** MEDIUM (architecture audit, doc-only deliverables)

---

## 1. Problem statement

ADMESH (this repo) and [CHILmesh](https://github.com/domattioli/CHILmesh) are sibling Python projects authored by the same maintainer. Both touch unstructured 2D meshes and share concepts (nodes, elements, boundary segments, smoothing, quality metrics). Issue #81 asks a high-level architectural question:

> Which components currently in ADMESH should be outsourced to CHILmesh, or kept in ADMESH with CHILmesh inheriting them? Need a high-level view of the ecosystem before implementing.

Today the boundary is informal:
- `CLAUDE.md` says CHILmesh is the **mesh data structure + smoother** library and ADMESH is the **mesh generator**, with CHILmesh "composes downstream of ADMESH."
- `admesh/quad_prep.py` (spec 004 `smooth_for_quadrangulation()`) exists in ADMESH but is conceptually a smoother — exactly CHILmesh's stated domain.
- `admesh/quality.py` lives in ADMESH but quality is a consumption-side concern.
- `admesh/valence.py` (referenced in issue #84) sits between generation and post-processing.
- Tests `tests/test_fort14_chilmesh_compat.py` + `tests/test_fort14_chilmesh_smoke.py` already pin the ADMESH↔CHILmesh round-trip contract via `fort.14`.

The risk of inaction: ad-hoc duplication, drift between the two repos, and unclear ownership when issues (#84 valence, #41 dimensional mapping for smoothing, #9 segmenter sibling) span the seam.

## 2. Acceptance criteria

- [ ] An inventory table classifies every public module in `admesh/` as **generator-side**, **consumer-side**, or **boundary**.
- [ ] A second table catalogs CHILmesh's current public surface (per its README + module list) with the same classification.
- [ ] Each ADMESH module marked **consumer-side** receives one of three dispositions: `keep` (with justification), `move-to-chilmesh` (with deprecation plan), or `extract-to-shared-lib` (with new-package proposal).
- [ ] The cross-repo contract is named explicitly: what data structure crosses the seam (today: `Mesh` dataclass via `fort.14`), and what optional shared base would replace ad-hoc round-tripping.
- [ ] A decision record (ADR-style) is written into `docs/adr/ADR-001-chilmesh-boundary.md` capturing: status, context, decision, consequences.
- [ ] Follow-up issues are filed on `domattioli/ADMESH` for every disposition that requires future code work — one issue per move/extract action, labeled `planning-required` + `cross-repo`.
- [ ] The issue #81 comment thread receives a closing comment summarizing the disposition table and linking the ADR + follow-up issues.

## 3. Files to create / modify

**Create:**
- `specs/015-chilmesh-overlap-analysis/spec.md` (this file)
- `specs/015-chilmesh-overlap-analysis/plan.md` — analysis workflow + module classification rubric
- `specs/015-chilmesh-overlap-analysis/tasks.md` — atomic task decomposition
- `specs/015-chilmesh-overlap-analysis/inventory.md` — the ADMESH-side and CHILmesh-side module tables
- `docs/adr/ADR-001-chilmesh-boundary.md` — the decision record

**Modify (light touch, doc-only):**
- `CLAUDE.md` — link the ADR from the "ecosystem" section
- `README.md` — clarify ADMESH ↔ CHILmesh boundary if the ADR settles a public-facing line

**Do NOT modify (this is planning phase):**
- Any file in `admesh/` (no code moves yet)
- Any file in `tests/`

## 4. Approach (2–4 sentences)

Catalog the public surface of ADMESH and CHILmesh in parallel, classify each module against a three-way rubric (generator-side / consumer-side / boundary), and produce a disposition for every module that lives on the wrong side of the line. Codify the result in an ADR plus follow-up issues so future code work has a single source of truth instead of relitigating the boundary. Keep the analysis read-only against CHILmesh — we infer its surface from its public docs, not by importing it — so this spec is safe to run without a CHILmesh checkout.

## 5. Risks

| Risk | Mitigation |
|---|---|
| CHILmesh's public surface drifts between now and execution, making the inventory stale | ADR captures the inferred surface as a snapshot with a `last-verified` date; future runs reverify |
| Disposition decisions need maintainer input that this spec can't unilaterally resolve | Default to `keep` + open issue for the harder calls; never `move-to-chilmesh` without an issue thread |
| Moving smoothers (`quad_prep`, future) to CHILmesh breaks downstream callers of `admesh.triangulate(...)` that expect the smoother in-tree | Disposition must include a deprecation plan with a shim re-export horizon (≥1 minor version) |
| `admesh.valence` overlap with issue #84 (max-valence feature) | This spec must coordinate with #84 — flag valence as `boundary` and route #84's design through the same ADR |

## 6. Token budget rationale

**MEDIUM.** The work is doc-only with no code shipping, but the inventory step must read every `admesh/*.py` module's docstring to classify it (~25 files) and cross-reference CHILmesh's published surface. Decomposable into smaller issues per disposition (which is exactly what the follow-up issues do), so this spec is the umbrella; individual moves get their own future specs.

## 7. Out of scope

- Actual code moves (each becomes its own follow-up issue with its own spec).
- Renaming any module today.
- Changing the `fort.14` boundary contract (locked by spec 009 R4 + existing chilmesh-compat tests).
- Investigating whether CHILmesh should depend on ADMESH or vice versa (that's a packaging decision downstream of the ADR).
- Multi-language considerations (MATLAB QuADMesh, legacy_chilmesh) — those are upstream sources, not active siblings.

## 8. Related

- Issue #84 — max-valence (touches `admesh/valence.py`, boundary module)
- Issue #41 — dimensional mapping for smoothing (touches `admesh/quad_prep.py`, candidate consumer-side)
- Issue #9 — `admesh-segmenter` sibling proposal (precedent for sibling-not-feature decisions)
- Issue #75 (closed) — chilmesh smoke vs compat split (prior boundary clarification)
- `tests/test_fort14_chilmesh_compat.py`, `tests/test_fort14_chilmesh_smoke.py` — existing seam contract
