# Motor de negociação — progresso e limites

O motor atual executa compras e vendas simuladas, contabiliza custos e resultados e solicita notificações ao Telegram. Não há integração de envio de ordens reais.

## Correção de execução

A aprovação era consultada antes de buscar a cotação de execução. Agora o arquivo e sua validade são conferidos novamente antes de cada preenchimento simulado. Uma aprovação vencida, de outra versão ou revogada bloqueia a ordem. STOP e drawdown são verificados depois dessa leitura, imediatamente antes do preenchimento.

O diário registra decisões aprovadas pelo primeiro gate: ativo, regime, fração-alvo, candle e valor pretendido. Essa decisão ainda não é uma ordem: depende das travas finais. Esses registros não enviam notificações ao Telegram; compras, vendas e bloqueios mantêm os avisos existentes.

## Verificação ponta a ponta

`test_trading_flow.py` usa pasta temporária, preços artificiais e relatório de aprovação sintético, somente em memória/arquivos temporários de teste. Não altera a validação do usuário nem aprova uma estratégia real.

- Compra com custo e limites de exposição/orçamento.
- Novo ciclo sobre o mesmo candle não duplica a ordem, usando estado persistido.
- Novo candle com sinal de saída vende, registra custos e reconcilia resultado realizado e não realizado.
- Compra e venda geram mensagens ao adaptador Telegram simulado. Não testa entrega no Telegram real.
- Expiração ou revogação da validação durante a consulta de cotação impede o preenchimento.
- STOP recebido após a leitura inicial impede a ordem.

## Por que a candidata diária ainda não opera

No relatório histórico de 18/10/2026, `sma200_vol` teve +16,04% no cenário contínuo e drawdown de 7,42%, mas isso não basta:

| Cenário | Estratégia | Comprar e manter 50/50 | Motivo da reprovação |
|---|---:|---:|---|
| Segunda janela de avaliação | +4,33% | +82,89% | Não superou o mercado |
| Período final | -0,56% | -30,64% | Retorno líquido negativo |
| Período final, custos dobrados | -0,80% | -30,92% | Retorno líquido negativo |

Fonte: `reports/2026-10-18-daily-results.json`. São resultados históricos já consultados, não uma nova evidência independente. Não foram alterados parâmetros ou critérios para fazer essa candidata passar. As hipóteses diárias ainda pertencem ao módulo de pesquisa, separado do motor horário ativo.

## Atualização operacional

Encerre `watch` e o painel com Ctrl+C antes de atualizar:

```powershell
git pull --ff-only
python -m unittest -q
python bot.py observation-archive
python bot.py observe
python bot.py watch
```

O arquivo anterior de observação é preservado no arquivo de sessões. Esta mudança altera a identidade do código; a sessão anterior não pode ser misturada com a nova. Se algum comando falhar, resolva o erro antes de seguir.

Em outro terminal, na mesma pasta:

```powershell
python dashboard.py
```

`watch` coleta sinais sem operar. `run` é o motor contínuo de ordens simuladas, mas continua exigindo validação vigente e aprovada; não habilita trading real. Não execute `run` e `watch` simultaneamente: eles compartilham a trava da carteira/processo.

A próxima etapa de estratégia exige uma nova hipótese fundamentada e confirmação futura; repetir otimizações no histórico já visto não resolve a falta de aprovação. A integração real permanece pendente e não deve ser confundida com a aprovação dos testes de software.
