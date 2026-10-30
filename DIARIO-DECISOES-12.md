# Evidência das entradas do perfil12

O perfil12 registra `SIGNAL` uma vez por par/candle fechado, `ENTRY_INTENT` antes de reservar caixa e `RESERVATION` depois do retorno do ledger. Tudo fica em arquivos imutáveis por identidade, fase e chave em `reports/local/decision-trace/`. O conteúdo contém campos selecionados do sinal, EMAs, ATR, cotação da tentativa, caixa anterior, filtros e resposta da reserva. A cotação é recebida por REST: seu instante não prova a idade do livro na origem.

Nenhuma variável de ambiente ou chave de API entra nesse registro. JSON não finito, sinal futuro, conteúdo excessivo e conflito com evidência já gravada são recusados. Arquivos parciais após falha de escrita ficam inválidos, impedindo substituir a evidência silenciosamente.

A escrita anterior à entrada é obrigatória. Se falhar, `AUDIT_ENTRY_BLOCKED` impede nova reserva. A escrita de resposta pode falhar depois da reserva; o painel do motor mostra `decision_audit=DEGRADED`, mas não apaga a ordem nem presume seu cancelamento. O resultado financeiro continua no SQLite reconciliado. Intenção sozinha não confirma compra, preenchimento ou saída. Em falha após intenção e antes de reserva, uma nova cotação conflitante não sobrescreve a intenção anterior: essa chave fica bloqueada conservadoramente.

O histórico do painel associa o ID da compra preenchida à evidência da mesma identidade, exigindo registro anterior ao fill e mesmo par. Operações antigas de seis pares permanecem com indicadores não registrados; não se usa o radar de hoje para preencher lacunas históricas. O registro atual não adiciona indicadores anteriores/próximo candle que não estejam disponíveis: explicita apenas os valores fornecidos pelo scanner causal existente.

Não há novas regras de sinal, risco ou tamanho. São novas proteções de auditoria na próxima versão ainda não ativada. Os arquivos do perfil12 participam da identidade; não atualizar essas fontes durante uma sessão12 ativa. A sessão original de seis pares não muda.

```powershell
python -m unittest tests.test_decision_trace tests.test_portfolio12 -v
node test_dashboard_frontend.cjs
```
