import {validateInputReplay} from './gem-actions.js';
// Presentation metadata only: no Sim RNG or source rules are read or changed here.
export const LEGACY_RUN_KEY='uzmap.gemtower.run.v1';
const PREFIX='uzmap.gemtower.runs.v2.';
const AUTO_PREFIX='uzmap.gemtower.autos.v1.';
const safeId=id=>typeof id==='string'&&/^[a-zA-Z0-9_-]{8,80}$/.test(id);
const safeBuild=build=>typeof build==='string'&&/^[a-f0-9]{16}$/.test(build);
function validatedTrace(input){
 const trace=validateInputReplay(input);
 if(Object.hasOwn(trace,'replayBuild')&&!safeBuild(trace.replayBuild))throw Error('재생 호환 식별 정보가 올바르지 않습니다');
 return trace;
}
export function createRunId(){return crypto.randomUUID();}
export function restoredRunId(trace){return safeId(trace.runId)?trace.runId:createRunId();}
export function saveRunRecord(storage,input,savedAt=Date.now(),{automatic=false}={}){
 const trace=validatedTrace(input);
 if(!safeId(trace.runId)||!safeBuild(trace.build)||!Number.isFinite(savedAt)||savedAt<0)throw Error('저장 식별 정보가 올바르지 않습니다');
 const saved={...trace,savedAt},key=(automatic?AUTO_PREFIX:PREFIX)+trace.build+'.'+trace.runId,raw=JSON.stringify(saved);
 storage.setItem(key,raw); // One atomic write; legacy and the other save namespace are never write targets.
 return {key,raw,trace:saved};
}
export function isRunCompatible(input,build,replayBuild=null){
 let trace;try{trace=validatedTrace(input);}catch{return false;}
 if(!safeBuild(build)||!safeBuild(trace.build)||trace.mode==='classic')return false;
 return trace.build===build||safeBuild(replayBuild)&&safeBuild(trace.replayBuild)&&trace.replayBuild===replayBuild;
}
export function listRunRecords(storage,build,replayBuild=null){
 const keys=[];for(let i=0;i<storage.length;i++){const key=storage.key(i);if(key===LEGACY_RUN_KEY||key?.startsWith(PREFIX)||key?.startsWith(AUTO_PREFIX))keys.push(key);}
 return keys.map(key=>{
  const raw=storage.getItem(key),legacy=key===LEGACY_RUN_KEY,automatic=key.startsWith(AUTO_PREFIX);let trace,error;
  try{trace=validatedTrace(raw);if(!legacy&&key!==(automatic?AUTO_PREFIX:PREFIX)+trace.build+'.'+trace.runId)throw Error('저장 식별 정보가 다릅니다');}catch(e){error=e.message;}
  const reason=trace?.mode==='classic'?'classic':null;
  // Restoration boots trace.seed; a new-game URL must not hide older runs.
  const compatible=!error&&!reason&&isRunCompatible(trace,build,replayBuild);
  return {key,raw:raw??'',legacy,automatic,trace,error,reason,compatible};
 }).sort((a,b)=>(Number(b.trace?.savedAt)||0)-(Number(a.trace?.savedAt)||0)||a.key.localeCompare(b.key));
}
