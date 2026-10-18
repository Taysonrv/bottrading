# Grid Spot experimental

Este módulo não altera `config.json`, `validation.json`, carteira, observação ou notificações. Não envia ordens à Binance. Os parâmetros foram fixados antes da primeira execução; não há busca por parâmetros vencedores.

```powershell
python -m unittest test_grid_research -v
python grid_research.py
```

Usa apenas dados públicos BTCUSDT/ETHUSDT, com corte horário UTC comum, 365 dias e exclusão da vela aberta. Produz os resultados `.json` e `.md` em `reports/2026-10-18-grid-results`. Nova execução substitui esses arquivos locais; o nome identifica o experimento, não garante a data da coleta. A data efetiva consta dentro do relatório.

## Hipóteses

- `grid_range_v1`: oito degraus de exposição dentro de faixa fixa, estabelecida pelas mínimas/máximas das 168 horas anteriores. Inicia somente se médias de 24h e 168h diferirem menos de 1%. Intervalo de cada degrau deve superar quatro vezes a soma de taxa e slippage estimados. Capital por ativo e por ordem continua limitado pela configuração do motor.
- `grid_hybrid_v1`: mesmo Grid; quando não existe episódio e a carência terminou, permite alvo comprado se preço > média 24h > média 168h e o mercado não está lateral. É uma hipótese, não um classificador confiável por definição.

Queda de pelo menos 6% em 24h ou desvio padrão horário de pelo menos 1,8% suspende novas compras. Ruptura de qualquer extremidade da faixa ou proteção de volatilidade encerra o episódio e solicita alvo zero. A faixa não acompanha o preço para esconder perdas. Carência de 24h após encerramento antes de novo episódio.

Um episódio aberto continua até ruptura/proteção; uma simples mudança de média não faz alternar instantaneamente entre Grid e tendência. Ao cair dentro da faixa, o alvo de inventário aumenta; ao subir, diminui. Não usa aumento multiplicativo de ordens ou martingale.

## Alcance da simulação

É uma aproximação de Grid por inventário, com sinais no fechamento e preenchimento na abertura seguinte, a mercado com custos estimados. Não é o backtest de ordens limitadas nativas: não simula fila, múltiplos ciclos intradiários, toque de preço como garantia de fill nem preço exato de execução de cada nível. Resultados não podem ser atribuídos ao bot nativo da Binance.

O período já foi consultado pelo projeto. Usa três janelas nos primeiros 75% após aquecimento, último quarto para comparação, cenário contínuo, estresse de custos 2x e carteira com 80% investido no começo do período final. São reinícios independentes para diagnóstico; a linha contínua não reinicia saldos.

O patrimônio inclui todas as posições remanescentes, com custo estimado de saída no encerramento. Comprar e manter 50/50 com custos é o benchmark principal. Não há benchmark individual nem fills intradiários nesta etapa.

Os limites atuais de exposição e ordem são mantidos. Redução de posições não é instantânea. O gatilho de drawdown de 15% congela ordens no cenário padrão e posições podem continuar perdendo. O cenário separado `reduce_experimental` vende gradualmente após o gatilho e jamais aumenta posição. Nenhuma dessas políticas garante drawdown máximo de 15%.

Qualificação exige todos os cenários com retorno líquido positivo superior ao benchmark, drawdown abaixo de 15%, pelo menos três operações e ausência de trava. Mesmo passar esses critérios históricos não liberaria a hipótese no motor: exige confirmação futura e revisão humana. Não foram alterados critérios para aprovar o Grid.

## Testes

Cobrem ausência de dados futuros, aumento/redução de inventário, faixa fixa, carência após ruptura, recusa de faixa estreita diante dos custos, perdas nas posições abertas e STOP impedindo ordens. Os testes não atestam rentabilidade.
