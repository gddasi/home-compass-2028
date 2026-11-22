/* HOME COMPASS strategy UI — state stored only in original browser-local backup. */
(function(){
'use strict';
const M=window.HousingStrategyModel;
const mount=document.getElementById('housingStrategy');
if(!mount||!M){return}
const ALL=[
 ['rent','월세 유지','유동성 중심 · 기간 내 매수 없음'],
 ['apartment','아파트 즉시 매수','비교 시작 시점에 매수'],
 ['wait','2년 관망 후 아파트 매수','월세로 기다린 뒤 동일 유형 아파트 매수'],
 ['existing','기존 단독주택 + 보강','토지·주택 매입과 시설 보강의 총비용'],
 ['modular','토지 + 모듈러 + ESS','토지·인허가·기초·건축·태양광·ESS 포함 총비용']
];
const BASIC=[
 ['years','비교 기간','년',1,30],
 ['waitYears','관망 후 매수 시점','년 후',0,25],
 ['monthlyBudget','월 주거비·투자 공통 예산','만원',0,10000],
 ['capital','비교 시작 자기자본','만원',0,100000000],
 ['overseasShare','여유자금 해외자산 비중','%',0,100]
];
const RENT=[
 ['rentDeposit','월세 보증금','만원',0,100000000],
 ['rentMonthly','시작 월세','만원',0,10000],
 ['rentOther','월세 주택 기타 유지비','만원/월',0,10000]
];
const PURCHASE=[
 ['apartmentPrice','아파트 매수 총 가격','만원',0,100000000],
 ['existingHousePrice','기존 단독주택 + 보강 총비용','만원',0,100000000],
 ['modularPrice','모듈러 + ESS + 토지 등 총비용','만원',0,100000000],
 ['apartmentMonthly','아파트 월 유지비','만원/월',0,10000],
 ['existingMonthly','기존 단독주택 월 유지·수선비','만원/월',0,10000],
 ['modularMonthly','모듈러 월 유지·수선비','만원/월',0,10000]
];
const DEBT=[
 ['ltv','매수 시 적용할 대출 비율','%',0,100],
 ['loanYears','대출 상환 기간','년',1,50],
 ['buyCostPct','매수 시 취득·부대비용 가정','%',0,30],
 ['sellCostPct','매도 시 부대비용 가정','%',0,30],
 ['ownershipTaxPct','연간 보유세·공적 부담 단순 가정','%',0,10],
 ['replacementYear','설비 교체 발생 시점','매수 후 년',1,30],
 ['existingFutureCost','기존 단독 설비 교체비 가정','만원',0,100000],
 ['modularFutureCost','모듈러·ESS 교체비 가정','만원',0,100000]
];
const MACRO=[
 ['inflation','연평균 소비자물가 상승률','%',-20,100],
 ['mortgageRate','주택담보대출 연이율','%',0,40],
 ['rentRise','연간 월세 인상률','%',-30,100],
 ['domesticReturn','원화 금융자산 연 수익률','%',-50,100],
 ['overseasReturn','해외자산 자체 연 수익률','%',-50,100],
 ['fxDepreciation','연간 원화 약세율(외화 대비)','%',-50,100],
 ['apartmentGrowth','아파트 연 가격변화','%',-30,100],
 ['existingGrowth','기존 단독주택 연 가격변화','%',-30,100],
 ['modularGrowth','모듈러주택 연 가격변화','%',-30,100],
 ['rentEnergy','월세 에너지비 추가 충격','만원/월',0,10000],
 ['apartmentEnergy','아파트 에너지비 추가 충격','만원/월',0,10000],
 ['existingEnergy','기존 단독 에너지비 추가 충격','만원/월',0,10000],
 ['modularEnergy','모듈러 에너지비 추가 충격','만원/월',0,10000]
];
function esc(v){return String(v??'').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]))}
function amount(v){return (Number(v)/10000).toLocaleString('ko-KR',{maximumFractionDigits:2})+'억원'}
function n(v){return Number(v).toLocaleString('ko-KR',{maximumFractionDigits:1})}
function preset(){return ['baseline','currency','energy'].includes(state.strategyScenario)?state.strategyScenario:'baseline'}
function config(){return Object.assign({},M.BASE,state.strategy||{})}
function assumptions(id){return Object.assign({},M.PRESETS[id],((state.strategyOverrides||{})[id]||{}))}
function capitalInfo(x){
 let source=0;
 try{let p=plan();source=(p&&Number(p.equity)>0)?Number(p.equity):0;}catch(e){source=0}
 let auto=!!x.usePlan;
 return {amount:auto&&source>0?source:Number(x.capital||0),
         linked:auto&&source>0,example:auto&&source===0};
}
function field(row,group,values,disabled=false){
 const [key,title,unit,min,max]=row,v=Number(values[key]);
 return '<div class="hs-field"><label for="hs-'+key+'">'+esc(title)+'</label>'+
 '<div class="hs-input-wrap"><input id="hs-'+key+'" type="number" step="any" min="'+min+'" max="'+max+
 '" value="'+(Number.isFinite(v)?v:'')+'" '+(disabled?'disabled ':'')+
 'onchange="window.housingStrategySet(\''+group+'\',\''+key+'\',this.value)">'+
 '<span class="hs-unit">'+esc(unit)+'</span></div></div>';
}
function fields(rows,group,vals,disabledKey){return '<div class="hs-fields">'+rows.map(r=>field(r,group,vals,disabledKey===r[0])).join('')+'</div>'}
function resCard(item,max){
 const itemName=ALL.find(x=>x[0]===item.kind)||[item.kind,item.kind,''];
 if(!item.valid)return '<div class="hs-result hs-invalid"><div class="hs-head"><b>'+esc(itemName[1])+'</b><span class="pill amber">실행 불가</span></div>'+
 '<p class="hs-real">'+esc(item.reason||'입력 확인 필요')+'</p><p class="hs-sub">자기자본·보증금·대출 비율을 조정해보세요.</p></div>';
 const width=max>0?Math.max(0,Math.min(100,item.real/max*100)):0;
 const warn=item.liquidityShortfall||item.monthlyBudgetExceeded>0;
 const problem=item.liquidityShortfall?' · 중간 현금잔고 부족 가능':'';
 return '<div class="hs-result '+(warn?'hs-alert':'')+'"><div class="hs-head"><b>'+esc(itemName[1])+'</b>'+
 '<span class="pill '+(warn?'amber':'')+'">'+(warn?'지출·유동성 점검':'조건부 계산')+'</span></div>'+
 '<div class="hs-real">'+amount(item.real)+' <span class="hs-muted">실질 환산 순자산</span></div>'+
 '<div class="hs-bar"><i style="width:'+width.toFixed(1)+'%"></i></div>'+
 '<div class="hs-sub">명목 순자산 '+amount(item.nominal)+' · 현금성 잔액 '+amount(item.liquid)+'</div>'+
 '<div class="hs-sub">첫 달 주거 관련 지출 '+n(item.firstHousingCost)+'만원 · 월 공통예산 초과 '+item.monthlyBudgetExceeded+'개월'+problem+'</div>'+
 '<div class="hs-small">'+esc(itemName[2])+'</div></div>';
}
function render(){
 const x=config(),mode=preset(),v=assumptions(mode),cap=capitalInfo(x);
 const initial=Math.max(0,cap.amount);
 const all=M.compare(x,v,initial);
 const viable=all.filter(r=>r.valid);
 const max=Math.max(0,...viable.map(r=>r.real));
 const investmentYield=(M.investedFactor(Object.assign({},v,{overseasShare:x.overseasShare}))-1)*100;
 const date=state.deadline?state.deadline:'2028년 (예시)';
 const scores={baseline:[],currency:[],energy:[]};
 for(const key of Object.keys(scores))scores[key]=M.compare(x,assumptions(key),initial);
 const rowValues=BASIC.map(r=>r[0]==='capital'?['capital',r[1],r[2],r[3],r[4]]:r);
 mount.innerHTML='<div class="hs-top"><div><h3>주거 전략 · 매수와 관망 비교</h3>'+
 '<p class="hs-muted">같은 시작자본과 월 주거·투자 예산으로 월세, 즉시 매수, 관망 후 매수, 기존 단독 보강, 모듈러·ESS 신축을 비교합니다.</p></div>'+
 '<span class="pill">계획상 이사 기준일: '+esc(date)+'</span></div>'+
 '<div class="hs-tabs">'+Object.keys(M.PRESETS).map(k=>'<button type="button" class="hs-tab" aria-pressed="'+(k===mode)+
 '" onclick="window.housingStrategyPreset(\''+k+'\')">'+esc(M.PRESETS[k].title)+'</button>').join('')+'</div>'+
 '<div class="hs-explainer">이 시뮬레이션은 미래를 예측하지 않습니다. 선택한 가정 아래에서만 계산하며, **원화 약세·고물가 시나리오도 발생을 전제로 하지 않습니다.** 초기 자본과 월 예산을 모든 선택지에 동일하게 적용하고 남는 자금은 설정한 투자비율로 운용하는 것으로 가정합니다.</div>'+
 '<div class="hs-layout" style="margin-top:16px"><div class="hs-inputs">'+
 '<section class="hs-panel"><h4>① 자금·기간 설정</h4>'+
 '<label class="hs-toggle"><input type="checkbox" '+(x.usePlan?'checked':'')+
 ' onchange="window.housingStrategySet(\'base\',\'usePlan\',this.checked)">기존 자금·저축 계획의 퇴거일 예상 자기자본 사용</label>'+
 (cap.linked?'<p class="hs-small">기존 계획 연동: '+amount(initial)+' 기준</p>':cap.example?'<p class="hs-watch">기존 계획의 예상 자기자본이 0원입니다. 아래 4.5억원은 <b>예시 가정</b>이며 사용자 자산이 아닙니다. 실제 자금으로 검토하려면 계획 설정을 입력하거나 연동을 해제하세요.</p>':'')+
 fields(rowValues,'base',Object.assign({},x,{capital:initial}),x.usePlan?'capital':'')+
 '<p class="hs-small">월 예산은 주거비를 지불하고 남은 금액을 투자할 수 있는 동일한 가계 예산입니다. 비교기간 동안 명목 금액이 일정하다고 가정합니다.</p></section>'+
 '<section class="hs-panel"><h4>② 월세 조건</h4>'+fields(RENT,'base',x)+'</section>'+
 '<section class="hs-panel"><h4>③ 매수가·총건축비·월 유지비</h4>'+
 '<p class="hs-small">모듈러 총비용에는 반드시 토지·인허가·기초·운송·전력 및 상하수도 인입·태양광·ESS를 포함해야 합니다. 입력값은 <b>실제 매물·견적이 아닌 예시</b>입니다.</p>'+
 fields(PURCHASE,'base',x)+'</section>'+
 '<details class="hs-panel"><summary>④ 대출·거래비용·설비 교체비 조정</summary><div class="hs-details">'+
 fields(DEBT,'base',x)+'<p class="hs-small">대출비율은 임의 입력값입니다. 규제지역별 LTV·DSR, 신용·소득심사 등 실제 승인 여부를 확인하지 않습니다.</p></div></details>'+
 '<details class="hs-panel" open><summary>⑤ '+esc(M.PRESETS[mode].title)+'의 거시경제 가정</summary><div class="hs-details">'+
 fields(MACRO,'macro',v)+
 '<p class="hs-small">원화 약세율이 양수이면 해외자산의 원화 환산 수익이 높아지는 가정입니다. 해외자산 자체 가격 하락·환율 반등 위험도 별도로 조절할 수 있습니다.</p></div></details></div>'+
 '<div class="hs-output">'+
 '<section class="hs-panel"><div class="hs-top"><div><h4>비교기간 종료 시 가계 순자산</h4>'+
 '<div class="hs-muted">'+n(x.years)+'년 후 · '+esc(M.PRESETS[mode].title)+
 ' · 물가상승률 '+n(v.inflation)+'% 가정</div></div><span class="hs-recalc">조건 변경 즉시 재계산</span></div>'+
 '<p class="hs-small">동일 예산 내 남는 돈 투자 · 집 매각 또는 보증금 반환을 가정한 시점의 실질 구매력 기준</p>'+
 '<div class="hs-results">'+all.map(r=>resCard(r,max)).join('')+'</div>'+
 '<div class="hs-watch">⚠ 비교 결과 중 <b>자기자본 부족</b>은 해당 선택지의 매수를 시작할 수 없다는 뜻입니다. 월 예산 초과나 중간 투자잔액이 음수인 경우도 현실에서는 추가 소득·차입이 필요할 수 있으므로 실행 가능한 결과로 취급하면 안 됩니다.</div></section>'+
 '<section class="hs-panel"><h4>거시경제 가정을 바꾸면 결과는 어떻게 달라질까?</h4>'+
 '<p class="hs-muted">같은 입력 자금·주택가격을 유지하면서 세 가지 가정에서의 <b>실질 순자산(억원)</b>을 비교합니다.</p>'+
 '<div class="hs-table-wrap"><table><thead><tr><th>주거 방식</th>'+
 Object.keys(scores).map(k=>'<th>'+esc(M.PRESETS[k].title)+'</th>').join('')+
 '</tr></thead><tbody>'+ALL.map((item,i)=>'<tr><td>'+esc(item[1])+'</td>'+
 Object.keys(scores).map(k=>'<td>'+(scores[k][i].valid?amount(scores[k][i].real):'자본 부족')+'</td>').join('')+'</tr>').join('')+
 '</tbody></table></div>'+
 '<p class="hs-note">각 시나리오는 설명용 가정으로, 환율·물가·부동산가격의 실제 상관관계나 미래 발생확률을 반영하지 않습니다. 서로 다른 시나리오에서 금액 차이가 큰 전략은 가정에 더 민감한 것으로 해석하세요.</p></section>'+
 '<section class="hs-panel"><h4>현재 모델의 범위와 주의점</h4>'+
 '<p class="hs-note">월세 보증금은 종료 시 전액 반환, 매수주택은 종료 시 매각한다고 가정합니다. 집 매각비용과 단순화된 취득비용·보유비용은 반영하지만, 실제 취득세·양도세·대출규제·보증금 미회수 위험·공사 기간 중 이중 주거비·실제 모듈러 감가상각 구조·환금성의 차이까지 정밀 산정하지는 않습니다.</p>'+
 '<p class="hs-note">대출금리는 입력한 값이 전체 대출기간에 유지되는 가정입니다. 금리충격 시나리오는 처음부터 높은 금리가 적용되는 별도의 조건이지, 대출 실행 뒤 금리가 상승하는 구체적 재조정 스케줄은 아닙니다.</p>'+
 '<p class="hs-note">정기 설비교체비는 설정한 한 차례만 반영되며, ESS 용량·실제 태양광 발전량·한전 계약·정전 대응시간을 예측하는 기능은 아닙니다. 기본 해외자산 비중은 투자수익률의 결정론적 모델로 위험 및 과세를 반영하지 않습니다.</p>'+
 '<p class="hs-note">이 비교는 공식 금융상품 추천, 구체적 부동산 매수 권유 또는 미래 가치 보증이 아닙니다. 실제 구매 전 은행의 대출 심사와 건축사·전기기술자의 실사를 권장합니다.</p>'+
 '<p class="hs-note"><b>계산에 사용한 해외/원화 혼합 명목 연 수익률 가정:</b> '+n(investmentYield)+'%</p>'+
 '<div class="hs-explainer">입력한 값은 공개 GitHub 저장소로 전송되지 않고 지금 사용하는 브라우저의 기존 HOME COMPASS 개인 데이터에만 저장됩니다. 상단의 백업 내려받기에도 포함됩니다.</div>'+
 '<p class="hs-note"><button type="button" class="btn" onclick="go(\'buying\')">대출·구매력 시뮬레이터로 이동</button></p></section>'+
 '</div></div>';
}
window.housingStrategyPreset=function(id){if(!M.PRESETS[id])return;state.strategyScenario=id;save();render()};
window.housingStrategySet=function(group,key,value){
 if(group==='base'){
   const defaults=M.BASE;if(!(key in defaults))return;
   let v=key==='usePlan'?!!value:Number(value);
   if(key!=='usePlan'&&!Number.isFinite(v))return;
   state.strategy=Object.assign({},state.strategy||{},{[key]:v});
 }else if(group==='macro'){
   if(!MACRO.some(row=>row[0]===key))return;
   let v=Number(value);if(!Number.isFinite(v))return;
   let prefs=Object.assign({},state.strategyOverrides||{}),name=preset();
   prefs[name]=Object.assign({},prefs[name]||{},{[key]:v});
   state.strategyOverrides=prefs;
 }else{return}
 save();render();
};
window.renderHousingStrategy=render;
render();
})();
