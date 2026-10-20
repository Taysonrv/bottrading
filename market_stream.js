'use strict';
// Public-data observer only. No credentials, order messages or trading adapter.
const fs=require('node:fs'),path=require('node:path');
const SYMBOLS=['BTCUSDT','ETHUSDT','DOGEUSDT','PEPEUSDT'];
class Flow{
 constructor(now=Date.now()){this.started=now;this.rows={};this.received=0;this.rejected=0;this.gaps=0;}
 accept(m,now=Date.now()){
  if(!m||!SYMBOLS.includes(m.s)){this.rejected++;return false;}
  const r=this.rows[m.s]??={trades:[],book:null,lastId:null,lastBookId:null,reset:now};
  if(m.e==='aggTrade'){
   const price=Number(m.p),qty=Number(m.q),event=Number(m.E),id=Number(m.a);
   if(![price,qty,event,id].every(Number.isFinite)||price<=0||qty<=0||typeof m.m!=='boolean'||!Number.isSafeInteger(id)||id<0||now-event>5000||event-now>2000){this.rejected++;return false;}
   if(r.lastId!==null&&id<=r.lastId){this.rejected++;return false;}
   if(r.lastId!==null&&id!==r.lastId+1){this.gaps++;r.trades=[];r.reset=now;}
   r.lastId=id;r.trades.push({time:now,price,notional:price*qty,buy:!m.m});
   while(r.trades.length&&r.trades[0].time<now-60000)r.trades.shift();
   if(r.trades.length>10000){r.trades=r.trades.slice(-10000);r.reset=now;this.gaps++;}
  }else if('b' in m&&'a' in m){
   const bid=Number(m.b),ask=Number(m.a),id=Number(m.u);
   if(![bid,ask,id].every(Number.isFinite)||bid<=0||ask<bid||!Number.isSafeInteger(id)||r.lastBookId!==null&&id<=r.lastBookId){this.rejected++;return false;}
   r.book={bid,ask,time:now};r.lastBookId=id;
  }else{this.rejected++;return false;}
  this.received++;return true;
 }
 snapshot(now=Date.now()){
  return SYMBOLS.map(symbol=>{
   const r=this.rows[symbol],trades=(r?.trades||[]).filter(t=>t.time>=now-60000),book=r?.book;
   const total=trades.reduce((n,t)=>n+t.notional,0),buy=trades.reduce((n,t)=>n+(t.buy?t.notional:0),0);
   const share=total?buy/total:null,change=trades.length>1?trades.at(-1).price/trades[0].price-1:null;
   const fresh=Boolean(book&&now-book.time<=5000&&trades.length&&now-trades.at(-1).time<=5000);
   const warm=Boolean(r&&now-Math.max(this.started,r.reset)>=60000);
   const spread=book?book.ask/book.bid-1:null;
   const event=fresh&&warm&&trades.length>=20&&total>=10000&&share>=.65&&change>0&&spread<=.001;
   return {symbol,bid:book?.bid??null,ask:book?.ask??null,spread,book_age_seconds:book?(now-book.time)/1000:null,
    trades:trades.length,notional_usdt:total,buy_share:share,change,fresh,warm,
    observation:!fresh?'Dados insuficientes ou antigos':!warm?'Aquecimento de 60 segundos':event?'Pressão compradora observada; NÃO é ordem':'Sem gatilho experimental',event};
  });
 }
}
function run(){
 const root=__dirname,folder=path.join(root,'reports','local');fs.mkdirSync(folder,{recursive:true});
 const lock=path.join(folder,'market-stream.lock');const fd=fs.openSync(lock,'wx');fs.writeFileSync(fd,String(process.pid));fs.closeSync(fd);
 const output=path.join(folder,'market-stream.json'),started=Date.now(),end=started+24*3600000;
 let flow=new Flow(),ws,timer,retry,phase='connecting',reconnects=0,backoff=1000,lastMessage=Date.now(),opened=0,stopping=false,error=null;
 function save(){const data={started:started/1000,end:end/1000,updated:Date.now()/1000,pid:process.pid,phase,error,reconnects,
  received:flow.received,rejected:flow.rejected,gaps:flow.gaps,rows:flow.snapshot(),trading_enabled:false};fs.writeFileSync(output+'.tmp',JSON.stringify(data,null,2));fs.renameSync(output+'.tmp',output);}
 function connect(){
  if(stopping)return;
  phase='connecting';flow=new Flow();lastMessage=Date.now();opened=Date.now();
  const streams=SYMBOLS.flatMap(s=>[s.toLowerCase()+'@aggTrade',s.toLowerCase()+'@bookTicker']).join('/');
  ws=new WebSocket('wss://data-stream.binance.vision:443/stream?streams='+streams);
  ws.addEventListener('open',()=>{phase='connected';error=null;});
  ws.addEventListener('message',e=>{try{const msg=JSON.parse(e.data);if(flow.accept(msg.data)){lastMessage=Date.now();if(Date.now()-opened>60000)backoff=1000;}}catch{flow.rejected++;}});
  ws.addEventListener('error',()=>{error='Falha na conexão pública';phase='error';ws.close();});
  ws.addEventListener('close',()=>{if(stopping)return;phase='reconnecting';reconnects++;save();retry=setTimeout(connect,backoff);backoff=Math.min(backoff*2,30000);});
 }
 function stop(){if(stopping)return;stopping=true;clearInterval(timer);clearTimeout(retry);phase='stopped';ws?.close();save();if(fs.readFileSync(lock,'utf8')===String(process.pid))fs.unlinkSync(lock);}
 process.on('SIGINT',stop);process.on('SIGTERM',stop);
 connect();timer=setInterval(()=>{if(Date.now()>=end||fs.existsSync(path.join(root,'STOP'))){stop();return;}if(Date.now()-lastMessage>20000){error='Sem mensagens válidas por 20 segundos';ws?.close();}save();},2000);
 save();
}
module.exports={Flow,SYMBOLS};
if(require.main===module)run();
