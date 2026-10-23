# Estabilidade do supervisor PAPER

O supervisor mantém um diário local em `reports/local/supervisor-events.jsonl` com início, término e código de saída de seus componentes. Reinícios de painel ou coletor têm eventos próprios. O diário não inclui ambiente, chaves ou código de acesso e mantém um segmento anterior ao atingir aproximadamente 1 MB.

Se uma execução anterior deixou estado ativo sem registro de encerramento, a próxima inicialização registra uma lacuna com causa desconhecida. Isso não identifica se houve suspensão do PC, encerramento externo ou falha do sistema operacional.

## Recuperação limitada

Enquanto o processo do motor permanece vivo, o supervisor pode tentar recuperar **somente seus próprios processos de painel e coletor de mercado**, no máximo três vezes por componente, esperando 15, 30 e 60 segundos. Não recupera um painel externo iniciado com `--execution-only`.

O motor nunca é reiniciado por essa política. STOP, término de prazo, falha de dados/ledger e limites de risco não são removidos ou reinterpretados. Nenhuma carteira é reiniciada. O coletor de contexto e monitor executados como serviços internos continuam com seu tratamento existente; não são cobertos pela recuperação de subprocessos.

A recuperação não funciona se o próprio supervisor for encerrado, o computador desligar ou suspender. Operação contínua exige depois uma implantação supervisionada no sistema operacional, com regras explícitas para retomada do motor.

## Ativação e testes

As mudanças no supervisor entram em vigor na próxima inicialização de `python operar.py --engine portfolio --port 8768 --start`. Não execute outro supervisor enquanto uma sessão estiver ativa. A sessão em execução não é interrompida apenas para atualizar este código.

Teste com `python -m unittest tests.test_supervisor_health tests.test_system_integration -v`. Os testes verificam atrasos, limite de tentativas, proibição de reiniciar o motor, privacidade do diário e distinção entre encerramento limpo e lacuna.
