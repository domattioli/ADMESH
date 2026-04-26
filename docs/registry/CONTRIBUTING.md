# Contributing to ADCIRC Mesh Registry

Thank you for contributing to the ADCIRC mesh registry! This document explains how to submit new meshes.

## Overview

The registry uses a **GitHub pull request workflow**. Contributions go through automated validation before merging:

1. **Fork** the ADMESH repo
2. **Add your mesh entry** to the manifest
3. **Validate locally** (optional but recommended)
4. **Open a PR** — CI validates automatically
5. **Respond to feedback** from maintainers
6. **Merge** — your mesh is published on the next release

## Step-by-Step Guide

### 1. Fork the Repository

```bash
git clone https://github.com/YOUR-USERNAME/ADMESH
cd ADMESH
git remote add upstream https://github.com/domattioli/ADMESH
```

### 2. Compute Your Mesh's Content Hash

```bash
sha256sum your-mesh.fort.14
# Output: abc123def456... your-mesh.fort.14
```

Keep this hash handy—you'll need it for your manifest entry.

### 3. Create a Manifest Entry

Edit `registry_data/manifest.toml` and add your mesh as a new `[[meshes]]` block:

```toml
[[meshes]]
id = "your-namespace/your-mesh@v2026"
name = "Your Mesh Name"
source_url = "https://your-host/your-mesh.fort.14"
content_hash = "sha256:abc123def456..."
num_triangles = 12345
license = "CC-BY-4.0"
created_by = "Your Name <you@example.org>"
created_date = 2026-04-26T00:00:00Z
review_state = "draft"
features = ["levee", "estuary"]

  [meshes.bounding_box]
  min_lon = -97.0
  min_lat = 25.0
  max_lon = -88.0
  max_lat = 30.0
```

### Field Descriptions

- **id**: Unique composite slug: `<namespace>/<name>@<version>`
  - `namespace`: Your org/username (e.g., `"noaa"`, `"usace"`, `"yourname"`)
  - `name`: Mesh slug (lowercase, hyphens ok)
  - `version`: Any version string (e.g., `v2026`, `2024-Q1`)
- **source_url**: Public URL where your mesh file lives (S3, GitHub releases, institutional archive)
- **content_hash**: SHA-256 hash of the canonical mesh file (obtained above)
- **num_triangles**: Integer triangle count
- **license**: One of:
  - `"public-domain"` — No restrictions
  - `"MIT"` — MIT license
  - `"CC-BY-4.0"` — Attribution required
  - `"CC-BY-SA-4.0"` — Attribution + ShareAlike
  - `"CC0-1.0"` — Public domain dedication
  - `"proprietary"` — Proprietary; licensing details in description
  - `"unknown"` — License unclear; contact owner for clarification
- **created_by**: Your name and email
- **created_date**: ISO-8601 timestamp (use current UTC time)
- **review_state**: Always `"draft"` on submission
- **features**: List of relevant tags from the controlled vocabulary:
  - `open_ocean`, `inlet`, `estuary`, `tidal_flat`, `barrier_island`, `levee`, `breakwater`, `wetland`, `shipping_channel`, `river_outflow`, `bay`, `lagoon`, `reef`
- **bounding_box**: Geographic extent (min/max longitude and latitude)

### 4. Validate Locally (Optional)

```bash
pip install -e ".[registry]"
mesh-registry validate registry_data/manifest.toml
```

You should see:
```
✅ Manifest valid (X entries)
```

If validation fails, the error message will tell you what to fix.

### 5. Open a Pull Request

```bash
git add registry_data/manifest.toml
git commit -m "Add my-mesh to registry"
git push origin main
```

Then open a PR against `domattioli/ADMESH:main` with a title like:

```
Add your-namespace/your-mesh@v2026 to registry
```

### 6. CI Validation

GitHub Actions will automatically run validation on your PR. Within ~30 seconds, you'll see:

- ✅ **Schema validation**: All fields present and typed correctly
- ✅ **Invariants**: No dangling parent references, no duplicate IDs, etc.
- ✅ **Sanity checks**: URL reachability, hash consistency, bbox plausibility
- ✅ **Diff summary**: What you added/modified

If any checks fail, fix the issues and push again—CI will re-run automatically.

### 7. Address Feedback

A maintainer will review your entry. Common feedback:

- **"Hash mismatch"** → Re-compute `sha256sum` and update `content_hash`
- **"Dangling derived_from"** → Verify parent mesh ID (if you're refining an existing mesh)
- **"Bbox spans wrong sign"** → Check longitude signs (e.g., `-97` not `97`)
- **"Unknown feature tag"** → Use one from the controlled vocabulary above

### 8. Merge

Once approved, the maintainer will merge your PR. Your mesh appears in the registry on the next release (typically within a week).

## Derived Meshes (Refinements)

If your mesh is a refinement of an existing registry entry, add provenance:

```toml
[[meshes]]
id = "your-namespace/galveston-refined@v2026"
name = "Galveston Bay Refined"
derived_from = "noaa/hsofs@v2021"
# ... other fields ...

  [[meshes.provenance_history]]
  operation_type = "refine_box"
  applied_date = 2026-04-26T00:00:00Z
  applied_by = "Your Name <you@example.org>"

    [meshes.provenance_history.parameters]
    bbox = [-95.5, 28.5, -94.0, 29.5]
    target_resolution = 25.0
```

## Troubleshooting

### "URL unreachable"

The CI validator tries to fetch your file to verify the hash. If your source is private:

1. Make the file publicly accessible temporarily during the PR review
2. Or comment in the PR explaining the access restriction

### "License field required"

Every mesh must have an explicit license. If unsure, use `"unknown"` and provide attribution info in your PR description.

### "Hash mismatch"

Make sure you're hashing the **same file** at `source_url`. Possible causes:

- File was updated at the URL after you computed the hash
- You're hashing a local copy that differs from the remote version
- Symlinks or compression differences

Verify with:
```bash
curl https://your-host/your-mesh.fort.14 | sha256sum
```

## Questions?

- **Syntax issues**: Check the [manifest schema](../../specs/005-adcirc-mesh-registry/contracts/manifest-schema.md)
- **Feature vocabulary**: See [Feature Tags](../../specs/005-adcirc-mesh-registry/contracts/manifest-schema.md#features)
- **General questions**: Open an issue on GitHub

## See Also

- [Quickstart: Using the Registry](../../specs/005-adcirc-mesh-registry/quickstart.md)
- [Manifest Schema](../../specs/005-adcirc-mesh-registry/contracts/manifest-schema.md)
