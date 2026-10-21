# Kronos: laboratorio prospectivo sem ordens

Escopo: BTC/USDT1h,512candles fechados, ate24horas de previsao,1a100 trajetorias.
O padrao e4 trajetorias para medir CPU. Nao e backtest de lucro nem bot ativo.
Nenhuma API paga, Jev, REA ou permissao de negociacao e usada.

O adaptador chama `predict(sample_count=1)` para cada semente, pois a API oficial
faz a media internamente ao usar multiplas amostras em uma unica chamada.
Cada caminho de fechamento e salvo, junto com P10/mediana/P90. Essas faixas
descrevem o modelo, nao probabilidades calibradas do mercado nem sinais de compra.

Versoes: fonte Kronos67b630e67f6a18c9e9be918d9b4337c960db1e9a; checkpoints
oficiais NeoQuasar/Kronos-small e Kronos-Tokenizer-base, com revisoes HF resolvidas
e registradas por previsao. Pesos safetensors, sem executar codigo remoto do Hub.
O modelo roda em CPU com quatro threads, em ambiente separado. PyTorch precisa
de centenas de MB de download e espaco adicional. No Windows, ambiente curto em
LOCALAPPDATA evita o limite de caminhos do ambiente longo do projeto.

## Instalar e executar

```powershell
.\configurar-spot.ps1
.\configurar-kronos.ps1
& "$env:LOCALAPPDATA\SpotLab\kronos-venv\Scripts\python.exe" -u -m spot_engine.kronos_lab --samples 4 --horizon 24
```

O comando gera uma previsao e termina. Nao inicia tarefas recorrentes nem altera
a carteira20USDT. Resultados privados em `reports/local/kronos-lab`, com
identificador unico, timestamps UTC, entradas OHLCV, hashes, sementes,
tempo de inferencia e revisoes. O arquivo `latest.json` alimenta o painel
Estrategias; arquivos anteriores permanecem preservados.

## Avaliar depois do fechamento dos candles futuros

Use o arquivo com UUID, nao `latest.json`, para avaliar uma previsao especifica:

```powershell
& "$env:LOCALAPPDATA\SpotLab\kronos-venv\Scripts\python.exe" -m spot_engine.kronos_lab --evaluate reports/local/kronos-lab/UUID.json
```

Sem candle futuro fechado, statusPENDING: nao ha erro zero nem ganho. Avaliacao
parcial/final compara MAE da mediana com a referencia de preco constante e mede
cobertura da faixa. Uma previsao, especialmente com poucas amostras, nao mede
calibracao robusta. Horizontes sobrepostos nao sao observacoes independentes.
Nao se interpreta fracao de trajetorias ascendentes como confianca de trade.

## Publicacao Opus/Jev analisada

A imagem e uma proposta de processo, nao evidencia de rentabilidade. Mantemos
modulos, regras de risco deterministicas, logs e validacao. Um modelo fornecer
tipos corretos ou confianca nao prova que suas decisoes financeiras sejam boas.
Nao foram ativadas chamadas pagas, instalacao AgenKit, operacoes reais ou novo
modelo de execucao. Os nomes de modelos no texto nao alteram o agente em uso.

Fontes oficiais consultadas21/10/2026:

- https://github.com/shiyu-coder/Kronos
- https://huggingface.co/NeoQuasar/Kronos-small
- https://typesafe.ai/

Testes sem dependencias ML:

```powershell
.\.venv-spot\Scripts\python.exe -m unittest tests.test_kronos_lab tests.test_kronos_view -v
```
