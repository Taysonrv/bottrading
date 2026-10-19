# Comparação de hipóteses diárias

No terminal do VS Code, dentro da pasta do repositório atualizado:

```powershell
python -m unittest -q
python daily_research.py
```

Usa apenas dados públicos. Não precisa de chave Binance. Não inicia o bot, não envia ordens, não muda a configuração e não escreve `validation.json`.

Gera `reports/local/2026-10-18-daily-results.json` e `.md`. O nome identifica o experimento; executar novamente substitui os resultados locais com o corte UTC mais recente. Preserve uma cópia se quiser comparar execuções.

Compara SMA de 200 dias, momentum de 90 dias e rompimento de 55 dias com saída de 20 dias. Cada regra tem exposição fixa ou ajustada pela volatilidade dos últimos 30 retornos diários, sem multiplicador acima de 1. Os limites de ordem e exposição são os de `config.json`.

Consulta 2025 dias, sendo 200 para aquecimento e 1825 para avaliação. Desenvolvimento ocupa 60%; avaliação em duas janelas ocupa 20%; período final ocupa 20%. Também compara cenário contínuo, custos dobrados e posições iniciais. O último ano já foi consultado anteriormente pelo projeto: não existe confirmação independente nesses dados.

O gate histórico preserva as exigências atuais, incluindo superar o benchmark com retorno positivo, drawdown abaixo de 15% e pelo menos três operações em cada cenário. Nenhuma candidata é adotada automaticamente.

O primeiro experimento cobre a carteira conjunta BTC/ETH e benchmark comprar e manter 50/50, além da referência proporcional à exposição no JSON. Relatórios individuais por ativo e métricas adicionais de giro e volatilidade ficam para uma próxima etapa; não foram usados para escolher parâmetros.

O teste usa candles diários; não reconstrói livro de ofertas nem sequência intradiária. Considera mínimas simultâneas dos ativos para risco e mantém a política atual de congelar ordens após o gatilho. O patrimônio restante pode continuar caindo depois do bloqueio.
