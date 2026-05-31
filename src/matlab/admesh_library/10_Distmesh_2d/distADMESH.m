function MESH = distADMESH(PTS,D,H,xyzFun,hmin,sb,pH,viewStatus)
% distmesh2d - Generates a mesh based on mesh size h
%
% Syntax:  [p,t] = distmesh2d(DistanceFun,MeshSizeFun,hmin,guiFig)
%
% Inputs:
%    DistanceFun - gridded interpolant of the Distance Function
%    MeshSizeFun - gridded interpolant of the Mesh Size Function
%    hmin        - minimum element size
%    guiFig - handle that identifies the figure
%
% Outputs:
%    p - points of delaunay triangulation
%    t - connectivity list
%
% Other m-files required: none
% Subfunctions: none
% MAT-files required: none

% DISTMESH2D 2-D Mesh Generator using Distance Functions.
% distmesh2d.m v1.1
% Copyright (C) 2004-2012 Per-Olof Persson. See COPYRIGHT.TXT for details.
%
% Author of Adjustments: Dustin West, Colton Conroy, Ethan Kubatko
% The Ohio State University
% email address: dww.425@gmail.com
% August 2013; Last revision: 08-August-2013
%--------------------------- BEGIN CODE -----------------------------------

%--------------------------------------------------------------------------
% GUI check - Check if user wants to view mesh generation
%--------------------------------------------------------------------------
viewMesh = (get(viewStatus,'value') == 2); axes(pH); drawnow

%--------------------------------------------------------------------------
% Initialize variables
%--------------------------------------------------------------------------
ttol    = .01;           % Specifies how far the points can move (relatively) before a retriangulation
Fscale  = 1.15;         % "Internal pressure" of truss    
deltat  = .3;           % Time step in Euler's method
geps    = .001*hmin;    % Tolerance in the geometry evaluations.
densityctrlfreq= 75;    % Frequency in which to check for nodes that are too close to one another
niter   = 1000;         % Number of iterations
pold    = inf;          % Initialize current positions
qold    = 0;            % Intitalize current element quality

%--------------------------------------------------------------------------
% Create initial distribution in bounding box (equilateral triangles)
%--------------------------------------------------------------------------
sb.setText('Creating initial distribution of nodal points...')
p = createInitialPointList(D.f,PTS,hmin,geps); drawnow

%--------------------------------------------------------------------------
% Apply the rejection method
%--------------------------------------------------------------------------
p = rejectionMethod(p,H); drawnow

%--------------------------------------------------------------------------
% Apply mesh constraints and fixed points
%--------------------------------------------------------------------------
[p,nC,C,MESH] = GetMeshConstraints(p,hmin,PTS); drawnow

N = size(p,1); % number of nodes

in = ((nC+1):N)'; % Vector of non-pfix indices

%--------------------------------------------------------------------------
% Update status bar
%--------------------------------------------------------------------------
sb.ProgressBar.setVisible(true)
set(sb.ProgressBar, 'Minimum',1, 'Maximum',niter, 'Value',1)
sb.setText(['Generating mesh... ' num2str(0,'%.2f') '%'])
drawnow

%--------------------------------------------------------------------------
% Remove previous plot before starting
%--------------------------------------------------------------------------
if viewMesh == 1; 
    plotItems = get(pH, 'Children');
    if ~isempty(plotItems); delete(plotItems); end
    colorbar('delete') % Delete current colorbar
    drawnow
end

%--------------------------------------------------------------------------
% Generate Mesh
%--------------------------------------------------------------------------
for k = 1:niter
    
    drawnow; % for graphics
    
    % Retriangulation by the Delaunay algorithm 
    if( max(sqrt(sum((p-pold).^2,2))/hmin) > ttol )  % Any large movement?

        % Save current positions
        pold=p;
        
        % Perform Delaunay Triangulation
        if isempty(C)
            dt = delaunayTriangulation(p);
        else
            dt = delaunayTriangulation(p,C);
        end

        % Compute centroids & Interpolate distances 
        ind = D.f((p(dt(:,1),:)+p(dt(:,2),:)+p(dt(:,3),:))/3) < -geps;
        
        % Keep interior triangles
        t = sort(dt(ind,:),2); drawnow; % for graphics

        % Describe each bar by a unique pair of nodes
        bars = unique([t(:,[1,2]);t(:,[1,3]);t(:,[2,3])],'rows'); 
        
        % Graphical output of the current mesh
        if (get(viewStatus,'value') == 2)
            
            % If user turns on view in middle of run, delete plot
            if viewMesh == 0;
                plotItems = get(pH, 'Children');
                if ~isempty(plotItems); delete(plotItems); end
                colorbar('delete') % Delete current colorbar
                viewMesh = 1; drawnow
                
                % Plot mesh
                meshPlot = patch(...
                    'vertices',p,...
                    'faces',t,...
                    'edgecol',[0 .4 .8],...
                    'facecol','none',...
                    'Tag','Mesh');
                
            end
            
            if k == 1
                % Plot mesh
                meshPlot = patch(...
                    'vertices',p,...
                    'faces',t,...
                    'edgecol',[0 .4 .8],...
                    'facecol','none',...
                    'Tag','Mesh');
                
            else
                meshPlot.Vertices = p;
                meshPlot.Faces = t;
            end
            
            drawnow; pause(1e-12);
            
        end
        
    end
  
    % Move mesh points based on bar lengths L and forces F
    barvec  = p(bars(:,1),:)-p(bars(:,2),:);              % List of bar vectors
    L       = sqrt(sum(barvec.^2,2));                     % L = Bar lengths
    hbars   = H((p(bars(:,1),:)+p(bars(:,2),:))/2); % hbar = mesh size
    L0      = hbars*Fscale*sqrt(sum(L.^2)/sum(hbars.^2)); % L0 = Desired lengths
    
    % Density control
    %if( (mod(k,densityctrlfreq) == 0) && (k < niter-5) )
    if( (mod(k,densityctrlfreq) == 0) && (k < niter-5) )
        
        %set(sb.ProgressBar,'Value',k)
        %sb.setText(['Generating mesh... ' num2str((k/niter)*100,'%.0f') '%'])
        
        if any(L0>2*L) % Remove points that are too close together
            
            p(setdiff(reshape(bars(L0>2*L,:),[],1),1:nC),:)=[];
            
            N=size(p,1); 
            pold=inf;
            
            in = ((nC+1):N)';
            
            continue;
            
        elseif(k > niter/2)
            
            p = BoundaryDensityControl(p,t,C);
            
            p = ConstraintDensityControl(p,nC,C,H);
            
            N=size(p,1); 
            pold=inf; 
            in = ((nC+1):N)';
            
            continue;
            
        end
        
    end

    F            = max(L0-L,0);         % Bar forces (scalars)
    Fvec         = F./L*[1,1].*barvec;  % Bar forces (x,y components)
    Ftot         = full(sparse(bars(:,[1,1,2,2]),ones(size(F))*[1,2,1,2],[Fvec,-Fvec],N,2));
    Ftot(1:nC,:) = 0;                   % Force = 0 at fixed points
    p            = p+deltat*Ftot;       % Update node positions
    
    % Bring outside points back to the boundary
    p(in,:) = projectBackToBoundary(D,p(in,:),geps);
    
    % Check element quality. Keep track of best triangulation
    if k > (niter-50)
        [q, ~] = MeshQuality(p,t,0,'Triangle');
        if q > qold; P = p; T = t; qold = q; end
    end
    
    set(sb.ProgressBar,'Value',k)
    sb.setText(['Generating mesh... ' num2str((k/niter)*100,'%.0f') '%'])
    
end

sb.ProgressBar.setVisible(false)

%--------------------------------------------------------------------------
% Clean up 
%--------------------------------------------------------------------------
sb.setText('Cleaning up final mesh...')

T = BoundaryCleanUp(P,T,C); % Remove bad boundary elements

[p,t]=fixmesh(P,T);         % Fix mesh

%--------------------------------------------------------------------------
% store final mesh results
%--------------------------------------------------------------------------
MESH = createMeshStruct(t,p,MESH,PTS,xyzFun);

assignin('base','MESH',MESH)
