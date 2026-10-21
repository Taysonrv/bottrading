# Revisão técnica V2 — protótipo offline

Estado: revisão concluída; publicação da demonstração depende do gate humano. Escopo aprovado pelo usuário: processo equivalente sem AgenKit, somente fixtures locais. Este parecer não aprova provedor externo, coleta real V2, execução de ordens, integração no motor atual ou dinheiro real.

## Parecer

Recomendação: pode seguir para publicação controlada da demonstração offline, com o rótulo OFFLINE_FIXTURE e as limitações abaixo preservadas. A sessão paper existente não foi modificada. Módulos de produção ainda não existem; não descrever o build como sistema autônomo 24/7 ou integração Jev concluída.

## Falhas reproduzidas e corrigidas nesta revisão

| Achado | Reprodução | Correção e verificação |
| --- | --- | --- |
| Checkpoint vazio podia reiniciar a base de risco | Gravar risk={} após inicialização e avaliar novamente | Contrato estrito para o checkpoint; rejeitar vazio, campos ausentes, números inválidos, flags não booleanas e dia inconsistente. Teste exige ValueError, sem nova elegibilidade. |
| Pico/base diária inválidos não eram rejeitados uniformemente | Alterar peak/day_start para zero ou flag para string | Validar valores e relação entre pico/base antes de calcular risco; relógio retroativo permanece bloqueado. |
| Elegibilidade textual podia ser interpretada como verdadeira | Passar eligible='false' à política | Exigir eligible is True, sem coerção de truthiness. Resposta ótima não contorna risco malformado. |
| Brier aceitava timestamp NaN | label_at=NaN em label artificial | Exigir timestamps numéricos finitos, positivos e posteriores à previsão. Baseline também valida cutoff e horários de labels. |
| Multiplicação de preços extremos podia distorcer o label | Entrada e saída próximas do maior float finito | Calcular a razão de preços antes dos fatores de custo e rejeitar resultado não finito. Mesmo preço produz somente o custo esperado. |
| Verificação de plano diferente podia testar apenas o lock | Tentar novo plano com primeiro escritor ainda aberto | Acrescentar teste que fecha escritor e confirma rejeição por metadados, com reabertura posterior do plano correto. |

Os primeiros testes de regressão falharam para checkpoint vazio, flags/base inválidas e timestamps NaN. Depois das correções, passaram. Achados anteriores do build (overflow em mid, duplicata inconsistente, inventário sem reconciliação e revisão não persistida) continuam cobertos.

## Evidências

- python -m unittest -q: 264 testes passaram, incluindo 38 casos V2.
- node test_dashboard_frontend.cjs: verificações passaram.
- node test_market_stream.cjs: verificações passaram.
- Smoke test da demo em diretório temporário com socket.socket bloqueado: OFFLINE_FIXTURE, zero ordens, zero chamadas pagas.
- Dados artificiais identificados no relatório; rótulo SHADOW_CANDIDATE não é compra nem lucro.
- Nenhum resultado de fixture foi usado para selecionar estratégia, estimar Kelly, afirmar calibração de Jev ou aprovar retorno.

## Conformidade com o plano

| Pacote | Estado real |
| --- | --- |
| B1 contratos | Núcleo normalizado implementado e testado; não é parser HTTP real TypeSafe. |
| B2 journal | SQLite e idempotência locais implementados; falha de armazenamento bloqueia a demo. Sem simulação exaustiva de perda física de disco. |
| B3 coletor/estado | Replay de fixtures e estado causal implementados. Sem WebSocket V2, reconciliação de L2 ou prova de cobertura real. |
| B4 risco/política | Travas locais testadas; nenhuma execução. |
| B5 adaptador | Fixture e circuit breaker locais. Sem chave, rede, preço/cota ou tokenizer do provedor. |
| B6 calibração/revisão | Funções para dados artificiais e sumário inconclusivo. Sem estudo prospectivo, agendamento noturno ou mudança automática. |
| B7 CLI | Uma demonstração offline por evento, com journal separado e hash de plano/código. Não é loop contínuo. |
| B8 dashboard/lançamento | Ainda não integrado; pertence à próxima entrega aprovada. |

## Limites que bloqueiam produção

1. Não há transporte Jev. Timeout, distribuição e crise são casos artificiais; 81ms e o limite de 400 tokens não foram medidos.
2. A rotulagem aceita quotes fornecidas pelo chamador e valida tempos/custos; somente uma ingestão real auditável poderá comprovar que são as primeiras quotes elegíveis. Recebimento de eventos históricos além do cutoff é rejeitado no estado.
3. Hashes e SQLite não protegem contra usuário/processo com acesso ao mesmo disco. Processos locais não equivalem a sandbox de segurança.
4. Sem labels reais, cobertura, incerteza estatística ou benchmark econômico alinhado. Revisão continua INCONCLUSIVO independentemente da fixture escolhida.
5. O runner processa um exemplo determinístico. Não migra sessões e recusa código/plano diferente no mesmo journal. Para nova versão, preservar dados anteriores; não editar banco para contornar a identidade.
6. Não existe caminho de ordens. Sem broker, saldo da conta, assinatura, redução real ou autorização para mover dinheiro.
7. Não foi instalada licença AgenKit; não declarar execução do kit. A autorização foi para processo equivalente offline.

## Próximo gate proposto

Publicar apenas módulos offline, testes, plano e documentação no repositório, sem arquivos reports/local ou chaves. Depois da aprovação, oferecer comando de demonstração opcional claramente separado do iniciar.py. Integração de dados reais/provedor, credenciais, transmissão de campos e orçamento continua exigindo gate específico.

## WHAT COULD I BE WRONG ABOUT?

Fixtures podem não representar estados reais; testes não cobrem toda corrupção de disco, queda de energia ou comportamento do sistema operacional. Uma interface correta ainda pode representar uma pergunta economicamente inútil. O software pode passar em todos os testes e a estratégia perder dinheiro. A publicação offline não remove nenhum desses limites.

## Hashes dos artefatos revisados

- ai_shadow/__init__.py: 65a336daf34d05264e746a7d4b0685477dfec6b3a17007ba747ad3c45a7428ec
- ai_shadow/calibration.py: 1df6657c657c193dd3f4ba83fdf342b0af7242dea15ae14a3ca4eafc19f2e655
- ai_shadow/collector.py: 17e6e754c97deb16527a5f056aa7d94fdcdbaa4f2b69ca6df74ed473c5e6005e
- ai_shadow/contracts.py: b6c023b77580aae2b115b74daf2bdbf0321e4d1387ca604e6c3814df5a0395fe
- ai_shadow/jev_client.py: 4a888814b53c5e8bafae7fec0ecb819d9729cbc76b97066680496d17eedec5a2
- ai_shadow/journal.py: 762b3ae3cd64a4d59f5aa5bb2623028e1c8103b77a4de34b7ac44b9fe516b323
- ai_shadow/policy.py: 35d123a3502ced1de3f7f33594fa684def5c6f637728a305bb8a73f88bfca7b6
- ai_shadow/review.py: 29ecfebda87fe325199735d39f39f2713a3d8b6a717446bd1d3f685ce36e3e09
- ai_shadow/risk.py: 888c5015d7378ca819572afa03bcc606b181df8bf0c5bbdfd62d96bae898993b
- ai_shadow/state.py: d477a2d8412dbf9fa2e4ef9288af96215658dc886ffde1d594f80a2488c27677
- ai_shadow_run.py: f9d07f178b5c7e31f6c0f678f9d0e528489abe165cac7414ca8bb6749554a5cd
- tests/test_ai_shadow.py: 3bdf56a1036c5f79310f77abebe3bc17f42f70c1d2fd30562dcb8f030e38331e
