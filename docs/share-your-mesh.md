# Share your mesh

<!-- TODO: the valence-intake repo does not exist yet. Update the link below once it does. -->

We are building an open collection of ADCIRC fort.14 meshes for testing mesh tools. If you have a mesh you can share, we would be glad to receive it.

## What we accept

- Any fort.14 (.14) triangular, quadrilateral, or mixed mesh.
- Meshes from any generator, including QuADMESH, SMS, and OceanMesh2D.
- Meshes of any size and region.

## What to send

Open the [share-mesh form](https://github.com/domattioli/valence-intake/issues/new?template=share-mesh.yml) and fill in these fields.

1. The .14 file. Drag it into the upload box.
2. A license: CC-BY-4.0, CC0-1.0, ODbL-1.0, or other.
3. The tool that generated the mesh.
4. A short description: region, purpose, and resolution.
5. Your consent. Confirm that you have the right to share the mesh and that it may be redistributed under the license you chose.

## Before you share

Check that the mesh is yours to share. Remove anything confidential from the title line. Large files may need a link to a download location instead of an upload.

## Questions

Open an issue in this repository. We will reply as soon as we can.

## Silence the log hint

ADMESH writes one log line after the first fort.14 it saves. Set the environment variable `ADMESH_NO_SHARE_HINT` to any non-empty value to turn the line off.
