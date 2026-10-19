# Pesquisa de venda e recompra, somente leitura

Execute `python wallet_quote_research.py`. Consulta 1 GRASS → USDC → GRASS via Jupiter e 50 BCOIN → WBNB → BCOIN via PancakeSwap V2. Não usa endereços pessoais, chaves, assinaturas, aprovações ou métodos de envio. Resultados ficam em `reports/local/wallet-quote-research.json`, ignorados pelo Git. Não há atualização automática ou integração de execução com o bot.

As duas pernas são cotações independentes no estado observado. Não há atualização contrafactual dos pools após a venda. Na BNB Smart Chain as leituras de cotação usam o mesmo bloco; a amostra de gasPrice é separada. Na Solana cada cotação pode ter slot diferente. Taxas das rotas estão refletidas no resultado cotado, sem taxas adicionais do nosso aplicativo.

Slippage é tolerância, não taxa garantida: 50 bps na consulta Jupiter. O retorno cotado em tokens não inclui gas, prioridade, aluguel de contas, aprovações, impostos de token ou falhas. Custos nativos apresentados são cenários hipotéticos, não estimativas obtidas da execução. Valores SOL são convertidos em USDC por outra cotação de 1 SOL.

Não verifica honeypot, impostos, capacidade de execução, melhor rota global ou saldo necessário. BCOIN é cotado contra WBNB, que não é dólar estável. Não envolve pontes. Só preparar transações e simular suas instruções permitiria estimar custos de forma mais concreta; executar exige etapa separada de autorização.

Jupiter V1/lite é um serviço legado sujeito à disponibilidade. Se indisponível, o relatório identifica a falha em vez de inventar preços. Não ativar estratégias com base em uma fotografia de cotações.

Fontes:
- https://developers.jup.ag/docs/swap/v1/get-quote
- https://developer.pancakeswap.finance/contracts/v2/addresses
