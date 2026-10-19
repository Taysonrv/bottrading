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
