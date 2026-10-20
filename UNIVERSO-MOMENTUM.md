# Seleção experimental entre SOL, RENDER e PEPE

`python momentum_universe_research.py` mantém a mesma lógica do motor anterior small_cap_research e altera somente os pares candidatos para SOLUSDT, RENDERUSDT e PEPEUSDT. Não copia proporções 45/30/25 ou operações de terceiros. Esta é uma adaptação própria de uma proposta incompleta de portfólio, não reprodução da estratégia anunciada.

Compara 30 dias contínuos e três períodos de 10 dias. Cada janela recebe seus próprios 20 USDT fictícios e 60 horas anteriores apenas para aquecimento; as barras negociadas não se sobrepõem. O contínuo preserva posições entre os períodos, enquanto janelas reiniciam em caixa, portanto seus resultados não devem ser somados ou tratados como equivalentes ao contínuo. Todos os dados já foram consultados; as janelas não são validação prospectiva independente.

Uma posição por vez, até 5 USDT por compra incluindo custos, sem aumentar ordem para alcançar mínimos. Filtros atuais, taxa/slippage de 0,1% cada por lado no cenário normal e dobrados no stress. Sinal de pullback com tendência em médias de 20/60 e momentum de seis horas; entre candidatos executáveis escolhe o maior momentum passado. Saída por alvo líquido de 1%, perda líquida de 2% ou perda de tendência. Sinal no fechamento, execução aproximada na abertura seguinte. Resíduos podem impedir nova posição. Sem spread histórico, fila ou validação completa dos filtros.

STOP/drawdown de 15% bloqueiam ordens, sem garantir liquidação. Retorno terminal inclui saída estimada das posições, não necessariamente executável pelo mínimo. Estudo separado da sessão contínua e do plano prospectivo congelado. Não há mudança de estratégia em uma posição aberta. Não habilita dinheiro real ou aprovação automática.

Arquivo reports/local/momentum-universe.json, ignorado pelo Git, e tabela na aba Estratégias. Critério para próxima etapa: observar robustez, número de operações, custos e viabilidade; não escolher a maior linha positiva isolada. Requer novo plano prospectivo para avaliar este universo com dados futuros sem o adicionar retroativamente ao plano anterior.
