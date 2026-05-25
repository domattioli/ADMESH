function [NOPE,NETA,NVDLL,NBDV] = ExractNodeString(t,p,PTS,cNum)

%------------------------------------------------------------------------------
% If there are no open ocean boundaries, return
%------------------------------------------------------------------------------
if ~any(ismember([PTS.BC.num],cNum))
    NOPE = nan; NETA = nan; NVDLL = nan; NBDV = nan;
    return
end

%------------------------------------------------------------------------------
% Find which cells contain open ocean boundaries
%------------------------------------------------------------------------------
ix = find(ismember([PTS.BC.num],cNum));

% Assign NOPE
NOPE = length(ix);

% Initialize NETA
NETA = 0;

% Initialize NVDLL
NVDLL = zeros(size(ix));

NBDV = cell(size(ix));

%------------------------------------------------------------------------------
% Get boundary edge segments of triangulation in the form xb (2xm) and
% yb (2xm). Each row corresponds the end points of each edge segment.
%------------------------------------------------------------------------------
trep = triangulation(t, p(:,1), p(:,2)); % Re-triangulate
fb = freeBoundary(trep); % Get boundary edge node pairs list

%------------------------------------------------------------------------------
% For each node string in IBtype, define the new node string in the new mesh
%------------------------------------------------------------------------------
for i = 1:length(ix)
    
    drawnow; % for graphics
    
    % Find starting node & ending node in the exisiting BC
    Snode = PTS.BC(ix(i)).points(1,:); 
    Enode = PTS.BC(ix(i)).points(end,:);
    
    % Use Snode & Enode to determine the new starting and ending node
    % for the node string in p.
    [~,loca] = min(sum([abs(Snode(1,1) - p(:,1)).^2  abs(Snode(1,2) - p(:,2)).^2],2));
    [~,locb] = min(sum([abs(Enode(1,1) - p(:,1)).^2  abs(Enode(1,2) - p(:,2)).^2],2));
    
    %------------------------------------------------------------------------------
    % Find the polygon we're closest to
    %------------------------------------------------------------------------------
    % vector for comparing distances
    d = zeros(1,length(PTS.Points));
    
    % Compute minimum distance to each boundary, find closest
    % boundary
    for k = 1:length(PTS.Points)
        d(k) =  min(Point2EdgeDistance(Snode(1),Snode(2),PTS.Points{k}(:,1),PTS.Points{k}(:,2))); 
    end
    
    [~,cp] = min(d); % find closest polygon
    
    %------------------------------------------------------------------------------
    % Determine if original open ocean node list is going cw or ccw
    %------------------------------------------------------------------------------
    
    % Get first edge in IBtype
    edgex = [PTS.BC(ix(i)).points(1,1) PTS.BC(ix(i)).points(2,1)];
    edgey = [PTS.BC(ix(i)).points(1,2) PTS.BC(ix(i)).points(2,2)];
        
    % Compute Mid-point on edge
    Midp = [mean(edgex) , mean(edgey)]; % MID point
    
    % Compute normals
    L = sqrt(diff(edgex).^2 + diff(edgey).^2);
    nx =  diff(edgey)./L;
    ny = -diff(edgex)./L;
    
    % Determine which way to project the mid-point by guessing an
    % initial projection and testing if that projection is inside (1)
    % or outside (0) the domain PTS.
    in = PointInPolygon(Midp(1) - nx*(L/2), Midp(2) - ny*(L/2), PTS.Points{cp}(:,1), PTS.Points{cp}(:,2));
    
    if in; sgn = -1; elseif in == 0; sgn = +1; end
    
    %------------------------------------------------------------------------------
    % Now we know which direction to project the midpoint, use
    % this test on the starting point of the node string in p
    % to see which end point should be the the next node and so on.
    %------------------------------------------------------------------------------
    
    xb = p(:,1); yb = p(:,2); xb = xb(fb)'; yb = yb(fb)'; % Extract coordinates
    
    % Determine which edge is going the same direction as the original
    
    % Find the starting location in [xb,yb], test the first edge associated
    % with the starting location
    
    k = find( ((xb(1,:) == p(loca,1)) & (yb(1,:) == p(loca,2))) )
    
    edgex = [xb(1,k) xb(2,k)];
    edgey = [yb(1,k) yb(2,k)];
    
    % Compute Mid-point on edge
    Midp = [mean(edgex) , mean(edgey)]; % MID point
    
    % Compute normals
    L = sqrt(diff(edgex).^2 + diff(edgey).^2);
    nx =  diff(edgey)./L;
    ny = -diff(edgex)./L;
    
    Midp
        
    % Test projection obtained from above.
    in = PointInPolygon(Midp(1) + sgn*nx*(L/2), Midp(2) + sgn*ny*(L/2), PTS.Points{cp}(:,1), PTS.Points{cp}(:,2));
    
    % If test fails (in == 0), then choose the other edge in the xb, yb
    % edge list.
    if in
        
        % Passed test
        % Remove points from edge list, xb & yb
        xb(:,k) = nan;
        yb(:,k) = nan;
        
    else
        
        k = find( ((xb(2,:) == p(loca,1)) & (yb(2,:) == p(loca,2))) );
        edgex = [xb(2,k) xb(1,k)];
        edgey = [yb(2,k) yb(1,k)];
        
        % Remove points from edge list, xb & yb
        xb(:,k) = nan;
        yb(:,k) = nan;
        
    end
    
    % Enter loop, connecting end points until end point is reached
    Looping = 1;
    ptr = 2; % Pointer to current end point
    
    while Looping
        
        % Find the next connecting edge with same end point
        ind = find(edgex(ptr) == xb & edgey(ptr) == yb,1,'first');
        
        % convert linear index to subscript
        [r,c] = ind2sub(size(xb),ind);
        
        if r == 1 % if r == 1, we want to grab the opposite end point
            
            ptr = ptr+1;
            edgex(ptr) = xb(2,c); edgey(ptr) = yb(2,c);
            
            % Mark recorded points as nan's
            xb(:,c) = nan; yb(:,c) = nan;
            
        else
            
            c
            
            ptr = ptr+1;
            edgex(ptr) = xb(1,c); edgey(ptr) = yb(1,c);
            
            % Mark recorded points as nan's
            xb(:,c) = nan; yb(:,c) = nan;
            
        end
        
        % Mark recorded points as nan's
        %xb(:,c) = nan; yb(:,c) = nan;
        
        % Check if we've reached end point
        if ( edgex(ptr) == p(locb,1) && edgey(ptr) == p(locb,2) )
            Looping = 0;
            continue;
        end
        
        
    end
    
    % Transpose vectors
    edgex = edgex';
    edgey = edgey';
    
    % Get running total for NETA
    NETA = length(edgex) + NETA;
    
    % Store NVDLL
    NVDLL(i) = length(edgex);
    
    % Define nodal points
    for n = 1:length(edgex)
        
        loc = find( edgex(n) == p(:,1) & edgey(n) == p(:,2) );
  
        NBDV{i}(n) = loc;
        
    end

end

end