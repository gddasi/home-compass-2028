/* Read-only development headline monitor. Deliberately does not read/export personal money data. */
(function(){
'use strict';
var old = document.getElementById('areas');
if (!old || document.getElementById('developmentRadar')) return;
var panel=document.createElement('section');
panel.className='panel dev-radar';
panel.id='developmentRadar';
panel.style.marginBottom='18px';
old.insertBefore(panel,old.firstChild);
var metro='전체',kind='all',newOnly=false,show=20;
function escapeText(value){return String(value==null?'':value).replace(/[&<>"']/g,function(x){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','"':'&quot;',"'":'&#39;'}[x]})}
function link(value){return /^https?:\/\/[^\s]+$/i.test(String(value||''))?escapeText(value):'#'}
function amt(value){return (Number(value||0)/10000).toLocaleString('ko-KR',{maximumFractionDigits:2})+'억원'}
function marketLine(event){
  if(!event.region_exact||!event.region) return '';
  var markets=(window.HOME_PULSE_DATA||{}).market||[];
  var m=markets.find(function(x){return x.region===event.region});
  if(!m||!m.months||m.months.length<2) return '';
  var last=m.months[1],data=(last.bands||[]).find(function(b){return b.band==='60~84㎡'});
  if(!data||data.median==null||data.count<3) return '';
  var suffix=last.complete?'':' (일부 자료 누락)';
  return '<div class="dev-market">같은 행정구역 60~84㎡ 실거래 중위값: '+amt(data.median)+' · '+escapeText(last.month)+' · '+data.count+'건'+suffix+'</div>';
}
function filterState(name,value){if(name==='metro')metro=value;if(name==='kind')kind=value;if(name==='new')newOnly=!!value;show=20;render()}
window.devRadarSet=function(field,value){filterState(field,value)};
window.devRadarMore=function(){show+=20;render()};
function kindLabel(x){return {rail:'철도·지하철',renewal:'재개발·재건축',urban:'도시개발'}[x]||'개발 발표'}
function card(e){
 var date=escapeText(e.date||'날짜 미확인'),region=escapeText(e.scope||e.region||'지역 미특정');
 var pills='<span class="dev-pill">'+kindLabel(e.category)+'</span>';
 if(e.is_new)pills+='<span class="dev-pill new">새 발표</span>';
 if(e.change_hint)pills+='<span class="dev-pill warn">일정·내용 변경 표현 감지</span>';
 return '<article class="dev-item"><header>'+pills+'</header>'+
 '<a class="dev-title" href="'+link(e.url)+'" target="_blank" rel="noopener noreferrer">'+escapeText(e.title)+'</a>'+
 '<div class="dev-meta"><span>'+date+'</span><span>'+region+'</span><span>'+escapeText(e.source)+'</span></div>'+
 '<div class="dev-stage">'+escapeText(e.stage_hint||'단계 미확인')+' · 정식 사업 단계는 반드시 원문/기관 사업대장 확인</div>'+
 marketLine(e)+
 '<div class="dev-actions"><a href="'+link(e.url)+'" target="_blank" rel="noopener noreferrer">발표 확인 ↗</a></div></article>';
}
function selector(id,opts,value){
 return '<select aria-label="'+escapeText(id)+'" onchange="window.devRadarSet(\''+id+'\',this.value)">'+
 opts.map(function(o){return '<option value="'+escapeText(o[0])+'"'+(value===o[0]?' selected':'')+'>'+escapeText(o[1])+'</option>'}).join('')+'</select>';
}
function render(){
 var d=(window.HOME_PULSE_DATA||{}).development||{},events=(d.events||[]).filter(function(e){
 return (metro==='전체'||e.metro===metro)&&(kind==='all'||e.category===kind)&&(!newOnly||e.is_new);
 });
 var p=(window.HOME_PULSE_DATA||{}),health=(p.health||[]).filter(function(x){return /철도|정비사업|개발|도시계획/.test(x.name||'')});
 var hasDev=!!d.generated_at;
 var sources=[
   ['서울 정비사업 정보몽땅','https://cleanup.seoul.go.kr/cleanup/view/busiTotal.do'],
   ['인천 월별 정비사업 현황','https://renewal.incheon.go.kr/ires/program/0000-0020-0037/program/board/board.do?bbs_id=BBSMSTR_000000000001'],
   ['경기도 철도계획 자료','https://www.gg.go.kr/bbs/boardView.do?bIdx=214237326&bsIdx=564&menuId=1927'],
   ['국가철도공단 사업 현황','https://www.kr.or.kr/sub/info.do?m=05010402'],
   ['국토부 정책 발표','https://www.molit.go.kr/']
 ];
 panel.innerHTML='<div class="dev-head"><div><h3 class="section-title">수도권 개발사업 발표 레이더</h3>'+
 '<p class="section-sub">재개발·재건축, 지하철·GTX, 도시개발 공공 발표를 매일 감시하고 원문과 같은 지역의 실거래 통계를 함께 제공합니다.</p></div>'+
 '<span class="pill">'+(hasDev?'최종 수집 '+escapeText(d.generated_at)+' (UTC 날짜)':'첫 실행 전')+'</span></div>'+
 '<div class="dev-counters"><div class="dev-stat"><small>누적 발표 항목</small><b>'+Number(d.total_events||0).toLocaleString('ko-KR')+'건</b></div>'+
 '<div class="dev-stat"><small>새로 포착한 항목</small><b>'+Number(d.new_count||0)+'건</b></div>'+
 '<div class="dev-stat"><small>변경 표현 포함 항목</small><b>'+Number(d.change_count||0)+'건</b></div></div>'+
 '<div class="dev-filters">'+selector('kind',[['all','전체 종류'],['rail','🚆 철도·지하철'],['renewal','🏗️ 재개발·재건축'],['urban','🏙️ 도시개발']],kind)+
 selector('metro',[['전체','서울·경기·인천 전체'],['서울','서울'],['경기','경기'],['인천','인천'],['','지역 미특정']],metro)+
 '<label style="display:flex;align-items:center;gap:5px;font-size:12px"><input type="checkbox" '+(newOnly?'checked':'')+' onchange="window.devRadarSet(\'new\',this.checked)">새 소식만</label>'+
 '<span class="small muted">표시 '+Math.min(show,events.length)+' / '+events.length+'건</span></div>'+
 (events.length?'<div class="dev-list">'+events.slice(0,show).map(card).join('')+'</div>':
 '<div class="dev-empty">'+(hasDev?'선택한 조건의 관련 공식 발표가 없습니다. 수집이 불완전하거나 제목에 지역이 명시되지 않았을 수 있습니다.':'자동 수집 재실행 후 개발사업 발표가 표시됩니다.')+'</div>')+
 (events.length>show?'<div class="dev-actions"><button onclick="window.devRadarMore()">더 보기 ('+(events.length-show)+'건 남음)</button></div>':'')+
 '<div class="dev-action-note">⚠ 이 화면은 공식기관 도메인을 대상으로 한 뉴스 검색·제목 분류입니다. 발표 제목에 있는 ‘착공’, ‘계획’, ‘변경’은 자동 검출 문구이며 실제 행정 승인이나 확정 개통일이 아닙니다. 예정일 변경은 공식 원문에서 재확인하세요. 아래 실거래 중위값은 같은 행정구역 통계이며 개발사업의 가격 효과를 측정하지 않습니다.</div>'+
 (health.some(function(x){return x.ok===false})?'<div class="note warn">일부 개발 관련 수집처가 실패했습니다. 이 화면은 해당 시점의 전체 공식 발표를 포괄하지 않을 수 있습니다.</div>':'')+
 '<div class="divider"></div><h4 class="subheading">공식기관 사업 현황 확인</h4><div class="dev-quicklinks">'+sources.map(function(v){return '<a class="dev-source" target="_blank" rel="noopener noreferrer" href="'+link(v[1])+'">'+escapeText(v[0])+' ↗</a>'}).join('')+'</div>';
}
window.renderDevelopmentRadar=render;
render();
})();
