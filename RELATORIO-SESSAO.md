# Resultado e cobertura da sessão PAPER

O terminal apresenta patrimônio, realizado líquido, não realizado estimado, taxas, número total de ciclos fechados e estatísticas descritivas do ledger completo. Taxas já estão descontadas do resultado: não subtrair novamente. Profit factor sem perdas fica desconhecido, não infinito. Uma única operação não demonstra vantagem.

Sem posição, caixa reconciliado determina o patrimônio. Com posição, exige marca recente correspondente ao mesmo ledger; se não existir, patrimônio e retorno ficam desconhecidos. O fechamento do prazo não implica venda de inventário.

O relatório usa os segundos amostrados pelo monitor de disponibilidade. Todo tempo antes do início do monitor, depois da última amostra e lacunas já marcadas permanece desconhecido. Contadores inconsistentes, fora do intervalo da sessão ou no futuro não recebem crédito de disponibilidade. Isso não mede uptime contínuo nem revela a causa das interrupções.

Não se inventa Sharpe ou drawdown máximo com uma sequência esparsa de relatórios. A comparação futura entre seis e doze pares precisa preservar sessões, capital e custos separados, além do contexto de mercado e das lacunas. Somar carteiras de experimentos diferentes não é retorno composto.

Para salvar uma fotografia verificável sem alterar o motor:

```powershell
python -m session_performance --data-dir CAMINHO_DA_SESSAO
python -m unittest tests.test_session_performance -v
```

JSONs com identidade exclusiva e `latest.json` ficam em `reports/local/session-performance/`. São fotografias no instante de consulta, não certificações de desempenho. O painel utiliza o mesmo endpoint e polling já existentes. Não há nova ordem, risco, saldo ou prazo.
