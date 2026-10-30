# Mesa integrada de pesquisa — primeira etapa

Um comando liga importação de evidências, avaliação explícita e resumo. Isso não é ainda uma equipe de agentes noturnos nem pesquisa nova de todo o mercado.

```powershell
python -m research_desk --data-dir CAMINHO_DA_SESSAO
python -m research_desk --data-dir CAMINHO_DA_SESSAO --replay-csv CAMINHO_DO_CSV_ORIGINAL
python -m research_desk --data-dir CAMINHO_DA_SESSAO --collect-macro
```

Sem CSV, importa três fontes fixas já existentes, preservando hashes e horários: EMA/ATR15m com janelas móveis, EMA20/50 1h com saída única e pullback 1h. Com CSV, também reexecuta as duas hipóteses horárias com regras congeladas; exige o hash do histórico original. Não testa novos parâmetros e não usa uma repetição como evidência independente.

Antes do replay salva `manifest.json`, com protocolo, fontes e hashes do código. Cada execução tem diretório exclusivo em `reports/local/research-desk/`; saídas do replay têm seus próprios hashes. Depois salva avaliação JSON, resumo Markdown e `latest.json`. Nenhum saldo, ordem, STOP ou arquivo de validação do motor é alterado.

## Critérios e limites

As hipóteses horárias precisam de retorno positivo após custos, ao menos30 ciclos, drawdown até10%, três de quatro blocos positivos, stress com custos dobrados positivo, superar buy & hold e não ter saídas abertas/bloqueadas ou drawdown travado. Ainda assim, os dados importados já foram inspecionados: **não existe OOS intocado neste conjunto**. Um campo `approved=true` ou `independent_oos=true` no relatório não muda esse fato. Não se inventa score18/25 ou ranking de vencedoras.

O construtor fica `BLOCKED_NO_VALIDATED_STRATEGY`. Isso não impede um ensaio PAPER exploratório explicitamente identificado, mas não promove uma hipótese rejeitada a estratégia validada. As três avaliações podem — e atualmente devem — terminar sem candidatas aprovadas.

O resumo inclui resultados conhecidos, causas possíveis de falha, estado da sessão PAPER e pendências. Contexto salvo não é apresentado como notícia/preço ao vivo. O download Markdown exige a mesma autenticação do painel; o conteúdo é apresentado como texto, nunca instruções ou HTML executável.

## O que ainda falta

Cobertura ampliada além dos três RSS oficiais macro; avaliação das janelas prospectivas registradas; testes de dependência/seleção múltipla e Monte Carlo de drawdown; agenda, entrega às07h30 e revisão semanal; infraestrutura sempre disponível. O registro local e a coleta manual futura já estão em `prospective_protocol.py`, separados da carteira e sem promoção automática. Nada disso foi agendado nesta etapa. O parâmetro `--collect-macro` coleta publicações oficiais com datas e hashes; elas não alteram os testes ou sinais. Nenhuma mensagem externa, conexão de conta ou chamada de IA paga é realizada.

```powershell
python -m unittest tests.test_research_desk -v
node test_dashboard_frontend.cjs
```
