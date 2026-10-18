# Capital fictício e análise do guia Binance

Capital de referência adotado: **1.000 USDT fictícios**, sem usar saldo da conta. É a mesma base efetivamente usada nos experimentos diário e Grid já executados. Esta revisão converte os resultados salvos em USDT; não é um novo backtest nem uma recomendação de depósito real.

| Limite | Percentual do patrimônio | Valor no início |
|---|---:|---:|
| Por ordem, incluindo orçamento de custos | 5% | 50 USDT |
| Por ativo | 20% | 200 USDT |
| Total configurado | 60% | 600 USDT |
| Total efetivo com somente BTC/ETH | 40% | 400 USDT |
| Caixa após ocupar ambos os limites, aproximadamente | 60% | 600 USDT |
| Gatilho de drawdown desde o pico | 15% | 150 USDT se o pico for 1.000 |

Limites variam com o patrimônio. Não se dividem 1.000 USDT igualmente entre BTC/ETH: cada ativo pode usar até 200 USDT inicialmente. O benchmark principal 50/50 usa 100% investido; a referência com exposição proporcional também aparece nos JSONs. Não se deve esconder essa diferença ao comparar retornos.

O gatilho não garante perda limitada a 150 USDT: posições, gaps e execução gradual podem levar a perda maior. O mínimo de 10 USDT usado na pesquisa é uma aproximação, não confirmação dos filtros atuais de cada par na Binance.

## Uso efetivo no experimento Grid

Fonte: `2026-10-18-grid-results.json`, cenário `continuous`, 365 dias horários incluindo aquecimento. Nenhuma dessas hipóteses passou.

| Hipótese | Inicial | Patrimônio final líquido estimado | Resultado líquido | Taxas + slippage acumulados |
|---|---:|---:|---:|---:|
| Grid por inventário | 1.000,00 | 888,40 | -111,60 | 106,42 |
| Grid + tendência | 1.000,00 | 880,71 | -119,29 | 68,13 |

Valores em USDT. Custos já estão incorporados ao resultado; não descontá-los novamente. O patrimônio final inclui as posições remanescentes avaliadas com custo estimado de saída, não apenas o saldo livre.

## Leitura do guia e decisões do projeto

[Fonte oficial consultada em 18/10/2026](https://www.binance.com/pt-BR/academy/articles/your-guide-to-binance-trading-bots). A página indica atualização em 26/06/2026.

O guia apresenta Grid como ordens menores de compra e venda dentro de uma faixa; DCA Spot distribui compras/vendas; Investimento Automático acumula com compras recorrentes. Rebalanceamento mantém alocações. Recomenda objetivos, gestão de risco e monitoramento periódico. Não demonstra que alguma dessas estratégias supera o mercado.

Nossa aplicação: manter Spot sem alavancagem, orçamento limitado e monitoramento. Futures Grid e arbitragem com futuros estão fora do escopo. Marketplace fornece parâmetros de outros bots, não validação para nossa carteira ou momento de entrada.

Lacuna principal: nosso Grid atual é ajuste de inventário por fechamento horário, não uma grade de ordens limitadas. Ainda faltam reserva de saldo por ordem, cancelamento/reposição, preenchimentos parciais, filtros de preço/quantidade/mínimo por par e tratamento explícito da sequência intradiária. STOP e o bloqueio por drawdown existentes não equivalem a um stop-loss de saída implementado na corretora.

Próximo simulador deve representar essas regras e cenários adversos antes de qualquer integração real. Não presumir execução só porque a máxima/mínima tocou um preço; OHLC não informa fila ou ordem dos acontecimentos. Testes precisam incluir patrimônio total, custos, resíduos e ordens pendentes. O guia orienta o produto, mas não substitui especificação técnica da API nem validação quantitativa.

