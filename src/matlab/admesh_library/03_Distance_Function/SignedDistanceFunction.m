function [D,gradD,IB] = SignedDistanceFunction(PTS,X,Y,delta,hmax,sb)
% DistanceFunction - Computes the nearest distance from a background
% point in (X,Y) to the boundaries in PTS
%
% Syntax:  [D,gradD] = SignedDistanceFunction(PTS,X,Y,delta,hmax)
%
% Inputs:
%    PTS    - ADMESH Edge Structure
%    X      - (nxm) x-coordinates to rectangular grid
%    Y      - (nxm) y-coordinates to rectangular grid
%    delta  - Grid spacing
%    hmax   - Maximum Element Size
%
% Outputs:
%    D     - (nxm) distance function (negative values indicate points
%             inside domain.
%    gradD -  Array Structure; gradient of the distance function
%
% Other m-files required: none
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
NARGIN6	= nargin == 6;
if NARGIN6
    % Initialize waitbar
    sb.ProgressBar.setVisible(true)
    sb.ProgressBar.setIndeterminate(true);
    sb.setText('Computing Distance Function.')
    drawnow
end

%------------------------------------------------------------------------------
% Find Points in Domain
%------------------------------------------------------------------------------
[IN,~,~] = InPolygon(X,Y,PTS.Points{1}(:,1),PTS.Points{1}(:,2));
%IN = PointsInDomain(X,Y,PTS);
%drawnow

%figure; hold on;
%plot(X(IN),Y(IN),'k.')

%------------------------------------------------------------------------------
% Approximate signed distance to the boundary with bwdist
%------------------------------------------------------------------------------
D = double(bwdist(IN))*delta; 
drawnow

%------------------------------------------------------------------------------
% Space each polygon/line coordinate by delta
%------------------------------------------------------------------------------
P = spacePointsEqually(PTS,delta);
drawnow

%------------------------------------------------------------------------------
% Update status bar
%------------------------------------------------------------------------------
if NARGIN6
    sb.setText('Computing Distance Function..'); drawnow
end

%------------------------------------------------------------------------------
% Compute nearest neighbor
%------------------------------------------------------------------------------
% Find all points less than hmax 
ix = find(D <= hmax);

% Create nearest neighbor search object
ns = KDTreeSearcher([vertcat(P(:).x) vertcat(P(:).y)],'distance','euclidean');

% Perform nearest neighbor search on all points <= hmax
[idx,D(ix)] = knnsearch(ns,[X(ix) Y(ix)]); clear ns
drawnow

%------------------------------------------------------------------------------
% Get total number of segments in P
%------------------------------------------------------------------------------
nsegments = numel(P); drawnow

%------------------------------------------------------------------------------
% Update status bar
%------------------------------------------------------------------------------
if NARGIN6
    sb.setText('Computing Distance Function...')
    sb.ProgressBar.setIndeterminate(false)
    set(sb.ProgressBar, 'Minimum',1, 'Maximum',nsegments, 'Value',1); drawnow
end

%------------------------------------------------------------------------------
% With the nearest neighbor, compute exact distance 
%------------------------------------------------------------------------------
j = 0; % Initialize end index

for k = 1:nsegments % Loop over each segment in PTS.Poly
    
    % Increment index vector
    i = j + 1;
    j = size(P(k).x,1) + j;
    
    % Find the location in idx where idx is in (i:j)'
    lia = ismember(idx,(i:j)'); 
    
    % Check for matches
    if NARGIN6
        if ~any(lia); set(sb.ProgressBar,'Value',k); continue; end
    end
    % Store indexes to P(k), Rescale 1:numel(P(k).x)
    id = idx(lia); id = id - (min(id)-1);
    
    % Stor indices for [X,Y]
    loc = ix(lia);

    % Compute exact distance 
    D(loc) = min(distFunSubroutine(X(loc),Y(loc),P(k).x,P(k).y,id), D(loc));
    
    if NARGIN6
        set(sb.ProgressBar,'Value',k); drawnow
    end
end

% Create signed distance function
D(IN) = -D(IN);

if NARGIN6
    sb.ProgressBar.setVisible(false) ; drawnow
end

%------------------------------------------------------------------------------
% Store indices closest to open ocean boundary to enforcing hmax
%------------------------------------------------------------------------------
if ~isempty(PTS.BC)
    
    % Are there any open ocean boundaries?
    im = find(ismember([PTS.BC.num],-1));
    
    if ~isempty(im)
        
        % Initialize cell
        IB = cell(length(im),1);
        
        % Loop over each open ocean boundary segment
        for k = 1:length(im)

            % Asign coordinates
            p = PTS.BC(im(k)).points;
            
            % Compute edge lengths
            L = sqrt(diff(p(:,1)).^2 + diff(p(:,2)).^2);
            
            % Determine the number of points to fit between each edge
            nP = floor(L/delta);
            
            % For any edges where nP <= 1, nP = 2. We don't need more res. here
            nP(nP<=1) = 2;
            
            % Initialize temporary cell to hold new coordinate list
            pt = cell(numel(nP),1);
            
            % Loope over each edge
            for j = 1:numel(nP)
                pt{j} = [...
                    linspace(p(j,1), p(j+1,1),nP(j))',...
                    linspace(p(j,2), p(j+1,2),nP(j))'];
            end
            
            % Convert cell to mat and creat unique point list
            pt = unique(cell2mat(pt),'rows','stable');
            
            % Find the location in boundary segment
            loc = knnsearch([P(1).x,P(1).y],pt);
            
            % Find the location in idx where idx is in (i1:i2)'
            lia = ismember(idx,loc);
            
            % Stor indices for [X,Y]
            IB{k} = ix(lia);
        end
        
        % Convert cell 2 mat
        IB = cell2mat(IB);
    else
        IB = [];
    end
else
    IB = [];
end

%------------------------------------------------------------------------------
% Compute the gradient
%------------------------------------------------------------------------------
%[gradD.x,gradD.y] = gradient(D,delta,delta);

[LY,LX] = size(D);

gradD.x = zeros(LY,LX);
gradD.y = zeros(LY,LX);

gradD.x(3:LY-2,3:LX-2) = ( 1*D(3:LY-2,1:LX-4) + -8*D(3:LY-2,2:LX-3) + ...
    8*D(3:LY-2,4:LX-1) + -1*D(3:LY-2,5:LX) )/(12*delta);
gradD.y(3:LY-2,3:LX-2) = ( 1*D(1:LY-4,3:LX-2) + -8*D(2:LY-3,3:LX-2) + ...
    8*D(4:LY-1,3:LX-2) + -1*D(5:LY,3:LX-2) )/(12*delta);
