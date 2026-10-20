# Evidências, validação e operação

## Auditoria da sessão

`python auditar.py` gera reports/local/session-audit.json, session-audit.md e research-registry.json. O iniciador também atualiza esses arquivos a cada minuto, em uma thread independente. O painel reconcilia a sessão salva a cada leitura, sem alterar ordens ou regras. Relatórios são locais, ignorados pelo Git.

A reconstrução usa custo médio, preços fictícios já com slippage, taxas e PNL de cada venda. Verifica caixa, resultado realizado, posição e decomposição do patrimônio. Fator de lucro usa resultados líquidos por execução de venda (uma execução parcial não é um ciclo completo). Sem perdas, o fator fica indefinido. Drawdown e lacunas cobrem apenas a curva retida, de até 1.500 pontos. 180 segundos é um limiar de observação, não prova da duração exata de uma indisponibilidade. O histórico de até 500 ordens pode estar truncado, caso em que não certificamos reconciliação integral. Dados posteriores não recuperam períodos perdidos.

O benchmark em caixa tem PNL zero, sem juros. Comprar e manter exige cotações independentes, mesmo início/fim e mesmos custos: permanece indisponível enquanto essa série não existir. Não anualizamos Sharpe ou CAGR da sessão curta, irregular e incompleta. Reconciliação correta não comprova vantagem.

## Registro dos experimentos

O registro preserva hashes SHA-256 dos relatórios locais disponíveis e configurações identificáveis (estratégia, universo quando registrado, capital, custos, janela e intervalo de entrada). Cada nova versão do relatório é outro snapshot, sem substituir os anteriores no registro. Reportar estudos e configurações separadamente: uma repetição com dados novos não é necessariamente outra regra. Esse inventário não recupera experimentos apagados, parâmetros não registrados ou versões anteriores do código, e não equivale a pré-inscrição. Não atribui significância nem corrige múltiplas comparações.

## Protocolo para pesquisas futuras

1. Antes de coletar a amostra de avaliação, congelar regras, universo, filtros, parâmetros, horários, benchmark, custos, variantes previstas e critérios de interrupção em um plano identificado por hash. O plano prospectivo existente permanece intacto.
2. Guardar horário do evento e horário de recebimento/disponibilidade. Sinais só podem usar dados disponíveis no instante da decisão; preço de execução vem depois do sinal. Fundamentais e notícias exigem data de publicação, não apenas data de referência.
3. Separar períodos cronologicamente. Escolher parâmetros apenas no desenvolvimento; não retocar a regra usando o resultado reservado. Um período já consultado não volta a ser não visto. Usar múltiplas janelas temporais, sem embaralhar observações.
4. Registrar todas as configurações, inclusive resultados negativos e exclusões por dados ausentes. Estudo de sensibilidade de parâmetros vizinhos deve ser planejado previamente, com quantidade total de tentativas explicitada.
5. Incluir taxa por lado, spread executável e slippage. Sem spread histórico observado, rotular a aproximação. Testar custos base e dobrados. Mínimo/lote não podem ser ajustados para forçar preenchimentos. Sem liquidez histórica suficiente, não alegar execução realista de grande volume.
6. Comparar desempenho líquido, drawdown, número de negócios e estabilidade com caixa e benchmark alinhado. Poucos negócios, dados incompletos ou resultado favorável em uma só janela mantêm o veredito inconclusivo. Nenhum selo aprova dinheiro real automaticamente.
7. Considerar risco de seleção do universo atual e ativos removidos. Não chamar um conjunto atual de pares de base livre de sobrevivência. Dados point-in-time precisam de aquisição e verificação próprias.
8. Reproduzir choques históricos como testes de cenário, não previsão. Testar atrasos, desconexão, preço inválido e recuperação. Não alterar a estratégia durante uma sessão em execução para melhorar sua curva.

## Limites do que foi aplicado

Sem contratação de QuantGPT, Alpaca ou nuvem. O computador ainda precisa permanecer ligado e conectado. Não foram adquiridos dados point-in-time, histórico de ativos removidos nem infraestrutura redundante. Não foram criados retornos, benchmarks ou Sharpe fictícios. Essa documentação não transforma os backtests anteriores em validações prospectivas.
