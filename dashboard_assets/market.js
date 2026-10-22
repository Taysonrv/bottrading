let marketBusy=false,marketFetched=0,marketData=null;
function renderMarket(m){
 const asset=(labMarketState?.performance?.assets||[]).find(a=>a.symbol===m.symbol);
 const basis=asset?.quantity>0?asset.cost_basis/asset.quantity:null;
 const breakEven=basis===null?null:basis/((1-.001)*(1-.001));
 const candles=m.candles,first=candles[0].time,end=candles.at(-1).time+900;
 const trades=(labMarketState?.orders||[]).filter(o=>o.symbol===m.symbol&&o.time>=first&&o.time<=end);
 const references=[basis,breakEven,...trades.map(o=>o.price)].filter(Number.isFinite);
 const min=Math.min(...candles.map(c=>c.low),...references),max=Math.max(...candles.map(c=>c.high),...references),range=max-min||1;
 const x=t=>30+(t-first)/(end-first)*720,y=p=>30+(max-p)/range*220;
 const line=(price,color,label)=>price===null?'':`<path d="M30 ${y(price)} H750" stroke="${color}" stroke-dasharray="5 5"/><text x="755" y="${y(price)-3}" fill="${color}" font-size="10">${escape(label)} ${number(price)}</text>`;
 $('lab-candles').innerHTML=`<svg viewBox="0 0 930 295" role="img" aria-label="Candles de quinze minutos ${escape(m.symbol)}"><text x="30" y="15" fill="#a4b6aa" font-size="10">${number(max)} USDT</text>${candles.map(c=>{const cx=x(c.time+450),color=c.close>=c.open?'#b4f8cc':'#f19b93';return `<g opacity="${c.closed?1:.6}"><title>${escape(date(c.time))} · A ${number(c.open)} · M ${number(c.high)} · m ${number(c.low)} · F ${number(c.close)}${c.closed?'':' · Em formação'}</title><path d="M${cx} ${y(c.high)} V${y(c.low)}" stroke="${color}"/><rect x="${cx-3}" y="${Math.min(y(c.open),y(c.close))}" width="6" height="${Math.max(1,Math.abs(y(c.open)-y(c.close)))}" fill="${color}"/></g>`;}).join('')}${line(basis,'#8cbce8','Custo')}${line(breakEven,'#d4b983','Equilíbrio')}${trades.map(o=>`<g><title>${escape(o.side==='BUY'?'Compra simulada':'Venda simulada')} · ${escape(date(o.time))} · ${number(o.price)} USDT</title><circle cx="${x(o.time)}" cy="${y(o.price)}" r="5" fill="${o.side==='BUY'?'#b4f8cc':'#f19b93'}" stroke="#0c100f"/><text x="${x(o.time)+7}" y="${y(o.price)-7}" fill="#edf2ee" font-size="11">${o.side==='BUY'?'C':'V'}</text></g>`).join('')}<text x="30" y="275" fill="#a4b6aa" font-size="10">${escape(date(first))} → ${escape(date(end))}</text></svg>`;
 $('lab-exit-guide').innerHTML=table(['Referência de saída · não é ordem','Preço USDT'],[['Média atual de 200 dias fechados',number(m.sma200)],['Referência do próximo fechamento diário¹',number(m.next_close_reference)],['Bid estimado para empatar após custos²',number(breakEven)]]);
 $('lab-candle-time').textContent=`${m.symbol} · 15 minutos · consulta ${date(m.as_of)}. Último candle pode estar em formação. Próximo fechamento diário: ${date(m.next_daily_close)}.`;
}
async function refreshMarket(force=false){
 if($('app').hidden||!labMarketState?.started||marketBusy||(!force&&Date.now()-marketFetched<30000))return;
 marketBusy=true;const symbol=$('lab-market-symbol').value;
 try{const m=await api('/api/lab-market?symbol='+encodeURIComponent(symbol));if(symbol===$('lab-market-symbol').value){marketData=m;marketFetched=Date.now();renderMarket(m);$('lab-candle-error').textContent='';}}
 catch(e){$('lab-candle-error').textContent=e.message+' O gráfico anterior, se houver, conserva a data da última consulta.';marketFetched=Date.now();}
 finally{marketBusy=false;if(symbol!==$('lab-market-symbol').value)void refreshMarket(true);}
}
$('lab-market-symbol').addEventListener('change',()=>{marketData=null;$('lab-candles').innerHTML=empty('Carregando candles…');$('lab-exit-guide').innerHTML='';$('lab-candle-time').textContent='Consultando '+$('lab-market-symbol').value+'…';void refreshMarket(true);});
setInterval(()=>{if(marketData&&marketData.symbol===$('lab-market-symbol').value)renderMarket(marketData);void refreshMarket();},5000);

let liveCandleBusy=false,liveCandleFetched=0,liveCandleData=null,liveRequestedSymbol=null;
function renderLiveCandles(m){
 const s=live20MarketState,p=s?.position;
 if(!p||p.symbol!==m.symbol||!(p.units>0&&p.cost>0))return;
 const c=m.candles,first=c[0].time,end=c.at(-1).time+900;
 const breakEven=p.cost/p.units/(.999*.999),refs=[
  [breakEven,'#ffd078','Equilíbrio'],[breakEven*1.01,'#34e8ad','Alvo +1%'],[breakEven*.98,'#ff7ca8','Proteção −2%']];
 const orders=(s.orders||[]).filter(o=>o.symbol===m.symbol&&o.time>=first&&o.time<=end);
 const prices=[...c.flatMap(r=>[r.low,r.high]),...refs.map(r=>r[0]),...orders.map(o=>o.price)];
 const low=Math.min(...prices),high=Math.max(...prices),span=high-low||high*.01;
 const x=t=>30+(t-first)/(end-first)*700,y=v=>30+(high-v)/span*230;
 $('live20-candles').innerHTML=`<svg viewBox="0 0 950 310" role="img" aria-label="Candles ${escape(m.symbol)} com referências de saída"><text x="30" y="15" fill="#a0b1d0" font-size="11">${escape(m.symbol)} · ${number(high,8)} USDT</text>${[30,145,260].map(v=>`<path d="M30 ${v} H730" stroke="#2b3c5a" stroke-dasharray="3 5"/>`).join('')}${c.map(r=>{const cx=x(r.time+450),color=r.close>=r.open?'#34e8ad':'#ff7ca8';return `<g opacity="${r.closed?1:.55}"><title>${escape(date(r.time))} · A ${number(r.open,8)} · M ${number(r.high,8)} · m ${number(r.low,8)} · F ${number(r.close,8)}${r.closed?'':' · Em formação'}</title><path d="M${cx} ${y(r.high)} V${y(r.low)}" stroke="${color}"/><rect x="${cx-3}" y="${Math.min(y(r.open),y(r.close))}" width="6" height="${Math.max(1,Math.abs(y(r.open)-y(r.close)))}" fill="${color}"/></g>`;}).join('')}${refs.map(([v,color,label])=>`<path d="M30 ${y(v)} H730" stroke="${color}" stroke-dasharray="5 5"/><text x="740" y="${y(v)-5}" fill="${color}" font-size="11">${label} ${number(v,8)}</text>`).join('')}${orders.map(o=>`<g><title>${escape(date(o.time))} · ${o.side==='BUY'?'Compra':'Venda'} fictícia</title><circle cx="${x(o.time)}" cy="${y(o.price)}" r="5" fill="${o.side==='BUY'?'#22d3ee':'#ff7ca8'}"/><text x="${x(o.time)+7}" y="${y(o.price)-8}" fill="#f2f6ff" font-size="12">${o.side==='BUY'?'C':'V'}</text></g>`).join('')}<text x="30" y="288" fill="#a0b1d0" font-size="11">${escape(date(first))} → ${escape(date(end))}</text></svg>`;
 $('live20-candle-time').textContent=`${m.symbol} · consulta ${date(m.as_of)}${Date.now()/1000-m.as_of>=120?' · ATENÇÃO: CANDLES DESATUALIZADOS':''} · cotação visual independente da execução; atualização a cada 30 segundos.`;
}
async function refreshLiveCandles(){
 if($('app').hidden||$('live20').hidden)return;
 const symbol=live20MarketState?.position?.symbol;
 if(!symbol){liveRequestedSymbol=null;liveCandleFetched=0;liveCandleData=null;$('live20-candles').innerHTML=empty('Sem posição aberta.','Candles aparecerão quando houver uma compra fictícia.');$('live20-candle-time').textContent='';$('live20-candle-error').textContent='';return;}
 if(liveCandleData?.symbol!==symbol){liveCandleData=null;$('live20-candles').innerHTML=empty('Consultando candles de '+symbol+'…');$('live20-candle-time').textContent='';}
 if(liveRequestedSymbol!==symbol){liveRequestedSymbol=symbol;liveCandleFetched=0;}
 if(liveCandleData)renderLiveCandles(liveCandleData);
 if(liveCandleBusy||Date.now()-liveCandleFetched<30000)return;
 liveCandleBusy=true;
 try{const m=await api('/api/live-market?symbol='+encodeURIComponent(symbol));if(live20MarketState?.position?.symbol===symbol){liveCandleData=m;liveCandleFetched=Date.now();renderLiveCandles(m);$('live20-candle-error').textContent='';}}
 catch(e){$('live20-candle-error').textContent=e.message+' Confira a data da última consulta; candles anteriores podem estar desatualizados.';}
 finally{liveCandleFetched=Date.now();liveCandleBusy=false;}
}
setInterval(()=>void refreshLiveCandles(),5000);

// Operational visualization: independent of every signal, wallet and order.
let operationsState={},operationsCandles=null,operationsBusy=false,operationsAttempt=0;
let mapYaw=.65,mapPitch=-.35,mapDrag=null;
function mapFeatures(rows){
 const points=(rows||[]).filter(r=>r.status==='OK'&&[r.ema_fast,r.ema_slow,r.ema_trend,r.close,r.atr_fraction].every(v=>typeof v==='number'&&Number.isFinite(v))&&r.ema_slow>0&&r.ema_trend>0&&r.close>0&&r.atr_fraction>=0).map(r=>({symbol:r.symbol,action:r.action,raw:[r.ema_fast/r.ema_slow-1,r.close/r.ema_trend-1,r.atr_fraction]}));
 const scale=[0,1,2].map(i=>Math.max(1e-8,...points.map(p=>Math.abs(p.raw[i]))));
 return points.map(p=>({...p,xyz:p.raw.map((v,i)=>v/scale[i]*145)}));
}
function projectMap(xyz,yaw,pitch){
 const [x,y,z]=xyz,a=x*Math.cos(yaw)-z*Math.sin(yaw),b=x*Math.sin(yaw)+z*Math.cos(yaw);
 const c=y*Math.cos(pitch)-b*Math.sin(pitch),d=y*Math.sin(pitch)+b*Math.cos(pitch),zoom=650/(650+d);
 return {x:450+a*zoom,y:240-c*zoom,depth:d,zoom};
}
function drawOperationsMap(){
 const canvas=$('operations-map');if(!canvas||typeof canvas.getContext!=='function')return;
 const ctx=canvas.getContext('2d');if(!ctx)return;
 const m=operationsState.multipair||{},age=Date.now()-m.updated_ms,fresh=Number.isFinite(age)&&age>=0&&age<180000;
 ctx.clearRect(0,0,900,480);ctx.fillStyle='#100b1c';ctx.fillRect(0,0,900,480);
 const origin=projectMap([0,0,0],mapYaw,mapPitch);
 for(const [xyz,label,color] of [[[190,0,0],'X · EMA20/50','#9d8cff'],[[0,190,0],'Y · preço/EMA200','#53dbe5'],[[0,0,190],'Z · ATR/preço','#ed72ba']]){
   const p=projectMap(xyz,mapYaw,mapPitch);ctx.strokeStyle=color;ctx.globalAlpha=.6;ctx.beginPath();ctx.moveTo(origin.x,origin.y);ctx.lineTo(p.x,p.y);ctx.stroke();ctx.globalAlpha=1;ctx.fillStyle=color;ctx.font='14px sans-serif';ctx.fillText(label,p.x+8,p.y);
 }
 const points=mapFeatures(m.pairs).map(p=>({...p,...projectMap(p.xyz,mapYaw,mapPitch)})).sort((a,b)=>b.depth-a.depth);
 ctx.globalAlpha=fresh?1:.35;
 for(const p of points){
   const color=p.action==='ENTER_LONG'?'#50e5df':p.action==='EXIT_LONG'?'#ff76b7':'#af97f7';
   ctx.strokeStyle='#60506c';ctx.beginPath();ctx.moveTo(origin.x,origin.y);ctx.lineTo(p.x,p.y);ctx.stroke();
   ctx.shadowColor=color;ctx.shadowBlur=16;ctx.fillStyle=color;ctx.beginPath();ctx.arc(p.x,p.y,Math.max(4,9*p.zoom),0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;
   ctx.font='bold 15px sans-serif';ctx.fillText(String(p.symbol),p.x+14,p.y-8);
 }
 ctx.globalAlpha=1;
 $('operations-map-status').textContent=points.length?(fresh?'Dados recentes':'DADOS VENCIDOS · última amostra')+' · '+points.length+' pares · coleta '+date(m.updated_ms/1000):'Sem indicadores válidos para desenhar. Nenhum ponto artificial foi criado.';
}
function operationsChart(m,p){
 const candles=m.candles||[];if(candles.length<2)return empty('Sem candles válidos.');
 const position=p?.position?.symbol?.replace('/','')===m.symbol?p.position:null;
 const refs=position?[[Number(position.stop),'Stop sintético','#ff76b7'],[Number(position.take),'Alvo sintético','#50e5df']]:[];
 const values=[...candles.flatMap(c=>[c.low,c.high]),...refs.map(r=>r[0])];
 const low=Math.min(...values),high=Math.max(...values),span=high-low||high*.001;
 const first=candles[0].time,last=candles.at(-1).time+900,x=t=>40+(t-first)/(last-first)*740,y=v=>35+(high-v)/span*270;
 let svg='<svg viewBox="0 0 940 350" role="img" aria-label="Candles públicos 15 minutos '+escape(m.symbol)+'">';
 for(let i=0;i<4;i++){const price=high-span*i/3,py=y(price);svg+='<path d="M40 '+py+' H780" stroke="#49344c" stroke-dasharray="3 5"/><text x="790" y="'+py+'" fill="#c6b4cf" font-size="12">'+number(price,price<1?6:2)+'</text>';}
 for(const c of candles){const cx=x(c.time+450),color=c.close>=c.open?'#50e5df':'#ff76b7';svg+='<g opacity="'+(c.closed?1:.5)+'"><title>'+escape(date(c.time))+' · A '+number(c.open,6)+' · M '+number(c.high,6)+' · m '+number(c.low,6)+' · F '+number(c.close,6)+(c.closed?'':' · EM FORMAÇÃO')+'</title><path d="M'+cx+' '+y(c.high)+' V'+y(c.low)+'" stroke="'+color+'"/><rect x="'+(cx-4)+'" y="'+Math.min(y(c.open),y(c.close))+'" width="8" height="'+Math.max(1,Math.abs(y(c.open)-y(c.close)))+'" fill="'+color+'"/></g>';}
 for(const [price,label,color] of refs)svg+='<path d="M40 '+y(price)+' H780" stroke="'+color+'" stroke-dasharray="6 5"/><text x="45" y="'+(y(price)-6)+'" fill="'+color+'" font-size="12">'+label+' '+number(price,6)+'</text>';
 return svg+'<text x="40" y="335" fill="#c6b4cf" font-size="12">'+escape(date(first))+' → '+escape(date(last))+'</text></svg>';
}
async function refreshOperationsCandles(){
 if($('app').hidden||$('terminal').hidden||operationsBusy)return;
 const symbol=$('operations-symbol').value;
 if(operationsCandles?.symbol===symbol){
   $('operations-candles').innerHTML=operationsChart(operationsCandles,operationsState.portfolio);
   const age=Date.now()/1000-operationsCandles.as_of;
   $('operations-candle-status').textContent=symbol+' · consulta '+date(operationsCandles.as_of)+(age>=120||age<0?' · DADOS VENCIDOS':'')+' · último fechamento visual '+number(operationsCandles.candles.at(-1).close,6)+' USDT';
 }
 if(Date.now()-operationsAttempt<30000)return;
 operationsAttempt=Date.now();operationsBusy=true;
 try{
   const m=await api('/api/live-market?symbol='+encodeURIComponent(symbol));
   if(symbol===$('operations-symbol').value){operationsCandles=m;$('operations-candles').innerHTML=operationsChart(m,operationsState.portfolio);$('operations-candle-status').textContent=symbol+' · consulta '+date(m.as_of)+' · último candle pode estar em formação';}
 }catch{ $('operations-candle-status').textContent='Consulta indisponível. '+(operationsCandles?'Gráfico anterior preservado, consulta '+date(operationsCandles.as_of):'Sem candles salvos.')+' Não usado para execução.';}
 finally{operationsBusy=false;if(symbol!==$('operations-symbol').value){operationsAttempt=0;void refreshOperationsCandles();}}
}
function updateOperationsVisuals(data){operationsState=data;drawOperationsMap();void refreshOperationsCandles();}
$('operations-symbol').addEventListener('change',()=>{operationsAttempt=0;operationsCandles=null;$('operations-candle-status').textContent='Consultando '+$('operations-symbol').value+'…';$('operations-candles').innerHTML=empty('Consultando o par selecionado…');void refreshOperationsCandles();});
$('map-left').addEventListener('click',()=>{mapYaw-=.2;drawOperationsMap();});
$('map-right').addEventListener('click',()=>{mapYaw+=.2;drawOperationsMap();});
$('map-reset').addEventListener('click',()=>{mapYaw=.65;mapPitch=-.35;drawOperationsMap();});
const operationsCanvas=$('operations-map');
operationsCanvas.addEventListener('pointerdown',e=>{mapDrag=[e.clientX,e.clientY];operationsCanvas.setPointerCapture(e.pointerId);});
operationsCanvas.addEventListener('pointermove',e=>{if(!mapDrag)return;mapYaw+=(e.clientX-mapDrag[0])*.008;mapPitch=Math.max(-1.2,Math.min(1.2,mapPitch+(e.clientY-mapDrag[1])*.008));mapDrag=[e.clientX,e.clientY];drawOperationsMap();});
for(const event of ['pointerup','pointercancel','lostpointercapture'])operationsCanvas.addEventListener(event,()=>{mapDrag=null;});
setInterval(()=>void refreshOperationsCandles(),5000);
