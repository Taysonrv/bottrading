# V2 — publicação da demonstração offline

Publicação autorizada pelo usuário após revisão. Somente demonstração com fixtures; nenhuma integração ao motor atual ou provedor externo.

## Obter e testar

Na pasta do repositório, em outro terminal (não interrompa iniciar.py):

```powershell
git pull
python -m unittest tests.test_ai_shadow -v
python ai_shadow_run.py --paper --observe-only
```

O comando encerra após uma demonstração; não abre porta, não inicia outro painel, não usa chave, não consulta APIs e não emite ordens. Todos os preços, conta e resposta são artificiais. SHADOW_CANDIDATE significa apenas aprovação de filtros sobre a fixture, não sinal real ou recomendação. O motor de 20 USDT que já está rodando permanece separado.

## Arquivos locais

reports/local/ai-shadow-offline/session.sqlite e demo-report.json. Nunca publicar esses arquivos. Reexecutar o mesmo evento retorna duplicate=true; isso é comportamento esperado. O resultado anterior permanece no journal.

Se aparecer mensagem de plano/código diferente, preserve o diretório anterior antes de preparar nova sessão de demonstração. Não edite hashes no banco nem apague locks com processo ativo. Essas recusas não são convite para reiniciar ou alterar o saldo paper real do projeto.

## O que não foi ativado

Sem Jev, AgenKit, loop ao vivo V2, transmissão de dados financeiros, cobrança ou ordens. Não existe indicador de lucro da V2 nem calibração real. Para isso haverá outro gate com plano congelado, orçamento, chave local e fontes verificadas. Sem integração automática no iniciar.py.

## Voltar ao funcionamento anterior

Basta encerrar a demonstração. Ela não inicia serviços persistentes nem altera a configuração do bot atual. Preservar seu journal para auditoria. Não usar git reset, não apagar relatórios ou reiniciar a simulação para desfazer uma demonstração.

## Tela de leitura

A aba V2 · Offline do painel lê somente o resumo do demo-report.json da pasta atendida pelo servidor. Não inicia a demonstração, não lê o SQLite e não altera o bot. Fonte/dados artificiais aparecem explicitamente; relatórios que declarem rede/ordens ativas são recusados. Depois de atualizar dashboard.py, reinicie apenas pelo iniciador único para carregar o novo leitor.
