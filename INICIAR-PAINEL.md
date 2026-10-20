# Um terminal para o Spot Lab

Atualize o projeto e execute na pasta do bot:

```powershell
git pull
python iniciar.py
```

Inicia a simulação de 20 USDT fictícios, o coletor público e o painel em http://127.0.0.1:8768/. Não inicia bot.py watch, não importa saldo real e não envia ordens reais. Requer Python e Node.js 24+. O código de acesso aparece neste mesmo terminal e no log local do painel; não compartilhe o código ou o log.

Mantenha apenas esse terminal aberto. Ctrl+C encerra somente os processos criados pelo iniciador. O saldo e o histórico são preservados; uma interrupção pode deixar a última medição anterior à parada. O painel ficará indisponível após a parada. Falha ou término de um componente encerra os outros, sem reinício automático.

Antes da primeira execução, encerre os processos antigos pelos terminais que os iniciaram usando Ctrl+C. O iniciador recusa porta ocupada, processo paper já ativo, trava do coletor, STOP, drawdown travado ou sessão expirada. Não mata processos preexistentes, não apaga relatórios nem reinicia o saldo. Uma sessão existente continua somente até seu término original. Não remova uma trava de coletor sem conferir se ele está ativo.

Verificação sem iniciar: `python iniciar.py --check`. Outra porta: `python iniciar.py --port 8769`. Não execute junto com outros iniciadores na mesma pasta. Logs privados ficam em `reports/local/launcher-*.log`, ignorados pelo Git.

O mesmo terminal mostra a última compra/venda, patrimônio estimado e resultado realizado quando há nova ordem, mudança de saúde ou a cada cinco minutos. Medições com 180 segundos ou mais são sinalizadas como antigas. Um processo vivo não garante cotação atualizada. Esses avisos não alteram a estratégia nem enviam notificações ao Telegram.
