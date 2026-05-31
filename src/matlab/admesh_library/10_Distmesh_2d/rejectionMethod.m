function p = rejectionMethod(p,MeshFun)

% Probability to keep point
r0 = 1./(MeshFun(p)).^2;

% Rejection method
p = p(rand(size(p,1),1)<r0./max(r0),:);

end
