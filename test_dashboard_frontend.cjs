const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{hidden:false,textContent:'',innerHTML:'',style:{},addEventListener(){}});return elements.get(id);}
const ctx={document:{getElementById:element,querySelectorAll:()=>[]},setInterval:()=>0,clearInterval(){},fetch:()=>new Promise(()=>{}),console};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(__dirname+'/dashboard_assets/app.js','utf8'),ctx);
const state={phase:'waiting',started:Date.now()/1000-60,updated:Date.now()/1000,end:Date.now()/1000+3600,initial:20,cash:20,equity:20,pnl:0,drawdown:0,realized:0,orders:[],curve:[]};
ctx.renderLive20(state,true);
assert.match(element('notice').textContent,/STOP acionado/);
assert.match(element('connection').textContent,/ordens bloqueadas/);
ctx.renderLive20({...state,halted:true});
assert.match(element('notice').textContent,/Drawdown travado/);
ctx.renderLive20({...state,updated:Date.now()/1000-200});
assert.match(element('notice').textContent,/Medição antiga/);
ctx.renderLive20(state);
assert.match(element('connection').textContent,/dados recentes/);
assert.doesNotMatch(element('notice').textContent,/STOP|Drawdown travado/);
console.log('OK: STOP, drawdown, stale readings and recovery in live panel.');

element('overview').hidden=false;
ctx.renderOverview20({...state,equity:19.8,pnl:-.2,orders:[{fee:.01}]});
assert.equal(element('equity').textContent,(19.8).toLocaleString('pt-BR',{minimumFractionDigits:4,maximumFractionDigits:4}));
assert.equal(element('orders').textContent,'1');
assert.equal(element('process-help').hidden,true);
assert.match(element('notice').textContent,/Resumo da simulação de 20 USDT/);
ctx.renderOverview20({...state,updated:Date.now()/1000-300});
assert.match(element('notice').textContent,/sem atualização recente/);
ctx.renderOverview20(state,true);
assert.match(element('notice').textContent,/STOP acionado/);
console.log('OK: overview uses live session, fees and stale/STOP status.');

ctx.renderSessionHealth({...state,orders:[{side:'SELL',symbol:'DOGEUSDT',quantity:62,price:.08,fee:.004,pnl:-.02,time:100,reason:'perda de tendência'}]},true);
assert.match(element('events').innerHTML,/Venda fictícia/);
assert.match(element('events').innerHTML,/perda de tendência/);
assert.match(element('live20-health').innerHTML,/STOP acionado/);
assert.equal(element('legacy-readiness').hidden,true);
ctx.renderSessionHealth({});
assert.equal(element('live20-diagnostic').hidden,true);
assert.equal(element('legacy-health').hidden,false);
console.log('OK: current-session activity and diagnostics, with legacy fallback.');

ctx.renderShadow({status:'missing'});
assert.match(element('shadow-status').textContent,/ainda não executada/);
ctx.renderShadow({status:'available',saved_at:100,action:'SHADOW_CANDIDATE',orders:0,requests_paid:0,symbol:'BTCUSDT',features:{mid:100}});
assert.match(element('shadow-summary').innerHTML,/Fixture aceita/);
assert.match(element('shadow-status').textContent,/artificial/);
assert.match(element('shadow-summary').innerHTML,/Não realizada/);
console.log('OK: offline V2 remains explicitly artificial.');

element('ema').hidden=false;
ctx.renderEma({available:true,phase:'RUNNING',fresh:true,updated:Date.now()/1000,end:Date.now()/1000+3600,capital:20,equity:20,pnl:0,realized:0,reserved:0,cash:20,units:0,fees:0,buy_fills:0,sell_fills:0,last_signal:'WARMUP_REPLAYED',reason:'NO_FILL',orders:[],fills:[]});
assert.match(element('ema-cards').innerHTML,/20,000000/);
assert.match(element('ema-orders').innerHTML,/Nenhuma ordem solicitada/);
assert.match(element('ema-signal').textContent,/Indicadores aquecidos/);
assert.match(element('ema-fills-pie').innerHTML,/Zero compras/);
ctx.renderEma({available:true,phase:'STOPPED',fresh:false,stop:true,cash:20,reserved:0,units:0,orders:[],fills:[],buy_fills:0,sell_fills:0});
assert.match(element('ema-status').textContent,/STOP acionado/);
assert.doesNotMatch(element('connection').textContent,/dados recentes/);
ctx.renderEma({available:false,status:'invalid'});
assert.match(element('ema-cards').innerHTML,/Sem dados disponíveis/);
console.log('OK: EMA live panel, real zeros, empty orders, STOP and invalid state.');

ctx.renderEmaDiagnosis({available:true,phase:'RUNNING',fresh:true,updated:Date.now()/1000,age_seconds:5,last_signal:'HOLD:NO_CROSS',stop:false,cash:20,reserved:0,units:0,orders:[],risk:{available:true,updated:Date.now()/1000,daily_loss:0,drawdown:0,daily_halted:false,drawdown_halted:false}});
assert.match(element('ema-health').innerHTML,/Aguardando cruzamento/);
assert.match(element('ema-health').innerHTML,/Dados recentes/);
ctx.renderEmaDiagnosis({available:true,phase:'STOPPED',fresh:false,orders:[],risk:{available:false}});
assert.match(element('ema-health').innerHTML,/Sessão encerrada/);
assert.match(element('ema-health').innerHTML,/Checkpoint indisponível/);
console.log('OK: EMA diagnostics distinguish waiting signals and unknown risk checkpoints.');
const watchFresh={updated_ms:Date.now(),timeframe:'15m',pairs:Array.from({length:6},()=>({status:'OK'}))};
ctx.renderEmaDiagnosis({available:false},watchFresh);
assert.match(element('ema-health').innerHTML,/Seis pares com dados recentes/);
ctx.renderEmaDiagnosis({available:false},{...watchFresh,updated_ms:Date.now()-600000});
assert.doesNotMatch(element('ema-health').innerHTML,/Seis pares com dados recentes/);
ctx.renderSessionHealth({...state,updated:Date.now()/1000-86400});
assert.match(element('live20-health').innerHTML,/Coleta da simulação anterior/);
assert.match(element('live20-health').innerHTML,/não representa a coleta EMA/);
console.log('OK: old simulation collection is distinct from fresh/stale multipair collection.');
ctx.renderSpotResearch({reports:[]});
assert.match(element('spot-research-results').innerHTML,/Relatórios não encontrados/);
ctx.renderSpotResearch({reports:[{symbol:'BTC/USDT',timeframe:'1h',source:'Pesquisa local',saved:100,rows:[{scenario:'base',start_ms:1000,end_ms:2000,net_return:-.04,buy_hold_return:.16,max_drawdown:.05,closed_trades:32,win_rate:.2,profit_factor:.6,sharpe_zero_rf:-1}]}]});
assert.match(element('spot-research-status').textContent,/sem aprovação/);
assert.match(element('spot-research-results').innerHTML,/BTC\/USDT/);
assert.match(element('spot-research-results').innerHTML,/-4/);
console.log('OK: research shows negative results and explicit missing reports.');
assert.match(ctx.renderResearchJournal({available:false}),/integridade inválida/);
const journalHtml=ctx.renderResearchJournal({available:true,groups:[{scenario:'fixed_base',count:1,net:-.2,gross:0,fees:.1,slippage:.1,reasons:{STOP:1},trades:[{window:1,entry_ms:1000,exit_ms:2000,entry:100,exit_price:99,quantity:1,reason:'STOP',gross_pnl:0,fees:.1,slippage_cost:.1,net_pnl:-.2}]}]});
assert.match(journalHtml,/Diário histórico verificado/);
assert.match(journalHtml,/<details>/);
assert.match(journalHtml,/Stop/);
console.log('OK: historical journal shows costs, reasons and integrity failures.');
ctx.renderKronos({available:false,status:'missing'});
assert.match(element('kronos-status').textContent,/sem previsão registrada/);
ctx.renderKronos({available:true,issued_ms:3601000,cutoff_ms:3600000,samples:2,horizon:2,anchor_close:100,paths:[[100,101],[102,103]],bands:[{p50:101},{p50:102}]});
assert.match(element('kronos-status').textContent,/2 trajetórias separadas/);
assert.match(element('kronos-paths').innerHTML,/não preços observados/);
assert.match(element('kronos-paths').innerHTML,/<svg/);
console.log('OK: Kronos forecasts remain separate from observed prices and trading.');
const terminalState={ema:{available:true,phase:'RUNNING',fresh:false,last_signal:'HOLD:NO_CROSS',capital:20,equity:20,pnl:0,realized:0,cash:20,reserved:0,units:0,fees:0,buy_fills:0,sell_fills:0,orders:[],fills:[],updated:100,risk:{available:false}},multipair:{updated_ms:100000,timeframe:'15m',pairs:[{symbol:'BTC/USDT',close:100,status:'OK',action:'HOLD',reason:'NO_CROSS'}]},kronos_lab:{available:false}};
ctx.renderTerminal(terminalState);
assert.match(element('term-metrics').innerHTML,/20,0000 USDT/);
assert.match(element('term-pipeline').innerHTML,/Coleta sem confirmação/);
assert.match(element('term-pipeline').innerHTML,/Risco sem leitura recente/);
assert.match(element('term-orders').innerHTML,/Nenhuma ordem registrada/);
assert.match(element('term-chart').innerHTML,/Aguardando candles verificados/);
assert.doesNotMatch(element('term-radar-state').textContent,/^COLETA RECENTE$/);
const chart=ctx.terminalChart({available:true,horizon:2,paths:[[103,104]],bands:[{p50:103},{p50:104}],candles:[{time_ms:3600000,open:100,high:102,low:99,close:101},{time_ms:7200000,open:101,high:103,low:100,close:102}]},{});
assert.match(chart,/Candles reais registrados e futuros simulados/);
assert.match(chart,/Previsão/);
assert.doesNotMatch(chart,/NaN|Infinity/);
console.log('OK: terminal preserves real zeros, stale state and observed/forecast separation.');

ctx.renderSystemIntegration({controller:{fresh:false},execution:{fresh:false},market:{fresh:false}});
assert.match(element('term-system').textContent,/sem atividade confirmada/);
assert.match(element('term-system').textContent,/estado próprio/);
ctx.renderSystemIntegration({controller:{fresh:true},execution:{fresh:true},market:{fresh:true}});
assert.match(element('term-system').textContent,/iniciador único ativo/);
console.log('OK: central integration scope and stale controller.');

ctx.renderPortfolio({available:true,fresh:false,phase:'STOPPED',cash:'20',capital:'20',reserved:'0',equity:null,fees:'0',realized:'0',orders:[],fills:[]});
assert.match(element('portfolio-status').textContent,/Sem atualização recente/);
assert.match(element('portfolio-wallet').innerHTML,/20,000000/);
assert.match(element('portfolio-fills').innerHTML,/Nenhum preenchimento/);

ctx.renderTerminal({system:{controller:{engine:'portfolio'}},portfolio:{available:true,fresh:true,capital:'20',cash:'20',reserved:'0',equity:'20',fees:'0',realized:'0',drawdown:'0',updated:Date.now()/1000,orders:[],fills:[],reason:'WAITING_SIGNAL'},multipair:{},kronos_lab:{}});
assert.match(element('term-metrics').innerHTML,/20,0000 USDT/);
assert.match(element('notice').textContent,/Saldo compartilhado fictício/);
assert.match(element('connection').textContent,/Multipar/);
console.log('OK: terminal switches to active shared wallet without summing EMA.');

element('diagnosis').hidden=false;
ctx.renderLaunchHelp({system:{execution:{fresh:true},controller:{fresh:true}}});
assert.equal(element('process-help').hidden,true);
ctx.renderLaunchHelp({system:{execution:{fresh:false,reason:'STOP'}},portfolio:{}});
assert.equal(element('process-help').hidden,false);
assert.equal(element('process-command').hidden,true);
ctx.renderLaunchHelp({system:{execution:{fresh:false,reason:'NO_REPORT'}},portfolio:{}});
assert.equal(element('process-command').hidden,false);
element('diagnosis').hidden=true;
ctx.renderLaunchHelp({system:{execution:{fresh:false}}});
assert.equal(element('process-help').hidden,true);
console.log('OK: startup guidance uses current motor and respects active/STOP state.');

const enow=Date.now(),emarket={updated_ms:enow},erow={status:'OK',symbol:'BTC/USDT',reason:'NO_CROSS',action:'HOLD'};
assert.match(ctx.entryExplanation(erow,emarket,{}, {},false,enow),/novo cruzamento/);
assert.match(ctx.entryExplanation(erow,{updated_ms:enow-200000},{}, {},false,enow),/sem leitura recente/);
assert.match(ctx.entryExplanation(erow,emarket,{pending:{symbol:'ETH/USDT'}},{},false,enow),/Saldo reservado para ETH/);
assert.match(ctx.entryExplanation(erow,emarket,{halt:'DAILY_LOSS'},{},false,enow),/DAILY_LOSS/);
assert.match(ctx.entryExplanation({...erow,action:'ENTER_LONG',candle_close_ms:enow-130000},emarket,{}, {},false,enow),/fora da janela/);
assert.match(ctx.entryExplanation({...erow,action:'ENTER_LONG',candle_close_ms:enow},emarket,{}, {controller:{engine:'portfolio'},execution:{fresh:true}},false,enow),/precisam de confirmação/);
ctx.renderEntryDiagnostics({multipair:{updated_ms:enow,timeframe:'15m',pairs:[{...erow,ema_fast:101,ema_slow:100,close:102,ema_trend:99,atr_fraction:.002,candle_close_ms:enow}]}});
assert.match(element('entry-checks').innerHTML,/EMA20 acima/);
assert.match(element('entry-checks').innerHTML,/novo cruzamento/);
console.log('OK: entry explanations distinguish missing data, pending cash and unconfirmed signals.');

const perfFills=[{side:'BUY',symbol:'BTC/USDT',quantity:'1',price:'100',fee:'.1',time_ms:1000},{side:'SELL',symbol:'BTC/USDT',quantity:'1',price:'102',fee:'.102',time_ms:61000}];
const perf=ctx.portfolioPerformance({fills:perfFills,buy_fills:1,sell_fills:1});
assert.equal(perf.winRate,1);assert.equal(perf.averageMinutes,1);assert.equal(perf.profitFactor,null);
assert.equal(ctx.portfolioPerformance({fills:perfFills,buy_fills:2,sell_fills:2}).complete,false);
assert.equal(ctx.portfolioPerformance({fills:[],buy_fills:0,sell_fills:0}).winRate,null);
ctx.renderPortfolioPerformance({available:true,equity:null,capital:'20',realized:'0',fees:'0',fills:[],buy_fills:0,sell_fills:0});
assert.match(element('portfolio-performance').innerHTML,/Sem amostra completa/);
assert.doesNotMatch(element('portfolio-performance').innerHTML,/NaN|Infinity/);
console.log('OK: performance distinguishes missing marks, open inventory and incomplete history.');

ctx.renderExternalContext({});
assert.match(element('external-context').innerHTML,/NOT_COLLECTED/);
ctx.renderExternalContext({sources:{alternative:{status:'OK',fetched_ms:Date.now(),data:{value:0,source_ms:Date.now()}}}});
assert.match(element('external-context').innerHTML,/>0<\/td>/);
ctx.renderExternalContext({sources:{geckoterminal:{status:'PARTIAL',fetched_ms:Date.now(),data:{networks:{solana:'RATE_LIMITED'},pools:[{network:'bsc',name:'<img>',liquidity_usd:10,volume_24h_usd:1}]}}}});
assert.match(element('external-context').innerHTML,/RATE_LIMITED/);
assert.doesNotMatch(element('external-context').innerHTML,/<img>/);
console.log('OK: external context preserves zero, freshness and partial-provider failures.');
vm.runInContext(fs.readFileSync(__dirname+'/dashboard_assets/market.js','utf8'),ctx);
const points=ctx.mapFeatures([{symbol:'BTC/USDT',status:'OK',action:'HOLD',ema_fast:101,ema_slow:100,ema_trend:99,close:102,atr_fraction:.002},{symbol:'BAD',status:'OK',ema_fast:NaN}]);
assert.equal(points.length,1);assert.equal(points[0].symbol,'BTC/USDT');
const projected=ctx.projectMap(points[0].xyz,.6,-.3);
assert.ok(Number.isFinite(projected.x)&&Number.isFinite(projected.y));
assert.equal(ctx.mapFeatures([]).length,0);
const candleSvg=ctx.operationsChart({symbol:'BTCUSDT',candles:[{time:1000,open:100,high:102,low:99,close:101,closed:true},{time:1900,open:101,high:103,low:100,close:102,closed:false}]},{position:{symbol:'BTC/USDT',stop:'98',take:'104'}});
assert.match(candleSvg,/Stop sintético/);assert.match(candleSvg,/EM FORMAÇÃO/);assert.doesNotMatch(candleSvg,/NaN|Infinity/);
const otherPairSvg=ctx.operationsChart({symbol:'ETHUSDT',candles:[{time:1000,open:100,high:102,low:99,close:101},{time:1900,open:101,high:103,low:100,close:102}]},{position:{symbol:'BTC/USDT',stop:'98',take:'104'}});
assert.doesNotMatch(otherPairSvg,/Stop sintético/);
console.log('OK: 3D features use valid data and chart protection matches selected pair.');

ctx.renderOperationHealth({});assert.match(element('operation-health').innerHTML,/sem medições/);
ctx.renderOperationHealth({version:1,updated:Date.now()/1000-100,started:Date.now()/1000-1000,recent_seconds:60,stopped_seconds:0,unknown_seconds:940,last_gap_seconds:940,state:'RECENT'});
assert.match(element('operation-health').innerHTML,/SEM ATUALIZAÇÃO RECENTE/);
assert.match(element('operation-health').innerHTML,/15,7 min/);
console.log('OK: availability keeps sampling gaps unknown and marks stale monitors.');

element('research').hidden=true;element('diagnosis').hidden=false;
ctx.renderLaunchHelp({system:{execution:{fresh:true,timeframe:'15m'},controller:{engine:'portfolio'}}});
assert.match(element('heading').textContent,/operação atual/);
assert.doesNotMatch(element('notice').textContent,/Diagnóstico da sessão EMA/);
ctx.renderExternalContext({sources:{geckoterminal:{status:'PARTIAL',fetched_ms:Date.now(),data:{networks:{bsc:'OK',solana:'UNAVAILABLE'},pools:[]}}}});
assert.match(element('external-context').innerHTML,/Cobertura parcial/);
assert.doesNotMatch(element('external-context').innerHTML,/Último dado salvo abaixo/);
console.log('OK: current diagnostics override legacy state and partial coverage is not stale data.');

ctx.renderSystemIntegration({controller:{engine:'portfolio',fresh:false,age_seconds:125},execution:{fresh:true,symbol:'SHARED_6_PAIRS',timeframe:'15m'},market:{fresh:false,age_seconds:null}});
assert.match(element('operation-summary').innerHTML,/Sem confirma/);
assert.match(element('operation-summary').innerHTML,/indispon/);
assert.match(element('operation-summary').innerHTML,/PAPER/);
ctx.renderPortfolio({available:true,fresh:true,capital:'20',cash:'14',position:{symbol:'BTC/USDT',quantity:'.0001',stop:'50000',take:'60000',exit_request:{reason:'STOP_LOSS'}}});
assert.match(element('portfolio-position').innerHTML,/STOP_LOSS/);
assert.match(element('portfolio-position').innerHTML,/sint/);
console.log('OK: operational summary separates stale services and displays requested synthetic exits.');

ctx.renderTerminal({system:{controller:{engine:'portfolio'}},portfolio:{available:true,fresh:true,cash:'14',equity:'20',position:{symbol:'BTC/USDT',quantity:'.0001',exit_request:{reason:'STOP_LOSS'}}},multipair:{}});
assert.match(element('term-pipeline').innerHTML,/Saída sintética solicitada/);
console.log('OK: pending synthetic exit is visible in the execution pipeline.');

const premiumData={portfolio:{available:true,capital:'20',cash:'20',equity:'20',fills:[],buy_fills:0,sell_fills:0},multipair:{updated_ms:Date.now(),pairs:[{symbol:'BTC/USDT',status:'OK',action:'HOLD',close:60000,candle_close_ms:Date.now()-120000}]}};
ctx.renderPremium(premiumData);
assert.match(element('premium-metrics').innerHTML,/Série de retornos ainda indisponível/);
assert.match(element('premium-pairs').innerHTML,/Aguardando 2 candles/);
ctx.renderPremium(premiumData);
assert.doesNotMatch(element('premium-pairs').innerHTML,/<polyline/);
premiumData.multipair.pairs[0].candle_close_ms+=60000;
premiumData.multipair.pairs[0].close=60100;
ctx.renderPremium(premiumData);
assert.match(element('premium-pairs').innerHTML,/<polyline/);
premiumData.multipair.updated_ms=Date.now()-400000;
ctx.renderPremium(premiumData);
assert.match(element('premium-heatmap').innerHTML,/Sem confirmação/);
console.log('OK: premium panels do not invent metrics, duplicate candles or stale signals.');

assert.ok(perf.averageWin>0);assert.equal(perf.maxWinStreak,1);assert.equal(perf.maxLossStreak,0);assert.equal(perf.byPair[0].count,1);
assert.equal(ctx.portfolioPerformance({fills:[...perfFills,{...perfFills[0],time_ms:0}],buy_fills:2,sell_fills:1}).complete,false);
const csv=ctx.journalCsv([{time:1000,kind:'Ordem',symbol:'=FORMULA()',side:'BUY',state:'NEW',reason:'a,"b',price:'1',quantity:'2',fee:null}]);
assert.match(csv,/1970-01-01T00:00:01.000Z/);assert.match(csv,/'=FORMULA/);assert.match(csv,/a,""b/);
element('trade-search').value='ETH';
assert.equal(ctx.filteredJournal({orders:[{symbol:'BTC/USDT'},{symbol:'ETH/USDT'}]}).length,1);
element('trade-search').value='';
console.log('OK: journal filtering, CSV escaping and complete-history statistics.');

const decisionData={system:{controller:{engine:'portfolio'},execution:{end_ms:Date.now()+60000}},portfolio:{available:true,fresh:true,updated:Date.now()/1000,orders:[{created_ms:1000,symbol:'BNB/USDT',status:'CANCELED',reason:'EXPIRED'}]},multipair:{updated_ms:Date.now(),pairs:['BTC','ETH','SOL','BNB','XRP','DOGE'].map(x=>({symbol:x+'/USDT',status:'OK',action:'HOLD'}))}};
let decision=ctx.decisionSnapshot(decisionData);assert.equal(decision.state,'WAITING');assert.equal(decision.counts.canceled,1);assert.equal(decision.intentions,0);
assert.equal(ctx.decisionSnapshot({...decisionData,portfolio:{...decisionData.portfolio,pending:{symbol:'BNB/USDT'}}}).state,'ENTRY_PENDING');
assert.equal(ctx.decisionSnapshot({...decisionData,portfolio:{...decisionData.portfolio,position:{exit_request:{reason:'STOP_LOSS'}}}}).state,'EXIT_PENDING');
assert.equal(ctx.decisionSnapshot({...decisionData,portfolio:{...decisionData.portfolio,reason:'STOP',fresh:false}}).state,'STOP');
assert.equal(ctx.decisionSnapshot({...decisionData,portfolio:{...decisionData.portfolio,updated:Date.now()/1000-120}}).state,'STALE');
assert.equal(ctx.decisionSnapshot({...decisionData,multipair:{...decisionData.multipair,pairs:[]}}).intentions,null);
assert.equal(ctx.decisionSnapshot({...decisionData,portfolio:{available:false}}).counts,null);
ctx.renderDecisionAudit(decisionData);assert.match(element('decision-orders').innerHTML,/Expirada sem preenchimento/);assert.doesNotMatch(element('decision-orders').innerHTML,/liquidez insuficiente/);
console.log('OK: decision audit distinguishes expired, pending, stale, STOP and incomplete radar.');
ctx.renderV3({});assert.match(element('v3-health').textContent,/Aguardando/);
ctx.renderV3({available:true,fresh:false,report:{updated_ms:Date.now()-100000,reason:'DATA_UNAVAILABLE',
  signals:[{symbol:'<script>',regime:'CRISIS',score:0,action:'HOLD',reason:'GATES',timestamp_ms:1000,components:{momentum:0}}]}});
assert.match(element('v3-health').textContent,/Sem confirmação/);
assert.match(element('v3-signals').innerHTML,/&lt;script&gt;/);assert.doesNotMatch(element('v3-signals').innerHTML,/<script>/);
assert.match(element('v3-session').innerHTML,/BLOQUEADA/);assert.match(element('v3-session').innerHTML,/observador sem carteira/);
console.log('OK: V3 uses same polling, escapes data, marks stale readings and never invents a wallet.');
ctx.renderV3({feasibility:{updated_ms:Date.now(),pairs:[{symbol:'BTC/USDT',actual_score:0,
 normalized_rules:{min_notional:'5'},minimum_aggregate_stop_notional:'15',cap_precludes_three_stop_legs:true,
 strategy_score_plan:{reason:'SCORE_TOO_LOW'},hypothetical_perfect_score_plan:{reason:'ATR_RANGE'}}]},
 backtest:{scope:'V3_COUNTERFACTUAL_CONSTANT_FILTER_CANDLE_MODEL',symbol:'BTC/USDT',candidate_count:2,closed_trades:0,net_return:0,
 rejected_candidates:{PARTIAL_EXIT_FILTER:2},verdict:'NO_TRADES_NOT_VALIDATED'}});
assert.match(element('v3-feasibility').innerHTML,/SCORE_TOO_LOW/);assert.match(element('v3-feasibility').innerHTML,/ATR_RANGE/);
assert.match(element('v3-backtest').innerHTML,/NO_TRADES_NOT_VALIDATED/);assert.match(element('v3-backtest').innerHTML,/BLOQUEADA/);
console.log('OK: V3 separates current signals, hypothetical feasibility and zero-trade research results.');
ctx.renderV3({single_exit:{scope:'SINGLE_EXIT_FIXED_HYPOTHESIS_RESEARCH',verdict:'REJECTED',
 scenarios:[{name:'base',continuous:{final_equity:'18.12',net_return:-.094,closed_trades:55,profit_factor:.51,max_drawdown:.097},
 windows:[{net_return:-.02},{net_return:-.05},{net_return:-.01},{net_return:-.07}]}]}});
assert.match(element('single-exit-research').innerHTML,/REJECTED/);
assert.match(element('single-exit-research').innerHTML,/55/);assert.match(element('single-exit-research').innerHTML,/BLOQUEADA/);
console.log('OK: single-exit losses are research only and never displayed as active wallet equity.');
ctx.renderQuant({});assert.match(element('quant-mode').textContent,/Aguardando/);
ctx.renderQuant({available:true,fresh:true,report:{reason:'OBSERVING',pairs:[{symbol:'BTC/USDT',status:'OK',
 snapshot:{numeric:{mid:100,spr:0,imb:0,rv:0,dd:0,dl:null},bytes:220},
 policy:{action:'REVIEW_REQUIRED',confidence:null,gates_failed:['SESSION_ACTIVE','PROVIDER_CALIBRATED']}}]},
 review:{scope:'FULL_SESSION_RESEARCH_REVIEW',completed:4,account:{fills:0},mature_labels:0,brier:null,calibration_status:'UNMEASURED_NO_REAL_PROVIDER'}});
assert.match(element('quant-mode').textContent,/IA desativada/);assert.match(element('quant-gates').innerHTML,/Sessão expirada/);
assert.match(element('quant-gates').innerHTML,/—/);assert.match(element('quant-review').innerHTML,/UNMEASURED/);
assert.match(element('quant-review').innerHTML,/DESATIVADOS/);
console.log('OK: quantitative control keeps real zeros, unknown confidence/Brier and execution gates distinct.');
ctx.renderSingleExitAudit({});assert.match(element('single-exit-audit').innerHTML,/ainda não carregada/);
ctx.renderSingleExitAudit({baseline_reproduced:true,run_id:'unit',scenarios:[{name:'<base>',summary:{trades:55,net_pnl:'-1.8795837367'},by_exit_reason:[{reason:'STOP',trades:25,net_pnl:'-3.2522595656'}],trades:[{entry_utc:'<script>',reason:'STOP',quantity:'0.001',net_pnl:'-0.13'}]}]});
assert.match(element('single-exit-audit').innerHTML,/55/);
assert.match(element('single-exit-audit').innerHTML,/Diário histórico/);
assert.ok(!element('single-exit-audit').innerHTML.includes('<script>'));
console.log('OK: offline audit journal renders losses and escapes external text.');
ctx.renderOperationalAudit({state:'ENGINE_UNCONFIRMED',engine_age_seconds:120,ledger_available:false,recent_events:[{kind:'<script>',exit_code:0,time_ms:1000}]});
assert.match(element('operational-audit-state').textContent,/sem confirmação/);
assert.ok(!element('operational-audit-events').innerHTML.includes('<script>'));
assert.match(element('operational-audit-trades').innerHTML,/desconhecido/);
ctx.renderOperationalAudit({state:'RECENT_REPORTS',engine_age_seconds:0,controller_age_seconds:0,ledger_available:true,total_closed_cycles:1,trades:[{symbol:'SOL/USDT',entry:'101.99',exit:'100',reason:'SIGNAL_EXIT',fees:'0.01171542',net_pnl:'-0.12713542'}]});
assert.match(element('operational-audit-trades').innerHTML,/Sinal de saída/);
assert.match(element('operational-audit-trades').innerHTML,/-0[,.]127135/);
console.log('OK: operational audit separates stale evidence, unknown results, realized losses and actual exit reasons.');
ctx.renderSessionPerformance({available:false});assert.match(element('session-performance-report').innerHTML,/não confirmado/);
ctx.renderSessionPerformance({available:true,equity:'19.87286458',realized:'-0.12713542',fees:'0.01171542',closed_cycles:1,coverage:{elapsed_seconds:100,recent_seconds:40,stopped_seconds:0,unknown_seconds:60}});
assert.match(element('session-performance-report').innerHTML,/Tempo desconhecido/);
assert.match(element('session-performance-report').innerHTML,/-0[,.]127135/);
assert.match(element('session-performance-report').innerHTML,/Amostra insuficiente/);
console.log('OK: complete session performance keeps unknown coverage and insufficient evidence explicit.');
ctx.renderOperationalAudit({state:'RECENT_REPORTS',ledger_available:true,trades:[{symbol:'LINK/USDT',reason:'TAKE_PROFIT',fees:'0.01',net_pnl:'0.1',entry_snapshot:{candle_close_ms:1000,close:100,ema_fast:99,ema_slow:98,ema_trend:97,atr_fraction:.01}}]});
assert.match(element('operational-audit-trades').innerHTML,/Sinal registrado antes da reserva/);
assert.match(element('operational-audit-trades').innerHTML,/EMA20/);
console.log('OK: historical entry evidence is displayed only when actually recorded.');
