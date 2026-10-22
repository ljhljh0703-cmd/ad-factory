/** Read-only casino receipts. The source owns spin timing, RNG, payment and prizes. */
const plain=text=>String(text??'').replace(/\|c[\da-f]{8}|\|r/gi,'').replace(/\|n/g,'\n').trim();
export function parseCasinoPayout(text){
 const value=plain(text),ordinary=value.match(/^(\d+)\s*골드\s*당첨!$/),jackpot=value.match(/빠칭코\s*잭팟\s*x\d+\s*당첨!\s*(\d+)\s*골드/);
 const match=ordinary??jackpot;if(!match)return null;const amount=Number(match[1]);
 return Number.isSafeInteger(amount)&&amount>=0?{amount,jackpot:!ordinary}:null;
}
/** One instance per newly booted world; input replay reconstructs the same receipts. */
export function createCasinoFeedback(playerId=0){
 const active=new Map(),results=[];let sequence=0;
 function observe(casino,events=[],tick=0){
  const stations=casino?.stations??[],byId=new Map(stations.map(s=>[s.id,s]));
  for(const s of stations)if(s.owned&&s.spinning&&!active.has(s.id))active.set(s.id,{id:s.id,index:s.index,title:s.title,amount:0,paid:false,jackpot:false,unknown:false,sourceTexts:[]});
  for(const event of events){
   if(event.kind!=='TextDisplayed'||!Array.isArray(event.playerIds)||!event.playerIds.includes(playerId))continue;
   const spin=active.get(event.sourceUnitId);if(!spin)continue;
   const prize=parseCasinoPayout(event.text);
   if(prize){spin.paid=true;spin.amount+=prize.amount;spin.jackpot||=prize.jackpot;spin.sourceTexts.push(plain(event.text));if(!Number.isSafeInteger(spin.amount))spin.unknown=true;}
   else if(/당첨/.test(plain(event.text)))spin.unknown=true;
  }
  const completed=[];
  for(const [id,spin] of active){
   const station=byId.get(id);
   if(!station?.owned){active.delete(id);continue;}
   if(station.spinning)continue;
   active.delete(id);const outcome=spin.unknown?'unknown':spin.paid?spin.jackpot?'jackpot':'win':'loss',amount=spin.unknown?null:spin.amount;
   const label=outcome==='unknown'?'추첨 종료 · 당첨금 확인 필요':outcome==='loss'?'꽝 · 당첨금 0 골드':`${outcome==='jackpot'?'잭팟!':'당첨!'} · 당첨금 ${amount.toLocaleString('ko-KR')} 골드`;
   const result={sequence:++sequence,unitId:id,index:spin.index,tick,outcome,amount,message:`${spin.title} · ${label}`,sourceTexts:spin.sourceTexts};
   results.unshift(result);results.length=Math.min(results.length,5);completed.push({...result,sourceTexts:[...result.sourceTexts]});
  }
  return completed;
 }
 const copy=r=>r?{...r,sourceTexts:[...r.sourceTexts]}:null;
 return {observe,snapshot(){return {last:copy(results[0]),results:results.map(copy)};}};
}
