const assert=require('node:assert/strict');
const {Flow}=require('./market_stream.js');
const trade=(id,m=false)=>({e:'aggTrade',s:'BTCUSDT',a:id,p:'100',q:'2',m,E:1000});
{
 const f=new Flow(1000);f.accept(trade(1),1000);f.accept(trade(2,true),1000);
 const r=f.snapshot(1000)[0];assert.equal(r.notional_usdt,400);assert.equal(r.buy_share,.5);assert.equal(r.event,false);
 assert.equal(f.accept(trade(2),1000),false);
 f.accept(trade(4),1000);assert.equal(f.gaps,1);assert.equal(f.snapshot(1000)[0].trades,1);
}
{
 const f=new Flow(1000);assert.equal(f.accept(trade(1),10000),false);
 assert.equal(f.accept({...trade(1),q:'NaN'},1000),false);
 assert.equal(f.accept({s:'BTCUSDT',u:1,b:'100',a:'99'},1000),false);
 f.accept({s:'BTCUSDT',u:2,b:'100',a:'100.01'},1000);f.accept(trade(1),1000);
 assert.equal(f.snapshot(1000)[0].fresh,true);assert.equal(f.snapshot(7000)[0].fresh,false);
 assert.equal(f.snapshot(100000)[0].notional_usdt,0);
}
{
 const f=new Flow(1000);f.accept(trade(1),1000);
 for(let i=2;i<=25;i++)f.accept({...trade(i),E:65000,p:String(100+i*.01),q:'20'},65000);
 f.accept({s:'BTCUSDT',u:1,b:'100',a:'100.01'},65000);
 assert.equal(f.snapshot(65000)[0].event,true);
 assert.equal(f.snapshot(71000)[0].event,false);
}
console.log('WebSocket flow: agressor, notional, deduplicação, lacunas, validade, aquecimento e gatilho sem execução OK.');
