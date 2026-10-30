# Hipótese registrada antes da janela futura

`DONCHIAN20_BTC1H_RESEARCH_V1` é uma hipótese não validada de rompimento BTC/USDT1h. Entrada após600 candles de aquecimento: fechamento acima das máximas dos20 candles anteriores, acima da EMA200 e ATR14/preço entre0,1% e2%. Só uma entrada hipotética na abertura seguinte. A especificação registra capital20 USDT, orçamento6, risco1%, stop2%, alvo5%, saída completa em48 horas, limite diário3%, drawdown10%, custos0,1% por lado e stress dobrado. Nenhuma dessas ordens é executada nesta etapa.

## Registro e coleta manual

```powershell
python -m prospective_protocol --data-dir CAMINHO_DA_SESSAO --register --collect
python -m prospective_protocol --data-dir CAMINHO_DA_SESSAO --collect
python -m prospective_protocol --data-dir CAMINHO_DA_SESSAO --verify
```

O primeiro comando exige que ainda não exista registro. Usa hora pública da Binance, define início na próxima hora UTC inteira após uma margem mínima de5 minutos e fim fixo30 dias depois. A margem evita registrar um protocolo quando o próximo candle já está prestes a começar. A primeira observação futura só está disponível quando esse primeiro candle fechar. O registro preserva regras, janela e hashes das implementações. Repetir `--register` é recusado; não se sobrescreve uma experiência.

O registro inicial de30/10/2026 tem janela30/10 às12h até29/11 às12h, Brasília. O hash está referenciado em `experiments/prospective_commitment_20261030.json` para comparação pública. Essa referência não é uma certificação externa do experimento nem aprova a estratégia.

Cada coleta usa somente OHLCV público, fechado e alinhado. Os600 candles anteriores são aquecimento e não contam como amostra futura. Snapshots cumulativos têm encadeamento de hashes, criação exclusiva e prefixos consistentes: revisão de um candle anterior é recusada, não substituída silenciosamente. O índice evita duplicar downloads no mesmo fechamento. Arquivos órfãos não alinhados ao índice exigem revisão. O comando `--verify` verifica todos os snapshots e a cadeia sem fazer rede. O painel verifica registro, fontes e último snapshot; não apresenta isso como auditoria externa de toda a cadeia.

## Limites importantes

- Registro local não é timestamp certificado por terceiro nem prova contra alteração deliberada pelo dono do computador.
- Editar arquivos referenciados na identidade suspende o uso do protocolo; não alterar hashes para esconder mudança de regras. Desenvolvimento posterior deve ocorrer em módulos separados ou outra versão identificada.
- Trinta dias não garantem30 ciclos. Menos ciclos continua inconclusivo, sem estender a janela automaticamente.
- Fechar a janela produz somente dados, não estratégia aprovada. Ainda faltam avaliação explícita, custos/filtros de execução identificados, robustez e revisão.
- Não há carteira, ordens, conta, IA paga, serviço de coleta periódico ou promoção automática. O trading anterior continua encerrado.

Arquivos ficam em `reports/local/prospective/`. O painel e o resumo da mesa mostram a reserva futura e suas pendências. O download de metadados exige autenticação e nunca dispara coleta. Uma falha de integridade mostra estado desconhecido, não uma estatística de desempenho.
