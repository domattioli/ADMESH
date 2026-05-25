function p = createInitialPointList(DistFun,PTS,hmin,geps)
% createInitialPointList - Creates initial point set for distmesh2d
% function
%
% Syntax:  p = createInitialPointList(PTS,hmin)
%
% Inputs:
%    PTS    - ADMESH Edge Structure
%    hmin   - Minimum element size
%
% Outputs:
%    p - initial point list for distmesh2d
%
% Other m-files required: distmesh2d
% Subfunctions: none
% MAT-files required: none
%
% Author: Dustin West
% The Ohio State University
% email address: dww.425@gmail.com
% Last revision: 25-April-2014

%---------------------------------------------------------------------
% Begin Code
%---------------------------------------------------------------------

% Find bounding box
points = vertcat(PTS.Points{:});
xmin = min(points(:,1));
xmax = max(points(:,1));
ymin = min(points(:,2));
ymax = max(points(:,2));

% Create initial distribution in bounding box (equilateral triangles)
[x,y] = meshgrid(xmin:hmin:xmax,ymin:(hmin*sqrt(3)/2):ymax);

% Shift even rows
x(2:2:end,:)=x(2:2:end,:)+hmin/2;

% Store coordinate list in p
p=[x(:),y(:)];

% Keep only d<0 points
p = p(DistFun(p) < geps, : );

end