# Simulação de custos GRASS/USDC

Execute `python solana_cost_research.py --wallet ENDERECO_PUBLICO_SOLANA`. Compartilha o endereço público com Jupiter para construir swaps sem assinatura e com o RPC Solana para consultar/simular. Não forneça seed ou chave privada. O módulo não assina nem transmite transações e bloqueia métodos RPC fora da lista de leitura/simulação.

Consulta venda de 1 GRASS por USDC e recompra com o valor cotado. Cria transações temporárias sem assinaturas, consulta getFeeForMessage e chama simulateTransaction com sigVerify=false. Isso não executa nem altera a rede. Não persiste os bytes das transações. Não oferece caminho para assinar/enviar, e não valida todas as instruções para uso real.

As simulações são independentes. A primeira não credita USDC na carteira, portanto a segunda pode falhar por saldo insuficiente. Uma taxa retornada para uma mensagem cuja simulação falhou não valida o custo operacional da recompra. Falhas ficam registradas; não são consideradas aprovação.

Prioridade configurada em até 10.000 lamports por perna. getFeeForMessage já inclui a prioridade da mensagem; não somar duas vezes. Não inclui todos os possíveis depósitos de aluguel. Saldos e simulações são observados em slots distintos. Não concluir custo exato por simples diferença de saldos.

Relatório privado em `reports/local/solana-cost-research.json`, ignorado pelo Git. Contém logs de simulação potencialmente associados à carteira e não deve ser publicado. A saída não ativa o bot ou altera o laboratório Binance.

Fontes:
- https://developers.jup.ag/docs/swap/v1/build-swap-transaction
- https://solana.com/docs/rpc/http/simulatetransaction
- https://solana.com/docs/rpc/http/getfeeformessage
