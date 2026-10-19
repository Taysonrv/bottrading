# Tela MetaMask

Acesse MetaMask no menu do painel local. Reutiliza autenticação, estilo e atualização de relatórios do painel principal, sem conectar a extensão ou conceder acesso de negociação.

Mostra saldos por rede do relatório local `metamask-balances.json`, cotações de venda/recompra de `wallet-quote-research.json` e simulações Solana de `solana-cost-research.json`, todos dentro de `reports/local/` e ignorados pelo Git. Nenhum relatório privado deve ser publicado.

As consultas são manuais. O painel relê os arquivos a cada 10 segundos; isso não atualiza preços na blockchain. Horários individuais são exibidos. Ausência de relatório gera estado vazio e nunca saldos fictícios apresentados como reais. Os saldos importados são parciais e não constituem carteira completa ou patrimônio total em dólares.

A calculadora interativa usa capital de 20 USDC por padrão, variação do preço, custo proporcional por lado e gas total informado pelo usuário. Estes parâmetros são hipóteses; não são taxas verificadas. Gráfico mostra resultado para cinco cenários de movimento. Não registra ordens, não cria histórico de rentabilidade nem modifica carteira. Lucro realizado fica explicitamente não medido, e transações executadas por este módulo são zero.

Ações reais, assinatura, aprovação de tokens e execução automática não estão disponíveis. O botão de desligar Binance não aparece nesta tela para evitar confundir os dois módulos. O laboratório noturno continua independente. Logs brutos e bytes de transação não são expostos pelo resumo das simulações.
