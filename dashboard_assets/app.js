const $ = id => document.getElementById(id);
let csrf = '', timer, busy = false;
let labMarketState=null,live20MarketState=null,shadowViewState={};
const number = (value, digits=2) => Number.isFinite(value) ? value.toLocaleString('pt-BR', {minimumFractionDigits:digits, maximumFractionDigits:digits}) : '—';
const percent = v => Number.isFinite(v) ? number(v*100) + '%' : '—';
const date = value => { if(!value) return 'Sem leitura'; const d=new Date(typeof value==='number'?value*1000:value); return Number.isNaN(d.getTime())?'Sem leitura':d.toLocaleString('pt-BR'); };
const escape = value => String(value??'—').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const empty = (title, detail='') => `<div class="empty"><strong>${escape(title)}</strong>${escape(detail)}</div>`;
// Premium views consume the same authenticated /api/status snapshot as the
// trading panels. They never generate orders or synthetic performance values.
const premiumHistory=new Map();
let latestPortfolioRecord={};
function journalRows(p){
 const fills=(p.fills||[]).map(f=>({time:f.time_ms,kind:'Preenchimento',symbol:f.symbol,side:f.side,state:'FILLED',reason:f.reason||'',price:f.price,quantity:f.quantity,fee:f.fee}));
 const orders=(p.orders||[]).map(o=>({time:o.created_ms,kind:'Ordem',symbol:o.symbol,side:o.side,state:o.status,reason:o.reason||'',price:o.limit,quantity:o.quantity,fee:null}));
 return [...fills,...orders].sort((a,b)=>(b.time||0)-(a.time||0));
}
function journalCsv(rows){
 const cell=value=>{
   let s=String(value??'');
   if(/^[=+\-@\t\r\n]/.test(s))s="'"+s;
   return '"'+s.replace(/"/g,'""')+'"';
 };
 return '\uFEFF'+[['timestamp_utc','tipo','par','lado','estado','motivo','preco','quantidade','taxa'],...rows.map(r=>[Number.isFinite(r.time)?new Date(r.time).toISOString():'',r.kind,r.symbol,r.side,r.state,r.reason,r.price,r.quantity,r.fee])].map(r=>r.map(cell).join(',')).join('\r\n');
}
function filteredJournal(p){
 const query=String($('trade-search').value||'').trim().toLowerCase();
 return journalRows(p).filter(r=>[r.symbol,r.side,r.kind,r.state,r.reason].join(' ').toLowerCase().includes(query));
}
function renderTradeJournal(p){
 latestPortfolioRecord=p;
 const rows=filteredJournal(p);
 $('trade-journal').innerHTML=rows.length?table(['Horário','Tipo','Par','Lado','Estado','Motivo','Taxa'],rows.slice(0,50).map(r=>[escape(date(r.time/1000)),escape(r.kind),escape(r.symbol),escape(r.side),escape(r.state),escape(r.reason),r.fee===null?'—':escape(r.fee)])):empty('Nenhum registro para este filtro.');
}
function renderPremium(data){
 const p=data.portfolio||{},m=data.multipair||{},stats=portfolioPerformance(p);
 renderTradeJournal(p);
 const numeric=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v))?Number(v):NaN;
 const metric=(label,value,note)=>'<article class="term-stat"><p>'+escape(label)+'</p><strong>'+escape(value)+'</strong><small>'+escape(note)+'</small></article>';
 $('premium-metrics').innerHTML=[metric('Acerto dos ciclos',percent(stats.winRate??NaN),'Somente ciclos fechados completos'),metric('Posições abertas / ciclos fechados',(p.available?(p.position?'1':'0'):'—')+' / '+(stats.closed??'—'),'Uma posição simultânea no máximo'),metric('PnL do dia','—','Ainda sem série diária reconciliada'),metric('Sharpe / drawdown máximo','—','Série de retornos ainda indisponível')].join('');
 const pairs=Array.isArray(m.pairs)?m.pairs:[];
 const age=Date.now()-m.updated_ms;
 const recent=Number.isFinite(age)&&age>=0&&age<180000;
 const spark=(row)=>{
   const price=numeric(row.close),stamp=row.candle_close_ms;
   let points=premiumHistory.get(row.symbol)||[];
   if(recent&&row.status==='OK'&&Number.isFinite(price)&&price>0&&Number.isSafeInteger(stamp)&&stamp<=Date.now()){
     if(!points.length||stamp>points.at(-1).time){points=[...points,{time:stamp,price}].slice(-24);premiumHistory.set(row.symbol,points);}
   }
   if(points.length<2)return '<span class="spark-empty">Aguardando 2 candles</span>';
   const min=Math.min(...points.map(p=>p.price)),max=Math.max(...points.map(p=>p.price));
   const xy=points.map((p,i)=>(i*110/(points.length-1)).toFixed(1)+','+(26-(p.price-min)/(max-min||1)*22).toFixed(1)).join(' ');
   return '<svg class="pair-spark" viewBox="0 0 112 30" role="img" aria-label="Fechamentos observados neste navegador"><polyline points="'+xy+'" fill="none" stroke="currentColor" stroke-width="2"/></svg>';
 };
 $('premium-heatmap').innerHTML=pairs.map(row=>{
   const valid=recent&&row.status==='OK',action=valid?row.action:'UNKNOWN';
   const kind=action==='ENTER_LONG'?'buy':action==='EXIT_LONG'?'sell':'hold';
   return '<div class="heat-tile '+kind+'"><b>'+escape(row.symbol)+'</b><span>'+escape(!valid?'Sem confirmação':action==='ENTER_LONG'?'Intenção de compra':action==='EXIT_LONG'?'Intenção de saída':'Aguardar')+'</span></div>';
 }).join('')||empty('Radar sem dados recentes.');
 $('premium-pairs').innerHTML=pairs.length?table(['Par','Posição','Entrada','Fechamento radar','Variação bruta','Tempo aberto','Mini histórico','Regime V3'],pairs.map(row=>{
   const pos=p.position?.symbol===row.symbol?p.position:null;
   const fill=pos?(p.fills||[]).findLast(f=>f.side==='BUY'&&f.symbol===row.symbol&&f.time_ms===pos.opened_ms):null;
   const entry=numeric(fill?.price),price=numeric(row.close);
   const change=recent&&row.status==='OK'&&entry>0&&price>0?price/entry-1:NaN;
   const elapsed=pos&&Number.isSafeInteger(pos.opened_ms)&&pos.opened_ms<=Date.now()?Math.floor((Date.now()-pos.opened_ms)/60000)+' min':'—';
   return [escape(row.symbol),pos?'Long':'Em caixa',number(entry,6),number(price,6),percent(change),escape(elapsed),spark(row),escape(data.v3?.fresh?(data.v3.report?.pairs||[]).find(p=>p.symbol===row.symbol)?.regime_v3||'UNKNOWN':'Sem confirmação')];
 })):empty('Aguardando o radar de seis pares.');
}
function premiumClock(){
 const now=new Date();$('premium-clock').textContent=now.toLocaleTimeString('pt-BR',{timeZone:'America/Sao_Paulo'})+' BRT · '+now.toLocaleTimeString('pt-BR',{timeZone:'UTC'})+' UTC';
}
premiumClock();setInterval(premiumClock,1000);
$('sidebar-collapse').addEventListener('click',()=>{
 const collapsed=$('app').classList.toggle('nav-collapsed');
 $('sidebar-collapse').setAttribute('aria-expanded',String(!collapsed));
});
$('premium-stop').addEventListener('click',()=>$('stop').click());
try{const name=localStorage.getItem('spotlab-display-name');if(name)$('bot-display-name').value=name.slice(0,28);}catch{}
$('bot-display-name').addEventListener('change',()=>{try{localStorage.setItem('spotlab-display-name',$('bot-display-name').value.slice(0,28));}catch{}});
const names={regime_v1:'Regimes de mercado',trend_v1:'Tendência por médias',breakout_v1:'Rompimento de máxima'};
const regimes={tranquilo:'Tranquilo',lateral:'Lateral',nervoso:'Volátil',queda_forte:'Queda forte',aquecimento:'Aquecimento'};
function table(headers, rows){return `<table><thead><tr>${headers.map(h=>`<th>${escape(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;}
function labChart(id,points,mode){
 const target=$(id),valid=points.filter(p=>Number.isFinite(p.time)&&Number.isFinite(p.equity));
 if(valid.length<2){target.innerHTML=empty('Aguardando duas medições.','O gráfico usa somente valores registrados nesta sessão.');return;}
 let peak=1000;
 const values=valid.map(p=>{peak=Math.max(peak,p.equity);return mode==='drawdown'?(1-p.equity/peak)*100:p.equity;});
 const min=Math.min(...values),max=Math.max(...values),span=max-min||1;
 const first=valid[0].time,last=valid.at(-1).time;
 const xy=values.map((v,i)=>[20+(valid[i].time-first)/(last-first||1)*650,25+(max-v)/span*120]);
 const path=xy.map((p,i)=>(i?'L':'M')+p.map(n=>n.toFixed(2)).join(',')).join(' ');
 const unit=mode==='drawdown'?'%':' USDT',label=mode==='drawdown'?'Drawdown da carteira fictícia':'Patrimônio da carteira fictícia';
 target.innerHTML=`<svg viewBox="0 0 700 185" role="img" aria-label="${label}">${[25,85,145].map(y=>`<path d="M20 ${y} H670" stroke="#25375c" stroke-dasharray="3 6"/>`).join('')}<path d="${path}" fill="none" stroke="${mode==='drawdown'?'#d4b983':'#22d3ee'}" stroke-width="2.5"/><text x="20" y="15" fill="#9aaed1" font-size="10">${escape(number(max,mode==='drawdown'?4:2)+unit)}</text><text x="20" y="163" fill="#9aaed1" font-size="10">${escape(number(min,mode==='drawdown'?4:2)+unit)}</text></svg><p class="panel-note">${escape(date(first))} → ${escape(date(last))} · ${valid.length} medições</p>`;
}
async function api(path, body){const response=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},body:body?JSON.stringify(body):undefined});let data;try{data=await response.json();}catch{throw new Error('O painel retornou uma resposta inválida.');}if(!response.ok){if(response.status===401&&path!='/api/login') showLogin();throw new Error(data.error||'Não foi possível concluir.');}return data;}
function showLogin(){clearInterval(timer);$('login').hidden=false;$('app').hidden=true;csrf='';}
function showApp(){ $('login').hidden=true;$('app').hidden=false;clearInterval(timer);timer=setInterval(refresh,10000); }
function drawChart(points){const chart=$('chart');if(points.length<2){chart.innerHTML=empty('O histórico começa com a simulação.','São necessárias duas medições de patrimônio para desenhar a evolução.');$('chart-period').textContent='Aguardando medições';return;}const values=points.map(p=>p.equity),min=Math.min(...values),max=Math.max(...values),range=max-min||Math.max(1,Math.abs(max)*.01),w=700,h=170;const coords=values.map((v,i)=>[i/(values.length-1)*w,20+(max-v)/range*(h-35)]);const path=coords.map((p,i)=>(i?'L':'M')+p.map(n=>n.toFixed(2)).join(',')).join(' ');chart.innerHTML=`<svg viewBox="-5 0 710 190" role="img" aria-label="Histórico de patrimônio simulado"><defs><linearGradient id="shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#b4f8cc" stop-opacity=".16"/><stop offset="100%" stop-color="#b4f8cc" stop-opacity="0"/></linearGradient></defs>${[35,85,135,180].map(y=>`<path d="M0 ${y} H700" stroke="#25375c" stroke-dasharray="3 6"/>`).join('')}<path d="${path} L700 185 L0 185 Z" fill="url(#shade)"/><path d="${path}" fill="none" stroke="#b4f8cc" stroke-width="2.5" vector-effect="non-scaling-stroke"/><circle cx="${coords.at(-1)[0]}" cy="${coords.at(-1)[1]}" r="4" fill="#b4f8cc"/></svg>`;$('chart-period').textContent=`${points.length} medições · ${number(min)} — ${number(max)}`;}
function render(data){renderResearchDesk(data.research_desk||{});renderUpgradePackage(data);renderSessionPerformance(data.session_performance||{});renderOperationalAudit(data.operational_audit||{});renderQuant(data.quant_control||{});renderV3(data.v3||{});if(data.system?.controller?.engine==='portfolio'&&!$('overview').hidden)document.querySelector('[data-view="terminal"]').click();renderPortfolio(data.portfolio||{});renderSystemIntegration(data.system||{});renderKronos(data.kronos_lab||{});renderSpotResearch(data.spot_research||{});renderShadow(data.ai_shadow||{});renderAudit(data.session_audit||{},data.research_registry||{});renderCoinGecko(data.coingecko||{});if(typeof renderMetamask==='function') renderMetamask(data.metamask);const active=data.activity.recent&&!data.stop;
 const lab=data.paper_lab||{},lp=lab.performance||{};
 labMarketState=lab;
 const exitTrial=data.exit_trial||{comparisons:[]};
 const micro=data.micro_trial||{comparisons:[]};
 const momentumStudy=data.momentum_universe||{comparisons:[]};
 $('momentum-study').innerHTML=momentumStudy.comparisons.length?table(['Período','Custos','Resultado USDT','Compras','Vendas','Drawdown','Bloqueios'],momentumStudy.comparisons.map(r=>[escape(r.window),`${number(r.stress,0)}x`,number(r.pnl,6),number(r.buys,0),number(r.sells,0),percent(r.drawdown),number(r.blocked,0)])):empty('Estudo do universo ainda não disponível.');
 $('momentum-study-time').textContent=momentumStudy.created?`Salvo em ${date(momentumStudy.created)} · 20 USDT por cenário histórico · nenhuma adoção.`:'Aguardando relatório.';
 const stream=data.market_stream||{},streamAge=Date.now()/1000-(stream.updated||0);
 $('stream-status').textContent=stream.updated?`${stream.phase==='connected'&&streamAge<10?'Conectado · relatório recente':stream.phase==='stopped'?'Coletor encerrado':'Conexão pendente, interrompida ou relatório atrasado'} · ${date(stream.updated)} · reconexões ${number(stream.reconnects,0)} · lacunas de trades ${number(stream.gaps,0)}. Não executa ordens.`:'Coletor ainda não iniciado.';
 $('stream-rows').innerHTML=stream.rows?.length?table(['Par','Spread','Negócios em até 60s','Volume USDT','Agressão compradora','Delta USDT · janela','Variação observada','Leitura'],stream.rows.map(r=>[escape(r.symbol),percent(r.spread),number(r.trades,0),number(r.notional_usdt,2),percent(r.buy_share),number(Number.isFinite(r.buy_share)&&Number.isFinite(r.notional_usdt)?r.notional_usdt*(2*r.buy_share-1):null,2),percent(r.change),escape(streamAge<10&&stream.phase==='connected'?r.observation:'Dados antigos; observação bloqueada')])):empty('Aguardando eventos reais do WebSocket.');
 const suite=data.spot_suite||{comparisons:[]},suiteNames={grid_spot_proxy:'Grid Spot · proxy de inventário',dca_spot:'DCA Spot · compras periódicas',rebalance:'Rebalanceamento',souto_quartiles:'Souto · quartis e médias 10/16/26',ma_cross:'Médias 9/21',breakout_volume:'Rompimento + volume',pullback_fixed:'Pullback · saída fixa',pullback_rsi:'Pullback + RSI',pullback_atr:'Pullback · saída ATR',mean_reversion:'Reversão à média · range',vwap_filter:'VWAP móvel · filtro',momentum_volume:'Momentum + volume',macd_cross:'Cruzamento MACD',ema_9_20:'EMA 9/20 + RSI',ema_ribbon:'Ribbon EMA 5/8/13',bollinger_squeeze:'Squeeze Bollinger + volume',stochastic_pullback:'Estocástico + tendência'};
 $('spot-suite').innerHTML=suite.comparisons.length?table(['Estratégia experimental','Custos','Resultado USDT','Compras','Vendas','Drawdown','Bloqueios'],suite.comparisons.map(r=>[escape(suiteNames[r.strategy]||r.strategy),`${number(r.stress,0)}x`,number(r.pnl,6),number(r.buys,0),number(r.sells,0),percent(r.drawdown),number(r.blocked,0)])):empty('Pesquisa Spot ainda não disponível.');
 $('spot-suite-time').textContent=suite.created?`Consulta ${date(suite.created)} · 30 dias históricos, 20 USDT fictícios por cenário. Nenhuma adoção.`:'Execute python spot_strategy_suite.py.';
 const small=data.small_cap||{results:[]};
 const smallComparison=data.small_comparison||{comparisons:[]};
 $('small-comparison').innerHTML=smallComparison.comparisons.length?table(['Limite experimental','Custos','Resultado USDT','Compras','Vendas','Bloqueios','Drawdown'],smallComparison.comparisons.map(r=>[`${percent(r.fraction)} · até ${number(20*r.fraction,2)} USDT`,`${number(r.stress,0)}x`,number(r.pnl,6),number(r.buys,0),number(r.sells,0),number(r.blocked,0),percent(r.drawdown)])):empty('Comparação histórica ainda não disponível.');
 $('small-comparison-time').textContent=smallComparison.created?`Salvo em ${date(smallComparison.created)} · ${date(smallComparison.start/1000)} até ${date(smallComparison.end/1000)}. Pesquisa não ativa.`:'Pesquisa não ativa.';
 $('small-cap-results').innerHTML=small.results.length?table(['Par','Sinal horário','Mínimo USDT','Spread','Viabilidade · sem execução'],small.results.map(r=>[escape(r.symbol),r.signal?'Alta':'Sem sinal',number(r.minimum,2),percent(r.spread),escape(r.reasons.join('; ')||'Candidato para pesquisa; sem validação')])):empty('Execute python small_cap_scan.py para consultar os pares.');
 $('small-cap-time').textContent=small.created?`Consulta salva em ${date(small.created)}. Fotografia do mercado; não é monitoramento contínuo.`:'Nenhuma consulta salva.';
 $('micro-results').innerHTML=micro.comparisons.length?table(['Margem líquida · NÃO ATIVA','Custos','Resultado USDT','Compras','Vendas','Drawdown'],micro.comparisons.map(r=>[percent(r.target),`${number(r.stress,0)}x`,number(r.pnl,4),number(r.buy_count,0),number(r.sell_count,0),percent(r.drawdown)])):empty('Pesquisa de pequenos ciclos ainda não disponível.');
 const exitNames={hold:'Manter o lote inicial',take_profit_1pct:'Take-profit de 1% líquido',trailing_halfpct_after_1pct:'Ativar em 1% líquido · recuo de 0,5%'};
 $('lab-exit-comparison').innerHTML=exitTrial.comparisons.length?table(['Saída hipotética · NÃO ATIVA','Resultado líquido USDT','Realizado USDT','Vendas','Drawdown'],exitTrial.comparisons.map(r=>[escape(exitNames[r.policy]||r.policy),number(r.pnl,4),number(r.realized,4),number(r.sales,0),percent(r.drawdown)])):empty('Comparação de saídas ainda não disponível.','O laboratório mantém sua regra diária.');
 $('lab-exit-comparison-time').textContent=exitTrial.created?`Pesquisa salva em ${date(exitTrial.created)} · período ${date(exitTrial.start/1000)} até ${date(exitTrial.end/1000)}. Não é o resultado ao vivo nem ativa uma saída.`:'Pesquisa separada, sem alteração da sessão.';
 const usingLab=Boolean(lab.started&&lab.performance);
 const p=usingLab?lp:(data.performance||{});
 const selectedHalted=usingLab?Boolean(lp.halted):data.halted;
 const selectedLimits=usingLab?{max_order_fraction:.05,max_symbol_fraction:.2,max_total_fraction:.6}:data.limits;
 const quoteTime=lp.as_of?Date.parse(lp.as_of)/1000:NaN,quoteAge=data.as_of-quoteTime;
 const labRecent=lab.phase==='waiting'&&Number.isFinite(quoteAge)&&quoteAge>=0&&quoteAge<180;
 $('paper-lab').hidden=!lab.started;
 const labPhases={waiting:'acompanhando',starting:'iniciando',stopped:'encerrado',error:'ciclo bloqueado'};
 $('lab-status').textContent=`Experimento sem aprovação histórica · ${labPhases[lab.phase]||'sem leitura'} · última atualização ${date(lab.updated)} · término ${date(lab.end)}`;
 $('lab-metrics').innerHTML=table(['Saldo inicial fictício','Patrimônio USDT','Resultado líquido USDT','Ordens','Taxas USDT'],[[number(1000),number(lp.equity),number(lp.total_pnl),number(lp.orders,0),number(lp.fees,4)]]);
 $('lab-signals').textContent=Object.entries(lab.signals||{}).map(([s,v])=>`${s}: ${v.reason}`).join(' · ')+(lab.error?` · Ciclo bloqueado: ${lab.error}`:'');
 const quoteLabel=!Number.isFinite(quoteAge)?'Aguardando a primeira cotação.':quoteAge<0?'Horário da cotação inconsistente.':quoteAge>=180?`Cotação atrasada: ${number(quoteAge/60,1)} minutos sem nova medição.`:`Cotação medida há ${number(quoteAge,0)} segundos.`;
 $('lab-data-health').textContent=quoteLabel+(lab.phase==='error'?' Última consulta falhou; os valores abaixo são da medição anterior.':'');
 $('lab-data-health').className=labRecent?'panel-note':'notice';
 const exposure=Number.isFinite(lp.equity)&&Number.isFinite(lp.cash)?lp.equity-lp.cash:NaN;
 $('lab-capital').innerHTML=table(['Caixa USDT','Exposição pelo bid USDT','Exposição %','Realizado líquido USDT','Não realizado líquido USDT','Drawdown atual'],[[number(lp.cash),number(exposure),Number.isFinite(exposure)&&lp.equity>0?percent(exposure/lp.equity):'—',number(lp.realized_pnl,4),number(lp.unrealized_pnl,4),percent(lp.drawdown)]]);
 $('lab-assets').innerHTML=(lp.assets||[]).length?table(['Ativo','Quantidade','Custo médio com taxas','Bid da medição','Valor líquido estimado','Não realizado USDT'],lp.assets.map(a=>[escape(a.symbol),number(a.quantity,8),a.quantity>0?number(a.cost_basis/a.quantity):'—',a.quantity>0?number(a.bid_value/a.quantity):'—',number(a.net_liquidation_estimate),`<span class="${a.unrealized_pnl>=0?'positive':'negative'}">${number(a.unrealized_pnl,4)}</span>`])):empty('Sem posições medidas no laboratório.','O saldo permanece fictício e separado da sua conta Binance.');
 labChart('lab-equity-chart',lab.curve||[],'equity');
 labChart('lab-dd-chart',lab.curve||[],'drawdown');
 $('lab-orders').innerHTML=(lab.orders||[]).length?table(['Horário','Ativo','Lado','Quantidade','Preço USDT','Taxa USDT','Realizado USDT'],lab.orders.map(o=>[escape(date(o.time)),escape(o.symbol),`<span class="tag ${o.side==='SELL'?'warn':''}">${o.side==='BUY'?'Compra':'Venda'}</span>`,number(o.quantity,8),number(o.price),number(o.fee,5),number(o.realized_pnl,4)])):empty('Nenhuma ordem simulada registrada.','O painel mostrará as compras e vendas efetivamente gravadas no diário.');
 const budget=data.test_budget||{};
 $('test-capital').textContent=number(budget.configured_cash)+' USDT fictícios';
 $('measurement-note').textContent=usingLab?'Os cartões, o gráfico e as posições abaixo mostram o laboratório noturno experimental, com saldo fictício e cotações reais. Não são saldos da Binance.':budget.measured?'Os cartões abaixo mostram a última medição salva da carteira principal.':'Ainda não há medição da carteira. Os traços abaixo não indicam saldo zero. O observador coleta sinais; os resultados dos experimentos estão na aba Estratégias.';
 const grid=data.grid_research||{comparisons:[]};
 const replay=data.grid_replay||{};
 $('replay-results').innerHTML=replay.created?table(['Negócios públicos','Duração (s)','Preenchimentos simulados','Ordens antes do corte','Patrimônio marcado USDT'],[[number(replay.events,0),number((replay.last_time-replay.first_time)/1000,3),number(replay.fills,0),number(replay.active_at_cutoff,0),number(replay.equity)]]):empty('Replay público ainda não disponível.','Execute python grid_replay.py na pasta do painel.');
 $('replay-time').textContent=replay.created?`Consulta: ${date(replay.created)}. Dados públicos reais; ordens e carteira fictícias. Janela curta, sem aprovação de estratégia.`:'Teste operacional separado da carteira e dos backtests.';
 $('grid-results').innerHTML=grid.comparisons.length?table(['Hipótese','Retorno contínuo','Drawdown','Custos USDT','Resultado'],grid.comparisons.map(r=>[escape(r.name==='grid_range_v1'?'Grid por inventário':'Grid + tendência'),percent(r.return),percent(r.drawdown),number(r.costs),r.qualified?'Critérios atendidos · não adotada':'Reprovada'])):empty('Relatório Grid não encontrado.','Atualize o repositório ou execute python grid_research.py.');
 $('grid-time').textContent=grid.created?`Histórico gerado em ${date(grid.created)} · 365 dias horários, incluindo aquecimento. Não é o Grid nativo da Binance.`:'Resultados de pesquisa separados da carteira.';
 const acceptance=data.limit_acceptance||{scenarios:[]};
 const cases={synthetic_roundtrip_and_replacement:'Compra / venda / reposição',synthetic_partial_then_cancel:'Parcial / cancelamento',synthetic_stop_before_fill:'STOP antes do preenchimento',synthetic_crash_with_existing_inventory:'Queda com posição inicial'};
 $('limit-results').innerHTML=acceptance.scenarios.length?table(['Cenário artificial','Patrimônio marcado USDT','Taxas USDT','Reserva USDT','Execuções','Ordens abertas'],acceptance.scenarios.map(r=>[escape(cases[r.name]||r.name),number(r.equity),number(r.fees,5),number(r.reserved_cash,5),number(r.fills,0),number(r.active_orders,0)])):empty('Demo de ordens limitadas ainda não disponível.','Execute python limit_demo.py na pasta do painel.');
 $('connection').textContent= data.stop?'■ STOP acionado':labRecent?'● Laboratório · dados recentes':active?'● Atividade recente':'○ Sem atividade recente';
 $('process-help').hidden=active||labRecent;
 $('process-instruction').textContent=data.stop?'STOP está acionado. Confira o Diagnóstico antes de iniciar qualquer processo.':`Não há atividade recente confirmada. Último processo registrado: ${data.activity.command||'nenhum'} · ${date(data.activity.time)}. Confira também os erros na aba Atividade.`;
 const daily=data.daily_research||{comparisons:[]};
 const dailyNames={sma200:'Média de 200 dias',momentum90:'Momentum de 90 dias',breakout55_20:'Rompimento 55 / saída 20 dias'};
 $('daily-time').textContent=daily.created?`Pesquisa gerada em ${date(daily.created)} · retorno acumulado em cinco anos, não anual.`:'Nenhum relatório diário disponível nesta pasta.';
 $('daily-strategies').innerHTML=daily.comparisons.length?table(['Hipótese','Retorno em 5 anos','Comprar e manter 50/50','DD contínuo','Retorno período final','Critérios históricos'],daily.comparisons.map(r=>{const key=r.name.replace(/_(fixed|vol)$/,'');return [escape((dailyNames[key]||key)+(r.name.endsWith('_vol')?' · volatilidade':' · exposição fixa')),percent(r.return),percent(r.benchmark),percent(r.drawdown),percent(r.final_return),`<span class="tag ${r.qualified?'':'warn'}">${r.qualified?'Atendidos · não adotada':'Reprovada'}</span>`];})):empty('Pesquisa diária ainda não carregada.','Atualize o repositório ou execute python daily_research.py na mesma pasta do painel.');
 $('updated').textContent=p.as_of?`${usingLab?'Laboratório experimental · ':''}Última medição: ${date(p.as_of)} · painel atualizado às ${new Date(data.as_of*1000).toLocaleTimeString('pt-BR')}`:`Nenhuma medição de carteira · painel atualizado às ${new Date(data.as_of*1000).toLocaleTimeString('pt-BR')}`;
 $('notice').textContent=data.stop?'STOP acionado. O processo deve reconhecer a trava antes da próxima ordem; posições não são liquidadas.':labRecent?'Laboratório experimental ativo com dinheiro fictício. Não é uma estratégia aprovada. O motor principal continua sujeito à validação.':data.halted?'A trava de drawdown foi acionada. Revise a exposição antes de qualquer retomada.':!data.validation.passed?'As estratégias ainda não passaram na validação. As operações permanecem bloqueadas; a observação de sinais pode continuar.':'Modo simulação. Uma aprovação histórica não garante resultados futuros.';
 $('equity').textContent=number(p.equity);$('pnl').textContent=number(p.total_pnl);$('pnl').className=Number.isFinite(p.total_pnl)?(p.total_pnl>=0?'positive':'negative'):'';$('drawdown').textContent=percent(p.drawdown);$('orders').textContent=number(p.orders,0);$('fees').textContent=Number.isFinite(p.fees)?`Taxas pagas: ${number(p.fees,4)} USDT`:'Custos ainda não medidos';
 $('risk-state').textContent=data.stop?'■ STOP acionado':selectedHalted?'■ Drawdown bloqueado':'◉ Proteções configuradas';$('risk-fill').style.width=`${Math.min(100,Math.max(0,(p.drawdown||0)/.15*100))}%`;
 $('limit-order').textContent=percent(selectedLimits.max_order_fraction);$('limit-symbol').textContent=percent(selectedLimits.max_symbol_fraction);$('limit-total').textContent=percent(selectedLimits.max_total_fraction);
 const expired=!data.validation.current;$('validation-status').textContent=usingLab?'Experimental · sem aprovação':expired?'Vencida ou desatualizada':data.validation.passed?'Aprovada no relatório':'Reprovada';
 $('stop').disabled=data.stop;drawChart(usingLab?(lab.curve||[]):data.curve);
 const latest=data.observation.latest;const signals=[];if(latest)for(const [symbol,asset] of Object.entries(latest.symbols||{}))for(const [strategy,s] of Object.entries(asset.signals||{}))signals.push([`<span class="asset-label">${escape(symbol)}</span>`,escape(names[strategy]||strategy),`<span class="tag ${s.regime==='queda_forte'?'bad':s.regime==='nervoso'?'warn':''}">${escape(regimes[s.regime]||s.regime)}</span>`,s.target>0?'Sinal de entrada':'Sem entrada']);
 const labSignals=Object.entries(lab.signals||{});
 if(lab.started&&labSignals.length){
  $('signals').innerHTML=table(['Ativo','Estratégia experimental','Leitura do sinal diário','Fração do limite por ativo','Candle fechado'],labSignals.map(([symbol,s])=>[escape(symbol),'Média 200 dias + volatilidade',escape(s.reason),percent(s.target),escape(date(Number(s.candle)/1000))]));
  $('sample-count').textContent='Laboratório · diário';
  $('signal-time').textContent=`Sinais do laboratório que está acompanhando a carteira fictícia. Calculados com candles diários fechados; a leitura não muda a cada minuto. Cotações da carteira: ${date(lp.as_of)}. Fração do limite não é ordem de compra nem percentual já investido. Estratégia ainda não aprovada.`;
 }else{
  $('signals').innerHTML=signals.length?table(['Ativo','Estratégia','Regime','Último sinal'],signals):empty('Nenhum sinal observado ainda.','O painel mostrará as amostras coletadas pelo observador.');$('sample-count').textContent=`${data.observation.samples} amostras`;$('signal-time').textContent=latest?`Última amostra: ${date(latest.observed_at)} · ${data.observation.gaps} intervalos ignorados por lacunas. Sinais não são ordens.`:'O painel não inicia o observador automaticamente.';
 }
 $('strategies').innerHTML=data.validation.comparisons.length?table(['Estratégia','Retorno final','Comprar e manter','DD contínuo','Resultado'],data.validation.comparisons.map(r=>[escape(names[r.name]||r.name),percent(r.return),percent(r.benchmark),percent(r.drawdown),`<span class="tag ${r.passed?'':'warn'}">${r.passed?'Aprovada':'Reprovada'}</span>`])):empty('Nenhuma validação registrada.','Execute a validação histórica pelo terminal.');
 const scenarios={freeze:'Bloqueio atual',reduce:'Saída gradual',reduce_stress:'Saída gradual · custos 2×',existing_freeze:'80% investido · bloqueio',existing_reduce:'80% investido · saída gradual'};
 const defense=[];for(const r of data.validation.comparisons)for(const d of r.defensive||[])defense.push([escape(names[r.name]||r.name),escape(scenarios[d.scenario]||d.scenario),percent(d.return),percent(d.drawdown),number(d.sales,0),number(d.remaining_exposure)]);
 $('defensive').innerHTML=defense.length?table(['Estratégia','Cenário','Retorno','Drawdown','Vendas defensivas','Exposição final (USDT)'],defense):empty('Experimento ainda não disponível.','Gere uma validação com a versão atual para incluir esta comparação.');
 const health=data.diagnostics; $('observation-ready').textContent=health.observation_ready?'Pode iniciar pelo terminal':'Requer atenção';$('paper-ready').textContent=health.paper_ready?'Condições atendidas':'Operações bloqueadas';
 $('observation-ready').className=health.observation_ready?'positive':'negative';$('paper-ready').className=health.paper_ready?'positive':'negative';
 const statusNames={ok:'OK',blocked:'Bloqueado',info:'Informação',attention:'Atenção'};
 $('health-checks').innerHTML=health.checks.map(c=>`<article class="health-check"><div><h3>${escape(c.title)}</h3><p>${escape(c.detail)}</p><small>${escape(c.next_step)}</small></div><span class="tag ${c.status==='blocked'?'bad':c.status==='attention'?'warn':''}">${escape(statusNames[c.status]||c.status)}</span></article>`).join('');
 $('positions-table').innerHTML=p.assets?.length?table(['Ativo','Quantidade','Custo contabilizado','Valor líquido estimado','Não realizado'],p.assets.map(a=>[escape(a.symbol),number(a.quantity,8),number(a.cost_basis),number(a.net_liquidation_estimate),number(a.unrealized_pnl)])):empty('Sem posições simuladas medidas.','Saldos da Binance não são importados automaticamente.');
 const labels={cycle:'Medição de patrimônio',blocked:'Operação bloqueada',paper_order:'Ordem simulada',validation:'Validação concluída',observation:'Amostra observada',review:'Revisão diária',started:'Processo iniciado',stopped:'Processo encerrado',error:'Ciclo interrompido'};
 $('events').innerHTML=data.events.length?data.events.map(e=>`<div class="event"><div class="event-icon">${e.kind==='error'?'!':e.kind==='blocked'?'■':'↗'}</div><div><div class="event-title">${escape(labels[e.kind]||e.kind)}${e.symbol?' · '+escape(e.symbol):''}</div><div class="event-detail">${escape(e.reason||e.error_type||(e.side?`${e.side==='BUY'?'Compra':'Venda'} · ${number(e.quantity,8)} · ${number(e.price)} USDT`:'Registro do processo de simulação'))}</div></div><time>${escape(date(e.time))}</time></div>`).join(''):empty('O diário está vazio.','Os eventos aparecerão aqui conforme o bot trabalhar.');
 renderLive20(data.live_small||{},data.stop);
 renderOverview20(data.live_small||{},data.stop);
 renderSessionHealth(data.live_small||{},data.stop);
 if(typeof metamaskChrome==='function') metamaskChrome();
 renderEma(data.ema||{},data.multipair||{});
 renderMultipair(data.multipair||{});
 renderTerminal(data);
 renderLaunchHelp(data);
 renderEntryDiagnostics(data);
 renderExternalContext(data.external_context||{});
 renderOperationHealth(data.operation_health||{});
 if(typeof updateOperationsVisuals==='function')updateOperationsVisuals(data);
}
async function refresh(){if(busy)return;busy=true;try{const response=await api('/api/status');csrf=response.csrf;render(response.data);$('error').textContent='';}catch(e){$('error').textContent=e.message;$('connection').textContent='○ Sem conexão com o painel';}finally{busy=false;}}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;$('login-error').textContent='';try{const response=await api('/api/login',{password:$('access').value});csrf=response.csrf;$('access').value='';showApp();await refresh();}catch(error){$('login-error').textContent=error.message;}finally{button.disabled=false;}});
for(const button of document.querySelectorAll('[data-view]'))button.addEventListener('click',()=>{document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==button.dataset.view);document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b===button));if(typeof location!=='undefined')location.hash=button.dataset.view;$('page-name').textContent=button.textContent.trim();$('heading').textContent={v3:'V3 · pesquisa sem execução.',terminal:'Terminal de operações.',ema:'Arquivo · experimento EMA/1h.',shadow:'V2 · demonstração offline.',live20:'Arquivo · simulação anterior.',metamask:'MetaMask · testes e simulações.',overview:'Tudo sob seu olhar.',activity:'O bot, passo a passo.',research:'Evidência antes de operar.',positions:'Sua simulação em detalhe.',diagnosis:'Entenda cada bloqueio.'}[button.dataset.view];if(typeof metamaskChrome==='function') metamaskChrome();refresh();});
$('refresh').addEventListener('click',refresh);$('stop').addEventListener('click',()=>{$('stop-result').textContent='';$('stop-dialog').showModal();});$('cancel-stop').addEventListener('click',()=>$('stop-dialog').close());$('confirm-stop').addEventListener('click',async()=>{const b=$('confirm-stop');b.disabled=true;try{const result=await api('/api/stop',{});$('stop-result').textContent=result.message;await refresh();}catch(e){$('stop-result').textContent=e.message;}finally{b.disabled=false;}});$('logout').addEventListener('click',async()=>{try{await api('/api/logout',{});showLogin();}catch(e){$('error').textContent=e.message;}});
(async()=>{try{const response=await api('/api/status');csrf=response.csrf;showApp();render(response.data);}catch{showLogin();}})();

function donut(target,segments,label){
 const valid=segments.filter(x=>Number.isFinite(x.value)&&x.value>=0),total=valid.reduce((a,x)=>a+x.value,0);
 if(!total){$(target).innerHTML=empty('Sem dados para distribuir.');return;}
 let offset=0;
 const rings=valid.map(x=>{const length=x.value/total*100,part=`<circle cx="90" cy="90" r="64" fill="none" stroke="${x.color}" stroke-width="18" pathLength="100" stroke-dasharray="${length} ${100-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 90 90)"><title>${escape(x.name)}: ${escape(number(x.value,4))}</title></circle>`;offset+=length;return part;}).join('');
 $(target).innerHTML=`<div class="donut"><svg viewBox="0 0 180 180" role="img" aria-label="${escape(label)}"><circle cx="90" cy="90" r="64" fill="none" stroke="#202c49" stroke-width="18"/>${rings}<text x="90" y="85" text-anchor="middle" class="donut-total">${escape(number(total, label==='Ordens registradas'?0:2))}</text><text x="90" y="107" text-anchor="middle" class="donut-unit">${escape(label==='Ordens registradas'?'ORDENS':'USDT')}</text></svg></div><div class="donut-legend">${valid.map(x=>`<div><span><i style="background:${x.color}"></i>${escape(x.name)}</span><b>${escape(percent(x.value/total))}</b></div>`).join('')}</div>`;
}
function renderLive20(s,stop=false){
 live20MarketState=s;
 const age=Date.now()/1000-(s.updated||0),fresh=s.phase==='waiting'&&age>=0&&age<180;
 const blocked=stop||s.halted,health=stop?'STOP acionado · posição preservada':s.halted?'Drawdown travado · ordens bloqueadas':fresh?'Processo com dados recentes':s.phase==='error'?'Ciclo bloqueado':s.phase==='stopped'?'Encerrado':'Aguardando dados recentes';
 const metricCards=[['Patrimônio líquido',number(s.equity,4),'USDT · estimativa após custos','cyan'],['Resultado da sessão',number(s.pnl,4),'USDT · realizado + não realizado',s.pnl<0?'coral':'purple'],['Drawdown atual',percent(s.drawdown),'Bloqueio de ordens em 15%','purple'],['Ordens registradas',String((s.orders||[]).length),'Compras e vendas fictícias','blue']];
 $('live20-cards').innerHTML=metricCards.map(([title,value,note,color])=>`<article class="metric accent-${color}"><p>${title}<span>↗</span></p><h2>${escape(value)}</h2><small>${note}</small></article>`).join('');
 labChart('live20-hero-chart',s.curve||[],'equity');
 const allocated=Number.isFinite(s.equity)&&Number.isFinite(s.cash)?s.equity-s.cash:null;
 donut('live20-allocation',[{name:'Caixa disponível',value:s.cash,color:'#22d3ee'},{name:s.position?.symbol||'Posição',value:allocated,color:'#a78bfa'}],'Capital líquido estimado');
 donut('live20-operation-pie',[{name:'Compras',value:(s.orders||[]).filter(o=>o.side==='BUY').length,color:'#34e8ad'},{name:'Vendas',value:(s.orders||[]).filter(o=>o.side==='SELL').length,color:'#ff7ca8'}],'Ordens registradas');

 $('live20-status').textContent=s.started?`${health} · medição ${date(s.updated)} · término ${date(s.end)}`:'Processo ainda não iniciado';
 $('live20-metrics').innerHTML=table(['Inicial USDT','Caixa USDT','Líquido estimado USDT','Resultado USDT','Realizado USDT','Drawdown'],[[number(s.initial),number(s.cash),number(s.equity,6),number(s.pnl,6),number(s.realized,6),percent(s.drawdown)]]);
 $('live20-decision').textContent=blocked?health+'; nenhuma liquidação automática. Última decisão registrada: '+(s.decision||'sem decisão'):s.decision||'Aguardando primeira consulta pública';
 labChart('live20-chart',s.curve||[],'equity');
 const p=s.position;
 $('live20-position').innerHTML=p?table(['Ativo','Quantidade','Custo USDT','Não realizado USDT'],[[escape(p.symbol),number(p.units,10),number(p.cost,6),number(s.unrealized,6)]]):empty('Sem posição fictícia aberta.');
 const validPosition=p&&Number.isFinite(p.cost)&&p.cost>0&&Number.isFinite(p.units)&&p.units>0;
 $('live20-exits').innerHTML=validPosition?table(['Par','Bid para ganho líquido de 1%','Bid para perda líquida de 2%','Outra saída'],[[escape(p.symbol),number(p.cost*1.01/(p.units*.999*.999),8),number(p.cost*.98/(p.units*.999*.999),8),'Último fechamento horário abaixo da média de 20 candles']]):empty('Sem posição aberta para calcular saída.');
 const orders=s.orders||[],sales=orders.filter(o=>o.side==='SELL'),buys=orders.filter(o=>o.side==='BUY'),fees=orders.reduce((total,o)=>total+(Number.isFinite(o.fee)?o.fee:0),0);
 $('live20-summary').innerHTML=table(['Compras registradas','Vendas registradas','Vendas positivas','Vendas negativas','Taxas registradas USDT','Não realizado USDT'],[[buys.length,sales.length,sales.filter(o=>o.pnl>0).length,sales.filter(o=>o.pnl<0).length,number(fees,6),number(s.unrealized,6)]]);
 $('live20-orders').innerHTML=s.orders?.length?table(['Horário','Par','Ordem fictícia','Quantidade','Preço USDT','Taxa USDT','Realizado USDT','Motivo'],s.orders.slice(-100).reverse().map(o=>[escape(date(o.time)),escape(o.symbol),o.side==='BUY'?'Compra':'Venda',number(o.quantity,10),number(o.price,8),number(o.fee,6),number(o.pnl,6),escape(o.reason)])):empty('Nenhuma ordem fictícia até agora.','Sinais e mínimos são respeitados; não criamos negócios para preencher a tabela.');
 if(!$('live20').hidden){$('updated').textContent=$('live20-status').textContent;$('connection').textContent=blocked?'■ Simulação · ordens bloqueadas':fresh?'● Simulação 20 USDT · dados recentes':'○ Simulação 20 USDT · confira atualização';$('notice').textContent=blocked?health+'. Somente saldo fictício; posição não liquidada.':!fresh?'Somente saldo fictício. Medição antiga ou processo indisponível; valores exibidos são a última leitura salva.':'Somente saldo fictício. Estratégia experimental; nenhuma ordem real.';$('process-help').hidden=true;}
}

function renderOverview20(s,stop=false){
 if(!s.started)return;
 const orders=s.orders||[],fees=orders.reduce((a,o)=>a+(Number.isFinite(o.fee)?o.fee:0),0);
 $('paper-lab').hidden=true;
 $('test-capital').textContent=number(s.initial)+' USDT fictícios · sessão atual';
 $('measurement-note').textContent='Indicadores desta página usam a mesma sessão de Simulação ao vivo. Última medição: '+date(s.updated)+'. Pesquisas antigas permanecem na aba Estratégias.';
 $('equity').textContent=number(s.equity,4);$('pnl').textContent=number(s.pnl,4);
 $('pnl').className=s.pnl<0?'negative':'positive';
 $('drawdown').textContent=percent(s.drawdown);$('orders').textContent=String(orders.length);
 $('fees').textContent='Taxas registradas: '+number(fees,6)+' USDT';
 drawChart(s.curve||[]);
 $('risk-state').textContent=stop?'■ STOP acionado':s.halted?'■ Drawdown bloqueado':'◉ Proteções da simulação 20 USDT';
 $('risk-fill').style.width=`${Math.min(100,Math.max(0,(s.drawdown||0)/.15*100))}%`;
 $('limit-order').textContent='Até 5 USDT / 25%';$('limit-symbol').textContent='Uma posição por vez';$('limit-total').textContent='25% na entrada';$('validation-status').textContent='Experimental · sem aprovação';
 $('sample-count').textContent='Sessão 20 USDT';
 $('signals').innerHTML=table(['Posição atual','Última decisão registrada'],[[escape(s.position?.symbol||'Em caixa'),escape(s.decision||'Aguardando consulta')]]);
 $('signal-time').textContent='Decisão do processo de simulação; não é recomendação. Medição: '+date(s.updated);
 const p=s.position;
 $('positions-table').innerHTML=p?table(['Par','Quantidade','Custo USDT','Não realizado USDT'],[[escape(p.symbol),number(p.units,8),number(p.cost,6),number(s.unrealized,6)]]):empty('Sem posição fictícia aberta nesta sessão.');
 const fresh=s.phase==='waiting'&&Date.now()/1000-s.updated>=0&&Date.now()/1000-s.updated<180;
 if(!$('overview').hidden){
  $('process-help').hidden=true;
  $('updated').textContent='Sessão 20 USDT · medição '+date(s.updated);
  $('connection').textContent=stop||s.halted?'■ Ordens bloqueadas':fresh?'● Simulação 20 USDT · dados recentes':'○ Simulação 20 USDT · confira atualização';
  $('notice').textContent=stop?'STOP acionado; posição fictícia preservada.':s.halted?'Drawdown travado; ordens bloqueadas, sem liquidação automática.':fresh?'Resumo da simulação de 20 USDT. Somente saldo fictício; nenhuma ordem real.':'Dados sem atualização recente. Valores abaixo são a última medição salva da sessão de 20 USDT.';
 }
}

function renderSessionHealth(s,stop=false){
 const exists=Boolean(s.started);
 $('live20-diagnostic').hidden=!exists;$('legacy-readiness').hidden=exists;$('legacy-health').hidden=exists;
 if(!exists)return;
 const age=Date.now()/1000-(s.updated||0),fresh=s.phase==='waiting'&&age>=0&&age<180,expired=Date.now()/1000>=s.end;
 const checks=[
 ['Coleta da simulação anterior',fresh?'Dados recentes nesta simulação':'Relatório antigo sem atualização',fresh?'ok':'attention','Última medição desta simulação: '+date(s.updated)+'. Este horário não representa a coleta EMA nem o observador de seis pares. Fase registrada: '+(s.phase||'indisponível')],
 ['Botão de desligar',stop?'STOP acionado':'STOP não acionado',stop?'blocked':'ok','A trava não vende a posição.'],
 ['Proteção de drawdown',s.halted?'Travada':'Não travada',s.halted?'blocked':'ok','Drawdown atual: '+percent(s.drawdown)+'; gatilho de 15%.'],
 ['Prazo da sessão',expired?'Prazo encerrado':'Dentro do prazo',expired?'blocked':'info','Término: '+date(s.end)+'. Não há reinício automático do saldo.'],
 ['Decisão registrada',s.decision||'Nenhuma decisão salva','info','Não é sinal em tempo real; refere-se à última medição.'],
 ['Operações reais','Desabilitadas','info','Experimento com saldo fictício, sem acesso de negociação à conta.']];
 $('live20-health').innerHTML=checks.map(([title,value,level,detail])=>`<article class="health-check"><div><h3>${escape(title)}</h3><p>${escape(value)}</p><small>${escape(detail)}</small></div><span class="tag ${level==='blocked'?'bad':level==='attention'?'warn':''}">${level==='blocked'?'Bloqueado':level==='attention'?'Atenção':level==='ok'?'OK':'Informação'}</span></article>`).join('');
 $('events-source').textContent='Sessão 20 USDT · últimas 50 ordens';
 const orders=(s.orders||[]).slice(-50).reverse();
 $('events').innerHTML=`<p class="panel-note">Ordens fictícias registradas nesta sessão. Última medição: ${escape(date(s.updated))}. O estado atual aparece no Diagnóstico; este histórico não inclui cada ciclo de consulta.</p>`+(orders.length?orders.map(o=>`<div class="event"><div class="event-icon">${o.side==='BUY'?'↗':'↘'}</div><div><div class="event-title">${o.side==='BUY'?'Compra':'Venda'} fictícia · ${escape(o.symbol)}</div><div class="event-detail">${number(o.quantity,8)} unidades · ${number(o.price,8)} USDT · taxa ${number(o.fee,6)} USDT${o.side==='SELL'?' · realizado '+number(o.pnl,6)+' USDT':''}<br>${escape(o.reason||'Motivo não registrado')}</div></div><time>${escape(date(o.time))}</time></div>`).join(''):empty('Nenhuma ordem fictícia nesta sessão.','A ausência de operações pode ser uma decisão válida da estratégia.'));
 if(!$('diagnosis').hidden||!$('activity').hidden||!$('positions').hidden){
  $('process-help').hidden=true;$('updated').textContent='Sessão 20 USDT · medição '+date(s.updated);
  $('connection').textContent=stop||s.halted?'■ Ordens bloqueadas':fresh?'● Simulação 20 USDT · dados recentes':'○ Confira atualização da simulação';
  $('notice').textContent='Dados da sessão fictícia de 20 USDT. '+(stop?'STOP acionado; posição preservada.':s.halted?'Drawdown travado; posição preservada.':fresh?'Nenhuma ordem real.':'Valores da última leitura salva; confira o Diagnóstico.');
 }
}

function renderCoinGecko(s){
 const age=Date.now()/1000-(s.updated||0),stale=age<0||age>1800;
 $('cg-status').textContent=(s.status==='disabled'?'Integração opcional desativada. Configure a chave Demo localmente.':s.status==='error'?(s.message||'Consulta falhou; valores anteriores podem estar desatualizados.')+(s.error_code?' Código: '+s.error_code+'.':''):s.updated?stale?'Consulta antiga; confira o coletor.':'Contexto consultado.':'Aguardando configuração ou primeira consulta.')+(s.updated?' Última consulta: '+date(s.updated):'');
 $('cg-table').innerHTML=s.rows?.length?table(['Ativo','Preço USD','Variação 24h','Volume 24h USD','Capitalização USD','Horário da fonte'],s.rows.map(r=>[escape(r.symbol),number(r.price_usd,6),percent(Number.isFinite(r.change_24h)?r.change_24h/100:null),number(r.volume_usd,0),number(r.market_cap_usd,0),escape(date(r.provider_updated))+((Date.now()/1000-r.provider_updated>1800)?' · Antigo':'')])):empty('Sem dados CoinGecko disponíveis.','A simulação Binance funciona independentemente desta integração.');
}

function renderAudit(a,r){
 if(!a.available){$('audit-status').textContent='Sem sessão válida para auditar.';$('audit-metrics').innerHTML='';$('audit-quality').innerHTML='';$('audit-registry').textContent='';$('audit-limitations').textContent='';return;}
 $('audit-status').textContent=(a.reconciled?'Reconciliação contábil conferida.':'Atenção: divergências ou histórico insuficiente. Não conclua rentabilidade.')+' Medição auditada: '+date(a.measurement);
 $('audit-metrics').innerHTML=table(['Taxas USDT','Vendas verificadas','Taxa de acerto','Ganho médio USDT','Perda média USDT','Fator de lucro'],[[number(a.fees,6),number(a.sells,0),percent(a.win_rate),number(a.average_win,6),number(a.average_loss,6),number(a.profit_factor,4)]]);
 $('audit-quality').innerHTML=table(['DD na curva retida','Medições retidas','Intervalos acima de 180s','Maior intervalo (s)','Referência em caixa · PNL USDT','Comprar/manter'],[[percent(a.saved_curve_drawdown),number(a.curve_points,0),number(a.gaps_over_180s,0),number(a.largest_gap_seconds,0),'0,00','Não disponível']]);
 $('audit-registry').textContent=r.studies?`Registro de pesquisa: ${r.studies.length} relatórios distintos e ${r.variants?.length||0} configurações identificadas. Inventário retrospectivo dos arquivos disponíveis; não é pré-inscrição nem correção de múltiplos testes.`:'Registro de pesquisa ainda não gerado nesta pasta. O iniciador atualizado gera o relatório a cada minuto; consulta manual: python auditar.py.';
 $('audit-limitations').textContent=[...(a.issues||[]),...(a.limits||[]),a.benchmarks?.reason||''].join(' ');
}

function renderShadow(s){
 shadowViewState=s;
 if(s.status!=='available'){
  $('shadow-status').textContent=s.status==='invalid'?'Relatório inválido ou incompatível com o modo offline; confira o arquivo local.':'Demonstração ainda não executada nesta pasta. Use os comandos abaixo para gerar o relatório.';
  $('shadow-summary').innerHTML=empty('Sem resultado offline disponível.');$('shadow-features').innerHTML='';return;
 }
 $('shadow-status').textContent='Fixture artificial · arquivo salvo em '+date(s.saved_at)+'. Não representa coleta de mercado.';
 const actions={HOLD:'Aguardar (teste)',REVIEW_REQUIRED:'Revisão necessária (teste)',SHADOW_CANDIDATE:'Fixture aceita pelos filtros'};
 $('shadow-summary').innerHTML=table(['Resultado de software','Ordens','Chamadas pagas','Calibração real','Veredito'],[[escape(actions[s.action]||'Indisponível'),number(s.orders,0),number(s.requests_paid,0),'Não realizada','Inconclusivo']]);
 const f=s.features||{};
 $('shadow-features').innerHTML=table(['Par fictício','Mid fictício','Spread fictício','Imbalance L1','Volatilidade não anualizada','DD fictício','Perda diária fictícia'],[[escape(s.symbol),number(f.mid,6),percent(f.spread),number(f.imbalance_l1,6),number(f.volatility,10),percent(f.drawdown),percent(f.daily_loss)]]);
}


function renderEma(s,multipair={}){
 renderEmaDiagnosis(s,multipair);
 const valid=!!s.available,active=!$('ema').hidden;
 const sides={BUY:'Compra',SELL:'Venda'},states={NEW:'Nova',PARTIAL:'Parcial',FILLED:'Preenchida',CANCELED:'Cancelada',REJECTED:'Rejeitada'};
 if(!valid){
  $('ema-status').textContent=s.status==='invalid'?'Relatório EMA/ATR indisponível ou inconsistente; confira o processo.':'Sessão EMA/ATR ainda não encontrada nesta pasta.';
  for(const id of ['ema-cards','ema-allocation','ema-fills-pie','ema-position','ema-orders','ema-fills']) $(id).innerHTML=empty('Sem dados disponíveis.');
  $('ema-signal').textContent='Aguardando relatório da sessão.';
 }else{
  const health=s.stop?'STOP acionado':s.phase==='STOPPED'?'Sessão encerrada':s.phase==='ERROR'?'Erro de coleta':s.fresh?'Processo atualizando':'Sem atualização recente';
  $('ema-status').textContent=`${health} · última medição ${date(s.updated)} · término ${date(s.end)}. ${s.in_transition?'Carteira em atualização; patrimônio temporariamente indisponível.':''}`;
  const cards=[['Patrimônio fictício',number(s.equity,6)+' USDT','Capital inicial: '+number(s.capital)+' USDT','cyan'],['Resultado líquido',number(s.pnl,6)+' USDT','Realizado: '+number(s.realized,6)+' USDT','violet'],['Caixa reservado',number(s.reserved,6)+' USDT','Disponível: '+number(s.cash-s.reserved,6)+' USDT','green'],['Preenchimentos',number(s.buy_fills+s.sell_fills,0),'Taxas: '+number(s.fees,6)+' USDT','pink']];
  $('ema-cards').innerHTML=cards.map(([title,value,note,color])=>`<article class="metric accent-${color}"><p>${escape(title)}<span>↗</span></p><h2>${escape(value)}</h2><small>${escape(note)}</small></article>`).join('');
  donut('ema-allocation',[{name:'Caixa disponível',value:s.cash-s.reserved,color:'#22d3ee'},{name:'Caixa reservado',value:s.reserved,color:'#a78bfa'},{name:'Posição marcada',value:Number.isFinite(s.equity)?Math.max(0,s.equity-s.cash):null,color:'#34e8ad'}],'Carteira fictícia');
  if(!s.buy_fills&&!s.sell_fills)$('ema-fills-pie').innerHTML=empty('Nenhum preenchimento ainda.','Zero compras e zero vendas nesta sessão.');else donut('ema-fills-pie',[{name:'Compras preenchidas',value:s.buy_fills,color:'#34e8ad'},{name:'Vendas preenchidas',value:s.sell_fills,color:'#ff7ca8'}],'Ordens registradas');
  $('ema-position').innerHTML=s.units>0?table(['Par','Quantidade','Custo USDT','Stop bid','Alvo bid'],[[escape(s.symbol),number(s.units,8),number(s.cost,6),number(s.protection?.stop,2),number(s.protection?.take,2)]]):empty('Sem posição aberta.','O bot permanece em caixa enquanto aguarda um sinal válido.');
  const signals={'WARMUP_REPLAYED':'Indicadores aquecidos. Aguardando novo candle fechado e cruzamento válido.','HOLD:NO_CROSS':'Aguardando cruzamento das médias: nenhuma entrada neste candle.','HOLD:ATR_FILTER':'Entrada bloqueada pelo filtro de volatilidade ATR.','HOLD:TREND_FILTER':'Entrada bloqueada pelo filtro de tendência EMA 200.','ENTER_LONG:EMA_CROSS_UP':'Cruzamento de compra identificado; confira a solicitação e os filtros.','EXIT_LONG:EMA_CROSS_DOWN':'Cruzamento de saída identificado; confira a posição e a ordem.'};
  const signal=signals[s.last_signal]||s.last_signal;
  $('ema-signal').textContent=`${signal} · ${s.reason==='NO_FILL'?'Sem preenchimento neste ciclo':s.reason}. Preços recebidos em ${date(s.price_received)}.`;
  $('ema-orders').innerHTML=s.orders?.length?table(['Horário','ID','Lado','Estado','Quantidade','Preenchido','Preço ref.','Motivo'],s.orders.slice().reverse().map(o=>[escape(date(o.time)),escape(o.id),escape(sides[o.side]),escape(states[o.status]),number(o.quantity,8),number(o.filled,8),number(o.price,2),escape(o.reason)])):empty('Nenhuma ordem solicitada ainda.','A sessão aguarda novos sinais; não importamos ordens da simulação anterior.');
  $('ema-fills').innerHTML=s.fills?.length?table(['Horário','Lado','Quantidade','Preço USDT','Taxa USDT'],s.fills.slice().reverse().map(f=>[escape(date(f.time)),escape(sides[f.side]),number(f.quantity,8),number(f.price,2),number(f.fee,6)])):empty('Nenhum preenchimento até agora.');
 }
 if(active){$('process-help').hidden=true;$('updated').textContent=valid?'EMA/ATR · medição '+date(s.updated):'EMA/ATR · relatório indisponível';$('connection').textContent=valid&&s.fresh&&!s.stop?'● EMA/ATR · dados recentes':'○ EMA/ATR · confira estado';$('notice').textContent='Sessão EMA/ATR com 20 USDT fictícios. Nenhuma ordem real. O botão STOP é global e não liquida posições.';$('notice').hidden=false;}
}

if(typeof location!=='undefined'&&!location.hash)location.hash='#terminal';
if(typeof location!=='undefined'&&['overview','activity','positions'].includes(location.hash.slice(1)))location.hash='terminal';
if(typeof location!=='undefined'&&['terminal','ema','diagnosis','live20','shadow','metamask','research','v3'].includes(location.hash.slice(1)))document.querySelector('[data-view="'+location.hash.slice(1)+'"]').click();


function renderEmaDiagnosis(s,multipair={}){
 const r=s.risk||{},age=Number.isFinite(s.age_seconds)?number(s.age_seconds,0)+' s':'indisponível';
 const rows=[];
 if(!s.available){rows.push(['Dados da sessão',s.status==='invalid'?'Relatório inválido ou indisponível':'Sessão ainda não encontrada','attention','Confira o iniciador EMA/ATR e sua pasta de dados; nenhum saldo foi reiniciado.']);}
 else{
  rows.push(['Atualização da coleta',s.phase==='STOPPED'?'Sessão encerrada':s.phase==='ERROR'?'Erro de coleta':s.fresh?'Dados recentes':'Sem atualização recente',s.fresh?'ok':'attention','Última medição: '+date(s.updated)+' · idade '+age+'. O painel não consulta processos do sistema.']);
  const hold=s.last_signal==='HOLD:NO_CROSS'||s.last_signal==='WARMUP_REPLAYED';
  rows.push(['Sinal da estratégia',hold?'Aguardando cruzamento EMA 20/50':s.last_signal,s.fresh?'ok':'attention',hold?'Permanecer em caixa é uma decisão válida. O bot exige novo candle fechado, tendência EMA 200 e filtro ATR.':'Último sinal salvo; confira ordens e filtros. Não garante preenchimento.']);
  rows.push(['STOP manual',s.stop?'Acionado':'Não acionado',s.stop?'blocked':'ok','STOP bloqueia ordens sem liquidar posições. O botão do painel afeta as simulações da pasta.']);
  const riskFresh=r.available&&Date.now()/1000-r.updated>=0&&Date.now()/1000-r.updated<60;
  rows.push(['Trava de perda diária',!r.available?'Checkpoint indisponível':r.daily_halted?'Entradas bloqueadas':riskFresh?'Não acionada':'Último estado salvo',!r.available?'attention':r.daily_halted?'blocked':riskFresh?'ok':'attention',r.available?'Perda em relação à base diária: '+percent(r.daily_loss)+' · checkpoint '+date(r.updated)+'. Recuperar saldo não remove a trava dentro do mesmo dia UTC.':'Sem checkpoint válido, não é possível confirmar a trava.']);
  rows.push(['Trava de drawdown',!r.available?'Checkpoint indisponível':r.drawdown_halted?'Entradas bloqueadas':riskFresh?'Não acionada':'Último estado salvo',!r.available?'attention':r.drawdown_halted?'blocked':riskFresh?'ok':'attention',r.available?'Queda em relação ao pico: '+percent(r.drawdown)+' · trava persiste após reinício e exige revisão.':'Não interpretar ausência de checkpoint como risco liberado.']);
  const pending=(s.orders||[]).find(o=>o.id===s.active_order_id);
  rows.push(['Ordem pendente',s.active_order_id?(pending?(pending.side==='BUY'?'Compra':'Venda')+' · '+(pending.status==='PARTIAL'?'parcial':'aguardando preenchimento'):'Ordem ativa fora do recorte'):'Nenhuma','info','Caixa reservado: '+number(s.reserved,6)+' USDT. Preenchimentos dependem das próximas cotações e da liquidez simulada.']);
  rows.push(['Inventário e proteção',s.units>0?(s.protection?'Posição com stop/alvo sintéticos':'Posição sem proteção confirmada'):'Sem posição aberta',s.units>0&&!s.protection?'blocked':'info',s.units>0?'Quantidade: '+number(s.units,8)+'. Proteção depende do processo ativo e pode falhar em gaps ou mínimos de ordem.':'Capital permanece em caixa; não existe posição a encerrar.']);
 }
 if(!$('diagnosis').hidden&&s.available){$('process-help').hidden=true;$('updated').textContent='Diagnóstico EMA/ATR · medição '+date(s.updated);$('connection').textContent=s.fresh&&!s.stop?'● EMA/ATR · dados recentes':'○ EMA/ATR · confira estado';$('notice').textContent='Diagnóstico da sessão EMA/ATR. Os relatórios da simulação anterior aparecem separadamente abaixo; não somar as carteiras.';}
 const scannerAge=Date.now()/1000-(multipair.updated_ms||0)/1000;
 const scannerPairs=multipair.pairs||[];
 const scannerFresh=Number.isFinite(multipair.updated_ms)&&scannerAge>=0&&scannerAge<180;
 const scannerOk=scannerFresh&&scannerPairs.length===6&&scannerPairs.every(p=>p.status==='OK');
 rows.push(['Coleta multipar · '+(multipair.timeframe||'sem período'),scannerOk?'Seis pares com dados recentes':scannerFresh?'Coleta incompleta ou com falhas':'Sem atualização recente',scannerOk?'ok':'attention','Última consulta: '+date(multipair.updated_ms?multipair.updated_ms/1000:null)+'. BTC, ETH, SOL, BNB, XRP e DOGE. Observação separada da carteira BTC/1h.']);
 $('ema-health').innerHTML=rows.map(([title,value,level,detail])=>`<article class="health-check"><div><h3>${escape(title)}</h3><p>${escape(value)}</p><small>${escape(detail)}</small></div><span class="tag ${level==='blocked'?'bad':level==='attention'?'warn':''}">${level==='blocked'?'Bloqueado':level==='attention'?'Atenção':level==='ok'?'OK':'Informação'}</span></article>`).join('');
}

function renderMultipair(s){
 let box=document.getElementById('ema-multipair');
 if(!box){const anchor=document.getElementById('ema-signal');if(!anchor)return;box=document.createElement('div');box.id='ema-multipair';anchor.parentElement.appendChild(box);}
 const recent=Number.isFinite(s.updated_ms)&&Date.now()-s.updated_ms>=0&&Date.now()-s.updated_ms<180000;
 box.innerHTML='<h3>Monitoramento BTC · ETH · SOL · BNB · XRP · DOGE</h3><p class="panel-note">Somente observação · candles '+escape(s.timeframe||'indisponível')+'. A carteira atual continua em BTC/1h. '+(recent?'Coleta recente.':'Sem coleta recente; não use estes sinais.')+'</p>'+(s.pairs?.length?table(['Par','Coleta','Sinal do último candle','Motivo'],s.pairs.map(p=>[escape(p.symbol),escape(p.status),escape(p.action||'Indisponível'),escape(p.reason)])):empty('Aguardando coleta multipar.'));
 if(s.selection){const c=s.selection;box.innerHTML+='<h3>Prévia de seleção: '+escape(c.candidate||'nenhum candidato')+'</h3><p class="panel-note">Caixa hipotético livre: 20 USDT · teto com taxa: 6 USDT. Não representa a carteira atual e não envia ordens. Desempate pelo menor spread, sem estimativa de lucro.</p>'+table(['Par','Elegível na prévia','Filtro'],(c.previews||[]).map(p=>[escape(p.symbol),p.eligible?'Sim':'Não',escape(p.reason)]));}
}

function renderSpotResearch(s){
 const reports=s.reports||[];
 $('spot-research-status').textContent=reports.length?'Pesquisa exploratória · sem aprovação. '+reports[0].source+' · salvo em '+date(reports[0].saved):'Nenhum relatório de auditoria temporal disponível nesta instalação. Não significa resultado zero.';
 $('spot-research-results').innerHTML=reports.length?reports.map(r=>'<h3>'+escape(r.symbol)+' · '+escape(r.timeframe)+' · '+escape(r.strategy||'EMA/ATR')+'</h3>'+table(['Custos','Período UTC/local','Retorno líquido','Comprar e manter','Drawdown','Operações','Acerto','Profit factor','Sharpe','Bruto USDT','Taxas USDT','Slippage USDT'],r.rows.map(w=>[escape(({base:'Base',double_costs:'Custos dobrados',fixed_base:'Alvo fixo · base',fixed_double_costs:'Alvo fixo · custos dobrados',trailing_base:'Stop móvel · base',trailing_double_costs:'Stop móvel · custos dobrados'})[w.scenario]||w.scenario),escape(date(w.start_ms/1000)+' → '+date(w.end_ms/1000)),percent(w.net_return),percent(w.buy_hold_return),percent(w.max_drawdown),number(w.closed_trades,0),percent(w.win_rate),number(w.profit_factor,2),number(w.sharpe_zero_rf,2),number(w.gross_pnl,4),number(w.closed_trade_fees,4),number(w.closed_trade_slippage,4)]))+renderResearchJournal(r.journal)).join(''):empty('Relatórios não encontrados.','Os relatórios da nova EMA/ATR aparecem aqui quando disponíveis; as pesquisas antigas abaixo são independentes.');
}

function renderResearchJournal(j){
 if(!j)return '';
 if(!j.available)return '<p class="panel-note">Diário indisponível ou integridade inválida. Não representa ausência de operações.</p>';
 const labels={fixed_base:'Alvo fixo · base',fixed_double_costs:'Alvo fixo · custos dobrados',trailing_base:'Stop móvel · base',trailing_double_costs:'Stop móvel · custos dobrados'};
 const reasons={STOP:'Stop',STOP_GAP:'Stop com gap',TARGET:'Alvo',END_LIQUIDATION:'Fim da janela'};
 return '<p class="panel-note">Diário histórico verificado por hash. Valores abaixo somam experimentos independentes, não uma carteira contínua. Horários de saída indicam o candle, não o instante exato do preenchimento. Últimas 30 operações por cenário.</p>'+j.groups.map(g=>'<details><summary>'+escape(labels[g.scenario]||g.scenario)+' · '+number(g.count,0)+' operações · líquido '+number(g.net,4)+' USDT</summary><p class="panel-note">Bruto '+number(g.gross,4)+' − taxas '+number(g.fees,4)+' − slippage '+number(g.slippage,4)+' = líquido '+number(g.net,4)+' USDT. '+escape(Object.entries(g.reasons).map(([k,v])=>(reasons[k]||k)+': '+v).join(' · '))+'</p>'+table(['Janela','Entrada','Candle da saída','Preço entrada','Preço saída','Quantidade','Motivo','Bruto','Taxas','Slippage','Líquido'],g.trades.map(t=>[number(t.window,0),escape(date(t.entry_ms/1000)),escape(date(t.exit_ms/1000)),number(t.entry,6),number(t.exit_price,6),number(t.quantity,8),escape(reasons[t.reason]||t.reason),number(t.gross_pnl,6),number(t.fees,6),number(t.slippage_cost,6),number(t.net_pnl,6)]))+'</details>').join('');
}

function renderKronos(s){
 if(!s.available){$('kronos-status').textContent=s.status==='invalid'?'Relatório Kronos inválido; previsão não exibida.':'Kronos ainda sem previsão registrada. Não significa saldo ou lucro zero.';$('kronos-paths').innerHTML=empty('Sem previsão disponível.');return;}
 $('kronos-status').textContent='Registrado em '+date(s.issued_ms/1000)+' · '+s.samples+' trajetórias separadas · próximos '+s.horizon+' candles de 1h · somente observação.';
 const all=[s.anchor_close,...s.paths.flat()],low=Math.min(...all),high=Math.max(...all),span=high-low||1;
 const y=v=>250-(v-low)/span*220,x=i=>50+i/s.horizon*700;
 const path=values=>[s.anchor_close,...values].map((v,i)=>(i?'L':'M')+x(i).toFixed(2)+','+y(v).toFixed(2)).join(' ');
 $('kronos-paths').innerHTML='<svg viewBox="0 0 800 290" role="img" aria-label="Trajetórias previstas pelo Kronos, não preços observados" style="width:100%;height:auto"><title>Previsões experimentais de fechamento</title><path d="M50 '+y(s.anchor_close)+' H750" stroke="#94a3b8" stroke-dasharray="5 5" fill="none"/>'+s.paths.map(p=>'<path d="'+path(p)+'" fill="none" stroke="#a78bfa" stroke-opacity="0.35" stroke-width="1.5"/>').join('')+'<path d="'+path(s.bands.map(b=>b.p50))+'" fill="none" stroke="#22d3ee" stroke-width="3"/><text x="50" y="280" fill="#94a3b8">Origem: '+escape(date(s.cutoff_ms/1000))+'</text><text x="600" y="280" fill="#94a3b8">Horizonte '+s.horizon+'h</text><text x="5" y="25" fill="#94a3b8">'+number(high,0)+'</text><text x="5" y="250" fill="#94a3b8">'+number(low,0)+'</text></svg><p class="panel-note">Roxo: amostras · ciano: mediana do modelo · tracejado: último fechamento conhecido.</p>';
}

function terminalChart(k,ema){
 const candles=k.candles||[];
 if(!k.available||candles.length<2)return empty('Aguardando candles verificados.','Os candles desta tela vêm da janela registrada na previsão Kronos; não usamos dados artificiais.');
 const future=k.paths||[],horizon=k.horizon||0,total=candles.length+horizon;
 const refs=ema.protection?[ema.protection.stop,ema.protection.take].filter(Number.isFinite):[];
 const values=[...candles.flatMap(c=>[c.low,c.high]),...future.flat(),...refs];
 const lo=Math.min(...values),hi=Math.max(...values),span=hi-lo||1;
 const x=i=>45+(i+.5)/total*850,y=v=>28+(hi-v)/span*265,width=Math.max(2,850/total*.58);
 const split=x(candles.length-.5),last=candles.at(-1);
 const plot=values=>values.map((v,i)=>(i?'L':'M')+x(candles.length-1+i).toFixed(2)+','+y(v).toFixed(2)).join(' ');
 let svg='<svg viewBox="0 0 950 340" role="img" aria-label="Candles reais registrados e futuros simulados pelo modelo"><title>BTC/USDT1h: observado versus previsto</title><rect x="'+split+'" y="15" width="'+(905-split)+'" height="287" fill="#fa70b509"/>';
 for(let i=0;i<5;i++){const v=lo+span*i/4;svg+='<path d="M45 '+y(v)+' H905" stroke="#2e2039" stroke-dasharray="3 5"/><text x="910" y="'+(y(v)+4)+'" fill="#a086b0" font-size="10">'+number(v,0)+'</text>';}
 svg+='<path d="M'+split+' 15 V302" stroke="#a26794" stroke-dasharray="4 5"/>';
 svg+=candles.map((c,i)=>{const color=c.close>=c.open?'#72efbc':'#ff7aab';return '<path d="M'+x(i)+' '+y(c.high)+' V'+y(c.low)+'" stroke="'+color+'"/><rect x="'+(x(i)-width/2)+'" y="'+Math.min(y(c.open),y(c.close))+'" width="'+width+'" height="'+Math.max(1,Math.abs(y(c.open)-y(c.close)))+'" fill="'+color+'"/>';}).join('');
 svg+=future.map(p=>'<path d="'+plot([last.close,...p])+'" fill="none" stroke="#f778c2" stroke-opacity=".4" stroke-width="1.5"/>').join('');
 svg+='<path d="'+plot([last.close,...(k.bands||[]).map(b=>b.p50)])+'" fill="none" stroke="#62e6e6" stroke-width="2.5"/>';
 if(ema.protection)for(const [name,value,color] of [['Stop',ema.protection.stop,'#ff7aab'],['Alvo',ema.protection.take,'#72efbc']])if(Number.isFinite(value))svg+='<path d="M45 '+y(value)+' H905" stroke="'+color+'" stroke-dasharray="6 6"/><text x="50" y="'+(y(value)-5)+'" fill="'+color+'" font-size="10">'+name+' EMA · '+number(value,2)+'</text>';
 for(const f of ema.fills||[]){const index=candles.findIndex(c=>f.time*1000>=c.time_ms&&f.time*1000<c.time_ms+3600000);if(index>=0)svg+='<circle cx="'+x(index)+'" cy="'+y(f.price)+'" r="4" fill="'+(f.side==='BUY'?'#72efbc':'#ff7aab')+'"/>';}
 return svg+'<text x="45" y="326" fill="#a086b0" font-size="10">'+escape(date(candles[0].time_ms/1000))+'</text><text x="'+(split+6)+'" y="326" fill="#f778c2" font-size="10">Previsão · '+horizon+'h</text></svg>';
}
function renderTerminal(data){
 renderPremium(data);
 const multi=data.system?.controller?.engine==='portfolio',p=data.portfolio||{};
 const num=v=>v===null||v===undefined?NaN:Number(v);
 const shared={available:p.available,fresh:p.fresh,capital:20,equity:num(p.equity),pnl:num(p.equity)-20,cash:num(p.cash),reserved:num(p.reserved),fees:num(p.fees),realized:num(p.realized),updated:p.updated||(Number.isFinite(data.system?.execution?.age_seconds)?Date.now()/1000-data.system.execution.age_seconds:null),reason:p.reason,last_signal:p.reason,symbol:p.position?.symbol||'6 pares / USDT',units:num(p.position?.quantity||0),active_order_id:p.pending?.id,synthetic_exit:!!p.position?.exit_request,stop:p.halt==='STOP'||p.reason==='STOP',buy_fills:p.buy_fills??(p.fills||[]).filter(f=>f.side==='BUY').length,sell_fills:p.sell_fills??(p.fills||[]).filter(f=>f.side==='SELL').length,orders:(p.orders||[]).map(o=>({...o,quantity:num(o.quantity),price:num(o.limit)})),fills:(p.fills||[]).map(f=>({...f,quantity:num(f.quantity),price:num(f.price),time:f.time_ms/1000})),risk:{available:p.available&&p.fresh,updated:p.updated,drawdown:num(p.drawdown),daily_halted:p.halt==='DAILY_LOSS',drawdown_halted:p.halt==='DRAWDOWN'}};
 const s=multi?shared:data.ema||{},m=data.multipair||{},k=data.kronos_lab||{},r=s.risk||{};
 const valid=!!s.available,now=Date.now()/1000,marketAge=now-(m.updated_ms||0)/1000;
 const marketFresh=marketAge>=0&&marketAge<180&&m.pairs?.length===6&&m.pairs.every(p=>p.status==='OK');
 const riskFresh=r.available&&now-r.updated>=0&&now-r.updated<60;
 const stop=!!(data.stop||s.stop),riskBlocked=!!(stop||r.daily_halted||r.drawdown_halted);
 const stage=(title,value,note,level)=>'<article class="term-stage '+level+'"><div class="term-stage-top"><span>'+title+'</span><span>⬡</span></div><b>'+escape(value)+'</b><small>'+escape(note)+'</small></article>';
 $('term-pipeline').innerHTML=[stage('01 / MARKET',marketFresh?'6 pares / coleta recente':'Coleta sem confirmação',m.updated_ms?'Consulta '+date(m.updated_ms/1000):'Sem relatório',marketFresh?'ok':'warn'),stage('02 / STRATEGY',valid?s.last_signal==='HOLD:NO_CROSS'?'Aguardando cruzamento':s.last_signal:'Sem sessão EMA',multi?'Seis pares · candle15m':'BTC/USDT · candle1h',s.fresh?'ok':'warn'),stage('03 / RISK',riskBlocked?'Entradas bloqueadas':riskFresh?'Travas sem acionamento':'Risco sem leitura recente','1% operação · 3% dia · 10% DD',riskBlocked||!riskFresh?'warn':'ok'),stage('04 / EXECUTION',s.synthetic_exit?'Saída sintética solicitada':s.active_order_id?'Ordem fictícia pendente':valid?'Sem ordem pendente':'Sem carteira confirmada','Nenhuma ordem real',s.fresh?'ok':'warn'),stage('05 / KRONOS',k.available?k.samples+' trajetórias registradas':'Sem previsão','Modelo experimental · sem ordens','model'),stage('06 / VALIDATION','Ainda sem aprovação','Resultados líquidos inconsistentes','warn')].join('');
 const stats=[['Patrimônio fictício',valid?number(s.equity,4)+' USDT':'—',valid?'Capital inicial '+number(s.capital)+' USDT':'Nenhuma medição disponível'],['Resultado líquido',valid?number(s.pnl,4)+' USDT':'—','Realizado '+number(s.realized,4)+' USDT'],['Drawdown atual',r.available?percent(r.drawdown):'—',riskFresh?'Checkpoint recente':'Confira idade em Diagnóstico'],['Preenchimentos',valid?number(s.buy_fills+s.sell_fills,0):'—','Taxas '+number(s.fees,6)+' USDT']];
 $('term-metrics').innerHTML=stats.map(([title,value,note])=>'<article class="term-stat"><p>'+escape(title)+'</p><strong>'+escape(value)+'</strong><small>'+escape(note)+'</small></article>').join('');
 $('term-chart').innerHTML=terminalChart(k,multi?{}:s);
 $('term-chart-note').textContent=k.available?'Candles históricos registrados até '+date(k.cutoff_ms/1000)+' · previsão emitida '+date(k.issued_ms/1000)+'. A linha futura é do modelo; não é preço observado nem sinal de entrada.':'Sem janela de candles verificada. A ausência de gráfico não significa preço zero.';
 const angle=valid&&Number.isFinite(s.equity)&&s.equity>0?Math.max(0,Math.min(360,(s.cash-s.reserved)/s.equity*360)):0;
 $('term-allocation').innerHTML=valid?'<div class="term-ring" style="--cash-angle:'+angle+'deg"><div><strong>'+number(s.cash-s.reserved,2)+'</strong><small>CAIXA LIVRE / USDT</small></div></div>':empty('Carteira sem medição.');
 const riskRows=[['Reserva',number(s.reserved,4)+' USDT'],['Posição',s.units>0?s.symbol+' · '+number(s.units,8):valid?'Em caixa':'Indisponível'],['Teto por entrada','6 USDT com taxa'],['Kill switch',stop?'Acionado':'Não acionado'],['Última medição',date(s.updated)]];
 $('term-risk').innerHTML=riskRows.map(([label,value])=>'<div class="term-risk-row"><span>'+escape(label)+'</span><b>'+escape(value)+'</b></div>').join('');
 $('term-radar-state').textContent=marketFresh?'COLETA RECENTE':'DADOS SEM ATUALIZAÇÃO RECENTE';
 $('term-radar').innerHTML=m.pairs?.length?table(['Par','Fechamento','Leitura','Motivo'],m.pairs.map(p=>[escape(p.symbol),number(p.close,p.close<1?5:2),escape(p.status==='OK'?(p.action==='HOLD'?'Aguardar':p.action):'Falha'),escape(p.reason)])):empty('Sem relatório multipar.');
 $('term-orders').innerHTML=s.orders?.length?table(['Lado','Estado','Quantidade','Preço'],s.orders.slice(-6).reverse().map(o=>[escape(o.side),escape(o.status),number(o.quantity,8),number(o.price,2)])):empty('Nenhuma ordem registrada.','Sem sinal válido, o bot pode permanecer em caixa.');
 const logs=[];
 if(valid)logs.push([s.updated,(multi?'MULTIPAR / ':'EMA / ')+s.last_signal,s.reason||'Estado registrado']);
 if(m.updated_ms)logs.push([m.updated_ms/1000,'RADAR / '+(m.timeframe||'—'),m.selection?.candidate?'Prévia: '+m.selection.candidate:'Sem candidato na prévia']);
 if(k.available)logs.push([k.issued_ms/1000,'KRONOS / previsão salva',k.samples+' trajetórias · horizonte '+k.horizon+'h']);
 for(const f of (s.fills||[]).slice(-5))logs.push([f.time,f.side+' / preenchimento fictício',number(f.quantity,8)+' · '+number(f.price,2)+' USDT']);
 logs.sort((a,b)=>b[0]-a[0]);
 $('term-log').innerHTML=logs.length?logs.map(([t,title,note])=>'<div class="term-event"><time>'+escape(date(t))+'</time><strong>'+escape(title)+'</strong><small>'+escape(note)+'</small></div>').join(''):empty('Nenhum evento disponível.');
 if(!$('terminal').hidden){$('process-help').hidden=true;$('heading').textContent='Terminal de operações.';$('updated').textContent=valid?(multi?'Carteira compartilhada · ':'Carteira EMA · ')+date(s.updated):'Carteira sem medição';$('connection').textContent=s.fresh?(multi?'● Multipar · dados recentes':'● EMA · dados recentes'):(multi?'○ Multipar · confira atualização':'○ EMA · confira atualização');$('notice').hidden=false;$('notice').textContent=stop?'STOP acionado. Posições não são liquidadas automaticamente.':(multi?'Saldo compartilhado fictício: seis pares15m, uma posição por vez. Gráfico BTC/Kronos é apenas observação.':'Somente saldo fictício. Monitoramento multipar e Kronos são observações; a execução atual permanece BTC/1h.');}
}

function renderSystemIntegration(s){
 const c=s.controller||{},e=s.execution||{},m=s.market||{};
 $('term-system').textContent='Integração: '+(c.fresh?'iniciador único ativo':'iniciador único sem atividade confirmada')+' · Motor '+(e.symbol||'BTC/USDT')+'/'+(e.timeframe||'1h')+': '+(e.fresh?'relatório recente':'sem leitura recente')+' · Radar de seis pares: '+(m.fresh?'recente':'sem leitura recente')+'. Carteira multipar experimental possui estado próprio abaixo; motor do iniciador: '+(c.engine||'ema')+'. Kronos e pesquisas não enviam ordens.';
 $('integration-diagnosis').textContent=$('term-system').textContent;
 const age=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0?(v<60?Math.floor(v)+' s':Math.floor(v/60)+' min'):'indisponível';
 const statusCard=(title,value,detail,ok)=>'<div class="operation-card '+(ok?'is-recent':'is-stale')+'"><span>'+escape(title)+'</span><strong>'+escape(value)+'</strong><small>'+escape(detail)+'</small></div>';
 $('operation-summary').innerHTML=statusCard('Motor',e.fresh?'Dados recentes':'Sem confirmação recente',(e.symbol||'—')+' · '+(e.timeframe||'—'),e.fresh)+statusCard('Radar',m.fresh?'Atualizado':'Confira a coleta','Idade da leitura: '+age(m.age_seconds),m.fresh)+statusCard('Supervisor',c.fresh?'Ativo':'Sem confirmação','Idade da leitura: '+age(c.age_seconds),c.fresh)+statusCard('Ambiente','Saldo fictício','PAPER · nenhuma ordem real',true);
}

function renderPortfolio(s){
 renderPortfolioPerformance(s);
 $('portfolio-status').textContent=s.available?((s.fresh?'Relatório recente':'Sem atualização recente')+' · '+s.phase+' · '+s.reason+' · Trava: '+(s.halt||'nenhuma registrada')):'Experimento multipar não iniciado ou indisponível: '+(s.reason||'NOT_STARTED');
 const fmt=v=>v===null||v===undefined?'—':number(Number(v),6);
 $('portfolio-wallet').innerHTML=s.available?table(['Capital fictício','Caixa','Reservado','Patrimônio estimado','Taxas','Realizado'],[[fmt(s.capital),fmt(s.cash),fmt(s.reserved),fmt(s.equity),fmt(s.fees),fmt(s.realized)]]):empty('Sem carteira multipar ativa.');
 const p=s.position;
 $('portfolio-position').innerHTML=p?table(['Par','Quantidade','Stop sintético','Alvo sintético','Saída solicitada'],[[escape(p.symbol),escape(p.quantity),escape(p.stop),escape(p.take),escape(p.exit_request?.reason||'Não solicitada')]]):empty('Sem posição aberta. O saldo permanece em caixa enquanto não houver entrada válida.');
 $('portfolio-orders').innerHTML=(s.orders||[]).length?table(['Par','Lado','Estado','Motivo'],s.orders.slice(-10).reverse().map(o=>[escape(o.symbol),escape(o.side),escape(o.status),escape(o.reason)])):empty('Nenhuma ordem multipar registrada.');
 $('portfolio-fills').innerHTML=(s.fills||[]).length?table(['Par','Lado','Preço','Quantidade','Taxa'],s.fills.slice(-10).reverse().map(f=>[escape(f.symbol),escape(f.side),escape(f.price),escape(f.quantity),escape(f.fee)])):empty('Nenhum preenchimento multipar registrado.');
}

function renderLaunchHelp(data){
 const e=data.system?.execution,c=data.system?.controller||{},p=data.portfolio||{};
 const running=!!(e?.fresh||c.fresh);
 if(e&&!$('research').hidden){$('connection').textContent=e.fresh?'● Bot ativo · pesquisas históricas':'Pesquisas históricas · confira Bot ao vivo';$('updated').textContent='Relatórios de pesquisa com datas próprias; não representam o saldo do motor ativo.';$('notice').hidden=false;$('notice').textContent='Pesquisas e experimentos não iniciam o bot nem autorizam dinheiro real. Acompanhe a execução atual em Bot ao vivo.';}
 const blocked=!!(data.stop||p.halt||['STOP','DEADLINE','DRAWDOWN','DAILY_LOSS'].includes(e?.reason));
 if(e&&!$('diagnosis').hidden){$('heading').textContent='Diagnóstico da operação atual.';$('connection').textContent=e.fresh?'● Motor atual · dados recentes':'○ Motor atual · confira atualização';$('updated').textContent='Motor '+(c.engine||'não identificado')+' · '+(e.timeframe||'—')+' · relatórios antigos identificados abaixo.';$('notice').hidden=false;$('notice').textContent=blocked?'Motor atual com trava ou prazo encerrado. Confira o motivo antes de retomar.':'Saúde da operação atual. Sessões antigas abaixo não representam o saldo ou o estado do motor ativo.';}
 $('process-help').hidden=!e||$('diagnosis').hidden||running;
 $('process-command').hidden=blocked||running;
 $('process-instruction').textContent=running?'Motor atual com atividade recente. Não inicie outro processo.':blocked?'O motor está parado com trava ou prazo encerrado. Revise o motivo no diagnóstico; iniciar novamente não remove essa condição.':'Não há execução recente confirmada. Confira processos existentes e o diagnóstico antes de iniciar o motor PAPER na pasta atualizada do projeto.';
}

function entryExplanation(row,market,p,system,stopped,nowMs){
 const stamp=market.updated_ms,age=nowMs-stamp;
 if(!Number.isFinite(stamp)||age<0||age>=180000)return 'Radar sem leitura recente; nenhuma conclusão de entrada';
 if(row.status!=='OK')return 'Falha nos dados públicos deste par';
 if(stopped||p.halt)return 'Entrada bloqueada: '+(p.halt||'STOP');
 if(p.position)return 'Carteira já possui posição em '+p.position.symbol;
 if(p.pending)return 'Saldo reservado para '+p.pending.symbol;
 const meanings={NO_CROSS:'Aguardando novo cruzamento EMA20 acima da EMA50',TREND_FILTER:'Cruzamento bloqueado pelo filtro EMA200',ATR_FILTER:'Cruzamento bloqueado pelo filtro de volatilidade ATR',WARMUP:'Indicadores em aquecimento',EMA_CROSS_DOWN:'Cruzamento de baixa; não é sinal de compra'};
 if(row.action==='ENTER_LONG'){
   const delta=nowMs-row.candle_close_ms;
   if(!Number.isFinite(delta)||delta<0||delta>120000)return 'Sinal registrado fora da janela de entrada de 2 minutos';
   if(system.controller?.engine!=='portfolio')return 'Sinal do radar; motor multipar não está selecionado';
   if(!system.execution?.fresh)return 'Sinal recente, mas execução sem atualização confirmada';
   return 'Sinal recente; reserva e filtros finais ainda precisam de confirmação no ledger';
 }
 return meanings[row.reason]||'Sem intenção de compra registrada: '+(row.reason||'motivo indisponível');
}
function renderEntryDiagnostics(data){
 renderDecisionAudit(data);
 const m=data.multipair||{},p=data.portfolio||{},system=data.system||{},now=Date.now();
 const rows=Array.isArray(m.pairs)?m.pairs:[];
 $('entry-check-time').textContent=m.updated_ms?'Última coleta do radar: '+date(m.updated_ms/1000)+' · candles '+(m.timeframe||'não informado')+'.':'Sem coleta do radar para analisar.';
 const n=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
 $('entry-checks').innerHTML=rows.length?table(['Par','Candle fechado','EMA20 / EMA50','Preço / EMA200','ATR observado','Situação da entrada'],rows.map(row=>{
   const fast=n(row.ema_fast),slow=n(row.ema_slow),close=n(row.close),trend=n(row.ema_trend),atr=n(row.atr_fraction);
   const relation=fast===null||slow===null?'Indisponível':fast>slow?'EMA20 acima':fast<slow?'EMA20 abaixo':'Médias iguais';
   const trendState=close===null||trend===null?'Indisponível':close>trend?'Acima da EMA200':'Em/abaixo da EMA200';
   return [escape(row.symbol),escape(date(row.candle_close_ms/1000)),escape(relation),escape(trendState),percent(atr),escape(entryExplanation(row,m,p,system,!!data.stop,now))];
 })):empty('Sem avaliações registradas.','Dados ausentes não significam sinal de compra.');
}

// Read-only operational explanation. A radar intention is never an order.
function decisionSnapshot(data,now=Date.now()){
 const p=data.portfolio||{},system=data.system||{},m=data.multipair||{};
 const orders=Array.isArray(p.orders)?p.orders:[];
 const age=typeof p.updated==='number'&&Number.isFinite(p.updated)?now-p.updated*1000:NaN;
 const marketAge=typeof m.updated_ms==='number'&&Number.isFinite(m.updated_ms)?now-m.updated_ms:NaN;
 const fresh=p.fresh===true&&age>=0&&age<60000;
 const pairs=Array.isArray(m.pairs)?m.pairs:[];
 const radarFresh=marketAge>=0&&marketAge<180000&&pairs.length===6&&
   pairs.every(r=>r.status==='OK')&&new Set(pairs.map(r=>r.symbol)).size===6;
 let state='UNKNOWN',message='Sem carteira reconciliada disponível.';
 if(system.controller?.engine!=='portfolio'){message='O motor multipar não está selecionado.';}
 else if(data.stop||p.halt==='STOP'||p.reason==='STOP'){state='STOP';message='STOP acionado: novas ordens bloqueadas. Posições não são liquidadas.';}
 else if(p.available){
   const end=system.execution?.end_ms;
   if(Number.isSafeInteger(end)&&now>=end){state='ENDED';message='Prazo da sessão encerrado; saldo e prazo não reiniciados.';}
   else if(p.halt){state='HALTED';message='Trava registrada: '+p.halt+'. Revise a causa antes de retomar.';}
   else if(!fresh){state='STALE';message='Sem atualização recente da carteira; não é possível confirmar execução atual.';}
   else if(p.position?.exit_request){state='EXIT_PENDING';message='Saída sintética solicitada; venda ainda depende de cotação posterior, filtros e liquidez.';}
   else if(p.pending){state='ENTRY_PENDING';message='Reserva de entrada registrada; ainda não confirma uma compra preenchida.';}
   else if(p.position){state='POSITION_OPEN';message='Posição registrada. Stop e alvo são sintéticos e dependem do processo ativo.';}
   else{state='WAITING';message='Em caixa, sem ordem pendente. Consulte as avaliações atuais de cada par abaixo.';}
 }
 const counts=p.available?{orders:orders.length,canceled:orders.filter(o=>o.status==='CANCELED').length,
   rejected:orders.filter(o=>o.status==='REJECTED').length,filled:orders.filter(o=>o.status==='FILLED').length}:null;
 const intentions=radarFresh&&Array.isArray(m.pairs)?m.pairs.filter(r=>r.status==='OK'&&r.action==='ENTER_LONG').length:null;
 return {state,message,fresh,counts,intentions,orders:p.available?orders:[]};
}
function renderDecisionAudit(data){
 const s=decisionSnapshot(data),c=s.counts;
 $('decision-status').textContent=s.message;
 const card=(label,value)=>'<div class="operation-card"><span>'+escape(label)+'</span><strong>'+escape(value??'—')+'</strong></div>';
 $('decision-counts').innerHTML=card('Intenções atuais do radar',s.intentions)+card('Ordens no recorte',c?.orders)+card('Canceladas no recorte',c?.canceled)+card('Rejeitadas no recorte',c?.rejected);
 const meanings={EXPIRED:'Expirada sem preenchimento',SIGNAL_EXIT:'Cancelada por sinal de saída',STOP:'Cancelada por STOP',ENTRY_BELOW_STOP:'Entrada abaixo do stop',RESERVED:'Caixa reservado',FILLED:'Preenchida'};
 $('decision-orders').innerHTML=s.orders.length?table(['Criação da ordem','Par','Estado registrado','Motivo registrado'],s.orders.slice(-10).reverse().map(o=>[escape(date(o.created_ms/1000)),escape(o.symbol),escape(o.status),escape(meanings[o.reason]||o.reason||'Não informado')])):empty(c?'Nenhuma ordem no recorte recebido.':'Histórico indisponível.');
}

function portfolioPerformance(s){
 const fills=Array.isArray(s.fills)?s.fills:[],buys=s.buy_fills??fills.filter(f=>f.side==='BUY').length,sells=s.sell_fills??fills.filter(f=>f.side==='SELL').length;
 const complete=Number.isInteger(buys)&&Number.isInteger(sells)&&buys+sells===fills.length;
 let position=null,valid=complete,lastTime=-1;const trades=[];
 if(complete)for(const f of fills){
   const q=Number(f.quantity),price=Number(f.price),fee=Number(f.fee),t=f.time_ms;
   if(![q,price,fee,t].every(Number.isFinite)||q<=0||price<=0||fee<0||t<0||t<lastTime||f.fee===null){valid=false;break;}
   lastTime=t;
   if(f.side==='BUY'&&!position)position={symbol:f.symbol,quantity:q,cost:q*price+fee,time:t};
   else if(f.side==='SELL'&&position&&position.symbol===f.symbol&&q===position.quantity&&t>=position.time){trades.push({symbol:f.symbol,net:q*price-fee-position.cost,minutes:(t-position.time)/60000});position=null;}
   else{valid=false;break;}
 }
 const gains=trades.reduce((a,t)=>a+Math.max(0,t.net),0),losses=trades.reduce((a,t)=>a+Math.max(0,-t.net),0);
 const wins=trades.filter(t=>t.net>0),losers=trades.filter(t=>t.net<0);
 let currentWin=0,currentLoss=0,maxWin=0,maxLoss=0;
 for(const t of trades){currentWin=t.net>0?currentWin+1:0;currentLoss=t.net<0?currentLoss+1:0;maxWin=Math.max(maxWin,currentWin);maxLoss=Math.max(maxLoss,currentLoss);}
 return {averageWin:valid&&wins.length?gains/wins.length:null,averageLoss:valid&&losers.length?-losses/losers.length:null,maxWinStreak:valid&&trades.length?maxWin:null,maxLossStreak:valid&&trades.length?maxLoss:null,
 byPair:valid?Array.from(new Set(trades.map(t=>t.symbol))).map(symbol=>{const rows=trades.filter(t=>t.symbol===symbol);return {symbol,count:rows.length,net:rows.reduce((a,t)=>a+t.net,0),winRate:rows.filter(t=>t.net>0).length/rows.length};}):[],
 buys,sells,complete:valid,closed:valid?trades.length:null,winRate:valid&&trades.length?trades.filter(t=>t.net>0).length/trades.length:null,
   profitFactor:valid&&losses>0?gains/losses:null,noLosses:valid&&trades.length>0&&losses===0,
   averageMinutes:valid&&trades.length?trades.reduce((a,t)=>a+t.minutes,0)/trades.length:null};
}
function renderPortfolioPerformance(s){
 const box=$('portfolio-performance'),note=$('portfolio-performance-note');
 if(!s.available){box.innerHTML=empty('Relatório da sessão indisponível.');note.textContent='Nenhum resultado inventado para dados ausentes.';return;}
 const stats=portfolioPerformance(s),v=x=>x===null||x===undefined?'—':number(Number(x),6);
 const equity=s.equity===null||s.equity===undefined?null:Number(s.equity),realized=Number(s.realized),capital=Number(s.capital);
 const net=Number.isFinite(equity)&&Number.isFinite(capital)?equity-capital:null;
 const unrealized=net!==null&&Number.isFinite(realized)?net-realized:null;
 box.innerHTML=table(['Métrica','Valor'],[
 ['Compras / vendas preenchidas',escape(String(stats.buys)+' / '+String(stats.sells))],
 ['Resultado realizado líquido',escape(v(s.realized)+' USDT')],
 ['Resultado em aberto estimado',escape(v(unrealized)+' USDT')],
 ['Resultado total estimado',escape(v(net)+' USDT')],
 ['Taxas registradas nos preenchimentos',escape(v(s.fees)+' USDT')],
 ['Acerto dos ciclos fechados',escape(stats.winRate===null?'Sem amostra completa':percent(stats.winRate))],
 ['Profit factor líquido',escape(stats.profitFactor===null?(stats.noLosses?'Sem perdas na amostra; razão não calculada':'Sem amostra calculável'):number(stats.profitFactor,3))],
 ['Duração média de um ciclo fechado',escape(stats.averageMinutes===null?'Sem amostra completa':number(stats.averageMinutes,2)+' minutos')],
 ['Média de ganho / perda líquida',escape(v(stats.averageWin)+' / '+v(stats.averageLoss)+' USDT')],
 ['Maior sequência de ganhos / perdas',escape((stats.maxWinStreak??'—')+' / '+(stats.maxLossStreak??'—'))],
 ...stats.byPair.map(p=>['Ciclos '+p.symbol,escape(p.count+' · líquido '+v(p.net)+' USDT · acerto '+percent(p.winRate))])
 ]);
 note.textContent='Taxas já estão incluídas no resultado líquido; não descontar novamente. Slippage integra os preços simulados e não está medido separadamente. '+(stats.complete?'Acerto e duração usam os ciclos fechados registrados, sem contar posição aberta como ganho.':'O histórico recebido está parcial ou inconsistente; acerto, profit factor e duração não são calculados.')+' Tempo ativo e comparação com comprar e manter ainda não foram medidos. Sem aprovação de rentabilidade.';
}

function renderExternalContext(report){
 const now=Date.now(),sources=report.sources||{},parts=[];
 for(const [key,label,maxAge] of [['alternative','Alternative.me · sentimento BTC diário',172800000],['coinpaprika','CoinPaprika · preços agregados USD',1800000],['geckoterminal','GeckoTerminal · amostra de pools',1800000]]){
   const source=sources[key]||{},d=source.data,age=now-source.fetched_ms;
   const partial=key==='geckoterminal'&&source.status==='PARTIAL';
   let fresh=(source.status==='OK'||partial)&&Number.isFinite(age)&&age>=0&&age<maxAge;
   if(key==='alternative')fresh=fresh&&Number.isFinite(d?.source_ms)&&now-d.source_ms>=0&&now-d.source_ms<maxAge;
   if(key==='coinpaprika')fresh=fresh&&Array.isArray(d?.tickers)&&d.tickers.length===6&&d.tickers.every(t=>Number.isFinite(t.source_ms)&&now-t.source_ms>=0&&now-t.source_ms<maxAge);
   parts.push('<h3>'+escape(label)+'</h3><p class="term-note">'+escape(fresh?(partial?'Cobertura parcial · consulta ':'Consulta válida · ')+date(source.fetched_ms/1000):(source.status||'NOT_COLLECTED')+' · sem confirmação recente')+'</p>');
   if(!d){parts.push(empty('Dados indisponíveis; não usados pelo motor.'));continue;}
   if(fresh&&partial)parts.push('<p class="term-note">Resultados recentes somente para as redes OK abaixo. Redes indisponíveis não têm dados confirmados.</p>');
   if(!fresh)parts.push('<p class="term-note">Último dado salvo abaixo; pode estar vencido.</p>');
   if(key==='alternative')parts.push(table(['Índice (0–100)','Data do índice'],[[escape(d.value),escape(date(d.source_ms/1000))]]));
   if(key==='coinpaprika')parts.push(table(['Ativo','Preço agregado USD','Atualização da fonte'],(d.tickers||[]).map(t=>[escape(t.symbol),number(t.usd_price,6),escape(date(t.source_ms/1000))])));
   if(key==='geckoterminal'&&d.networks)parts.push('<p class="term-note">'+escape(Object.entries(d.networks).map(([n,v])=>n+': '+v).join(' · '))+'</p>');
   if(key==='geckoterminal')parts.push(table(['Rede','Pool (amostra)','Liquidez USD','Volume 24h USD'],(d.pools||[]).map(p=>[escape(p.network),escape(p.name),number(p.liquidity_usd),number(p.volume_24h_usd)])));
 }
 $('external-context').innerHTML=parts.join('');
}

for(const button of document.querySelectorAll('[data-section-scroll]'))button.addEventListener('click',()=>{
 const target=document.getElementById(button.dataset.sectionScroll);
 if(target)target.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
});

function renderOperationHealth(s){
 const age=Date.now()/1000-s.updated,valid=s.version===1&&Number.isFinite(age)&&age>=0&&age<45;
 if(!s.version){$('operation-health').innerHTML=empty('Monitor ainda sem medições.');return;}
 const duration=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0?number(v/60,1)+' min':'—';
 $('operation-health').innerHTML='<p class="panel-note">'+escape(valid?'Monitor com leitura recente':'MONITOR SEM ATUALIZAÇÃO RECENTE')+' · início '+escape(date(s.started))+'</p>'+table(['Classificação dos intervalos','Duração estimada'],[['Sinais recentes nas amostras',duration(s.recent_seconds)],['Motor reportado como parado',duration(s.stopped_seconds)],['Sem evidência suficiente',duration(s.unknown_seconds)],['Última lacuna de coleta',duration(s.last_gap_seconds)]])+'<p class="panel-note">Último estado observado: '+escape(s.state)+' · '+escape(date(s.updated))+'. Não é uma garantia de funcionamento 24/7.</p>';
}

// [CONECTAR: API interna] All journal rows come from the existing wallet snapshot.
$('trade-search').addEventListener('input',()=>renderTradeJournal(latestPortfolioRecord));
$('trade-export').addEventListener('click',()=>{
 const url=URL.createObjectURL(new Blob([journalCsv(filteredJournal(latestPortfolioRecord))],{type:'text/csv;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;link.download='spotlab-paper-recorte.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
function setupWorkspace(){
 const applyTheme=value=>{const theme=['dark','light','matrix'].includes(value)?value:'dark';$('app').dataset.theme=theme;$('theme-select').value=theme;return theme;};
 const applyWorkspace=value=>{const workspace=['overview','risk','pairs','diagnosis'].includes(value)?value:'overview';$('workspace-select').value=workspace;$('terminal').dataset.workspace=workspace;if(workspace==='diagnosis')document.querySelector('[data-view="diagnosis"]').click();return workspace;};
 $('theme-select').addEventListener('change',()=>{const theme=applyTheme($('theme-select').value);try{localStorage.setItem('spotlab-theme',theme);}catch{}});
 $('workspace-select').addEventListener('change',()=>{const value=applyWorkspace($('workspace-select').value);try{localStorage.setItem('spotlab-workspace',value);}catch{}});
 try{applyTheme(localStorage.getItem('spotlab-theme'));const w=localStorage.getItem('spotlab-workspace');if(w&&w!=='diagnosis')applyWorkspace(w);}catch{}
 let panel=null,marker=null;
 const restore=()=>{if(panel&&marker){marker.replaceWith(panel);panel=null;marker=null;}};
 $('focus-close').addEventListener('click',()=>$('panel-focus').close());
 $('panel-focus').addEventListener('close',restore);
 for(const article of document.querySelectorAll('#terminal > article,#operations-visuals > article,#diagnosis > article')){
   const title=article.querySelector('h2');if(!title)continue;
   const button=document.createElement('button');button.className='panel-focus-button secondary';button.textContent='⤢ Ampliar';button.setAttribute('aria-label','Ampliar '+title.textContent);
   button.addEventListener('click',()=>{if(panel)return;panel=article;marker=document.createComment('panel workspace position');article.replaceWith(marker);$('focus-content').append(article);$('panel-focus').showModal();});
   title.after(button);
 }
}
if(typeof window!=='undefined')setupWorkspace();

// Reuses the authenticated status poll; no new timer, execution route or mock.
function renderV3(view){
 if(!$('v3-health'))return;
 renderSingleExitAudit(view.single_exit_audit||{});
 const r=view.report||{},wait='Aguardando dados do motor V3...';
 const one=view.single_exit||{};
 if($('single-exit-research'))$('single-exit-research').innerHTML=one.scope?'<p>Veredito: <strong>'+escape(one.verdict)+'</strong> · Execução BLOQUEADA</p>'+table(['Cenário','Patrimônio fictício final','Retorno líquido','Ciclos','Profit factor','DD máximo','Retornos dos 4 períodos'],(one.scenarios||[]).map(s=>[escape(s.name),number(s.continuous.final_equity==null?NaN:Number(s.continuous.final_equity))+' USDT',percent(s.continuous.net_return),number(s.continuous.closed_trades,0),number(s.continuous.profit_factor),percent(s.continuous.max_drawdown),escape((s.windows||[]).map(w=>percent(w.net_return)).join(' / '))])):empty('Teste de saída única ainda não carregado.');

 const f=view.feasibility||{},frows=Array.isArray(f.pairs)?f.pairs:[],bt=view.backtest||{};
 if($('v3-feasibility'))$('v3-feasibility').innerHTML=frows.length?'<p>Consulta salva: '+escape(date(f.updated_ms/1000))+' · não é cotação ao vivo</p>'+table(['Par','Mínimo/ordem','Mínimo agregado 3 stops','Score atual','Motivo atual','Teste score100','Teto impede 3 parcelas'],frows.map(p=>[escape(p.symbol),escape(p.normalized_rules?.min_notional),escape(p.minimum_aggregate_stop_notional),number(p.actual_score,0),escape(p.strategy_score_plan?.reason||p.reason),escape(p.hypothetical_perfect_score_plan?.reason),p.cap_precludes_three_stop_legs===true?'Sim':'Não demonstrado'])):empty('Auditoria de filtros ainda não coletada.');
 if($('v3-backtest'))$('v3-backtest').innerHTML=bt.scope?table(['Diagnóstico offline','Valor'],[['Par',escape(bt.symbol)],['Candidatos / ciclos fechados',escape(bt.candidate_count)+' / '+escape(bt.closed_trades)],['Retorno líquido hipotético',percent(bt.net_return)],['Rejeições',escape(JSON.stringify(bt.rejected_candidates||{}))],['Veredito',escape(bt.verdict)],['Execução','BLOQUEADA']]):empty('Backtest integrado V3 ainda não carregado.');

 $('v3-health').textContent=!view.available?wait:(view.fresh?'Observador recente':'Sem confirmação recente')+' · '+String(r.reason||'UNKNOWN')+' · '+date(r.updated_ms/1000);
 const pairs=Array.isArray(r.pairs)?r.pairs:[];
 const badge=regime=>'<span class="v3-regime '+(['TREND','BREAKOUT','RANGE','CRISIS'].includes(regime)?regime:'UNKNOWN')+'">'+escape(regime||'UNKNOWN')+'</span>';
 $('v3-regimes').innerHTML=pairs.length?table(['Par','Estado','Regime','ADX14','RSI14','ATR','Score'],pairs.map(p=>[escape(p.symbol),escape(view.fresh?p.status:'Dado salvo'),badge(p.regime_v3),number(p.state?.adx14),number(p.state?.rsi14),percent(p.state?.atr_fraction),number(p.score_estimate,0)])):empty(wait);
 const signals=Array.isArray(r.signals)?r.signals.slice(0,50):[];
 $('v3-signals').innerHTML=signals.length?table(['UTC/local','Par','Regime','Score','Ação','Motivo / componentes'],signals.map(s=>[escape(date(s.timestamp_ms/1000)),escape(s.symbol),badge(s.regime),number(s.score,0),escape(s.action),'<details><summary>'+escape(s.reason)+'</summary>'+Object.entries(s.components||{}).map(([k,v])=>'<p>'+escape(k)+' <meter min="0" max="20" value="'+Math.max(0,Math.min(20,Number(v)||0))+'"></meter> '+escape(v)+'/20</p>').join('')+'</details>'])):empty(wait);
 const shadows=Array.isArray(view.shadow_recent)?view.shadow_recent:[];
 $('v3-shadow').innerHTML=shadows.length?'<p>Concordância no recorte: '+escape(percent(view.agreement_recent))+' · '+shadows.length+' registros</p>'+table(['Horário','Par','Julgamento','Motivo'],shadows.slice(0,20).map(s=>[escape(date(s.timestamp_ms/1000)),escape(s.v3_signal?.symbol),escape(s.shadow_judgment?.action||s.status),escape(s.shadow_judgment?.reason||'Indisponível')])):empty('Nenhum julgamento shadow registrado.');
 $('v3-session').innerHTML=table(['Métrica','Valor'],[['Modo','PAPER / EXPERIMENTAL / OBSERVE ONLY'],['Cobertura recente neste processo',number(r.forward_observation_hours)+' h'],['48h de cobertura',r.observed_48h===true?'Registradas; ainda sem autorização':'Pendente'],['Revisão humana de dez sinais','Pendente'],['Carteira / PnL','Não aplicável: observador sem carteira'],['Execução','BLOQUEADA']]);
}

function renderSingleExitAudit(a){
 const el=$('single-exit-audit');if(!el)return;
 if(!a.baseline_reproduced){el.innerHTML=empty('Auditoria offline ainda não carregada.');return;}
 if(el.dataset&&el.dataset.runId===a.run_id)return;
 const money=v=>number(v==null?NaN:Number(v),6);
 const scenarios=Array.isArray(a.scenarios)?a.scenarios:[];
 el.innerHTML=scenarios.map(s=>'<h3>'+escape(s.name)+'</h3>'+table(['Saída','Ciclos','Referência USDT','Slippage + ticks','Taxas','Líquido USDT'],[...(s.by_exit_reason||[]),{reason:'TOTAL',...s.summary}].map(r=>[escape(r.reason),number(r.trades,0),money(r.reference_price_pnl),money(r.execution_impact),money(r.fees),money(r.net_pnl)]))+'<details><summary>Diário histórico: '+escape(s.summary?.trades)+' ciclos</summary>'+table(['Entrada UTC','Saída UTC','Motivo','Quantidade','Compra','Venda','Líquido USDT'],(s.trades||[]).map(t=>[escape(t.entry_utc),escape(t.exit_utc),escape(t.reason),escape(t.quantity),money(t.entry),money(t.exit),money(t.net_pnl)]))+'</details>').join('');
 if(el.dataset&&a.run_id)el.dataset.runId=a.run_id;
}

function renderResearchDesk(r){
 if(!$('research-desk-state'))return;
 $('research-desk-state').textContent=!r.scope?'Fluxo de pesquisa ainda não executado.':'Relatório salvo: '+date(r.updated_ms/1000)+' · '+String(r.mode)+' · Nenhuma estratégia promovida · sem agenda automática';
 $('research-desk-table').innerHTML=(r.evaluations||[]).length?table(['Hipótese','Estado','Retorno da amostra','Ciclos','OOS independente','Critérios pendentes'],r.evaluations.map(e=>[escape(e.title),escape(e.status),percent(e.metrics?.net_return),number(e.metrics?.closed_trades,0),'Não demonstrado',escape((e.checks||[]).filter(c=>c.passed!==true).map(c=>c.check).join(' · '))])):empty('Sem evidência de pesquisa carregada.');
 $('research-desk-brief').textContent=r.brief||'Sem resumo gerado.';
}

function renderUpgradePackage(data){
 if(!$('upgrade-package-status'))return;
 const r=data.upgrade_readiness||{},cost=data.paper12_feasibility||{},now=Date.now();
 const age=typeof r.updated_ms==='number'?now-r.updated_ms:null;
 $('upgrade-package-status').textContent=!r.scope?'Checklist de transição ainda não registrado.':
  'Checklist salvo em '+date(r.updated_ms/1000)+' · '+(age!==null&&age>=0&&age<60000?'leitura recente':'reavaliar antes de iniciar')+' · '+(r.ready_for_operator_review?'Pronto somente para revisão':'Há pendências')+' · sem ativação automática';
 $('upgrade-package-checks').innerHTML=(r.checks||[]).length?table(['Verificação','Resultado','Critério'],r.checks.map(c=>[escape(c.check),c.passed===true?'Atendida':'Pendente',escape(c.reason)])):empty('A sessão ativa permanece com suas regras originais.');
 const fresh=typeof cost.updated_ms==='number'&&now>=cost.updated_ms&&now-cost.updated_ms<1800000;
 $('upgrade-package-costs').innerHTML=(cost.pairs||[]).length?'<p>'+escape(fresh?'Consulta pública recente; preço salvo':'Consulta antiga; revalidar')+' · '+escape(date(cost.updated_ms/1000))+'</p>'+table(['Par','Mínimo USDT','Spread','Custo entrada','Perda estimada stop','RR líquido','Mecânica hipotética'],cost.pairs.map(p=>[escape(p.symbol),escape(p.min_notional),p.spread_fraction==null?'—':percent(Number(p.spread_fraction)),escape(p.entry_cost),escape(p.stop_loss_estimate),p.net_rr==null?'—':number(Number(p.net_rr)),p.mechanically_feasible===true?'Viável sob hipóteses':p.mechanically_feasible===false?escape(p.reason):'Dados indisponíveis'])):empty('Custos e filtros ainda não coletados.');
}

function renderSessionPerformance(s){
 const el=$('session-performance-report');if(!el)return;
 if(!s.available){el.innerHTML=empty('Relatório indisponível; resultado não confirmado.');return;}
 const c=s.coverage||{},money=v=>v==null?'—':number(Number(v),6)+' USDT';
 const hours=v=>typeof v==='number'?number(v/3600,2)+' h':'—';
 el.innerHTML=table(['Métrica da sessão','Valor'],[
 ['Patrimônio marcado',money(s.equity)],['Realizado líquido',money(s.realized)],
 ['Não realizado estimado líquido',money(s.unrealized_net)],['Taxas já descontadas',money(s.fees)],
 ['Retorno líquido',percent(s.net_return)],['Ciclos fechados',number(s.closed_cycles,0)],
 ['Win rate descritivo',percent(s.win_rate)],['Profit factor descritivo',number(s.profit_factor)],
 ['Sharpe / máximo drawdown','Não reconstruídos sem curva contínua'],
 ['Tempo decorrido no prazo',hours(c.elapsed_seconds)],['Tempo com amostras recentes',hours(c.recent_seconds)],
 ['Tempo parado observado',hours(c.stopped_seconds)],['Tempo desconhecido',hours(c.unknown_seconds)],
 ['Estado',escape(s.phase)],['Validação de vantagem','Amostra insuficiente; execução real bloqueada']]);
}

function renderOperationalAudit(a){
 if(!$('operational-audit-state'))return;
 const states={STOP:'STOP acionado',ENDED:'Prazo encerrado',ENGINE_UNCONFIRMED:'Motor sem confirmação recente',ENGINE_STOPPED:'Motor encerrado',SUPERVISOR_UNCONFIRMED:'Supervisor sem confirmação recente',RECENT_REPORTS:'Relatórios recentes do motor e supervisor'};
 const reasons={NO_ENTRY_SIGNAL:'Sem sinal de entrada',NO_CROSS:'Sem novo cruzamento',TREND_FILTER:'Tendência não permite entrada',ATR_FILTER:'Volatilidade fora da faixa',POSITION_OR_ORDER_EXISTS:'Posição ou reserva já existente',STALE_RADAR:'Radar sem confirmação recente',SESSION_ENDED:'Sessão encerrada',STOP:'STOP acionado',SIGNAL_EXIT:'Sinal de saída',STOP_LOSS:'Stop de perda',TAKE_PROFIT:'Alvo de lucro',RISK_EXIT:'Limite de risco',FEASIBLE_PREVIEW:'Prévia viável; não confirma ordem',MINIMUM_OR_NOTIONAL_FILTER:'Mínimo ou lote da exchange',WARMUP:'Indicadores em aquecimento'};
 const reason=v=>escape(reasons[v]||v||'Não registrado');
 const guard=a.external_guard||{},guardRecent=typeof guard.updated_ms==='number'&&Date.now()>=guard.updated_ms&&Date.now()-guard.updated_ms<90000;
 $('operational-audit-state').textContent=(states[a.state]||'Aguardando auditoria operacional')+' · Guardião externo: '+(guardRecent?String(guard.state):'sem confirmação recente');
 $('operational-audit-health').innerHTML=table(['Confirmação','Idade / valor'],[['Supervisor',a.controller_age_seconds==null?'—':number(a.controller_age_seconds,1)+' s'],['Motor',a.engine_age_seconds==null?'—':number(a.engine_age_seconds,1)+' s'],['Radar',a.radar_age_seconds==null?'—':number(a.radar_age_seconds,1)+' s'],['Auditoria das novas entradas',escape(a.entry_audit_health||'NOT_INSTRUMENTED')],['Ciclos completos no ledger',number(a.total_closed_cycles,0)],['Causa de interrupção sem encerramento',a.last_unexplained_gap?'Desconhecida':'Nenhuma no recorte']]);
 $('operational-audit-events').innerHTML=(a.recent_events||[]).length?table(['Horário','Evento','Componente','Código / motivo'],a.recent_events.slice().reverse().map(e=>[escape(date(e.time_ms/1000)),escape(e.kind),escape(e.component||'—'),escape(e.exit_code??e.reason??'—')])):empty('Sem eventos de disponibilidade registrados.');
 $('operational-audit-decisions').innerHTML=(a.decisions||[]).length?table(['Par','Ação do radar','Motivo do sinal','Contexto atual'],a.decisions.map(d=>[escape(d.symbol),escape(d.action||'—'),reason(d.signal_reason),reason(d.context_reason)])):empty('Sem avaliação reconciliada recente.');
 const entryProof=t=>t.entry_snapshot?'<details><summary>Sinal registrado antes da reserva</summary>'+table(['Fechamento do sinal','Preço fechado','EMA20 / EMA50 / EMA200','ATR'],[[escape(date(t.entry_snapshot.candle_close_ms/1000)),number(t.entry_snapshot.close,4),[t.entry_snapshot.ema_fast,t.entry_snapshot.ema_slow,t.entry_snapshot.ema_trend].map(v=>number(v,4)).join(' / '),percent(t.entry_snapshot.atr_fraction)]])+'</details>':'Indicadores não registrados na entrada';
 $('operational-audit-trades').innerHTML=(a.trades||[]).length?table(['Par','Compra','Venda','Motivo da venda','Taxas USDT','Líquido USDT','Evidência de entrada'],a.trades.slice().reverse().map(t=>[escape(t.symbol),escape(t.entry),escape(t.exit),reason(t.reason),number(Number(t.fees),6),number(Number(t.net_pnl),6),entryProof(t)])):empty(a.ledger_available?'Nenhum ciclo fechado registrado.':'Ledger indisponível; resultado desconhecido.');
}

function renderQuant(view){
 if(!$('quant-mode'))return;
 const r=view.report||{},review=view.review||{},pairs=Array.isArray(r.pairs)?r.pairs:[];
 const val=v=>typeof v==='number'&&Number.isFinite(v)?v:NaN;
 $('quant-mode').textContent=!view.available?'Aguardando o controle quantitativo...':(view.fresh?'Estado recente':'Sem confirmação recente')+' · '+String(r.reason||'UNKNOWN')+' · OBSERVE ONLY · IA desativada · 0 chamadas pagas';
 $('quant-state').innerHTML=pairs.length?table(['Par','Mid USDT','Spread bp','Imbalance L1','RV15m','DD','Perda diária','Bytes'],pairs.map(p=>{const n=p.snapshot?.numeric||{};return [escape(p.symbol),number(val(n.mid),4),number(val(n.spr)*10000,3),percent(val(n.imb)),percent(val(n.rv)),percent(val(n.dd)),percent(val(n.dl)),number(val(p.snapshot?.bytes),0)];})):empty('Nenhum estado numérico coletado.');
 const reasons={MODEL_STATE_FRESH:'Decisão anterior fora da validade',POSITION_LIMIT_CLEAR:'Posição ou reserva já existente',INVENTORY_UNDER_40_PERCENT:'Exposição excedida ou desconhecida',RISK_LEDGER_CLEAR:'Ledger de risco bloqueado ou desconhecido',STOP_CLEAR:'STOP acionado',FRESH_STATE:'Estado sem confirmação recente',DRAWDOWN_UNDER_10_PERCENT:'DD atingido ou desconhecido',DAILY_LOSS_UNDER_3_PERCENT:'Perda diária atingida ou desconhecida',SESSION_ACTIVE:'Sessão expirada, parada ou sem confirmação',HISTORICAL_EDGE_VALIDATED:'Vantagem histórica não validada',PROVIDER_CALIBRATED:'Provedor sem calibração medida',FLOW_VERIFIED:'Fluxo não verificado pelo L1',TOKEN_BUDGET_VERIFIED:'Contagem de tokens do provedor não verificada',VALID_TYPED_DECISION:'Sem decisão tipada de provedor',VALID_STATE:'Estado ou ledger indisponível'};
 $('quant-gates').innerHTML=pairs.length?table(['Par','Ação diagnóstica','Confiança','Bloqueios em código'],pairs.map(p=>[escape(p.symbol),escape(p.policy?.action),percent(val(p.policy?.confidence)),escape((p.policy?.gates_failed||[]).map(k=>reasons[k]||k).join(' · '))])):empty('Gates aguardando dados.');
 $('quant-review').innerHTML=review.scope?table(['Métrica','Valor'],[['Registros completos da sessão',number(val(review.completed),0)],['Fills no ledger',number(val(review.account?.fills),0)],['Previsões reais maduras',number(val(review.mature_labels),0)],['Brier',number(val(review.brier),5)],['Calibração',escape(review.calibration_status)],['Autoaplicar / ordens','DESATIVADOS']]):empty('Revisão ainda não produzida.');
}
