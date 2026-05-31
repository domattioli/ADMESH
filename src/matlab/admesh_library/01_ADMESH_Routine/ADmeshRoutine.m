function ADmeshRoutine(varargin)
% ADvanced Mesh Generator for hydrodynmaic models 1.1.6 (ADMESH)
%
% Variables:
%   Edge Structure Variable:
%    PTS : Data structure containing polygon (x & y) points of boundaries
%          and boundary conditions
%
%   User specified Variables:
%    res    : a factor multiple, either 1,3,or 4, of hmin controlling the
%             grid spacing.
%    hmin   : Minimum element size
%    hmax   : Maximum element size
%    K      : parameter specifying the number of elements per radian of
%             curvature
%    R      : parameter specifying the number of elements that span half
%             a channel/tributary
%    xyz    : gridded interpolant of elevation
%    s      : parameter specifying the density of elements in areas with
%             large changes in elevation
%    C      : parameter specifying the number of elements per tidal
%             wavelength
%    T      : frequency of wave propogation
%    g      : grading limiting
%
%   Function Output Variables
%    X           : x values of background grid
%    Y           : y values of background grid
%    delta       : cellsize (hmin/res)
%    D           : distance function ('-' values = region to be meshed)
%    gradD       : gradient of distance function
%    Z           : bathymetry on background mesh
%    h_curve     : mesh size values determined via curvature
%    h_lfs       : mesh size values determined via local feature size
%    h_bathy     : mesh size values determined via horizontal length scale
%    h_tide      : mesh size values determined via linear wave speed
%    DistFun     : gridded interpolant of distance function
%    DistGxFun   : gridded interpolant of gradient (x-direction) function
%    DistGyFun   : gridded interpolant of gradient (y-direction) function
%    MeshFun     : gridded interpolant of mesh size function
%    h           : mesh resolution determined via solution of PDE
%    mesh        : Data structure containing x and y coordinates of
%                  unstructured nodes, connectivity of mesh and node
%                  strings of boundary conditions.
%    minEQ       : minimum element quality
%    meanEQ      : mean element quality
%--------------------------------- BEGIN CODE -----------------------------

%--------------------------------------------------------------------------
% Get GUI data
%--------------------------------------------------------------------------
fig = varargin{1}; gui = guidata(fig);


%--------------------------------------------------------------------------
% Set ADMESH button to cancel
%--------------------------------------------------------------------------
% Turn off colormap
SetContourStatus(gui.Window,nan,'off'); drawnow

%--------------------------------------------------------------------------
% Check to make sure user an edge structure has been uploaded
%--------------------------------------------------------------------------
try
    quit = CheckUserInput(fig); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

% Stop ADMESH routine if something's not right
if quit == 1
    return
end

%--------------------------------------------------------------------------
% Assign ADmesh parameters
%--------------------------------------------------------------------------
try
    [res,hmax,hmin,K,R,s,C,T,g] = DealVariables(fig); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Save ADMESH settings for appending to file
%--------------------------------------------------------------------------
try
    Settings = SaveSettings(fig); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Begin ADmesh
%--------------------------------------------------------------------------
t=cputime; % Start Timer for ADmesh

%--------------------------------------------------------------------------
% Create structured background mesh
%--------------------------------------------------------------------------
try
    [X,Y,delta] = CreateBackgroundGrid(gui.PTS,hmax,hmin,res,gui.sb); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Generating cubic spline approximation of the boundary
%--------------------------------------------------------------------------
PTS = gui.PTS;

% gui.sb.setText('Generating cubic spline approximation of the boundary...')
%
% for k = 1:length(PTS.Points)
%
%     line = SpacePolyEqually(PTS.Points{k},hmin);
%
%     % Fit cubic spline
%     line = unique(fnplt(cscvn(line'))','rows','stable');
%
%     PTS.Points{k} = [line; line(1,:)];
%
%      drawnow
%     %hold on
%     %h1(k) = plot(line(:,1),line(:,2),'r','linewidth',2);
%
% end

%pause
%delete(h1)

%--------------------------------------------------------------------------
% Calculate distance function
%--------------------------------------------------------------------------
try
    [D,gradD,IB]   = SignedDistanceFunction(PTS,X,Y,delta,hmax,gui.sb); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%figure
%contourf(X,Y,D)
%colorbar
%daspect([1 1 1])
%hold on
%plot(X(IB),Y(IB),'g.')
%return

%--------------------------------------------------------------------------
% Initialize initial condition for mesh size function
%--------------------------------------------------------------------------
try
    h0 = hmax*ones(size(D));
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Compute boundary curvature
%--------------------------------------------------------------------------
try
    h0 = CurvatureFunction(h0,D,gradD,X,Y,K,g,hmax,hmin,Settings,gui.sb); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Compute local feature size
%--------------------------------------------------------------------------
try
    h0 = MedialAxisFunction(h0,X,Y,D,gradD,R,hmin,hmax,Settings,gui.sb); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Interpolate bathymetry to background grid if needed.
%--------------------------------------------------------------------------
try
    Z  = CreateElevationGrid(X,Y,gui.xyzFun,Settings,gui.sb); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Compute bathymetry
%--------------------------------------------------------------------------
try
    h0 = BathymetryFunction(h0,D,X,Y,Z,s,hmin,hmax,delta,Settings,gui.sb); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Compute dominate tide function
%--------------------------------------------------------------------------
try
    h0 = Dominate_tide(h0,T,C,Z,size(X),hmax,hmin,Settings);  drawnow; clear Z
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Enforce boundary conditions
%--------------------------------------------------------------------------
try
    h0 = EnforceBoundaryConditions(h0,X,Y,D,IB,gui.PTS,hmax,hmin,gui.sb); drawnow
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Compute mesh size function
%--------------------------------------------------------------------------
try
    h  = MeshSizeFunction(h0,D,hmax,hmin,g,delta,gui.sb); drawnow; clear h0
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

% h(D > 0) = nan;
% figure
% contourf(X,Y,h)
% colorbar
% return

%--------------------------------------------------------------------------
% Create an interpolant surface for the distance and mesh size function
%--------------------------------------------------------------------------
try
    
    gui.sb.setText('Preparing to start mesh generation...')
    
    % Create distance function, overwrite D
    Dist.f   = griddedInterpolant(X',Y',D','linear');
    Dist.fx  = griddedInterpolant(X',Y',gradD.x','linear');
    Dist.fy  = griddedInterpolant(X',Y',gradD.y','linear');
    
    % Create mesh size function
    H        = griddedInterpolant(X',Y',h','linear');
    
    % Get minimum element size
    hmin        = min(h(:));
    
    % Clear uneeded variables
    drawnow
    clear gradD D X Y h
    
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

%--------------------------------------------------------------------------
% Generate mesh
%--------------------------------------------------------------------------
%try
    %MESH = distquadmesh2d(PTS,DistFun,DistGxFun,DistGyFun,MeshFun,xyzFun,hmin,Settings);
    gui.MESH = distADMESH(PTS,Dist,H,gui.xyzFun,hmin,gui.sb,gui.ViewAxes,gui.ViewStatus);
    clear phi MeshFun
% catch ME
%     
%     gui.sb.setText('Ready.')
%     errordlg(ME.message,'ADMESH+'); return
% end

%--------------------------------------------------------------------------
% Update guidata
%--------------------------------------------------------------------------
guidata(fig,gui);

%--------------------------------------------------------------------------
% Plot Final Results
%--------------------------------------------------------------------------
try
    gui.sb.setText('Displaying final mesh...')
    PlotMesh(gui,.1)
catch ME
    gui.sb.setText('Ready.')
    errordlg(ME.message,'ADMESH+'); return
end

hold on
for i = 1:length(PTS.Points)
   plot( PTS.Points{i}(:,1),PTS.Points{i}(:,2),'g','linewidth',3)
end

%--------------------------------------------------------------------------
% Convert CPU time to hours minutes seconds time string
%--------------------------------------------------------------------------
time_string = seconds2HrMinSec(cputime-t);

%--------------------------------------------------------------------------
% Update status bar
%--------------------------------------------------------------------------
gui.sb.setText(['Run time: ' , time_string ])

%--------------------------------------------------------------------------
% Update .mat file
%--------------------------------------------------------------------------
if ~isempty(gui.FilePath)
    save(gui.FilePath,'Settings', '-append' );
end

% Turn on coordinate display.
set(gui.Window,'WindowButtonMotionFcn' , @CoordDisplay)

%--------------------------------------------------------------------------
% Screwing around
%--------------------------------------------------------------------------

ext_plot = 0;

if ext_plot == 1
    
    figure('units','normalized','pos',[.23,.15,.45,.7],'color','w'); hold on    % Initialize figure
    
    patchinfo.Vertices              = gui.MESH.Points;
    patchinfo.Faces                 = gui.MESH.ConnectivityList;
    patchinfo.EdgeColor             = 'b';
    patchinfo.FaceColor             = 'none';
    patchinfo.linewidth             = 1.0;
    patch(patchinfo);
    xlabel('X (m)','FontWeight','bold','FontSize',10)                             % X-Label
    ylabel('Y (m)','FontWeight','bold','FontSize',10)                             % Y-Label
    daspect([1 1 1])                            % Data aspect ratio
    
    xmin = min(gui.MESH.Points(:,1));
    xmax = max(gui.MESH.Points(:,1));
    ymin = min(gui.MESH.Points(:,2));
    ymax = max(gui.MESH.Points(:,2));
    
    XMIN = xmin - (xmax-xmin)*.05;
    XMAX = xmax + (xmax-xmin)*.05;
    YMIN = ymin - (ymax-ymin)*.05;
    YMAX = ymax + (ymax-ymin)*.05;
    
    axis([XMIN XMAX YMIN YMAX])
    
    hold on
    
    % Plot constraints
    for k = 1:numel(gui.MESH.Constraints)
        
        %    Determine line color
        if gui.MESH.Constraints(k).num == -1 % Open
            
            %         nStr = gui.MESH.Constraints(k).nodeStr;
            %
            %         patchinfo.Faces             = [ nStr(1:end-1),nStr(2:end) ];
            %         patchinfo.EdgeColor         = 'b';
            %         patchinfo.linewidth         = 1.5;
            %         h                           = patch(patchinfo);
            %         set(h,'tag','Mesh')
            
        elseif any(gui.MESH.Constraints(k).num == [0 2 10 12 20 22 30]); % External Boundary
            
            %         nStr = gui.MESH.Constraints(k).nodeStr;
            %
            %         patchinfo.Faces             = [ nStr(1:end-1),nStr(2:end) ];
            %         patchinfo.EdgeColor         = 'k';
            %         patchinfo.linewidth         = 1.5;
            %         h                           = patch(patchinfo);
            %         set(h,'tag','Mesh')
            
        elseif any(gui.MESH.Constraints(k).num == [1 11 21]); % Internal Boundary
            
            %         nStr = gui.MESH.Constraints(k).nodeStr;
            %
            %         patchinfo.Faces             = [ nStr(1:end-1),nStr(2:end) ];
            %         patchinfo.EdgeColor         = 'g';
            %         patchinfo.linewidth         = 1.5;
            %         h                           = patch(patchinfo);
            %         set(h,'tag','Mesh')
            
        elseif any(gui.MESH.Constraints(k).num == [3 13 23]); % External Constraints
            %
            %         nStr = gui.MESH.Constraints(k).nodeStr;
            %
            %         patchinfo.Faces             = [ nStr(1:end-1),nStr(2:end) ];
            %         patchinfo.EdgeColor         = [.7 .5 0];
            %         patchinfo.linewidth         = 1.5;
            %         h                           = patch(patchinfo);
            %         set(h,'tag','Mesh')
            
        elseif any(gui.MESH.Constraints(k).num == 18); % Channel Constraints
            
            nStr = gui.MESH.Constraints(k).nodeStr;
            
            patchinfo.Faces             = [ nStr(1:end-1),nStr(2:end) ];
            patchinfo.EdgeColor         = 'r';
            patchinfo.linewidth         = 1.5;
            h                           = patch(patchinfo);
            set(h,'tag','Mesh')
            
        elseif any(gui.MESH.Constraints(k).num == [4 5 24 25]); % Internal Constraints
            
            %        % Plot first side
            %         nStr = gui.MESH.Constraints(k).nodeStr(:,1);
            %
            %         patchinfo.Faces             = [ nStr(1:end-1),nStr(2:end) ];
            %         patchinfo.EdgeColor         = [.7 .5 0];
            %         patchinfo.linewidth         = 1.5;
            %         h                           = patch(patchinfo);
            %         set(h,'tag','Mesh')
            %
            %         %Plot second side
            %         nStr = gui.MESH.Constraints(k).nodeStr(:,2);
            %
            %         patchinfo.Faces             = [ nStr(1:end-1),nStr(2:end) ];
            %         patchinfo.EdgeColor         = [.7 .5 0];
            %         patchinfo.linewidth         = 1.5;
            %         h                           = patch(patchinfo);
            %         set(h,'tag','Mesh')
            %
        end
        
    end
    
    % Modify current axes
    set(gca,'Ticklength',[0 0],'box', 'on','xcolor' ,'k','ycolor' ,'k')
    
    % Get axes limits
    xlim = get(gca,'XLim'); ylim = get(gca,'YLim');
    
    % Create borders
    
    % Compute border widths
    bwy = diff(ylim)/100;  bwx = bwy;
    
    % transparent borders
    patch([xlim(1)+bwx,xlim(2)-bwx,xlim(2)-bwx,xlim(1)+bwx],ylim(1) + bwy*[0,0,1,1],'k','FaceColor','none','clipping','off')
    patch([xlim(1)+bwx,xlim(2)-bwx,xlim(2)-bwx,xlim(1)+bwx],ylim(2) - bwy*[0,0,1,1],'k','FaceColor','none','clipping','off')
    patch(xlim(1) + bwx*[0,0,1,1],[ylim(1)+bwy,ylim(2)-bwy,ylim(2)-bwy,ylim(1)+bwy],'k','FaceColor','none','clipping','off')
    patch(xlim(2) - bwx*[0,0,1,1],[ylim(1)+bwy,ylim(2)-bwy,ylim(2)-bwy,ylim(1)+bwy],'k','FaceColor','none','clipping','off')
    
    % Number of bars
    nB = 5; xspace = linspace(xlim(1),xlim(2),nB*2);
    
    for k = 2:2:nB*2
        
        xp = [xspace(k-1) xspace(k-1) xspace(k) xspace(k)];
        patch(xp,ylim(1) + bwy*[0,1,1,0],'k','FaceColor','k','clipping','off')
        patch(xp,ylim(2) - bwy*[0,1,1,0],'k','FaceColor','k','clipping','off')
        
    end
    
    % Number of bars
    nB = 5;
    yspace = linspace(ylim(1),ylim(2),nB*2);
    
    for k = 2:2:nB*2
        
        yp = [yspace(k-1) yspace(k) yspace(k) yspace(k-1)];
        patch(xlim(1) + bwx*[0,0,1,1],yp,'k','FaceColor','k','clipping','off')
        patch(xlim(2) - bwx*[0,0,1,1],yp,'k','FaceColor','k','clipping','off')
        
    end
    
end

end
