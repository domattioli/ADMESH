if isfield(PTS,'BC') && ~isempty(PTS.BC)
    
    %-------------------------------------------------------------------
    % Initialize cells for edge constraints & fixing points (pfix)
    %-------------------------------------------------------------------
    nT      = length([PTS.BC.num]); % Total number of segments/points
    cPoints = cell(nT,1);           % Cell for holding all points
    ixC     = find(ismember([PTS.BC.num],[3 13 23 4 5 24 25 18]))';
    nC      = length(ixC);          % Total number of edge constraints
    if nC > 0; C = cell(nC,1); end  % Initialize delaunay constraints matrix as a cell
    
    % Initialize mesh structure
    MESH.BC(nT,1) = ...
        struct('num',[],'type',[],'nodes',[],'data',[]);
    
    %-------------------------------------------------------------------
    % Build line constraints (BC == 18)
    %-------------------------------------------------------------------
    % delaunay triangulation requires a unique set of coordinates.
    % This poses a challenge for handling constraints with junctions
    % that have a common point. The following algorithm creates a
    % unique set of coordinates and modifies the constraints matrix
    % to handle junctions appropriately
    
    ix = find(ismember([PTS.BC.num],18)); % Find location
    
    if ~isempty(ix) % If there are any line constraints
        
        % Create cell array for storing length of each line segment
        l = cell(numel(ix),1);
        
        % Loop over each line segment
        for k = 1:numel(ix)
            
            % Store coordinates in cell array. Space array equally based on
            % minimum element size
            cPoints{i} = SpacePolyEqually(PTS.BC(ix(k)).points,hmin);
            
            l{k} = size(cPoints{i},1);      % Store length of segment
            i = i + 1;                      % Increment index counter
            
        end
        
        % Convert cell to matrix. Compute cumulative sum of the lengths
        pl = cell2mat(cPoints); l = cumsum(cell2mat(l));
        
        % Create unique coordinate set with back pointers
        [~,~,ic] = unique(pl,'rows','stable');
        
        % Determine the constraints matrix based on unique data set
        for k = 1:numel(ix)
            
            % Increase index
            s = e + 1;
            e = l(k);
            
            C{j} = [ic(s:e-1) ic(s+1:e)];
            
            % Assign node string in mesh structure
            MESH.BC(j).nodes = ic(s:e);
            
            % Assign number associated with constraint
            MESH.BC(j).num = PTS.BC(ix(k)).num;
            
            % Assign node string type
            MESH.BC(j).type = PTS.BC(ix(k)).type;
            
            % Check for channel width data
            if ~isempty(PTS.BC(ix(k)).data)
                
                % Create xyz scatter set
                xyz = [PTS.BC(ix(k)).points PTS.BC(ix(k)).data];
                
                % Interpolate channel width to new coordinates
                F = scatteredInterpolant(xyz(:,1),xyz(:,2),xyz(:,3));
                
                MESH.BC(j).data = F(cPoints{k}(:,1),cPoints{k}(:,2));
                
            else
                
                MESH.BC(j).data  = zeros(size(cPoints{k},1),1);
                
            end
            
            j = j + 1;
            
            drawnow; % for graphics
            
        end
        
    end
    
    %--------------------------------------------------------
    % Build External barrier (BC == [3 13 23])
    %--------------------------------------------------------
    
    % Find all external barrier constraints in PTS
    ix = find(ismember([PTS.BC.num],[3 13 23]))';
    
    if ~isempty(ix) % If there are any constraints
        
        for k = 1:numel(ix)
            
            cPoints{i} = PTS.BC(ix(k)).points;  % Assign pfix
            
            MESH.BC(j).data = PTS.BC(ix(k)).data;
            
            MESH.BC(j).num  = PTS.BC(ix(k)).num;
            
            MESH.BC(j).type = PTS.BC(ix(k)).type;
            
            % Increase index
            s = e + 1;
            e = size(cPoints{i},1) + e;
            
            % Do not want to constrain last point with first point
            C{i} = [ (s:e-1)' , (s+1:e)' ]; % Assign constraints
            
            % Assign node string in mesh structure
            MESH.BC(j).nodes = (s:e)';
            
            i = i + 1;
            
            j = j + 1;
            
            drawnow; % for graphics
            
        end
        
    end
    
    %--------------------------------------------------------
    % Build Internal barrier (BC == [4 5 24 25])
    %--------------------------------------------------------
    
    % Find all external barrier constraints in PTS
    ix = find(ismember([PTS.BC.num],[4 5 24 25]))';
    
    if ~isempty(ix)
        
        for k = 1:numel(ix)
            
            % Note: weirs are not closed boundaries themselves but are
            % stored that way for computing the signed distance function.
            % For constraining we need to put the coordinates back into
            % their original format.
            
            % Store data
            MESH.BC(j).data = PTS.BC(ix(k)).data;
            
            % Store constraint value
            MESH.BC(j).num  = PTS.BC(ix(k)).num;
            
            % Store constraint value
            MESH.BC(j).type = PTS.BC(ix(k)).type;
            
            % Number of nodes in each segment
            n = (length(PTS.BC(ix(k)).points(:,1)) - 1)/2;
            
            % Store first segment in pfix
            cPoints{i} = PTS.BC(ix(k)).points(1:n,1:2);
            
            s = e + 1; % Start indexing counter
            
            % Ending point in constraints
            e = size(cPoints{i},1) + e;
            
            % Assign constraints
            % Do not want to constrain last point with first point
            C{i} = [ (s:e-1)' , (s+1:e)' ];
            
            % Store first node string
            nodes = (s:e)';
            
            % Store second segment
            i = i + 1;
            
            % Store second segment in pfix
            cPoints{i} = flipud( PTS.BC(ix(k)).points(n+1:end-1,1:2) );
            
            % Increase index
            s = e + 1;
            e = size(cPoints{i},1) + e;
            
            % Assign constraints
            % Do not want to constrain last point with first point
            C{i} = [ (s:e-1)' , (s+1:e)'];
            
            % Assign node string back to back in mesh structure
            MESH.BC(j).nodes = [nodes (s:e)'];
            
            i = i + 1;
            
            j = j + 1;
            
            drawnow; % for graphics
            
        end
        
    end
    
    % Convert cell to matrix
    C = cell2mat(C);
    
    %------------------------------------------------------------------------
    % Fix points for remaining BC's
    %------------------------------------------------------------------------
    ix = find(~ismember([PTS.BC.num],[4 5 24 25 3 13 23 18]))'; % Find all remaining BC's
    
    if ~isempty(idx)
        
        for k = 1:length(ix)
            
            % Store in pfix
            cPoints{i} = [PTS.BC(ix(k)).points(1,:); PTS.BC(ix(k)).points(end,:)];
            
            % Increase index
            s = e + 1;
            e = size(cPoints{i},1) + e;
            
            % Store starting and ending nodes in mesh structure.
            % The final node string will be extracted after mesh is complete.
            MESH.BC(j).nodes = (s:e)';
            
            % Store constraint value
            MESH.BC(j).num = -1;
            
            % Store constraint value
            MESH.BC(j).type = PTS.BC(ix(k)).type;
            
            i = i + 1;
            
            j = j + 1;
            
            drawnow; % for graphics
            
        end
        
    end
    
    
    
    
    % External Boundary
    ix = find(ismember([PTS.BC.num],[0 2 10 12 20 22 30])); % Find location
    
    for k = 1:numel(ix)
        
        h = line(PTS.BC(ix(k)).points(:,1),PTS.BC(ix(k)).points(:,2));
        
        set(h,...
            'Color','k',...
            'LineWidth',LineWidth,...
            'tag','External BC',...
            'UserData',ix(k),'uicontextmenu',hcmenu)
        
        uistack(h, 'top')
        
    end
    
    % Internal Boundary
    ix = find(ismember([PTS.BC.num],[1 11 21])); % Find location
    
    for k = 1:numel(ix)
        
        h = line(PTS.BC(ix(k)).points(:,1),PTS.BC(ix(k)).points(:,2));
        
        set(h,...
            'Color',[0 .5 0],...
            'LineWidth',LineWidth,...
            'tag','Internal BC',...
            'UserData',ix(k),'uicontextmenu',hcmenu)
        
        uistack(h, 'top')
        
    end
    
    % Internal Constraints
    ix = find(ismember([PTS.BC.num],[4 24 5 25])); % Find location
    
    for k = 1:numel(ix)
        
        h = line(PTS.BC(ix(k)).points(:,1),PTS.BC(ix(k)).points(:,2));
        
        set(h,...
            'Color','r',...
            'LineWidth',LineWidth,...
            'tag','Internal Constraint',...
            'UserData',ix(k),'uicontextmenu',hcmenu)
        
        uistack(h, 'top')
        
    end
    
    % External Constraints
    ix = find(ismember([PTS.BC.num],[3 13 23])); % Find location
    for k = 1:numel(ix)
        
        h = line(PTS.BC(ix(k)).points(:,1),PTS.BC(ix(k)).points(:,2));
        
        set(h,...
            'Color','r',...
            'LineWidth',LineWidth,...
            'tag','External Constraint',...
            'UserData',ix(k),'uicontextmenu',hcmenu)
        
        uistack(h, 'top')
        
    end
    
    % Open Ocean
    ix = find(ismember([PTS.BC.num],-1)); % Find location
    for k = 1:numel(ix)
        
        h = line(PTS.BC(ix(k)).points(:,1),PTS.BC(ix(k)).points(:,2));
        
        set(h,...
            'Color','b',...
            'LineWidth',LineWidth,...
            'tag','Open Ocean',...
            'UserData',ix(k),'uicontextmenu',hcmenu)
        
        uistack(h, 'top')
        
    end
    
    % Line
    ix = find(ismember([PTS.BC.num],18)); % Find location
    for k = 1:numel(ix)
        
        h = line(PTS.BC(ix(k)).points(:,1),PTS.BC(ix(k)).points(:,2));
        
        set(h,...
            'Color','r',...
            'LineWidth',LineWidth,...
            'tag','Line Constraint',...
            'UserData',ix(k),'uicontextmenu',hcmenu)
        
        uistack(h, 'top')
        
    end
    
else
    
    MESH.BC = [];                   % Set mesh struct to []
    C = [];                         % Set delaunay constraints matrix to empty
    nC = 0;                         % 0 points to constrain
    p=unique(p,'rows','stable');    % remove duplicate nodes
    
    return
    
    
end