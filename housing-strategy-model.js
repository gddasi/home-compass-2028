/* HOME COMPASS housing strategy model. All values in KRW 10,000 (만원).
 * Scenario analysis only: NOT a forecast, bank approval, tax or planning advice.
 * Equal monthly household housing-and-investment budgets across alternatives.
 */
(function(root){
'use strict';
const BASE = Object.freeze({
  years:8, waitYears:2, capital:45000, usePlan:true, monthlyBudget:380,
  rentDeposit:10000, rentMonthly:160, rentOther:20,
  apartmentPrice:100000, existingHousePrice:75000, modularPrice:85000,
  existingMonthly:65, apartmentMonthly:45, modularMonthly:45,
  modularFutureCost:1500, existingFutureCost:2200, replacementYear:8,
  ltv:60, loanYears:30, buyCostPct:3, sellCostPct:1, ownershipTaxPct:0.2,
  overseasShare:30
});
const PRESETS = Object.freeze({
  baseline: {
    title:'기본 가정', inflation:2.5, rentRise:2.5, domesticReturn:3, overseasReturn:4,
    fxDepreciation:0, mortgageRate:4.5, apartmentGrowth:2, existingGrowth:1.5, modularGrowth:1.5,
    rentEnergy:0, apartmentEnergy:0, existingEnergy:0, modularEnergy:0
  },
  currency: {
    title:'고물가·원화 약세', inflation:5, rentRise:5, domesticReturn:4, overseasReturn:4,
    fxDepreciation:6, mortgageRate:6.5, apartmentGrowth:3, existingGrowth:2, modularGrowth:2,
    rentEnergy:12, apartmentEnergy:12, existingEnergy:18, modularEnergy:8
  },
  energy: {
    title:'전력비·설비비 충격', inflation:4, rentRise:4, domesticReturn:3, overseasReturn:4,
    fxDepreciation:2, mortgageRate:5.5, apartmentGrowth:1, existingGrowth:0.5, modularGrowth:0.5,
    rentEnergy:25, apartmentEnergy:25, existingEnergy:35, modularEnergy:12
  }
});
function clamp(n,low,high){n=Number(n);return Number.isFinite(n)?Math.max(low,Math.min(high,n)):low}
function annualToMonthly(pct){return Math.pow(1+clamp(pct,-90,300)/100,1/12)}
function loanPayment(principal,ratePct,months){
 if(principal<=0)return 0;
 const r=clamp(ratePct,0,40)/1200,n=Math.max(1,months);
 return r===0?principal/n:principal*r/(1-Math.pow(1+r,-n));
}
function investedFactor(v){
 const home=(1+clamp(v.domesticReturn,-50,100)/100);
 const overseas=(1+clamp(v.overseasReturn,-50,100)/100)*(1+clamp(v.fxDepreciation,-50,100)/100);
 return Math.pow(home,1-clamp(v.overseasShare,0,100)/100)*Math.pow(overseas,clamp(v.overseasShare,0,100)/100);
}
function evaluate(kind,settings,assumptions,capitalOverride){
 const x=Object.assign({},BASE,settings||{});
 const v=Object.assign({},PRESETS.baseline,assumptions||{}, {overseasShare:x.overseasShare});
 const N=Math.round(clamp(x.years,1,30)*12);
 const wait=Math.min(N,Math.round(clamp(x.waitYears,0,25)*12));
 const capital=clamp(capitalOverride==null?x.capital:capitalOverride,0,100000000);
 const monthlyBudget=clamp(x.monthlyBudget,0,1000000), rentDeposit=clamp(x.rentDeposit,0,100000000);
 const loanRate=clamp(v.mortgageRate,0,40)/1200;
 const monthlyGrowth=investedFactor(v)**(1/12);
 let investment=capital,heldDeposit=0,owner=false,price=0,loan=0,loanMonthsLeft=0,payment=0;
 let purchaseMonth=0,firstHousingCost=0,monthlyBudgetExceeded=0,minInvestment=Infinity,monthlySpendTotal=0,issue='';
 let baseExpense=0,energyExpense=0,appreciation=0,futureCapex=0;
 const purchase = (type,month) => {
   const info=type==='apartment'||type==='wait'?[
     x.apartmentPrice,x.apartmentMonthly,v.apartmentEnergy,v.apartmentGrowth,0
   ]:type==='existing'?[
     x.existingHousePrice,x.existingMonthly,v.existingEnergy,v.existingGrowth,x.existingFutureCost
   ]:[
     x.modularPrice,x.modularMonthly,v.modularEnergy,v.modularGrowth,x.modularFutureCost
   ];
   let [base,expense,energy,growth,capex]=info.map(Number);
   if(!base||base<0){issue='매수 총비용 입력 필요';return false}
   let shifted=(type==='wait')?Math.pow(1+clamp(growth,-30,100)/100,wait/12):1;
   price=base*shifted;
   let loanRatio=clamp(x.ltv,0,100)/100;
   loan=price*loanRatio;
   const upfront=price*(1+clamp(x.buyCostPct,0,30)/100)-loan;
   if(investment+heldDeposit+0.001<upfront){
     issue='매수 시점 자기자본 부족 ('+Math.ceil(upfront-investment-heldDeposit).toLocaleString('ko-KR')+'만원)';
     return false;
   }
   investment=investment+heldDeposit-upfront; heldDeposit=0;
   loanMonthsLeft=Math.round(clamp(x.loanYears,1,50)*12);
   payment=loanPayment(loan,v.mortgageRate,loanMonthsLeft);
   owner=true;purchaseMonth=month;baseExpense=clamp(expense,0,100000);
   energyExpense=clamp(energy,0,100000);
   appreciation=clamp(growth,-30,100);futureCapex=clamp(capex,0,1000000);
   return true;
 };
 if(kind==='rent'||kind==='wait'){
   if(rentDeposit>capital){return {kind,valid:false,reason:'월세 보증금이 시작 자기자본보다 큽니다.',capital}};
   heldDeposit=rentDeposit;investment-=rentDeposit;
 } else if(!purchase(kind,1)){
   return {kind,valid:false,reason:issue,capital};
 }
 let endProperty=0,endDebt=0;
 const capitalStart=capital, monthlyInvestmentReturn=monthlyGrowth-1;
 for(let month=1;month<=N;month++){
   if(kind==='wait'&&month===wait+1&&!owner){
     if(!purchase('wait',month))return {kind,valid:false,reason:issue,capital};
   }
   let housingCost=0;
   if(!owner){
     housingCost=clamp(x.rentMonthly,0,100000)*Math.pow(1+clamp(v.rentRise,-30,100)/100,(month-1)/12)
      +clamp(x.rentOther,0,100000)*Math.pow(1+clamp(v.inflation,-20,100)/100,(month-1)/12)
      +clamp(v.rentEnergy,0,100000);
   }else{
     const currentValue=price*Math.pow(1+appreciation/100,Math.max(0,month-purchaseMonth)/12);
     let interest=loan*loanRate, principal=0;
     if(loanMonthsLeft>0){
       principal=Math.min(loan,Math.max(0,payment-interest));
       loan=Math.max(0,loan-principal);loanMonthsLeft--;
       housingCost+=payment;
     }
     housingCost+=baseExpense*Math.pow(1+clamp(v.inflation,-20,100)/100,(month-1)/12);
     housingCost+=energyExpense;
     housingCost+=currentValue*clamp(x.ownershipTaxPct,0,10)/100/12;
     if(futureCapex>0&&Math.round(clamp(x.replacementYear,1,30)*12)===month-purchaseMonth+1){
       housingCost+=futureCapex;
     }
     endProperty=currentValue;endDebt=loan;
   }
   if(month===1)firstHousingCost=housingCost;
   monthlySpendTotal+=housingCost;
   if(housingCost>monthlyBudget+0.001)monthlyBudgetExceeded++;
   investment=investment*monthlyGrowth+(monthlyBudget-housingCost);
   minInvestment=Math.min(minInvestment,investment);
 }
 const asset=investment+(owner?endProperty*(1-clamp(x.sellCostPct,0,30)/100)-endDebt:heldDeposit);
 const deflator=Math.pow(1+clamp(v.inflation,-20,100)/100,N/12);
 return {
   kind,valid:true,capital:capitalStart,nominal:asset,real:asset/deflator,liquid:investment,
   houseValue:owner?endProperty:0,remainingLoan:owner?endDebt:0,deposit:heldDeposit,
   firstHousingCost,monthlyBudgetExceeded,liquidityShortfall:minInvestment<0,
   costTotal:monthlySpendTotal,years:N/12,usedAnnualPortfolioReturn:(monthlyInvestmentReturn+1)**12*100-100
 };
}
function compare(settings,assumptions,capital){
 return ['rent','apartment','wait','existing','modular'].map(k=>evaluate(k,settings,assumptions,capital));
}
root.HousingStrategyModel={BASE,PRESETS,loanPayment,investedFactor,evaluate,compare};
})(typeof window!=='undefined'?window:globalThis);
