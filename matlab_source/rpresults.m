rin=xlsread('Results_RPAtrail400.csv');
bsize=rin(:,1); 
netpayment=rin(:,2);
export=rin(:,3);
import=rin(:,4);
losses=rin(:,5);
rp=rin(:,6);
ab=rin(:,7);
fit=rin(:,8);
pvsize=rin(:,9);

figure(1)
plot(ab, bsize)

% figure(2)
%  plot(bsize, netpayment)
%  
%  figure(3)
%  plot(ab, bsize)
%  
%  figure(4)
%  plot(ab,netpayment)
%  
%  figure(5)
% plot(bsize,export,bsize,import)
% %  plot(pvsize, bsize)
%plot(pvsize, netpayment)
%  plot(bsize, netpayment)
%  plot(ab, bsize)
%  plot(ab,netpayment)
% % plot(bsize,export,bsize,import)
% plot(exp-imp) 
% plot(battin-battout)
% plot(soc)