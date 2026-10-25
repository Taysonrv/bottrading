# Upgrade: pesquisa, reflexo e controle de risco

25/10/2026. Engenharia autorizada pelo pedido do usuário. Modo entregue:
**observação com dados públicos reais, sem inferência paga ou ordens**.
Nenhum arquivo de spot_engine/, ai_shadow/ ou v3_engine/ foi alterado.
Identidades e ledgers das sessões existentes foram preservados.

## O que a imagem especifica e o que foi entregue

| Regra | Implementação / limite atual |
|---|---|
| Separar BRAIN e REFLEX | Pesquisa e relatórios permanecem offline; quant_control/ recebe somente estado numérico e valida contratos |
| Modelo apenas julga | Contrato recusa campos extras, inclusive tamanho/ordem; nenhuma ferramenta de execução existe nessa camada |
| Snapshot causal | REST L1, spread, imbalance, RV60 retornos15m, ATR14, retornos1/4/60, inventário e perdas calculados em código |
| Menos de 400 tokens | JSON numérico limitado a 1000 bytes; contagem Jev não verificada e gate permanece bloqueado; bytes não são tokens |
| Jev em um request paralelo | Template documentado com cinco perguntas Choice; parser valida todas as distribuições e confianças; sem transporteHTTP ativado |
| Qualidade>=2, confiança>.80, safe | Gates explícitos; Spot long/caixa, sem short, e regimecrisis encaminha revisão |
| Risco independente do modelo | DD 10%, perda diária 3%, posição/pending, exposição 40%, STOP e prazo verificados em código; política nunca retorna autorização de ordem |
| DD 15% da imagem | Mantido 10%, limite mais restritivo já acordado; não aumentamos tolerância depois de testes negativos |
| Kelly fracionado | Função de pesquisa capada em 1/4; runtime desativado, pois direção/confiança não são probabilidade de lucro com payoff validado |
| Revisão se confiança<.60/crise | REVIEW_REQUIRED, motivos no journal; nenhuma chamada automática a modelo caro ou promessa de análise Opus realizada |
| Revisão noturna | Ao iniciar e mudar o diaUTC, lê journal completo e ledger completo reconciliado; salva propostas versionadas, sem autoaplicar |
| Brier | Rotulador causal de 1h e Brier multiclasse por modelo/schema/custos; sem respostas reais, métrica permanece desconhecida |
| AgenKit / seis fases | Manifesto local de especificação, arquitetura, plano, build, review e ship; AgenKit não instalado ou declarado como executado |
| Pesquisa fundamental 5–10 setups | Ainda não conectada. Unlocks, receita, TVL e concentração não inventados; nenhum finalista aprovado |
| 24h contínuas | Comando de observação com duração explícita até 48h; não renova sessão de trading, não altera capital e não garante disponibilidade do computador |

## Arquitetura e fontes de verdade

```text
Binance pública -> candles fechados + REST L1 -> snapshot numérico
Ledger PAPER reconciliado --------------------> inventário / perdas
                         |
                         v
               Contrato de decisão tipada
               Adaptador Jev (DESATIVADO)
                         |
                         v
                  Gates em código
                         |
                         v
             Journal / revisão / painel
                  SEM rota de ordens
```

O broker existente continua sendo o único dono de reservas, tamanhos, filtros
financeiros e verificação de STOP antes das ordens. A camada nova não o chama.
Não há API de corretora privada, credencial Binance, assinatura de carteira,
saque, compra real, ordem de teste ou mudança de saldo neste pacote.

## Estado e causalidade

`state.py` exige 61 candles consecutivos 15m fechados, UTC, e quote recebido em
até 2s. Rejeita candle futuro, lacuna, book cruzado, quantidades inválidas e
risco numérico fora de domínio. Recepção local não é timestamp da exchange:
`origin_timestamp_available=false`. Imbalance é só L1, não toxicidade de fluxo;
`flow_verified=false`. Dado de risco ausente permanece `null`, nunca zero.
O cutoff vem depois da leitura do ledger, sem incorporar uma transação futura.

O payload usa campos numéricos compactos com legenda nas perguntas. O limite
de 1000 bytes evita crescimento acidental. Sem tokenizer compatível medido,
`token_count_verified=false`; não afirmamos ter cumprido 400 tokens Jev.

Decisões são deduplicadas por código/par/candle. Segurança é reavaliada com
estado atual a cada ciclo, inclusive STOP, sessão, posição e risco. Input de
modelo anterior a 2s não passa como uma decisão fresca. Não há nova inferência
depois de timeout desconhecido ou retomada de request incompleto.

## Contrato Jev e ausência de IA fictícia

Fontes oficiais consultadas em 25/10/2026:

- https://docs.typesafe.ai/introduction/quickstart
- https://docs.typesafe.ai/confidence
- https://docs.typesafe.ai/primitives/choice

O contrato trata confiança conforme a fórmula Choice publicada, distinta da
probabilidade escolhida. Por exemplo, pmax=.94 em três opções implica
confiança=.91. O campo qualidade usa Choice 0/1/2/3: Score do provedor pode ser
fracionário e não é truncado silenciosamente.

`jev.py` prepara o request e valida respostas fornecidas. **Não contém
transporteHTTP ou chamadas pagas**. `DisabledProvider` é a única implementação
instanciada pelo serviço. A presença de TYPESAFE_API_KEY no ambiente não ativa
nada. Não foi medido 81ms; provider_latency_ms permanece null. Para conectar
inferência real, faltam transporte autenticado, configuração segura da chave,
orçamento de chamadas aprovado, tokenização verificada e revisão do adaptador.
Não envie chaves pelo chat.

O endereço agenkit.xyz indicado na imagem não ficou acessível nesta consulta;
não instalamos script remoto nem um pacote de nome semelhante sem verificar
procedência. O manifesto de seis fases é local, sem alegação de ser AgenKit.
Não há simulação de aprovações humanas ou uso de Claude Opus neste serviço.

## Calibração, Kelly e revisão

`calibration.py` exige entrada posterior à previsão e saída de 1h posterior à
entrada, com recebimento conhecido até o cutoff. Fixtures não entram como
previsões reais. A coorte separa modelo/schema/definição de custos e recusa
duplicados por par e instante. O Brier é multiclasse, faixa 0–2; não misturar com
o Brier binário antigo. Horizontes e ativos podem ser correlacionados; a métrica
não é uma validação independente nem vantagem econômica.

`quarter_kelly_research` usa p_win e payoffs líquidos do mesmo alvo validado,
nunca confidence como substituto. A função é somente aritmética de pesquisa;
o serviço mantém kelly_enabled=false.

`review.py` lê todos os registros da sessão, não somente os últimos 50 do painel.
Lê também o ledger reconciliado completo. Failures de estado são registrados
uma vez por par/candle. Sem provedor real, genuine_model_predictions=0,
mature_labels=0 e Brier=null. Isso não mede acerto de IA ou lucro perdido.
As sugestões ficam em JSON com auto_apply=false; nenhum arquivo de estratégia
ou schema é reescrito automaticamente durante a noite.

## Operação

```powershell
git pull
python -m unittest tests.test_quant_control -v
node test_dashboard_frontend.cjs
python quant_control_run.py --data-dir . --hours 24 --with-panel --port 8768
```

Uma aplicação em um terminal: painel local e controle de pesquisa no mesmo
processo. Se o painel já estiver rodando, use sem `--with-panel`; não duplique
serviços. O serviço respeita STOP global e `reports/local/quant-control/STOP`.
Não remove travas nem renova carteira/prazo expirados. Não inicia ordens.

Arquivos locais separados:

- `reports/local/quant-control/journal.sqlite`: estados/decisões/erros, lock e identidade.
- `latest.json`: status atual e gates de cada par.
- `review-latest.json` e `reviews/*.json`: revisão diáriaUTC versionada.

Mudança de identidade recusa reutilizar journal. Preserve e revise a sessão
anterior; nunca altere o hash antigo para fazê-la passar. O controle é exibido
na viewV3 existente, com confiança/Brier desconhecidos e IA desativada visíveis.

## WHAT COULD I BE WRONG ABOUT?

- L1 e candles não descrevem toxicidade real de fluxo, fundamentos ou edge.
- Probabilidades calibradas em outro domínio podem falhar em cripto.
- Boa calibração não garante lucro depois de spread, taxas e slippage.
- Provedor pode mudar versão/custo/latência; os números da imagem não são medições locais.
- Computador suspenso ou processo interrompido encerra coleta; não há disponibilidade retroativa.
- Todas as hipóteses já reprovadas continuam reprovadas. Mais IA não substitui
  evidência de vantagem, execução viável e validação independente.
