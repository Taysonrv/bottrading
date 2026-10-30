# Disponibilidade e motivos das decisões

O terminal inclui a seção “Saúde e decisões verificáveis”, alimentada pelo mesmo polling existente. Não há nova carteira, novo timer de frontend ou mudança de regras de entrada e risco.

O backend lê o ledger completo em modo SQLite somente leitura e reconcilia sua identidade. Calcula cada ciclo fechado com taxas de compra e venda usando Decimal. Exibe até 30 ciclos, mas informa totais de todo o ledger. Sem acesso válido, mostra resultado desconhecido.

Saúde distingue STOP, prazo encerrado, motor sem confirmação recente (60s), motor encerrado e supervisor sem confirmação recente (30s). A idade do radar é mostrada separadamente; contexto acima de 180s é marcado antigo. Isso mede os relatórios salvos, não faz prova de processo ativo via sistema operacional.

O diário operacional mostra os 30 últimos eventos dentro de uma leitura limitada a 64KB. Preserva código de saída, componente e motivo registrado. Encerramento sem evidência mantém causa desconhecida. Informações sensíveis e campos arbitrários não são projetados.

O supervisor já recupera painel/coletor com três tentativas atrasadas; agora seus próximos relatórios também incluem os contadores. Não reinicia o motor automaticamente: uma saída pode representar STOP, prazo ou corrupção. Se o próprio supervisor ou computador parar, ele não consegue recuperar a si mesmo. Isso exige um serviço externo de sistema operacional, ainda não instalado. Não há promessa de funcionamento 24/7 enquanto essa dependência existir.

Motivos de venda vêm dos fills. O radar oferece contexto atual por par, nunca justificativa retroativa para uma compra antiga. Indicadores não persistidos na criação da ordem são explicitamente “NOT_RECORDED_AT_ORDER_TIME”. Uma prévia viável não prova que os limites de risco autorizaram uma ordem.

## Testes

```powershell
python -m unittest tests.test_operational_audit -v
node test_dashboard_frontend.cjs
```

Para carregar o novo backend, reinicie apenas o painel quando houver supervisor saudável. Não reinicie saldo, não remova STOP e não estenda sessões como parte de uma atualização visual. O motor continua verificando suas proteções enquanto o painel é atualizado.
