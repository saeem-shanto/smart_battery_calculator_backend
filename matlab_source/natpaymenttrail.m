clear all
global pv ld  xx yy cap_pv
lb=0; 
ub=50;
% dtin=xlsread('VaniData.xls'); % ORIGINAL DATA FILE
dtin=xlsread('Vanikavipuldata.xls'); % NEW DATA FILE
pv1=dtin(:,1); ld11=dtin(:,2); nn=length(pv1);
%scaling factor
% sc=;
ld1=ld11;
% ld1=(ld11/14.2766)*sc;

sfld=0; % scaling factor of load if it scale by 2% put 0.02
% ld=ld1.*(1+sfld)*(16110000)/5211; (for pedes paper)
ld=ld1.*(1+sfld);

%degradation factor of pv
dpv=0; % degradation factor for pv per year (if it degrades by 2%, put 0.02 as dpv)
% pv2= (1-dpv).*pv1;
pv2= (1-dpv).*pv1*(1742.7/1737);
icount=0;
% cap_pva=[0: 0.5: 5]; nb=length(cap_pva);
% for ib=1:nb
% cap_pv=cap_pva(ib);
cap_pv=5;
% cap_pv=5;
    pv=cap_pv*pv2/3;
% pv=pv2;

% ab=80;
%  nl=length(ab);
% for q= 1:nl
%   Ab=ab(q);
% Ab=78.04;  %for 600$ of bess
% Ab=45;
%  Ab= 52.0285; % for $400/kwh
%  Ab= 0; % for only PV case
 Ab=50; % it was taken to find out the power exchnage
 xx=Ab;

[x fval exitflag]=fminbnd(@battrail, lb, ub);

fprintf('\n')
    if exitflag == 1;
        icount=icount+1;
        outa(icount,:)=[x yy xx cap_pv];
      
        fprintf('  Optimal battery size:            %7.1f kWh \n', x)
        fprintf('  Net Payment:                     %7.1f $ \n', yy(1));
        fprintf('  Export to grid:                  %7.1f kWh \n', yy(2));
        fprintf('  Import from grid:                %7.1f kWh \n', yy(3));
%         fprintf('  Battery annual payment rate:     %7.1f $/kWh/year \n',xx)
        fprintf('  Battery annual payment rate:     %7.1f $/kWh/year \n',yy(6));
        fprintf('  Losses:                          %7.2f kWh \n', yy(4));
        fprintf('  Retail price:                    %7.3f dollar/kWh \n', yy(5));
        fprintf('  Feed-In-Tariff:                  %7.3f dollar/kWh \n', yy(7));
        fprintf('  Size of PV panel:                %7.3f kW \n', cap_pv);
    else
        fprintf('  Program did not converge, exitflag is %3.0f \n',exitflag)
    end 
%  end 
    csvwrite('Results_RPAtrail400.csv', outa);
% end 
%  rin=xlsread('Results_RPAtrail400.csv');
% bsize=rin(:,1); 
% netpayment=rin(:,2);
% export=rin(:,3);
% import=rin(:,4);
% losses=rin(:,5);
% rp=rin(:,6);
% ab=rin(:,7);
% fit=rin(:,8);
% pvsize=rin(:,9);
% plot(yy(6), x)
% 6/2/2017
% make one moral global variable for Ab
% made a loop for Ab
% produced graphs for system without battery
% saved result in excel file as well
% replaced Ab by loop of Ab (battery annual payment rate)

% 23/2/2018
% changed tehretail price and fir to 0.48 and 0.17
% changed the losses equation 

% 27/2/2018
% Step size of 2 is taken for Ab instead of 10 to produce more smooth curve
% change the value of Ab when power exchange to grid needs to find out
%6/3/2018
% include feed in tariff in results

% 31/05/2018
%taking Ab as 78.0427 for $600 bess and at discount rate 5.09% as per
%report of australian energy council solar report 2018

%21/6/2018
% to get only pv results, change upper limit to zero and ab to zero

%28.06.2018
%PLOTS FOR DIFFERENT fit for SA
%Uploaddat afro different states and save in different file. upoad rp and
%fit and pv,ld data

%1 feb 2019
% always upload right file  'VaniData.xls'