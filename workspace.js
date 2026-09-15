/* 工作区交互：只读展示现有行情，不改变数据文件或财务模型。 */
(function (root) {
  'use strict';
  function normalizedSeries(series, days) {
    if (!series || !Array.isArray(series.dates) || !Array.isArray(series.market)) return [];
    var rows = series.dates.map(function (date, i) { return {date:date, value:series.market[i]}; })
      .slice(-days).filter(function (r) { return typeof r.date === 'string' && Number.isFinite(r.value) && r.value > 0; });
    var base = rows.length ? rows[0].value : 1;
    return rows.map(function (r) { return {date:r.date, value:r.value / base * 100}; });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {normalizedSeries:normalizedSeries};
  if (!root.document) return;
  var doc = root.document, activeAdvice = 'advOverview', chart, series, days = 60;
  var $ = function (id) { return doc.getElementById(id); };
  var signed = function (v) { return (v > 0 ? '+' : '') + v.toFixed(2) + '%'; };
  function selectAdviceForTarget(target) {
    var panel = target && target.closest('#v-advice > article.card');
    if (!panel) panel = $(activeAdvice);
    if (!panel) return;
    activeAdvice = panel.id;
    doc.querySelectorAll('#v-advice > article.card').forEach(function (p) { p.hidden = p !== panel; });
    doc.querySelectorAll('#adviceSub button').forEach(function (b) {
      var active = b.dataset.scroll === panel.id;
      b.classList.toggle('on', active);
      if (active) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
    });
  }
  function drawer(open) {
    doc.body.classList.toggle('sidebar-open', open);
    $('sidebarScrim').hidden = !open;
    $('sidebarToggle').setAttribute('aria-expanded', String(open));
    $('workspace').inert = open;
    $('sidebar').inert = !open && root.innerWidth < 768;
    if (open) $('tbNav').querySelector('button.on').focus();
  }
  var labels = {
    pano:['市场总览','从全市场表现，到每一项底层资产。'],
    research:['研究分析','价格、周期与资产基本面的多维观察。'],
    advice:['配置与风险','面向专业投资者的估值、现金流与风险监测框架。'],
    inst:['机构间市场','机构间REITs项目与市场动态。']
  };
  function pageChanged(pg) {
    var label = labels[pg] || labels.pano;
    $('workspaceTitle').textContent = $('workspaceLocation').textContent = label[0];
    $('workspaceSubtitle').textContent = label[1];
    $('exportMarket').hidden = pg !== 'pano';
    selectAdviceForTarget($(activeAdvice));
    var wasOpen = doc.body.classList.contains('sidebar-open');
    drawer(false);
    if (wasOpen) $('workspaceMain').focus({preventScroll:true});
    if (chart) requestAnimationFrame(function () { chart.resize(); });
  }
  root.ReitsWorkspace = {selectAdviceForTarget:selectAdviceForTarget,pageChanged:pageChanged};
  function renderTrend() {
    var rows = normalizedSeries(series, days), el = $('workspaceTrend');
    if (!rows.length || !root.echarts) { el.textContent = '历史序列暂不可用，请稍后刷新。'; return; }
    if (!chart) { el.textContent = ''; chart = root.echarts.init(el); }
    var css = getComputedStyle(doc.documentElement), color = css.getPropertyValue('--accent').trim();
    var last = rows[rows.length - 1];
    $('workspaceTrendValue').textContent = last.value.toFixed(2);
    $('workspaceTrendChange').textContent = signed(last.value - 100);
    $('workspaceTrendChange').style.color = 'var(--' + (last.value >= 100 ? 'up' : 'down') + ')';
    $('workspaceTrendPeriod').textContent = rows[0].date + ' — ' + last.date;
    el.setAttribute('aria-label', '全市场等权价格指数，区间首日100，区间变化' + signed(last.value - 100));
    chart.setOption({animation:false,grid:{left:42,right:12,top:18,bottom:28},
      tooltip:{trigger:'axis',valueFormatter:function(v){return Number(v).toFixed(2);}},
      xAxis:{type:'category',data:rows.map(function(r){return r.date;}),boundaryGap:false,axisTick:{show:false},axisLine:{show:false},axisLabel:{color:css.getPropertyValue('--tx3').trim(),fontSize:10,formatter:function(v){return v.slice(5);}}},
      yAxis:{type:'value',scale:true,splitNumber:3,axisLabel:{color:css.getPropertyValue('--tx3').trim(),fontSize:10},splitLine:{lineStyle:{color:css.getPropertyValue('--grid').trim(),type:'dashed'}}},
      series:[{name:'等权价格指数',type:'line',data:rows.map(function(r){return r.value;}),showSymbol:false,lineStyle:{width:2.5,color:color},itemStyle:{color:color},areaStyle:{color:color,opacity:.07}}]});
    $('workspaceTrendTable').querySelector('tbody').replaceChildren();
    rows.forEach(function(r){var tr=doc.createElement('tr'); [r.date,r.value.toFixed(2)].forEach(function(v){var td=doc.createElement('td');td.textContent=v;tr.append(td);});$('workspaceTrendTable').querySelector('tbody').append(tr);});
  }
  function init() {
    selectAdviceForTarget($(activeAdvice)); drawer(false);
    $('sidebarToggle').addEventListener('click',function(){drawer(true);});
    $('sidebarScrim').addEventListener('click',function(){drawer(false);$('sidebarToggle').focus();});
    doc.addEventListener('keydown',function(e){
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {e.preventDefault();drawer(false);$('gSearch').focus();}
      if (!doc.body.classList.contains('sidebar-open')) return;
      if(e.key==='Escape'){drawer(false);$('sidebarToggle').focus();}
      if(e.key==='Tab') {var items=Array.from($('sidebar').querySelectorAll('a,button')).filter(function(x){return !x.disabled;});var i=items.indexOf(doc.activeElement);if(e.shiftKey&&i<=0){e.preventDefault();items[items.length-1].focus();}else if(!e.shiftKey&&i===items.length-1){e.preventDefault();items[0].focus();}}
    });
    doc.querySelectorAll('[data-advice-target]').forEach(function(b){b.addEventListener('click',function(){doc.querySelector('#tbNav [data-pg="advice"]').click();selectAdviceForTarget($(b.dataset.adviceTarget));window.scrollTo({top:0,behavior:'auto'});});});
    doc.querySelectorAll('[data-jump-view]').forEach(function(b){b.addEventListener('click',function(){var target=doc.querySelector('#subbar [data-v="'+b.dataset.jumpView+'"]');if(target)target.click();});});
    $('workspaceRange').addEventListener('click',function(e){var b=e.target.closest('[data-days]');if(!b)return;days=Number(b.dataset.days);this.querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b);x.setAttribute('aria-pressed',String(x===b));});renderTrend();});
    new MutationObserver(function(){if(series)renderTrend();}).observe(doc.documentElement,{attributes:true,attributeFilter:['data-theme']});
    root.addEventListener('resize',function(){if(chart)chart.resize();if(root.innerWidth>=768)drawer(false);else if(!doc.body.classList.contains('sidebar-open'))$('sidebar').inert=true;});
    if(root.ResizeObserver)new ResizeObserver(function(){if(chart&&$('workspaceTrend').clientWidth)chart.resize();}).observe($('workspaceTrend'));
    root.__DATA_READY.then(function(){
      var data=root.REITS_DATA, rows=data.reits||[];
      $('workspaceDate').textContent=data.lastTradeDate||'日期未提供';
      Array.from($('kpis').children).slice(4).forEach(function(el){$('marketContext').append(el);});
      var groups={};rows.forEach(function(r){if(Number.isFinite(r.pct)){if(!groups[r.sector])groups[r.sector]=[];groups[r.sector].push(r.pct);}});
      var sectors=Object.keys(groups).map(function(k){return {name:k,value:groups[k].reduce(function(a,b){return a+b;},0)/groups[k].length};}).sort(function(a,b){return b.value-a.value;});
      var max=Math.max.apply(null,sectors.map(function(r){return Math.abs(r.value);}).concat([.01]));
      $('workspaceSectors').replaceChildren();
      sectors.forEach(function(r){var b=doc.createElement('button');b.className='sector-line';var label=doc.createElement('span');label.className='sector-label';label.textContent=r.name;var track=doc.createElement('span');track.className='sector-track';var bar=doc.createElement('i');bar.style.width=Math.abs(r.value)/max*100+'%';bar.style.background='var(--'+(r.value>=0?'up':'down')+')';track.append(bar);var value=doc.createElement('span');value.className='sector-value';value.textContent=signed(r.value);value.style.color=bar.style.background;b.append(label,track,value);b.addEventListener('click',function(){var chip=Array.from(doc.querySelectorAll('#hmSectorChips button')).find(function(x){return x.dataset.s===r.name;});if(chip)chip.click();$('heatmapCard').scrollIntoView({block:'start'});});$('workspaceSectors').append(b);});
      rows.filter(function(r){return Number.isFinite(r.amount);}).sort(function(a,b){return b.amount-a.amount;}).slice(0,5).forEach(function(r){var b=doc.createElement('button');b.className='active-asset';var name=doc.createElement('span');name.textContent=r.name;var pct=doc.createElement('span');pct.textContent=Number.isFinite(r.pct)?signed(r.pct):'—';var code=doc.createElement('small');code.textContent=r.code;var amount=doc.createElement('span');amount.textContent=(r.amount/1e4).toFixed(0)+' 万元';b.append(name,pct,code,amount);b.addEventListener('click',function(){root.location.hash='/detail/'+r.code;});$('workspaceActive').append(b);});
      $('exportMarket').addEventListener('click',function(){var csv=[['代码','名称','板块','收盘价','当日涨跌幅(%)','成交额(元)']].concat(rows.map(function(r){return [r.code,r.name,r.sector,r.close,r.pct,r.amount];})).map(function(row){return row.map(function(v){return '"'+String(v==null?'':v).replace(/"/g,'""')+'"';}).join(',');}).join('\r\n');var url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));var a=doc.createElement('a');a.href=url;a.download='REITs行情-'+data.lastTradeDate+'.csv';a.click();setTimeout(function(){URL.revokeObjectURL(url);},1000);});
      fetch('data_research.json').then(function(r){if(!r.ok)throw new Error('历史数据加载失败');return r.json();}).then(function(data){series=data.series;renderTrend();}).catch(function(error){$('workspaceTrend').textContent='历史序列暂不可用，请刷新重试。';console.warn(error.message);});
    }).catch(function(){pageChanged('advice');$('workspaceDate').textContent='行情暂不可用';});
  }
  doc.addEventListener('DOMContentLoaded',init);
})(typeof window==='undefined'?globalThis:window);
