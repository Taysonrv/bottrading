"""Build unsigned swaps and simulate only. Never signs or broadcasts."""
import argparse
import base64
import datetime as dt
import json
from pathlib import Path
from local_reports import destination
from wallet_quote_research import get_json,quote_sol,GRASS,USDC


def rpc(method,params):
    if method not in ('simulateTransaction','getFeeForMessage','getBalance'):
        raise ValueError('Método não permitido nesta pesquisa')
    response=get_json('https://api.mainnet-beta.solana.com',dict(jsonrpc='2.0',id=1,method=method,params=params))
    if 'error' in response:
        raise ValueError('RPC: '+json.dumps(response['error']))
    return response['result']


def unsigned_message(encoded):
    raw=base64.b64decode(encoded,validate=True)
    count=offset=shift=0
    for byte in raw[:3]:
        count|=(byte&127)<<shift;offset+=1;shift+=7
        if not byte&128:
            break
    else:
        raise ValueError('Cabeçalho inválido')
    end=offset+64*count
    if not 0<count<=16 or len(raw)<=end or any(raw[offset:end]):
        raise ValueError('Esperada transação sem assinaturas')
    return base64.b64encode(raw[end:]).decode()


def inspect(quote,wallet):
    built=get_json('https://lite-api.jup.ag/swap/v1/swap',dict(
        quoteResponse=quote,userPublicKey=wallet,wrapAndUnwrapSol=True,
        dynamicComputeUnitLimit=True,prioritizationFeeLamports=10000))
    transaction=built['swapTransaction']
    message=unsigned_message(transaction)
    fee=rpc('getFeeForMessage',[message,{'commitment':'confirmed'}])
    simulated=rpc('simulateTransaction',[transaction,dict(encoding='base64',sigVerify=False,
        replaceRecentBlockhash=True,commitment='confirmed',accounts=dict(encoding='base64',addresses=[wallet]))])
    value=simulated['value']
    account=(value.get('accounts') or [None])[0]
    return dict(input_mint=quote['inputMint'],output_mint=quote['outputMint'],
                input_amount=quote['inAmount'],quoted_output=quote['outAmount'],minimum_output=quote['otherAmountThreshold'],
                fee_lamports=fee['value'],fee_slot=fee['context']['slot'],
                priority_lamports=built.get('prioritizationFeeLamports'),
                compute_limit=built.get('computeUnitLimit'),units_consumed=value.get('unitsConsumed'),
                simulation_error=value.get('err'),builder_error=built.get('simulationError'),
                simulation_slot=simulated['context']['slot'],
                simulated_wallet_lamports=account.get('lamports') if account else None,
                logs=(value.get('logs') or [])[-12:])


def main():
    parser=argparse.ArgumentParser(description='Pesquisa de custos sem assinatura ou envio')
    parser.add_argument('--wallet',required=True,help='Endereço público Solana; não fornecer chaves')
    args=parser.parse_args()
    if not 32<=len(args.wallet)<=44 or any(c not in '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz' for c in args.wallet):
        parser.error('Endereço público Solana inválido')
    balance=rpc('getBalance',[args.wallet,{'commitment':'confirmed'}])
    sell=quote_sol(GRASS,USDC,10**9)
    buy=quote_sol(USDC,GRASS,int(sell['outAmount']))
    report=dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),executed=False,signed=False,approved=False,
                native_balance_lamports=balance['value'],balance_slot=balance['context']['slot'],legs=[])
    for name,quote in (('venda',sell),('recompra',buy)):
        try:
            report['legs'].append(dict(leg=name,**inspect(quote,args.wallet)))
        except (OSError,ValueError,KeyError) as error:
            report['legs'].append(dict(leg=name,error_type=type(error).__name__,available=False))
    report['limitations']=[
        'Simulações independentes: a venda não credita USDC para a simulação seguinte. Recompra pode falhar por saldo insuficiente.',
        'getFeeForMessage inclui a taxa de prioridade codificada; não somar novamente priority_lamports.',
        'Taxa de mensagem não inclui depósito de aluguel para contas de tokens; balanço simulado pode refletir outros movimentos.',
        'Saldo e simulações têm slots distintos; diferença de saldo não é medição exata de custo.',
        'Sem validação completa de instruções/contratos; não usar transações preparadas para execução.',
        'Nenhuma assinatura, aprovação, transmissão de transação ou alteração de carteira.']
    path=destination(Path(__file__).resolve().parent,'solana-cost-research.json')
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='limitations'},indent=2))
    print('\n'.join(report['limitations']))


if __name__=='__main__':
    main()
