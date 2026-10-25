% function f = battrail(x) 
x=15; % battery size
global pv ld xx yy cap_pv
dtin=xlsread('Vanikavipuldata.xls'); % NEW DATA FILE
pv1=dtin(:,1); ld11=dtin(:,2); nn=length(pv1);
%scaling factor
% sc=;
ld1=ld11;
daily_avg=14.2766;  %%%% this is the input customer can enter to show their daily avg consumption
avgscale=(daily_avg*365/sum(ld1));
ld=ld1.*avgscale;

%degradation factor of pv
dpv=0; % degradation factor for pv per year (if it degrades by 2%, put 0.02 as dpv)
pv2= (1-dpv).*pv1*(1742.7/1737);
icount=0;
% cap_pva=[0: 0.5: 5]; nb=length(cap_pva);
% for ib=1:nb
% cap_pv=cap_pva(ib);
cap_pv=6; % input 
    pv=cap_pv*pv2/3; % can be replaced by data of renewable ninja

socmin=0.10;
socmax=0.95;
i=0.02; % Input: Interest rate
IC= 8000; % Input: Installation cost 
lspan=10;
crf=(i*(1+i)^lspan)/(((1+i)^lspan)-1);
Ab=IC.*crf; % anuual installment for the whole package (pv+inv+battery or battery only)
dc=101/100; % Input: daily supply charges - will be provided by the customer
% fit=0.124;
% rp=0.3773;

rp_tou=[0.33;.165;0.165;0.165;0.165;0.165;0.165;0.165;0.165;0.33;0.33;0.33;
0.22;0.22;0.33;0.33;0.33;0.33;0.33;0.33;0.33;0.33;0.33;0.33;
]; % need to replace this with the rate input provided by customer
fit_tou=[0.03;.03;0.03;0.03;0.03;0;0;0;0.0;0;0;0;
0.02;0.02;0.03;0.03;0.03;0.03;0.03;0.03;0.03;0.03;0.03;0.03;
]; % need to replace this with the fit input provided by customer
% inputs are rp_tou and fit_tou which is value of retail price and fit for
% 24 hours
rpp=rp_tou.*ones(1,365); rp=rpp(:);
fitt=fit_tou.*ones(1,365); fit=fitt(:);
effb=0.95;
effc=0.96;
effd=0.96;
nn=length(pv);
beta=0.37; % power flow rate
expmax=5; % export limit
exp=zeros(nn,1);imp=zeros(nn,1);
convout=zeros(nn,1);convin=zeros(nn,1);battin=zeros(nn,1);battout=zeros(nn,1);
E=zeros(nn,1);Pd=zeros(nn,1);soc=zeros(nn,1);curt=zeros(nn,1);
SOCc=zeros(nn,1);SOCd=zeros(nn,1);Pbin=zeros(nn,1);Pbout=zeros(nn,1);
loss=zeros(nn,1);Pbbout=zeros(nn,1);Pbbin=zeros(nn,1);aimp=zeros(nn,1); RExp=zeros(nn,1);
%asumming battery is already discharged and power is imported in the first instance 
Pd(1)=pv(1)-ld(1); %Excess Power
soc(1)=socmin; % soc after first discharge
imp(1)=-Pd(1);
exp(1)=0;curt(1)=0;Pbin(1)=0;Pbout(1)=0;
loss(1)=Pd(1)+Pbin(1)-Pbout(1)+imp(1)-exp(1)-curt(1);
E(1)=Pd(1)*1; % 1 represents hour
 for t=2:nn
  Pd(t)=pv(t)-ld(t);   
  E(t)=Pd(t)*1;
    Cinv=beta*x; % battery inverter size 
  if Pd(t)>= 0%EXCESS POWER
     imp(t)=0;
     SOCc(t)=((socmax-soc(t-1))*x)/(effc*1);
     Pbbin(t)=min(Cinv,Pd(t));
     Pbin(t)=min(Pbbin(t),SOCc(t));
     soc(t)=soc(t-1)+((Pbin(t)*1*effc)/x);
     exp(t)=min(expmax,(Pd(t)-Pbin(t)));
     curt(t)=-(min(0,(5-Pd(t))));
else
      exp(t)=0;
      curt(t)=0;
      SOCd(t)=(((soc(t-1)-socmin)*x*effd*effb)/1);
      Pbbout(t)=min(Cinv,(-Pd(t)));
      Pbout(t)=min(Pbbout(t),SOCd(t)); 
      soc(t)=soc(t-1)-((Pbout(t)*1)/(x*effd*effb));
      imp(t)=(-Pd(t)-Pbout(t));
 %    if (soc(t-1)+((E(t)*effc)/(1*x))) < socmax  
 %        soc(t)=soc(t-1)+((E(t)*effc)/(1*x));
 %        convin(t)=(Pd(t)*1);
 %        battin(t)=(Pd(t)*1*effc);
 %    else 
 %        soc(t)=socmax;
 %        exp(t)=E(t)-((socmax-(soc(t-1)))*(1*x)/effc);
 % 
 %    end
 % else
 %      if (soc(t-1)+ (Pd(t)*1)/((1*x)*effb))>socmin
 %          soc(t)=soc(t-1)-((-Pd(t)/((1*x)*effd*effb))); 
 %          convout(t)=-Pd(t);
 %          battout(t)=-(Pd(t)/effd);
 %      else 
 %        imp(t)=-(Pd(t)*1)-((soc(t-1)-socmin)*(1*x)*effb*effd);
 %        soc(t)=socmin;
 % 
 %      end  
  end
  aimp(t)= imp(t).*rpp(t);
  RExp(t)=exp(t).*fit(t);

  Exp=sum(exp);
  Imp=sum(imp);
  Cout=sum(convout);
  Cin=sum(convin);
  Bin=sum(battin);
  Bout=sum(battout);
  % Losses=Imp-Exp;
  Losses=sum(Pd+Pbin-Pbout+imp-exp-curt);
% Losses=(Bin-Bout)+(Cin-Bin)+(Bout-Cout);
 end
% Ab= 40;
%  Aab=(((x)*Ab)+(cap_pv*130));
  % Aab=(((x)*Ab));
 % Aimp=(Imp*rp);
 Aip= sum(aimp); %import price
 Ar= sum(RExp); % revenue
DC= dc*365; % supply charges for year 

 % Ap=Aab+Aimp;
 % Ar=Exp*fit;
  
 Anp=Aip+Ab-Ar+DC;
 yy=[Anp Exp Imp Losses Ab ];
 
fprintf('\n')
    % if exitflag == 1;
        icount=icount+1;
        outa(icount,:)=[x yy cap_pv];
      
        fprintf('  Battery size:            %7.1f kWh \n', x)
        fprintf('  Net Payment:                     %7.1f $ \n', yy(1));
        fprintf('  Export to grid:                  %7.1f kWh \n', yy(2));
        fprintf('  Import from grid:                %7.1f kWh \n', yy(3));
%         fprintf('  Battery annual payment rate:     %7.1f $/kWh/year \n',xx)
        fprintf('  annual installment:     %7.1f $/year \n',yy(5));
        fprintf('  Losses:                          %7.2f kWh \n', yy(4));
        % fprintf('  Retail price:                    %7.3f dollar/kWh \n', yy(5));
        % fprintf('  Feed-In-Tariff:                  %7.3f dollar/kWh \n', yy(7));
        fprintf('  Size of PV panel:                %7.3f kW \n', cap_pv);

%  end 
    csvwrite('Results_RPAtrail400.csv', outa);
% end 





% here we have assumed that the battery is already reached its socmin level
% and so at night the power is imported from the grid unlike discharging of
% battery in previous case, initila soc level and imported power is
% changed.
%2/3/2018
% added teh cost of inverter=112.5/year in ab to check the results
% 6/3/2018
% added range of feed in tariff
%exclude inverter cost
%29.06
% added cost of panels and inveretr in ab (ab=129.4/kw/year =130)

%29jan 2019
% added a multiplier 5% with x(battery capacity) to include degradation
% effect