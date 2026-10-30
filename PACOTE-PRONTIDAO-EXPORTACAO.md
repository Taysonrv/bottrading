# Pacote de prontidão, custos e exportação completa

O terminal reúne checklist salvo da transição12, diagnóstico público de mínimos/custos e downloads autenticados de todo o ledger. Nenhuma dessas leituras inicia ordens ou transforma uma hipótese em estratégia aprovada.

## Diagnóstico público

```powershell
python -m paper12_feasibility --data-dir CAMINHO_DA_SESSAO_ATUAL
python -m upgrade_readiness --current CAMINHO_DA_SESSAO_ATUAL --next CAMINHO_DA_PROXIMA_SESSAO
```

O diagnóstico consulta apenas dados públicos Spot. Supõe explicitamente um sinal de entrada para testar a mecânica, não emite esse sinal ao motor. Mostra mínimo, spread, custo até6 USDT, perda hipotética no stop, recompensa no alvo e RR líquido após taxas, slippage e arredondamento. Testa também os filtros da saída integral. O preço salvo não é oferta executável futura; falhas públicas ficam desconhecidas.

O checklist exige fim da sessão anterior, ledger reconciliado, nenhuma exposição/reserva remanescente, nenhuma trava de risco, próxima raiz distinta com perfil12 explícito, nenhum saldo já emitido e diagnóstico mecânico completo de até30min com pelo menos um par viável. Mesmo todas as condições atendidas autorizam somente revisão pelo operador. Não criam vantagem estatística ou autorização de dinheiro real. O checklist salvo pode ficar antigo; o painel mostra o horário e pede reavaliação.

## CSV completo

Os links do terminal usam `/api/export.csv?kind=fills` e `kind=cycles`, com a mesma autenticação e restrição de origem/host do painel. Não aceitam caminho de arquivo ou nome de carteira por URL. Leem o SQLite reconciliado em modo somente leitura; não se limitam às100 linhas da interface. Exportação inválida é recusada, nunca substituída por histórico fictício.

Ciclos incluem as duas taxas e o resultado líquido exato. Uma posição aberta não é exportada como ciclo fechado. Campos de texto são protegidos contra fórmula de planilha; números negativos legítimos continuam numéricos. Datas usam timestamps UTC em milissegundos para evitar ambiguidade. Os arquivos contêm simulação e não constituem extrato da Binance.

O guardião externo também cobre painel ausente por120s enquanto o supervisor permanece vivo, respeitando o limite próprio de três tentativas e o prazo/STOP. Só a interface é recuperada: falha do motor exige revisão. Atualização planejada pode solicitar recuperação imediata do painel uma vez, sem mexer em saldo ou posições.

```powershell
python -m unittest tests.test_upgrade_package tests.test_session_guard -v
node test_dashboard_frontend.cjs
```
