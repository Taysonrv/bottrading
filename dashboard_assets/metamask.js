/* Saved read-only reports and an isolated browser calculator. Never connects/signs. */
let mmReport={};
function renderMetamask(report){
 mmReport=report||{};
 const balances=mmReport.balances||{},quotes=mmReport.quotes||{},costs=mmReport.costs||{};
 $('mm-time').textContent=`Saldos: ${date(balances.created)} · cotações: ${date(quotes.created)} · simulação de rede: ${date(costs.created)}. Relatórios salvos; não são preços ao vivo.`;
 $('mm-balance').innerHTML=(balances.assets||[]).length?table(['Rede','Ativo','Saldo observado','Origem'],balances.assets.map(r=>[escape(r.network),escape(r.symbol),number(r.balance,8),escape(r.source||'RPC público')])):empty('Saldos ainda não importados.','Consultar endereços públicos não concede permissão de negociação.');
 $('mm-assets-count').textContent=number((balances.assets||[]).length,0);
 const legs=costs.legs||[],passed=legs.filter(r=>r.fee_lamports!=null&&!r.simulation_error&&!r.builder_error&&!r.error_type).length;
 $('mm-sim-count').textContent=`${passed} / ${legs.length}`;
 $('mm-real-orders').textContent='0';
 $('mm-profit').textContent='Não medido';
 $('mm-quotes').innerHTML=(quotes.results||[]).length?table(['Ativo vendido','Quantidade','Recebimento cotado','Recompra cotada','Diferença antes de gas'],quotes.results.map(r=>[escape(r.asset),number(r.input_tokens,4),`${number(r.sale_output,8)} ${escape(r.bridge_token)}`,number(r.repurchase_tokens,8),Number.isFinite(r.quote_loss_percent)?`−${number(r.quote_loss_percent,4)}%`:'—'])):empty('Nenhuma cotação salva.');
 $('mm-network-tests').innerHTML=legs.length?table(['Etapa','Estado','Taxa de mensagem SOL','Compute consumido','Diagnóstico'],legs.map(r=>[escape(r.leg),r.error_type?'Indisponível':r.simulation_error||r.builder_error?'Falhou':'Passou na simulação',number(Number.isFinite(r.fee_lamports)?r.fee_lamports/1e9:null,9),number(r.units_consumed,0),escape(r.diagnosis||r.error_type||((r.simulation_error||r.builder_error)?JSON.stringify(r.simulation_error||r.builder_error):'Sem erro retornado'))])):empty('Simulações de rede ainda não disponíveis.');
 $('mm-gas').innerHTML=(quotes.results||[]).flatMap(r=>(r.gas_sensitivity||[]).map(g=>`<p class="panel-note"><strong>${escape(r.asset)}</strong> · ${g.assumed_total_sol!=null?`${number(g.assumed_total_sol,6)} SOL → ${number(g.estimated_usdc,6)} USDC`:`${number(g.assumed_total_gas,0)} unidades de gas → ${number(g.estimated_bnb,8)} BNB`} · hipótese, não custo medido</p>`)).join('')||empty('Sem cenários de custo.');
 mmCalculate();
}
function mmCalculate(){
 const amount=Number($('mm-capital').value),move=Number($('mm-move').value),fee=Number($('mm-fee').value),gas=Number($('mm-gas-usd').value);
 if(![amount,move,fee,gas].every(Number.isFinite)||amount<=0||amount>100000||move<=-100||move>1000||fee<0||fee>=100||gas<0){$('mm-calc-result').textContent='Revise os valores: capital positivo, variação maior que −100% e custos não negativos.';return;}
 const after=amount*(1-fee/100)*(1+move/100)*(1-fee/100)-gas,pnl=after-amount;
 $('mm-calc-result').textContent=`Saldo hipotético: ${number(after,6)} USDC · resultado: ${number(pnl,6)} USDC · equilíbrio: alta de ${number(((amount+gas)/(amount*(1-fee/100)**2)-1)*100,4)}%. Não é backtest, cotação ou previsão.`;
 const cases=[-5,-2,0,2,5].map(v=>({v,p:amount*(1-fee/100)**2*(1+v/100)-gas-amount})),max=Math.max(...cases.map(r=>Math.abs(r.p)),.01);
 $('mm-scenario-chart').innerHTML=`<svg viewBox="0 0 620 250" role="img" aria-label="Resultado hipotético para cinco variações de preço"><path d="M45 110 H600" stroke="#64756b"/>${cases.map((r,i)=>{const x=65+i*110,h=Math.abs(r.p)/max*75,y=r.p>=0?110-h:110;return `<rect x="${x}" y="${y}" width="55" height="${Math.max(h,1)}" fill="${r.p>=0?'#b4f8cc':'#f19b93'}"/><text x="${x}" y="230" fill="#a4b6aa" font-size="12">${r.v}%</text><text x="${x}" y="${r.p>=0?y-8:y+h+16}" fill="#edf2ee" font-size="11">${number(r.p,3)}</text>`;}).join('')}</svg>`;
}
for(const id of ['mm-capital','mm-move','mm-fee','mm-gas-usd']) $(id).addEventListener('input',mmCalculate);

function metamaskChrome(){
 const active=!$('metamask').hidden,offline=!$('shadow').hidden;
 $('stop').hidden=active||offline;$('notice').hidden=active;
 document.querySelector('.page-heading .eyebrow').textContent=active?'METAMASK / LABORATÓRIO MULTIRREDE':'BINANCE SPOT / TRADING LAB';
 if(offline){$('process-help').hidden=true;$('updated').textContent=shadowViewState.saved_at?'Relatório offline salvo em '+date(shadowViewState.saved_at):'Relatório offline ainda não disponível';$('connection').textContent='⌘ V2 offline · sem execução';$('notice').textContent='DEMONSTRAÇÃO ARTIFICIAL. Esta tela não contém preços reais, compras ou previsões de lucro.';document.querySelector('.page-heading .eyebrow').textContent='V2 / FIXTURES LOCAIS';}
 if(active){$('process-help').hidden=true;$('updated').textContent='Carteira em leitura · testes sem assinatura · relatórios com horário próprio';$('connection').textContent='◇ MetaMask · relatórios salvos';}
}
