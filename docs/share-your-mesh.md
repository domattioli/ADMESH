# Share your mesh


We are building an open collection of ADCIRC fort.14 meshes for testing mesh tools. If you have a mesh you can share, we would be glad to receive it.

## What we accept

- Any fort.14 (.14) triangular, quadrilateral, or mixed mesh.
- Meshes from any generator, including QuADMESH, SMS, and OceanMesh2D.
- Meshes of any size and region.

## What to send

Open the open an issue in this repository (https://github.com/domattioli/ADMESH/issues/new) and fill in these fields.

1. The .14 file. Drag it into the upload box.
2. A license: CC-BY-4.0, CC0-1.0, ODbL-1.0, or other.
3. The tool that generated the mesh.
4. A short description: region, purpose, and resolution.
5. Your consent. Confirm that you have the right to share the mesh and that it may be redistributed under the license you chose.

## Before you share

Check that the mesh is yours to share. Remove anything confidential from the title line. For a large file, paste a download link instead of uploading it.

## Questions

Open an issue in this repository. We will reply as soon as we can.

## Turn off the share hint

ADMESH prints one line to stderr after it writes the first fort.14 in a process. To turn it off, set the environment variable `ADMESH_NO_SHARE_HINT` to any non-empty value.
