# Build V2 offline — registro de implementação

Fase: build offline, aguardando gate de revisão. Uso de processo equivalente sem AgenKit aprovado pelo usuário. Nenhum harness instalado, transporte Jev ligado ou alteração do motor paper existente. O plano continua frozen=false: esta demonstração não começa coleta ou avaliação prospectiva.

## Implementado

- ai_shadow/contracts.py: contrato normalizado estrito, domínios, números finitos, distribuição de probabilidades e confiança de Choice consistente. Não é parser de resposta HTTP real da TypeSafe.
- ai_shadow/collector.py: replay limitado de fixtures, cutoff de recebimento, cópia defensiva e sequência crescente de bookTicker. Não é coletor WebSocket de produção nem reconstrução de L2.
- ai_shadow/state.py: mid/spread/imbalance L1, volatilidade em 60 log-retornos de minuto, validação de timestamp e janela. Não mede 400 tokens: token_count_verified=false.
- ai_shadow/journal.py: SQLite WAL/synchronous FULL, escritor exclusivo por lock de SO, IDs únicos, divergência de estado detectada, plano/código fixos e pedidos pendentes marcados como unknown no reinício. Custo permitido nesta etapa: apenas zero. O journal da demonstração armazena os dados artificiais usados no cálculo.
- ai_shadow/risk.py: reconciliação de caixa/exposição da conta fictícia, 15% drawdown travado, 3% perda diária travada até dia UTC seguinte, checkpoint persistente e bloqueio de relógio retroativo. Checkpoint perdido não reinicia proteção.
- ai_shadow/policy.py: HOLD/REVIEW_REQUIRED/SHADOW_CANDIDATE; nunca ordem. Score fracionário não é arredondado para liberar sinal. Crise/pedido de revisão pode ser persistido no journal; o runner passa esse journal. Não existe função para reativar versão automaticamente.
- ai_shadow/jev_client.py: adaptador de fixture explícita e circuit breaker persistente. Não importa SDK, chave, urllib ou cliente de rede. Não mede latência real; simula resposta tardia como caso de teste.
- ai_shadow/calibration.py: rótulo futuro de 60min com tolerância e custos, dados faltantes não imputados, Brier da probabilidade explícita do evento e baseline cortado temporalmente. A função não prova que uma quote selecionada foi a primeira recebida no mundo real; isso depende da futura ingestão auditável.
- ai_shadow/review.py: revisão determinística de labels artificiais, sempre inconclusiva, sem autoaprovação/autoaplicação. Não é agendamento noturno nem chamada a modelo pesado.
- ai_shadow_run.py: uma execução de demonstração, com preços, conta e resposta artificiais claramente rotulados. Captura dados e julgamento no journal separado; conta paga e ordens ficam em zero. Não é um processo contínuo.

## Executar demonstração

Na raiz do checkout de desenvolvimento:

```powershell
python -m unittest tests.test_ai_shadow -v
python ai_shadow_run.py --paper --observe-only
```

Não inicia o bot atual, não pede chave e não consulta preço real. Resultado em reports/local/ai-shadow-offline/session.sqlite e demo-report.json, ignorados pelo Git. Reexecutar o mesmo evento não avalia outra vez. Código/plano diferentes bloqueiam reutilização: preserve a pasta anterior antes de criar outra sessão de teste; não edite o SQLite para contornar a validação.

SHADOW_CANDIDATE em uma fixture apenas mostra que os filtros aceitaram uma entrada artificial. Não é compra, recomendação, lucro simulado, prova de edge ou validação do modelo Jev. A demo utiliza timestamps sintéticos em segundos Unix, não horário de coleta atual.

## Test-first e limites

Os testes foram criados antes dos módulos e falharam inicialmente por módulos ausentes. Depois foram acrescentados casos que reproduziram overflow, duplicação inconsistente, inventário sem reconciliação e pedido de revisão não persistente; as implementações foram corrigidas antes da suíte final.

Não conectado nesta fase: API Jev, relógio externo, dados reais V2, transmissão de dados financeiros, preços/cotas de provedor, coleta e rotulagem prospectiva, nova aba no dashboard ou integração ao iniciar.py. Não há prova de isolamento forte entre processos do mesmo usuário. Não há tokenização do provedor, calibração real, benchmark de retorno ou autorização de trading real.

## Próximo gate

Revisar o build offline e os casos de falha. Só depois publicar/ativar uma nova sessão de observação; qualquer chamada paga exige os gates de orçamento, credenciais e dados. A sessão paper atual não foi alterada. O relatório de revisão ainda não deve declarar o sistema pronto para produção.
