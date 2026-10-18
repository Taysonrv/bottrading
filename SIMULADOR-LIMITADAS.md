# Simulador offline de ordens limitadas

Capital de aceitação: **1.000 USDT fictícios**. Não consulta conta, não tem rede e não envia ordens. É um componente separado; não altera o motor horário, validação ou sessão de observação.

```powershell
python -m unittest test_limit_simulator -v
python limit_demo.py
```

O segundo comando executa quatro cenários construídos e salva `reports/2026-10-18-limit-acceptance.json` e `.md`. Não são resultados de mercado. Preços e filtros são artificiais, mesmo usando o rótulo BTCUSDT.

## Implementado

- Ordens passivas GTC com identificador e estados NEW, PARTIALLY_FILLED, FILLED e CANCELED.
- Reserva de USDT incluindo taxa para compra; reserva do ativo para venda. Reservas incluem todas as ordens pendentes, evitando gastar ou vender duas vezes o mesmo saldo.
- Preço alinhado ao tick; quantidade arredondada para baixo pelo step; limites mínimo/máximo de preço e quantidade, mínimo financeiro e número máximo de ordens por símbolo. Valores dos filtros devem ser fornecidos explicitamente.
- Limites fixos de pesquisa: 5% por ordem incluindo custo, 20% por ativo e 60% no conjunto. Ordens de compra pendentes contam como exposição potencial. Preços e limites são reavaliados antes de executar.
- Preenchimentos parciais com volume compartilhado por evento, prioridade de preço e depois identificador. Participação máxima inicial de 10% do volume agressor informado.
- Somente evento posterior à submissão e com preço estritamente além do limite permite fill. Toque não preenche. Compra exige agressor vendedor; venda exige agressor comprador. O preço cobrado é o limite da ordem, sem melhoria de preço presumida.
- Cancelamento libera apenas a reserva remanescente. Reposição é uma nova ordem; não reutiliza um evento já consumido.
- STOP verificado antes de cada preenchimento. STOP e gatilho de drawdown cancelam todas as ordens simuladas pendentes; não liquidam posições. A trava de drawdown permanece mesmo após recuperação.
- Contabilidade decimal, taxa em USDT e verificação de saldos livres não negativos.

## Referência técnica e lacunas

A documentação oficial descreve [filtros de preço, lote e valor](https://developers.binance.com/en/docs/products/spot/filters) e [estados de ordens](https://developers.binance.com/en/docs/products/spot/enums). O módulo implementa apenas o subconjunto listado acima. Não equivale a uma validação integral da Binance.

Ainda não reproduz livro e fila reais, latência/cancelamento concorrente, taxas pagas em BNB ou ativo-base, ordens taker, filtros percentuais dinâmicos, todos os limites da corretora, persistência e reconciliação após queda do processo ou dados faltantes. A regra de 10% é uma hipótese, não uma estimativa comprovada de execução. O último preço não substitui bid/ask; a verificação de passividade também é aproximada.

Não há estratégia Grid automática conectada a este componente. O demo submete, cancela e repõe ordens explicitamente para verificar o mecanismo. Na próxima etapa, um controlador de episódios e um replay de negócios cronológicos precisam ser ligados a ele, antes de atribuir retornos históricos à estratégia. Dados OHLC sozinhos não determinam a ordem dos acontecimentos intradiários.

## Evidência de aceitação

Os testes cobrem reserva, fills parciais, cancelamento, filtros, orçamento por ordem, exposição de ordens pendentes, prioridade e volume compartilhado, recusa de eventos repetidos, reposição sem retroatividade, STOP entre fills e perdas após travamento de drawdown.

O ciclo positivo artificial compra a 95 e vende a 105, terminando em 1.002,45 USDT após taxas. Ele foi construído para verificar a contabilidade e não deve ser usado como evidência de lucro. O cenário adverso, com posição inicial, termina em 820 USDT: cancelamento não impede perda de 18% se o ativo continuar caindo.

Nenhuma estratégia foi aprovada ou ativada. Os testes verificam o componente de execução; não resolvem a ausência de vantagem estatística.
