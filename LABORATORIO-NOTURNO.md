# Acompanhamento experimental com saldo fictício

Autorizado para observar preços reais e simular a candidata diária `sma200_vol`, sem exigir que ela tenha passado o gate de estratégias. Essa é uma experiência separada; não aprova a candidata, não muda `validation.json` e não remove proteções do motor principal. A candidata teve resultado histórico agregado positivo, mas falhou nos critérios completos.

## Sessão

```powershell
python paper_lab.py --hours 10
```

Usa 1.000 USDT fictícios, BTC/ETH, médias de 200 candles diários fechados e multiplicador por volatilidade de 30 retornos (alvo anual experimental de 20%, multiplicador no máximo 1). Não otimiza nem troca parâmetros durante a noite.

Consulta apenas GETs públicos: candles diários e bid/ask. Não usa chave de conta nem possui chamada de ordem real. Considera spread, taxa de 0,1% e slippage de 0,1%. Há uma medição por minuto; compra/venda é ajustada no máximo uma vez por ativo e candle diário novo, com orçamento de 5% por ordem, limite de 20% por ativo e 60% no conjunto. Pode permanecer totalmente em caixa.

O resultado usa a última cotação salva. Patrimônio marcado pelo bid e resultado líquido estimado são diferentes, pois o segundo inclui custos estimados de saída. Uma noite com lucro ou sem trades não valida a estratégia. O modelo não reproduz filtros completos, quantidade mínima de cada par, liquidez real ou fila; mínimo nocional simulado de 10 USDT. Não reconstrói movimentos entre as consultas de um minuto.

## Persistência e encerramento

Salva em `reports/local/live-paper.json` e diário em `live-paper-events.jsonl`, fora do Git e separado da carteira principal. Não reinicia saldos se executado novamente: retoma a mesma sessão antes do término, ou exige preservar a sessão concluída. Uma trava de arquivo impede dois processos desse laboratório.

STOP da pasta do programa é verificado antes de cada ordem simulada. `--control-dir CAMINHO` permite também respeitar STOP de outra pasta, somente leitura. Drawdown de 15% trava novas ordens, mas não liquida posições; perdas podem ultrapassar o gatilho. Ao término do prazo, o processo encerra sem vender posições; o último relatório fica salvo.

O computador precisa ficar ligado, sem suspensão e com internet. Se uma consulta falhar, o ciclo é bloqueado e o erro é registrado. Não há serviço de reinício automático após reinicialização do computador. Esta versão do laboratório acompanha pelo painel e diário local; ainda não tem notificações Telegram próprias.

O painel deve usar a mesma pasta de dados do laboratório. A visão geral mostra um cartão separado, “Laboratório noturno”. Não confundir com os cartões da carteira principal. O botão Desligar bot aciona STOP e também encerra o laboratório dessa pasta.

## Execução iniciada nesta sessão

O experimento foi iniciado no checkout de trabalho do Codex, com painel próprio em `http://127.0.0.1:8768`, por dez horas, com término previsto em **19/10/2026 às 08:23 (America/Sao_Paulo)**. Não inicie outra cópia no projeto original enquanto esta sessão estiver ativa. Arquivos operacionais e código de acesso do painel não são publicados no GitHub.
