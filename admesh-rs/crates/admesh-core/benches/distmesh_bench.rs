//! Micro-benchmarks for the Rust distmesh hot path.

use admesh_core::sdf::{unit_disk_sdf, SdfFn};
use admesh_core::{distmesh2d, DistmeshConfig};
use criterion::{criterion_group, criterion_main, Criterion};

fn bench_unit_disk(c: &mut Criterion) {
    let sdf = SdfFn(unit_disk_sdf);
    let cfg = DistmeshConfig {
        h0: 0.1,
        bbox: (-1.2, -1.2, 1.2, 1.2),
        niter: 100,
        seed: 42,
        ..Default::default()
    };
    c.bench_function("unit_disk_h0=0.1", |b| {
        b.iter(|| {
            let (_mesh, _) = distmesh2d(&sdf, None, &cfg);
        });
    });
}

criterion_group!(benches, bench_unit_disk);
criterion_main!(benches);
