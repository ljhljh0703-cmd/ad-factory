import {rawCodeOf} from './dist/ir/fourcc.js';
/** View-only unit targeting. Source JASS owns cost, blacklist, positions and ability removal. */
export const GEM_TARGET_COMMAND_IDS=['A05L'];
const clean=text=>String(text??'').replace(/\|c[\da-f]{8}|\|r/gi,'').replace(/\|n/g,'\n');
export function targetGemActions(w,unitId){
 const unit=w.sim.getUnit(unitId);
 return GEM_TARGET_COMMAND_IDS.map(abilityId=>{
  const object=w.sim.mapIr.objectMods.find(o=>o.kind==='ability'&&(o.newId??o.baseId)===abilityId),field=id=>object?.mods.findLast(m=>m.field===id)?.value;
  const acquired=(unit?.abilities?.get(rawCodeOf(abilityId))??0)>0;
  const reason=w.gameOver?'game-over':w.sim.validateAbilityOrder(0,unitId,abilityId);
  const rangeU=w.gameOver?undefined:w.sim.abilityRange?.(abilityId,unit?.abilities?.get(rawCodeOf(abilityId))??1);
  const rangeNote=Number.isFinite(rangeU)?`시전 사거리 ${rangeU}`:'';
  return {abilityId,label:clean(field('anam')??abilityId),description:[clean(field('aub1')),rangeNote].filter(Boolean).join('\n'),rangeU,acquired,reason,disabled:reason!==null};
 });
}
export function cancelGemTarget(w){const had=Boolean(w.pendingTargetAbility);w.pendingTargetAbility=null;return had;}
export function currentGemTarget(w){
 const request=w.pendingTargetAbility;
 if(!request)return null;
 if(w.gameOver||w.sim.validateAbilityOrder(0,request.unitId,request.abilityId)!==null){cancelGemTarget(w);return null;}
 return request;
}
export function armGemTarget(w,unitId,abilityId='A05L'){
 if(w.gameOver||!GEM_TARGET_COMMAND_IDS.includes(abilityId)||w.sim.validateAbilityOrder(0,unitId,abilityId)!==null)return false;
 w.pendingPointAbility=null;w.pendingTargetAbility={unitId,abilityId};return true;
}
export function gemTargetReason(w,targetUnitId){
 const request=currentGemTarget(w);if(!request)return 'no-target-selection';
 if(!Number.isSafeInteger(targetUnitId)||targetUnitId<=0||targetUnitId===request.unitId)return 'invalid-target';
 // This set is the existing source-owned gem/rock picker, never a copied ability blacklist.
 if(w.gemTargetCandidateIds&&!w.gemTargetCandidateIds.has(targetUnitId))return 'invalid-target';
 return w.sim.validateAbilityOrder(0,request.unitId,request.abilityId,targetUnitId);
}
export function issueGemTarget(w,targetUnitId){
 if(gemTargetReason(w,targetUnitId)!==null)return false;const request=w.pendingTargetAbility;
 if(!w.sim.issueAbilityOrder(0,request.unitId,request.abilityId,targetUnitId))return false;
 w.recordInput?.({kind:'ability',playerId:0,unitId:request.unitId,abilityId:request.abilityId,targetUnitId});
 cancelGemTarget(w);return true;
}
