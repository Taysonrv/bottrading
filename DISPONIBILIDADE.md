# Monitor de disponibilidade

O monitor independente operation_health.py amostra o estado salvo do motor e do radar a cada 15 segundos. Não cria ordens, não retoma sessões e não altera STOP, saldo ou prazo.

Diagnóstico mostra início da medição, intervalos com sinais recentes nas amostras, motor reportado como parado e períodos desconhecidos. Um intervalo só é atribuído ao mesmo estado se as duas amostras concordarem e a distância for de até 45 segundos; intervalos maiores ou mudanças de estado são desconhecidos. Isso é estimativa por amostragem, não prova de funcionamento contínuo.

O checkpoint reports/local/operation-health.json sobrevive ao reinício. Relógio retrocedendo e checkpoint inválido são recusados sem zerar contadores. Últimas 50 transições são preservadas. A medição começa na primeira ativação, sem preencher o passado.

O iniciador atualizado tenta ativar o monitor automaticamente. Uma trava impede duas instâncias. Para um motor que já estava aberto, pode executar separadamente:

```powershell
.\.venv-spot\Scripts\python.exe operation_health.py --data-dir "PASTA_DE_DADOS"
```

Falhas no monitor não interrompem o motor; relatório vencido fica sinalizado. Se o computador inteiro estiver desligado, este monitor local não consegue enviar aviso enquanto estiver desligado. Serviço externo e hospedagem contínua seguem pendentes.
