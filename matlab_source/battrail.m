function f = battrail(x) 
global pv ld xx yy cap_pv
socmin=0.10;
socmax=0.95;
fit=0.124;
rp=0.3773;
% fit=0.17;
% rp=0.48;
effb=0.95;
effc=0.96;
effd=0.96;
nn=length(pv);

Pd=zeros(nn,1);soc=zeros(nn,1);exp=zeros(nn,1);imp=zeros(nn,1);
convout=zeros(nn,1);convin=zeros(nn,1);battin=zeros(nn,1);battout=zeros(nn,1);
E=zeros(nn,1);
%asumming battery is already discharged and power is imported in teh first instance 
Pd(1)=pv(1)-ld(1); %Excess Power
soc(1)=socmin; % soc after first discharge
imp(1)=-Pd(1);
E(1)=Pd(1)*1; % 1 represents hour
 for t=2:nn
  Pd(t)=pv(t)-ld(t);   
  E(t)=Pd(t)*1;
  if Pd(t)>= 0%EXCESS POWER
     imp(t)=0;
    if (soc(t-1)+((E(t)*effc)/(1*x))) < socmax  
        soc(t)=soc(t-1)+((E(t)*effc)/(1*x));
        convin(t)=(Pd(t)*1);
        battin(t)=(Pd(t)*1*effc);
    else 
        soc(t)=socmax;
        exp(t)=E(t)-((socmax-(soc(t-1)))*(1*x)/effc);
        
    end
 else
      if (soc(t-1)+ (Pd(t)*1)/((1*x)*effb))>socmin
          soc(t)=soc(t-1)-((-Pd(t)/((1*x)*effd*effb))); 
          convout(t)=-Pd(t);
          battout(t)=-(Pd(t)/effd);
      else 
        imp(t)=-(Pd(t)*1)-((soc(t-1)-socmin)*(1*x)*effb*effd);
        soc(t)=socmin;
        
      end  
  end
  Exp=sum(exp);
  Imp=sum(imp);
  Cout=sum(convout);
  Cin=sum(convin);
  Bin=sum(battin);
  Bout=sum(battout);
  Losses=Imp-Exp;
% Losses=(Bin-Bout)+(Cin-Bin)+(Bout-Cout);
 end
Ab=xx(1);

% Ab= 40;
%  Aab=(((x)*Ab)+(cap_pv*130));
  Aab=(((x)*Ab));
 Aimp=(Imp*rp);
 Ap=Aab+Aimp;
 Ar=Exp*fit;
  
 Anp=Ap-Ar;
 yy=[  Anp Exp Imp Losses rp Ab fit ];
 
%  figure(1)
% plot(exp-imp)
% 
% figure(2)
% plot(battin-battout)
% 
% figure(3)
% plot(soc)
f=Anp;





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