"""CLI for mesh registry operations: validate, find, publish."""

import json
import sys
from pathlib import Path
from typing import Optional

import click

from mesh_registry.manifest import load_manifest, validate_invariants
from mesh_registry.query import find


@click.group()
def cli():
    """ADCIRC Mesh Registry CLI."""
    pass


@cli.command()
@click.argument("manifest_path", type=click.Path(exists=True))
def validate(manifest_path: str) -> None:
    """Validate manifest file or directory.

    Checks:
    - Schema validation (all fields present and typed correctly)
    - Invariants (unique IDs, no dangling refs, no cycles, etc.)
    - Sanity checks (bbox plausibility, triangle count, etc.)

    Exits with code 0 if valid, 1 if invalid.
    """
    try:
        manifest_path = Path(manifest_path)

        # Load manifest
        try:
            manifest = load_manifest(manifest_path)
        except FileNotFoundError as e:
            click.echo(f"❌ Manifest not found: {manifest_path}", err=True)
            sys.exit(1)
        except ValueError as e:
            click.echo(f"❌ Failed to load manifest: {e}", err=True)
            sys.exit(1)

        # Validate invariants
        errors = validate_invariants(manifest)

        if errors:
            click.echo(f"❌ Validation failed with {len(errors)} error(s):", err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)
            sys.exit(1)
        else:
            click.echo(f"✅ Manifest valid ({len(manifest.meshes)} entries)")
            sys.exit(0)

    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--bbox",
    nargs=4,
    type=float,
    help="Bounding box: min_lon min_lat max_lon max_lat",
)
@click.option("--features", multiple=True, help="Feature filter (can be repeated)")
@click.option("--max-size", type=int, help="Maximum triangle count")
@click.option("--license", help="License filter (public-domain, MIT, CC-BY-4.0, etc.)")
@click.option("--manifest", type=click.Path(exists=True), help="Path to manifest file")
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def search(
    bbox: Optional[tuple],
    features: tuple,
    max_size: Optional[int],
    license: Optional[str],
    manifest: Optional[str],
    format: str,
) -> None:
    """Search registry for meshes.

    Example:
        mesh-registry search --bbox -97 25 -88 30 --features levee
    """
    try:
        # Convert bbox tuple to dict kwargs
        find_kwargs = {"include_deprecated": False}

        if bbox:
            find_kwargs["bbox"] = bbox

        if features:
            find_kwargs["features"] = list(features)

        if max_size:
            find_kwargs["max_size"] = max_size

        if license:
            find_kwargs["license"] = license

        if manifest:
            find_kwargs["manifest"] = manifest

        # Run query
        results = find(**find_kwargs)

        if format == "json":
            output = [
                {
                    "id": m.id,
                    "name": m.name,
                    "triangles": m.num_triangles,
                    "license": m.license.value,
                    "source_url": m.source_url,
                }
                for m in results
            ]
            click.echo(json.dumps(output, indent=2))
        else:
            if not results:
                click.echo("No meshes found")
            else:
                click.echo(f"Found {len(results)} mesh(es):")
                for m in results:
                    click.echo(
                        f"  {m.id}: {m.num_triangles:,} triangles ({m.license.value})"
                    )

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--manifest", type=click.Path(exists=True), help="Manifest path")
@click.option(
    "--dataset-slug",
    default="adcirc-meshes",
    help="HuggingFace dataset slug",
)
@click.option("--hf-token", envvar="HF_TOKEN", help="HuggingFace API token")
@click.option("--tag", help="Release tag for commit message")
def publish(
    manifest: Optional[str], dataset_slug: str, hf_token: Optional[str], tag: Optional[str]
) -> None:
    """Publish manifest to HuggingFace Datasets.

    Requires HF_TOKEN environment variable with write access.
    """
    if not hf_token:
        click.echo("Error: HF_TOKEN not set (provide via --hf-token or HF_TOKEN env var)", err=True)
        sys.exit(1)

    click.echo("⏳ Publishing to HuggingFace Datasets...")
    click.echo("(Implementation deferred to Phase 8)")
    # Implementation comes later in Phase 8


if __name__ == "__main__":
    cli()
