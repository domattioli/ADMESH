function h0 = CurvatureFunction(h0,D,gradD,X,Y,K,g,hmax,hmin,Settings,sb)
% curvature - Computes initial mesh size h_curve based on boundary
% curvature
%
% Syntax:  h_curve = curvature(D,gradD,X,Y,K,g,delta,guiFig)
%
% Inputs:
%    D - Distance function computed by the distance function.
%    X - x-coordinates to rectangular grid
%    Y - y-coordinates to rectangular grid
%    delta - Grid spacing
%    g - grading requirement
%    K - number of elements per radian
%    guiFig - handle that identifies the figure
%
% Outputs:
%    h_curve - mesh size based on curvature
%
% Other m-files required: none
% Subfunctions: meshgrid
% MAT-files required: none

% Author: Dustin West
% Equation obtained from Mesh Generation for Implicit Geometries by Per-Olof Persson
% The Ohio State University
% email address: dww.425@gmail.com
% August 2013; Last revision: 10-August-2013

%------------- BEGIN CODE --------------

%------------------------------------------------------------------------------
% Curvature Status
%------------------------------------------------------------------------------
Status = Settings.K.Status;

%------------------------------------------------------------------------------
% Compute Curavture, If On.
%------------------------------------------------------------------------------
if strcmp(Status,'On') 
    
    sb.ProgressBar.setVisible(true) 
    sb.ProgressBar.setIndeterminate(true); 
    sb.setText('Computing Boundary Curvature...')
                
    % Compute the magnitude of the gradient
    m = ( sqrt(gradD.x.^2 + gradD.y.^2) );
    
    % Compute the curvature using the divergence formula ( See Ron
    % Goldman,Per-Olof Persson)
    kappa = abs(divergence(X,Y,gradD.x./m,gradD.y./m));

    % Find points that are within abs(D) <= 2*delta
    I = abs(D) <= 2*hmin;
    
    % Initialize the curvature mesh size function
    h_curve = ones(size(D)).*hmax;
    
    % Specify the number of elements per radian
    K = K/pi;
    
    % Compute the mesh size for the narrow band around the boundary. This
    % equation factors in the distance function and grading to best obatin
    % actual curvature values since we are using the background mesh nodes,
    h_curve(I) = abs( (1 + kappa(I).*abs(D(I)))./ (K.*kappa(I)) ) - g.*D(I);
    
    % Enforce boundary conditions
    h_curve(h_curve < hmin) = hmin;
    h_curve(h_curve > hmax) = hmax;
    
    % Compare initial conditions and save
    h0 = min(h_curve, h0);
    
    sb.ProgressBar.setIndeterminate(false); 
    sb.ProgressBar.setVisible(false) 
        
end

end