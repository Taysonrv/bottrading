"""Read-only DEX quotes. No wallet addresses, keys, approvals or transactions."""
import datetime as dt
import json
from pathlib import Path
import urllib.parse
import urllib.request
from local_reports import destination

GRASS='Grass7B4RdKfBCjTKgSqnXkqjwiGvQyFbuSCUJr3XXjs'
USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
SOL='So11111111111111111111111111111111111111112'
BCOIN='0x00e1656e45f18ec6747f5a8496fd39b50b38396d'
WBNB='0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'
ROUTER='0x10ed43c718714eb63d5aa57b78b54704e256024e'


def get_json(url,payload=None):
    request=urllib.request.Request(url,data=json.dumps(payload).encode() if payload else None,
                                   headers={'Content-Type':'application/json','User-Agent':'SpotLab-readonly'})
    with urllib.request.urlopen(request,timeout=20) as response:
        return json.load(response)


def rpc(method,params):
    if method not in ('eth_call','eth_blockNumber','eth_gasPrice'):
        raise ValueError('Somente leitura')
    data=get_json('https://bsc-dataseed.binance.org/',dict(jsonrpc='2.0',id=1,method=method,params=params))
    if 'error' in data:
        raise ValueError('RPC não retornou cotação')
    return data['result']


def quote_sol(source,target,amount):
    params=dict(inputMint=source,outputMint=target,amount=amount,slippageBps=50,restrictIntermediateTokens='true')
    data=get_json('https://lite-api.jup.ag/swap/v1/quote?'+urllib.parse.urlencode(params))
    if data.get('inputMint')!=source or data.get('outputMint')!=target or int(data.get('inAmount',0))!=amount or int(data.get('outAmount',0))<=0:
        raise ValueError('Cotação inválida')
    return data


def encode_amounts(amount,path):
    if not isinstance(amount,int) or amount<=0 or len(path)<2:
        raise ValueError('Quantidade/caminho inválidos')
    for address in path:
        if len(address)!=42 or not address.startswith('0x'):
            raise ValueError('Contrato inválido')
        int(address[2:],16)
    return '0xd06ca61f'+f'{amount:064x}'+f'{64:064x}'+f'{len(path):064x}'+''.join(a[2:].lower().rjust(64,'0') for a in path)


def quote_bnb(amount,path,block):
    raw=rpc('eth_call',[dict(to=ROUTER,data=encode_amounts(amount,path)),block])[2:]
    words=[int(raw[i:i+64],16) for i in range(0,len(raw),64)]
    if len(words)!=len(path)+2 or words[0]!=32 or words[1]!=len(path) or words[2]!=amount or words[-1]<=0:
        raise ValueError('Resposta ABI inválida')
    return words[-1]


def solana():
    sell=quote_sol(GRASS,USDC,10**9)
    buy=quote_sol(USDC,GRASS,int(sell['outAmount']))
    sol_price=quote_sol(SOL,USDC,10**9)
    recovered=int(buy['outAmount'])/10**9
    unit_usdc=int(sell['outAmount'])/10**6
    # Sensitivity only: no transaction built, so gas, priority and rent cannot be estimated accurately.
    fees=[dict(assumed_total_sol=gas,estimated_usdc=gas*int(sol_price['outAmount'])/10**6)
          for gas in (.00002,.0002,.0023)]
    return dict(asset='GRASS',input_tokens=1,bridge_token='USDC',sale_output=unit_usdc,
                repurchase_tokens=recovered,quote_loss_percent=(1-recovered)*100,
                sell_quote=sell,buy_quote=buy,gas_sensitivity=fees,
                status='Cotação indicativa; custos totais não verificados')


def bnb():
    block=rpc('eth_blockNumber',[])
    sold=quote_bnb(50*10**18,[BCOIN,WBNB],block)
    back=quote_bnb(sold,[WBNB,BCOIN],block)
    gasprice=int(rpc('eth_gasPrice',[]),16)
    gas=[dict(assumed_total_gas=units,estimated_bnb=units*gasprice/10**18)
         for units in (350000,600000,1000000)]
    return dict(asset='BCOIN',input_tokens=50,bridge_token='WBNB',sale_output=sold/10**18,
                repurchase_tokens=back/10**18,quote_loss_percent=(1-back/(50*10**18))*100,
                block=block,gas_price_wei=gasprice,gas_sensitivity=gas,
                status='Apenas rota PancakeSwap V2 BCOIN/WBNB; impostos de token e execução não verificados')


def main():
    report=dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),executed=False,approved=False,results=[])
    for name,method in (('GRASS',solana),('BCOIN',bnb)):
        try:
            report['results'].append(method())
        except (OSError,ValueError,KeyError) as error:
            report['results'].append(dict(asset=name,status='Cotação indisponível',error=type(error).__name__))
    report['limitations']=['Duas cotações independentes no estado observado, sem aplicar o impacto da primeira troca antes da segunda.',
        'Taxas de pool embutidas nas cotações; slippage de execução, gas, aprovações, prioridade e aluguel de contas não estão no retorno em tokens.',
        'Gas apresentado como sensibilidade hipotética, não estimativa executável. Não garante venda, lucro ou melhor rota.',
        'Jupiter V1/lite é legado e depende da disponibilidade do provedor; nenhuma API key de carteira é necessária.',
        'WBNB flutua; não equivale a permanecer em dólar. Nenhuma ponte entre redes.']
    path=destination(Path(__file__).resolve().parent,'wallet-quote-research.json')
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    for r in report['results']:
        print(json.dumps({k:v for k,v in r.items() if k not in ('sell_quote','buy_quote')},ensure_ascii=False))
    print('Sem execução. Gas hipotético, não medido; retorno cotado não inclui todos os custos.')


if __name__=='__main__':
    main()
