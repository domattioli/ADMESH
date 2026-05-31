function p = projectBackToBoundary(phi,p,geps)

pdist = phi.f(p); 

%ox = find(pdist > 0);
ix = pdist > -geps*100;

% pgradx = phi.fx(p(ox,:));
% pgrady = phi.fy(p(ox,:));
% 
% p(ox,:)= p(ox,:)-[pdist(ox).*pgradx,pdist(ox).*pgrady];

p(ix,:)= p(ix,:)-[pdist(ix).*phi.fx(p(ix,:)),pdist(ix).*phi.fy(p(ix,:))];
