# Diagnóstico de decisões no painel

A seção Entradas reúne o estado atual da carteira, intenções recentes do radar e ordens do recorte recebido. Tudo é somente leitura; não existe aprovação ou envio de ordens por este diagnóstico.

Estados apresentados: carteira indisponível, motor multipar não selecionado, STOP, prazo encerrado, trava registrada, dados antigos, saída sintética solicitada, entrada pendente, posição aberta e caixa sem ordem pendente.

Uma intenção ENTER_LONG no radar não prova reserva ou preenchimento. Sua contagem só aparece quando os seis pares distintos têm leituras OK em um radar recente. Dados parciais ou antigos ficam indisponíveis, sem zero artificial.

As contagens de ordens/cancelamentos/rejeições são **do recorte recebido**, e não totais históricos. O painel mostra no máximo as dez ordens mais recentes do recorte nesta seção. O timestamp é o da criação, não do cancelamento. Nem toda recusa de prévia fica registrada como ordem rejeitada; zero rejeições no recorte não significa zero sinais bloqueados.

EXPIRED significa ordem expirada sem preenchimento. Não permite afirmar isoladamente se o preço não alcançou o limite, se a liquidez faltou ou se outra condição impediu a execução. O diagnóstico não inventa esse detalhe.

STOP bloqueia ordens e não liquida posições. Uma saída sintética pendente continua dependente de cotação posterior, filtros e liquidez. Dados recentes confirmam apenas atualização do relatório; não garantem operação contínua nem lucro.

Verificação: `node test_dashboard_frontend.cjs`. Os casos incluem reserva, saída pendente, STOP com relatório antigo, carteira indisponível, radar incompleto e cancelamento por expiração.
