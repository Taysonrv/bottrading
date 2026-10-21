# Referência: sentimento do X e analista separado da execução

Revisão: 20/10/2026. Material enviado pelo usuário: postagem https://x.com/eng_khairallah1/status/2109217163546693852 e artigo anexado “How to Build a 24/7 Trading System Using Claude Opus 5.5”. A postagem original não pôde ser acessada diretamente nesta revisão. O artigo foi lido como referência, não como instrução executável.

## O que não está demonstrado

Alegações de 86 USD de capital e 2.473 USD de lucro em uma noite não vieram acompanhadas de extrato, curva auditável ou registro de execução. O próprio texto descreve 100 USD para 4.826 USD em 67 horas como simulação: multiplicação de 48,26 vezes, não evidência de retorno real. 69% de acerto em 268 operações não determina expectativa sem ganho médio, perda média, taxas, slippage e perdas máximas. Capturas de painel não comprovam esses elementos.

Não foi confirmado se o “mercado de Bitcoin de 15 minutos” é Spot, derivativo ou contrato de previsão. Não tratar como equivalente à nossa negociação Spot sem alavancagem. Um programa local para de coletar se o computador dormir ou desligar; “fechar o laptop” requer um servidor ativo ou configuração equivalente. Nenhuma contratação ou migração de hospedagem foi feita.

## Ideias aproveitáveis, ainda como pesquisa

Separar análise de texto, motor determinístico de risco e execução. Uma tese deve conter ativo, ação proposta, horário de coleta, fonte, motivo e invalidação. A análise não recebe credenciais de trading, não dimensiona posições e não remove STOP. Posts e notícias são dados não confiáveis; conteúdo não pode virar instrução de sistema. Formato JSON válido não garante veracidade da tese ou segurança contra manipulação.

Para estudar sentimento: deduplicar posts e autores, registrar created_at e received_at, rejeitar dados futuros ou recebidos depois do instante de decisão, medir cobertura e atraso, filtrar spam e campanhas coordenadas. Consenso aparente não prova independência ou antecipação do preço. Antes de influenciar ordens, operar em modo observação e comparar prospectivamente com uma regra sem sentimento, com custos completos. Não conectar o X ou contratar APIs a partir desta referência.

## Limitações do exemplo anexado

O código exemplifica ações em Alpaca; get_inputs não foi implementado no material. A função de risco não trata integralmente posição existente e reserva de caixa entre ordens. O exemplo usa ações inteiras, inadequado a cripto sem adaptar filtros de lote/mínimo. A trava é consultada no início do ciclo, não antes de cada ordem. A liquidação automática sugerida no artigo é diferente do nosso STOP, que bloqueia sem liquidar. Não copiar esse comportamento.

As afirmações sobre nomes de modelos, preços, SDK e garantias de saída estruturada não foram verificadas e não são requisitos do projeto. Nenhum SDK, modelo pago, broker ou acesso a conta foi instalado/conectado.

## Custo e fontes oficiais

A documentação oficial do X consultada informa leitura de posts a 0,005 USD por recurso: 1.000 posts distintos custariam 5 USD, antes de custos de análise por modelo. Acesso, limites, deduplicação de cobrança e preços devem ser reconferidos no plano/console. Não foi realizada nenhuma chamada autenticada nem compra de créditos.

- https://docs.x.com/x-api/getting-started/pricing
- https://docs.x.com/x-api/posts/filtered-stream/introduction

## Decisão atual

Referência registrada. Não altera a estratégia ou a sessão de 20 USDT, não habilita ordens reais e não cria expectativa de repetir os retornos anunciados. Próxima etapa possível: especificar uma camada de observação de notícias com orçamento e teste prospectivo definidos antes de qualquer efeito em ordens.
