# Controlador de Grid e replay público

```powershell
python -m unittest test_grid_replay -v
python grid_replay.py
python grid_replay.py --minutes 10
```

Consulta somente `exchangeInfo` e os últimos 1.000 `aggTrades` de BTCUSDT no serviço público de dados da Binance. Não requer chave, não lê saldos da conta, não envia ordens. Capital simulado: 1.000 USDT.

Com `--minutes 10`, solicita dez minutos encerrados no último minuto UTC completo e pagina por identificador até confirmar um negócio no final ou depois dele. Aceita de 1 a 60 minutos. Os eventos da mesma fração de milissegundo não são descartados: continuação usa `fromId`, não horário acrescido de um. Exige IDs consecutivos entre páginas. Falha em vez de publicar resultado completo se faltarem dados ou ultrapassar 300 páginas.

O intervalo é `[início,fim)`. O negócio usado para confirmar o final não entra nos fills. A duração entre o primeiro e o último evento pode ser um pouco menor que a janela solicitada, por ausência de negócios nas extremidades.

A coleta salva dados públicos e os filtros consultados em `replay-data/last-public-input.json` (ignorado pelo Git). Para repetir exatamente essa entrada, sem rede:

```powershell
python grid_replay.py --input replay-data/last-public-input.json
```

Esse arquivo é substituído pela próxima coleta bem-sucedida; preserve uma cópia para manter a amostra. Uma coleta interrompida não substitui o relatório anterior por um replay parcial. O relatório inclui hash dos dados para conferir reprodução. Não use arquivos locais de procedência desconhecida como prova independente de qualidade dos dados.

## O que foi conectado

`grid_controller.py` coordena um episódio de quatro ordens de compra, de até 25 USDT cada incluindo taxa, com degraus fixos de 0,5% abaixo da âncora. Âncora é somente o primeiro negócio da amostra. Não seleciona a faixa depois de consultar as máximas/mínimas futuras.

Quando uma compra termina, coloca uma venda um degrau acima; quando a venda termina, repõe a compra. Preenchimento parcial não provoca reposição prematura. A quantidade original arredondada é reutilizada, sem martingale. As ordens novas só podem usar eventos posteriores.

Ruptura de ±3% cancela as pendências e encerra o episódio; não reinicia nem liquida as posições automaticamente. Os saldos restantes continuam marcados ao mercado. STOP e drawdown do simulador prevalecem. Falhas na submissão de reposições são registradas, não ignoradas ou convertidas em fills fictícios.

## Alcance dos dados

Os negócios agregados contêm preço, quantidade, horário, identificador e lado maker. O replay exige IDs consecutivos e horários não decrescentes. Não ordena uma sequência inválida para ocultar lacunas. Usa `m=true` como agressor vendedor, conforme a semântica do comprador maker.

É uma amostra recente e curta, não histórico suficiente para avaliar retorno, regime de mercado ou estabilidade. Não há classificador de lateralização nesse controlador inicial. Os filtros são os atuais; não são filtros históricos reconstruídos. Sem captura de livro, a fila e a latência permanecem aproximações; participação de 10% é hipótese do simulador.

Fonte: [dados de mercado da API Spot](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market). Os filtros usados ainda são um subconjunto das regras da corretora, conforme `SIMULADOR-LIMITADAS.md`.

## Resultado e painel

Produz `reports/2026-10-18-grid-replay.json` e `.md`, substituindo esses arquivos a cada execução. Inclui período efetivo, IDs, hashes do código/dados, fills, filtros, saldo, inventário, erros de reposição e ordens abertas antes do corte. Ao finalizar, cancela ordens pendentes e libera reservas. Não realiza venda de encerramento nem estima anualização.

O diagnóstico também registra mínima/máxima da amostra, primeiro nível de compra aceito, eventos estritamente abaixo desse nível e quantos tinham agressor vendedor. Distingue nível não alcançado de nível atravessado sem execução; não trata toda ausência de fill como falha da estratégia. Esses contadores descrevem o nível inicial, não comprovam que uma ordem permaneceu elegível em todos os eventos. Volume mínimo, cancelamentos e travas também precisam ser examinados.

O JSON guarda o diário completo das ordens: preço, quantidade, remanescente e estado final, inclusive ordens canceladas no corte. A estimativa líquida adicional desconta a taxa configurada sobre o inventário final; não modela slippage ou garante liquidez de saída. Esse valor não altera o patrimônio marcado exibido no painel.

A aba Estratégias mostra esse relatório com o rótulo Teste operacional. Nunca substitui os cartões da carteira ou a validação de estratégia.

Para atualizar o painel: encerre somente `dashboard.py` com Ctrl+C, execute `git pull --ff-only`, inicie `python dashboard.py` novamente e atualize a página. O observador pode continuar aberto: esta etapa não altera seu código ou configuração.

Nenhuma aprovação histórica ou execução real é habilitada. Faltam replay prolongado com paginação e controle de integridade, persistência/reconciliação, política de saída implementada e avaliação fora da amostra antes de integrar ao motor ativo.
