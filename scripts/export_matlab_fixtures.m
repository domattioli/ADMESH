% export_matlab_fixtures.m
%
% Emit reference fixtures from QuADMesh-MATLAB/01_ADMESH_Library for
% use by the Python port's pytest suite.
%
% Usage (from a MATLAB install with QuADMesh-MATLAB on path):
%   >> addpath(genpath('/workspace/QuADMesh-MATLAB/01_ADMESH_Library'));
%   >> cd /home/user/ADMESH
%   >> run('scripts/export_matlab_fixtures.m')
%
% Outputs .mat files under tests/fixtures/<stage>/<case>.mat. A
% Python-side helper (``scripts/mat_to_npz.py``) converts them to
% ``.npz`` for pytest consumption.
%
% Section layout matches the MATLAB module numbering in 01_ADMESH_Library/.

FIXTURE_ROOT = fullfile(fileparts(fileparts(mfilename('fullpath'))), ...
                        'tests', 'fixtures');
fprintf('export_matlab_fixtures.m: writing to %s\n', FIXTURE_ROOT);


%% 10_Distmesh_2d: BoundaryCleanUp on hand-constructed slivers ==============
outdir = fullfile(FIXTURE_ROOT, 'distmesh', 'boundary_cleanup');
if ~exist(outdir, 'dir'); mkdir(outdir); end

% Case A: 4-node, 2-triangle mesh with one near-collinear sliver.
p = [-0.4 -0.5;
     -0.2 -0.5;
      0.0 -0.5+1e-4;
      0.0  0.0];
t = [1 2 3; 1 2 4];     % MATLAB 1-based
t_cleaned = BoundaryCleanUp(p, t, []);   % no constraints
save(fullfile(outdir, 'collinear_sliver.mat'), ...
     'p', 't', 't_cleaned', '-v7');

% Case B: same geometry, with the sliver's (0,2) edge constrained.
C = [1 3];               % MATLAB 1-based constraint edge
t_constrained = BoundaryCleanUp(p, t, C);
save(fullfile(outdir, 'collinear_sliver_constrained.mat'), ...
     'p', 't', 'C', 't_constrained', '-v7');


%% 10_Distmesh_2d: projectBackToBoundary ====================================
outdir = fullfile(FIXTURE_ROOT, 'distmesh', 'project_back');
if ~exist(outdir, 'dir'); mkdir(outdir); end

% Case: unit disk, a few test points.
%   phi.f   = signed distance (|p|-1)
%   phi.fx  = p(:,1) / |p|
%   phi.fy  = p(:,2) / |p|
phi = struct();
phi.f  = @(p) sqrt(p(:,1).^2 + p(:,2).^2) - 1;
phi.fx = @(p) p(:,1) ./ max(sqrt(p(:,1).^2 + p(:,2).^2), eps);
phi.fy = @(p) p(:,2) ./ max(sqrt(p(:,1).^2 + p(:,2).^2), eps);
p_in = [ 0.0  0.0;     % interior, no project
         1.1  0.0;     % outside → project to (1, 0)
         0.999 0.0;    % boundary-adjacent inside — MATLAB pulls to (1, 0)
        -0.5  0.6];    % interior, well inside
geps = 1e-5;
p_proj = projectBackToBoundary(phi, p_in, geps);
save(fullfile(outdir, 'unit_disk.mat'), 'p_in', 'p_proj', 'geps', '-v7');


%% 10_Distmesh_2d: createInitialPointList ==================================
outdir = fullfile(FIXTURE_ROOT, 'distmesh', 'initial_points');
if ~exist(outdir, 'dir'); mkdir(outdir); end

% Minimal PTS proxy with a .Points cell.
PTS = struct();
PTS.Points = {[-0.5 -0.5; 0.5 -0.5; 0.5 0.5; -0.5 0.5]};
DistFun = @(p) max(abs(p(:,1)), abs(p(:,2))) - 0.5;
hmin = 0.2;
geps = 1e-4;
p_init = createInitialPointList(DistFun, PTS, hmin, geps);
save(fullfile(outdir, 'unit_square_coarse.mat'), ...
     'hmin', 'geps', 'p_init', '-v7');


%% 10_Distmesh_2d: distmesh2d end-to-end on a small domain =================
% Full distmesh2d.m has GUI plumbing (sb, pH, viewStatus) that can't run
% headless. Fixture capture here uses a slimmed adapter that strips the
% GUI calls; port that adapter in a later session.
fprintf('[skip] full distmesh2d fixture — GUI plumbing needs adapter.\n');


%% 04_Curvature_Function ===================================================
% Capture the MATLAB narrow-band curvature formula output on a unit
% disk grid. Match Python default delta=0.02; hmax=0.5, hmin=0.05,
% K=30 (elements per radian), g=0.2 to reproduce the hand-derived test.
outdir = fullfile(FIXTURE_ROOT, 'curvature');
if ~exist(outdir, 'dir'); mkdir(outdir); end

% Grid
xs = -1:0.02:1;
ys = -1:0.02:1;
[X, Y] = meshgrid(xs, ys);
D = sqrt(X.^2 + Y.^2) - 1;
% MATLAB's CurvatureFunction expects gradD struct + X, Y, K, g, hmax, hmin
[gradD_x, gradD_y] = gradient(D, 0.02, 0.02);
gradD = struct('x', gradD_x, 'y', gradD_y);
hmax = 0.5; hmin = 0.05; g = 0.2; K = 30;
h0 = ones(size(D)) * hmax;
% NOTE: MATLAB CurvatureFunction takes Settings.K.Status = 'On'; stub:
Settings = struct('K', struct('Status', 'On'));
h0_out = CurvatureFunction(h0, D, gradD, X, Y, K, g, hmax, hmin, Settings, []);
save(fullfile(outdir, 'unit_disk.mat'), ...
     'X', 'Y', 'D', 'gradD_x', 'gradD_y', 'K', 'g', 'hmax', 'hmin', 'h0_out', '-v7');


%% 05_Medial_Axis ==========================================================
% Capture MedialAxisFunction output on the annulus (r=0.4 to r=1.0).
outdir = fullfile(FIXTURE_ROOT, 'medial_axis');
if ~exist(outdir, 'dir'); mkdir(outdir); end

xs = -1:0.02:1;
ys = -1:0.02:1;
[X, Y] = meshgrid(xs, ys);
r = sqrt(X.^2 + Y.^2);
D = max(r - 1.0, 0.4 - r);          % annulus SDF
[gradD_x, gradD_y] = gradient(D, 0.02, 0.02);
gradD = struct('x', gradD_x, 'y', gradD_y);
hmax = 0.5; hmin = 0.01; R = 3.0;
h0 = ones(size(D)) * hmax;
Settings = struct('R', struct('Status', 'On'));
h0_out = MedialAxisFunction(h0, X, Y, D, gradD, R, hmin, hmax, Settings, []);
save(fullfile(outdir, 'annulus.mat'), ...
     'X', 'Y', 'D', 'R', 'hmax', 'hmin', 'h0_out', '-v7');


fprintf('export_matlab_fixtures.m: done.\n');
