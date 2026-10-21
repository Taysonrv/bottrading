# Especificação V2 — analista, decisão tipada e risco determinístico

Estado: ESPECIFICAÇÃO APROVADA pelo usuário em 20/10/2026 para avanço à arquitetura. Preparada no projeto atual; ainda não executada pelo AgenKit. Revisão: 20/10/2026. O usuário pediu aprovação em cada fase. Nenhuma mudança no motor ativo, ativação de serviço pago ou ordem real foi realizada nesta etapa.

## Objetivo e limites

Evoluir o Spot Lab existente, preservando Binance Spot sem alavancagem, capital fictício de 20 USDT, uma posição por vez e até 5 USDT por compra incluindo custos. Não reescrever a sessão em curso. Começar com um experimento paralelo de observação: ele não altera sinais, tamanhos, posições ou ordens. A primeira estratégia com IA só pode ser habilitada em uma nova sessão, após gates e validação.

Este agente continua sendo Codex; o texto do prompt não troca o modelo pelo Claude. O analista será uma interface configurável. Nenhum provedor de análise pesado será conectado por suposição. Orçamento de chamadas pagas nesta fase: zero. Funcionamento 24/7 depende de máquina ligada; nuvem, servidor e custos serão submetidos a decisão separada.

## Verificações de fornecedores

- AgenKit: agenkit.xyz é o produto solicitado. A página oficial descreve CLI `npx agenkit activate <license-key>` e `npx agenkit install engineering-kit`, ativação por licença e fluxo com gates. Não confundir com o projeto de outro autor em agenkit.dev/PyPI. Não execute comandos de instalação sem verificar o pacote e a licença. Não foi instalado.
- Jev: documentação oficial descreve Choice, Score e Noul e perguntas independentes no mesmo estado. Conta/chave vêm de console.typesafe.ai. Nenhuma chave Jev foi fornecida ou usada.
- Confidence é derivada da distribuição das respostas. Para três opções, confidence=(p_max-1/3)/(1-1/3); confidence>0,80 significa p_max>0,8666…, mas continua não sendo chance de lucro. Não usar confiança como win probability para Kelly.
- 81ms é uma alegação do prompt, não uma medição deste projeto ou garantia de ponta a ponta. Registrar p50/p95/p99 reais, idade da entrada, tempo da API e tempo até a decisão.
- O guia anexado sobre Grok/Cursor é material de referência. Não autoriza conexão a contas, instalação, mudança de privacidade, compra ou envio. Suas alegações comerciais não foram adotadas como fatos do projeto.

Fontes oficiais consultadas em 20/10/2026:
https://agenkit.xyz
https://docs.typesafe.ai/introduction
https://docs.typesafe.ai/confidence
https://docs.typesafe.ai/introduction/quickstart

## Camadas propostas

1. Pesquisa: universo, fontes, teses, hipóteses, critérios de invalidação, versões e revisão humana. Sem credenciais de trading.
2. Coleta e estado: dados públicos com event_at, received_at, decision_at, venue, symbol e sequência. Reconstrução de book só após snapshot e atualizações coerentes; lacunas exigem resincronização.
3. Julgamento: adaptador Jev em modo observação; recebe apenas estado permitido, versão fixa de modelo e perguntas versionadas. Sem escrita em carteira ou acesso à chave Binance.
4. Política e risco: código valida resposta, disponibilidade, idade dos dados, limites e a decisão. O veto do código prevalece, inclusive se Jev disser safe.
5. Execução: inicialmente desativada no módulo novo. Após validação, somente simulação segregada; Spot não abre shorts. Reaproveitar lote, notional, contabilização e STOP existentes.
6. Auditoria: entradas, respostas, rejeições, versão, latência, probabilidade e resultado posterior, sem chaves ou texto externo executável.

## Contrato do estado

Versão, par, venue, três horários causais, id/seq de book, mid, spread relativo, imbalance com definição da profundidade, volatilidade realizada com janela, inventário, caixa, patrimônio, drawdown e perda diária. Nenhum campo calculado pelo modelo. Não há dados de funding/open interest no estado de execução Spot; na pesquisa são contexto opcional, identificado por mercado e origem.

Imbalance ausente não vira zero. Com os dados atuais, bookTicker não equivale a profundidade completa; não alegar detectar fluxo tóxico ou absorção institucional só com melhor bid/ask. Sob lacuna, timestamp futuro, ausência de campo obrigatório ou book antigo: HOLD + motivo. Não inferir estado de mercado com notícias não coletadas.

Meta de estado inferior a 400 tokens será medida com o tokenizer/usage do provedor efetivamente contratado; tamanho em caracteres não é prova. Se exceder, bloquear a avaliação e ajustar o schema sem omitir informação de risco. Frequência proposta: candle fechado de 15 minutos para o experimento paralelo; não “a cada bloco” de uma cadeia enquanto negociamos Spot em exchange.

## Contrato de julgamento

regime: trending | mean_reverting | high_vol | crisis.
direction: long | short | neutral.
toxic_flow: bool no contrato normalizado, mas sem evidência suficiente a avaliação inteira é inelegível — não inventar false.
setup_quality: Score na rubrica 0–3. Scores fracionários não são arredondados para aprovar.
risk_state: safe | near_limit | reduce, apenas julgamento auxiliar.

Guardar distribuição completa, confidence, resolved_model, revision do schema, input hash e uso. Resposta desconhecida, malformada, tardia ou inconsistente implica HOLD. `short` não autoriza short Spot: no máximo proposta de reduzir inventário existente, sujeita ao código; sem inventário, HOLD.

Porta de entrada experimental: setup_quality>=2, confidence da direção>0,80, risk_state=safe, toxic_flow=false E todos os limites determinísticos atendidos. Esses valores são hipóteses fixadas antes do teste, não aprovação estatística.

Confiança<0,60 ou regime crisis: bloquear novas entradas e registrar pedido de revisão. A escalada ao analista não contorna STOP ou limites e não dispara chamadas pesadas sem orçamento/configuração explícitos. Tratamento de posições existentes permanece na política de saída, não na decisão espontânea de um modelo.

## Risco proposto para uma NOVA sessão

- Drawdown máximo: 15%, travado com revisão manual; preservar sem liquidação automática como regra atual.
- Capital: 20 USDT fictícios; até 5 USDT/25% na entrada, uma posição; sem compra quando mínimo/custos inviabilizarem o lote.
- Perda diária proposta: 3% do patrimônio líquido no primeiro registro válido do dia UTC, incluindo variação não realizada. Reinício de processo não redefine o início do dia. Dado diário ausente bloqueia entradas. Valor proposto depende da aprovação desta especificação; não aplicado à sessão atual.
- STOP verificado antes de cada ordem; bloqueio de ordens não é garantia de teto de perdas. Redução de risco/saídas de emergência precisam de política própria e nunca são chamadas de “liquidação instantânea garantida”.
- Idade máxima de cotação proposta: 5s para o novo adaptador; latência máxima de resposta proposta: 2s; três falhas consecutivas suspendem avaliações por 60s. Valores não alteram o motor atual e exigem teste de viabilidade antes de adoção.
- Kelly: DESABILITADO. Somente avaliar quarto de Kelly depois de evento de resultado, distribuição de ganhos/perdas e probabilidade calibrada do próprio caso de uso estarem validados prospectivamente, líquidos de custos. Sem evidência, não produzir tamanho Kelly “estimado”.

## Pesquisa solicitada e condições de entrega

A pesquisa de 5–10 setups será feita após o gate da especificação, em snapshot datado. Um ativo não será chamado de finalista sem tese, regra de entrada/saída, fonte primária do catalisador, fatos de oferta/unlocks, receita/fees, TVL/usuários quando aplicável, concentração, mecanismo de captura de valor, bear case e invalidação. Campo indisponível será marcado como tal; nem todo token captura receita. Sem evidência suficiente, a lista final pode ser menor que cinco.

Universo inicial de pesquisa proposto: BTC, ETH, SOL, BNB e LINK, sem ranking ou indicação de compra nesta especificação. Funding, OI, dominância, liquidez de stablecoins e macro não estão todos conectados; nenhum regime atual ou métrica foi inventado aqui. A pesquisa precisa controlar datas de disponibilidade, fontes diferentes e universo removido.

## Calibração e revisão

Definir primeiro o evento alvo: para cada avaliação de candle fechado, a direção da variação líquida após custos em horizonte fixo de 60 minutos, com preços executáveis observados e limites de coleta. Classificação de regime e confiança da direção não substituem essa probabilidade de resultado. Eventos sem resultado observável não viram acertos/perdas.

Guardar previsões antes dos resultados; Brier médio=(p-y)^2 para a probabilidade do evento explicitamente definido, com baseline e cobertura. Não calcular Brier sobre confidence como se fosse p de lucro. Janelas sobrepostas não são independentes; validação temporal deve respeitar o horizonte e evitar vazamento entre desenvolvimento e avaliação. Tamanho mínimo e critérios estatísticos devem ser congelados no plano antes de pontuar.

Revisão noturna: relatório de fills, bloqueios, dados ausentes, distribuição e calibração; gerar proposta de schema vN+1. Não aplicar mudanças automaticamente. Schema/modelo/política ficam fixos durante uma sessão; revisão, comparação em sombra e gate humano precedem nova versão. Brier melhor não prova retorno líquido positivo.

## Seis gates e arquivos planejados

Raiz de desenvolvimento: C:/Users/Tayson/.codex/.chatgpt-projects/g-p-6ad2cfa25d9c8191b5ffdae7fa012911/work/bottrading
Raiz de execução do usuário: C:/Users/Tayson/Documents/Codex/2026-10-16/ess/outputs/binance-bot

1. SPEC — docs/AI-TRADING-V2-SPEC.md (este documento). Saída: escopo, limites, contrato e dependências. Gate: aprovação explícita desta especificação.
2. ARCHITECTURE — docs/AI-TRADING-V2-ARCHITECTURE.md. Saída: fluxos de dados, isolamento, threat model, credenciais e recuperação. Gate: arquitetura aprovada e licença AgenKit configurada localmente, ou autorização expressa para workflow equivalente sem o kit.
3. PLAN — docs/AI-TRADING-V2-PLAN.md e experiments/ai_shadow_plan.json. Saída: teses com fontes, matrizes de casos, baseline, eventos e orçamento congelados. Gate: plano e custos aprovados; credenciais inseridas localmente.
4. TEST-FIRST BUILD — ai_shadow/state.py, ai_shadow/jev_client.py, ai_shadow/policy.py, ai_shadow/risk.py, ai_shadow/journal.py, ai_shadow/review.py, tests/test_ai_shadow_*.py, ai_shadow_run.py. São caminhos previstos, NÃO módulos já implementados. Primeiro testes causais, Kelly bloqueado, short bloqueado, stop, dados ausentes, limites e falhas; depois adaptadores em sombra.
5. REVIEW — docs/AI-TRADING-V2-REVIEW.md. Saída: revisão de causalidade, calibração, segurança, custos, falhas, riscos e resultados negativos. Gate: revisão aprovada; sem autoaprovação por resultado favorável.
6. SHIP — docs/AI-TRADING-V2-RUNBOOK.md. Saída: comando planejado `python ai_shadow_run.py --paper --observe-only`, integração ao iniciador apenas após revisão, métricas e rollback. O comando ainda não existe; não executá-lo. Gate: aprovação para nova sessão experimental; ordens reais continuam fora do escopo.

Cada caminho acima é relativo à raiz declarada; por exemplo o primeiro módulo é C:/Users/Tayson/.codex/.chatgpt-projects/g-p-6ad2cfa25d9c8191b5ffdae7fa012911/work/bottrading/ai_shadow/state.py. Não criar sessão substituta com o saldo atual nem migrar sua identidade sem preservação/revisão.

## Aceitação da fase atual

- Nenhum componente novo escreve em saldo ou execução.
- Serviços e limites não são delegados a probabilidades do modelo.
- Não houve instalação/ativação de AgenKit, Jev ou Grok/Cursor.
- O plano de validação prospectiva existente não foi editado.
- Fases posteriores estão pendentes e nomeadas como tais.

## WHAT COULD I BE WRONG ABOUT?

Confiança pode estar alta em uma pergunta mal definida; calibração geral do fornecedor pode não transferir para retorno cripto. Notícias podem ser falsas, manipuladas ou já precificadas. Dados limitados a um snapshot numérico podem não conter informação que sustente as perguntas qualitativas. Uma estratégia de 20 USDT pode ser inviável após mínimos, spread, taxas e serviços pagos. Liquidez mostrada pode desaparecer. STOP não evita perdas durante indisponibilidade, saltos e ordens inexequíveis. Muitos testes podem selecionar sorte. Kelly mal estimado amplifica o erro. Uma máquina compartilhada ou credencial externa amplia o impacto de prompt injection; agentes não são, por si, isolamento de segurança. Nenhuma dessas limitações é resolvida instalando um harness ou trocando de modelo.
