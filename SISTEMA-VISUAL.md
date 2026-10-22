# Sistema visual do painel

Pacote aplicado sem mudar estratégia, risco, carteira, rotas de API ou processos:

- Paleta central: fundo azul escuro, superfícies em camadas, violeta para navegação e ciano para informação; verde/âmbar/rosa preservam estados.
- Base de texto 14px, apoio 12–13px, títulos de painel 18–19px e métricas 24–32px. Segoe UI/Arial locais, sem download de fontes externas.
- Tabelas com números tabulares, espaçamento uniforme, contraste e rolagem interna quando necessário.
- Navegação lateral de quatro destinos, foco visível e controles com área de toque maior.
- Atalhos internos para Carteira, Gráficos, Entradas e Contexto; respeitam preferência de movimento reduzido.
- Desempenho detalhado recolhível, sem apagar dados ou alterar cálculos.
- Layout móvel com quatro destinos inferiores e colunas empilhadas. Tabelas de contexto não alargam a página inteira.

Validação: testes de interface existentes, inspeção real no navegador, viewport móvel 390x844 com verificação de largura da página e restauração do viewport após teste. Não foi feita certificação formal de acessibilidade.
