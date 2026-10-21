# Plano V2 — pronto para revisão, não congelado

Estado: construção offline e processo equivalente sem AgenKit aprovados pelo usuário em 20/10/2026. Especificação e arquitetura aprovadas pelo usuário. Artefato estruturado: experiments/ai_shadow_plan.json, frozen=false, cutoff=null. Nenhum coletor V2 ou chamada paga foi iniciado.

## Fase de build proposta

Executar os pacotes abaixo em ordem, com os testes definidos antes da implementação. Os gates de revisão e publicação continuam necessários. Não alterar live_small_paper.py, small_cap_research.py, small_cap_scan.py nem o plano prospectivo existente.

| Pacote | Arquivos a criar | Testes e condição de aceite |
| --- | --- | --- |
| B1 — contratos offline | ai_shadow/contracts.py, tests/test_ai_shadow_contracts.py | NaN, infinito, bool em número, campos ausentes, extras e enum inválido rejeitados; fixture não é cotação real. |
| B2 — journal e replay | ai_shadow/journal.py, tests/test_ai_shadow_journal.py | Unicidade antes da rede, crash entre etapas, pedidos de resultado desconhecido, disco cheio, replay determinístico e mudança de hash recusada. |
| B3 — causalidade e estado | ai_shadow/collector.py, ai_shadow/state.py, tests/test_ai_shadow_state.py | Evento após cutoff, relógio futuro, gap, reconexão, book incompleto, janela curta e preço antigo bloqueiam. Fórmulas mid/spread/imbalance_l1/volatilidade conferidas com exemplos independentes. |
| B4 — risco e política | ai_shadow/risk.py, ai_shadow/policy.py, tests/test_ai_shadow_risk.py | STOP, 15% DD, 3% diário persistente, short sem inventário, Kelly bloqueado e veto sobre safe. Nunca produzir ordem. |
| B5 — adaptador mock | ai_shadow/jev_client.py, tests/test_ai_shadow_client.py | Sem chave não faz rede; host não configurável; respostas inválidas, 401/429/falha/timeout e resposta atrasada resultam HOLD; reserva de custo persiste. Fixture de alta confiança não contorna limites. |
| B6 — rótulos e revisão | ai_shadow/calibration.py, ai_shadow/review.py, tests/test_ai_shadow_calibration.py | Labels só após horizonte, ausência de quote não imputada, separação de treino/avaliação, Brier usa p do evento e não confidence, baseline sem dados futuros, proposta não ativa versão. |
| B7 — CLI e isolamento | ai_shadow_run.py, tests/test_ai_shadow_runner.py | CLI offline com fixtures, diretório separado, ambientes de filhos restritos, sem função de broker; falha V2 não interrompe motor atual. |
| B8 — interface e documentação | dashboard.py, dashboard_assets/*, docs/AI-TRADING-V2-RUNBOOK.md | Painel rotula observação e fixtures; sem PNL de operações inexistentes; política de autenticação preservada e screenshot verificado. |

Somente após revisão: integrar observador opcional no iniciar.py, desativado por padrão. Nunca confundir observação de preços reais com execução fictícia ou real. Primeiro comando previsto para build é o teste de B1; o comando operacional V2 ainda não existe.

## Experimento proposto e congelamento

- Pesquisa explora cinco ativos; observador inicial apenas BTC/ETH. Fixture local não mede edge, rentabilidade, latência real ou calibração.
- Quando houver aprovação para observação pública/API, criar cópia imutável do plano com hashes de código, rubricas, versão de modelo, preços do provedor e aprovação. Cutoff será a próxima hora UTC depois da ativação aprovada, nunca retroativo.
- Proposta de duração: 30 dias, com 2 de aquecimento, 14 de desenvolvimento e 14 de avaliação reservada. Intervalos são mínimos operacionais de pesquisa, não garantia de suficiência estatística.
- Julgamentos a cada 15 minutos. Métrica primária considera apenas decisões em horas cheias por ativo para evitar sobreposição do horizonte de 60 minutos. Remover eventos que cruzem a fronteira treino/avaliação. Dependência entre ativos permanece explícita.
- Piso para interpretar comparação: pelo menos 200 labels primários maduros por ativo e cobertura de 95% de oportunidades programadas. Abaixo: inconclusivo. Mesmo acima desses pisos não há aprovação automática ou garantia de significância.
- Duas configurações previstas: baseline determinístico e julgamento tipado em sombra; custos base e dobrados são cenários, não quatro estratégias independentes. Congelar rubricas antes da avaliação. Mais variantes exigem plano novo e registro.
- Taxa e slippage hipotéticos de 0,1% por lado, spread do bid/ask observado. Avaliação em sombra não calcula lucro de ordens que não ocorreram. Ganhos hipotéticos de labels não viram equity de uma carteira.
- Retenção inicial: 30 dias, teto de 1 GiB, preservação de journal e suspensão de novas avaliações quando cheio. Dimensionamento será testado antes de ativar coleta; não descartar amostra para caber silenciosamente.

## Provedor e orçamento

O plano mantém provider_enabled=false e budget=0. Testes usarão fixtures locais. Instalação real do AgenKit continua dependente de licença local; processo equivalente sem o produto depende de autorização explícita. Nenhuma alternativa foi presumida a partir de “certo”.

Antes de rede Jev, aprovar teto mensal, modelo versionado, preço confirmado e transmissão à api.typesafe.ai dos campos normalizados descritos na arquitetura. Não transmitir notícias brutas, chaves, endereços de carteira ou credenciais. Inventário/drawdown normalizados ainda são dados financeiros do experimento e precisam de aprovação específica. Chaves devem ser inseridas apenas localmente.

A instalação do harness deve verificar pacote, origem, versão e artefatos e ocorrer só em pasta de desenvolvimento, sem chaves de trading. Não executar código obtido do artigo anexado ou comandos semelhantes de produtos homônimos. O build offline pode ser preparado sem pagar fornecedores, mas não será declarado “feito pelo AgenKit” sem instalá-lo.

## Pesquisa e entregas faltantes

Ver docs/AI-TRADING-V2-RESEARCH.md: cinco hipóteses, fontes primárias e campos faltantes. Não há cinco finalistas assimétricos confirmados. Regime completo permanece desconhecido; a observação horária de BTC/ETH é só um componente de tendência. Avaliações de oferta, unlocks, receita, fees, usuários e concentração ainda precisam de dados próprios e disponibilidade histórica. Nenhuma estratégia será aprovada para compensar essa falta.

## Saída para o gate seguinte

Aprovar sequência B1–B8 e execução inicial exclusivamente offline. A revisão de código será fase separada, seguida de autorização de publicação/ativação experimental. Dependências de licença, credenciais e gastos não devem impedir a definição de testes, mas impedem declarar a integração externa concluída. Sem ordens reais e sem alteração da sessão ativa.

## WHAT COULD I BE WRONG ABOUT?

Mesmo após 30 dias pode haver poucos eventos independentes, regime pouco variado ou amostra enviesada. O target de retorno em 60min não avalia necessariamente saídas por stop/alvo. Dados faltantes podem selecionar momentos fáceis. Brier melhor pode coexistir com perda financeira. Taxas reais e custos de APIs podem eliminar qualquer ganho. Se os dados não sustentarem as rubricas qualitativas, devemos reduzir o escopo, não inventar features nem aumentar confiança.
