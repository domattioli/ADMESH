% export_matlab_fixtures.m
%
% Emit reference fixtures from QuADMesh-MATLAB/01_ADMESH_Library for
% use by the Python port's pytest suite.
%
% Usage (from a MATLAB install with QuADMesh-MATLAB on path):
%   >> run('scripts/export_matlab_fixtures.m')
%
% Outputs .mat files under tests/fixtures/<stage>/<case>.mat, which a
% Python-side helper (scripts/mat_to_npz.py, TBD) converts to .npz.
%
% STUB: populate with per-stage fixture emitters as each stage is ported.
% Guideline: small inputs (< 1 MB per .mat), cover edge cases (empty
% input, degenerate geometry, common domain).

fprintf('export_matlab_fixtures.m: stub — no fixtures emitted yet.\n');
fprintf('See PROJECT_PLAN.md MVP phasing for the order in which fixtures are needed.\n');
