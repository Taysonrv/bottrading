# Scout macro: RSS oficial, somente referência

Fontes verificadas nos diretórios oficiais:

- Fed: https://www.federalreserve.gov/feeds/feeds.htm — feed `press_all.xml`.
- BCE: https://www.ecb.europa.eu/home/html/rss.en.html — feeds `press.html` e `statpress.html`.

```powershell
python -m macro_scout --data-dir CAMINHO_DA_SESSAO
python -m research_desk --data-dir CAMINHO_DA_SESSAO --collect-macro
```

A coleta manual registra o instante inicial de corte, recebimento por fonte, publicação original com timezone, URL oficial, hash SHA256 e snapshot XML local. Usa somente HTTPS com validação TLS, limite de1MB por feed, timeout10s e no máximo1000 itens por fonte. Não aceita URL arbitrária, redirecionamento fora da origem, entidades/DTD XML ou raiz de documento desconhecida. Não desativa certificados quando uma fonte falha.

O recorte é de24h até o início da coleta. Itens posteriores ao corte, antigos ou sem data verificável ficam excluídos, com contadores. Não se substitui uma data ausente por “agora” nem se usa data de atualização como se fosse publicação original. A interface exibe horário local; o JSON preserva UTC e timestamps em milissegundos. Artigos duplicados por URL e publicação mantêm as atribuições dos dois feeds. O relatório retém os100 itens mais recentes e informa a contagem total; o painel exibe até50. URLs com controles ou mais de2048 bytes são descartadas.

`OK` confirma consultas dos feeds, não relevância financeira, cobertura de todo o mercado ou existência de uma oportunidade. `PARTIAL` e `UNAVAILABLE` distinguem falhas de consulta de um recorte sem publicações verificadas. O coletor salva uma nova execução mesmo em falha, sem apresentar uma coleta anterior como recente. Títulos/resumos são dados de terceiros; não se executam instruções ou links contidos neles. O painel escapa texto e só cria links HTTPS para os dois domínios oficiais.

Arquivos em `reports/local/macro-scout/ID/` incluem manifesto, fontes obtidas e relatório. `latest.json` alimenta o painel e o resumo da mesa. O download JSON exige autenticação. Não há crawling dos artigos, análise de sentimento, leitura de X, calendário futuro ou gatilho de compra/venda. A coleção de dados públicos não estabelece causalidade de preço nem vantagem estatística.

No primeiro teste real, o Fed respondeu e os dois feeds do BCE ficaram indisponíveis por validação TLS no ambiente. A limitação foi preservada, não contornada. Investigar a cadeia de confiança é uma tarefa posterior; não instalar certificados ou ignorar verificação para forçar sucesso.
