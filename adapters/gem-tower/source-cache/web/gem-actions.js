import {GEM_TARGET_COMMAND_IDS} from './gem-targeting.js';
import {rawCodeOf} from "./dist/ir/fourcc.js";
import {gemTowerPlayerState} from "./dist/runtime/maps/gemtower.js";
/** GemTower presentation adapter. Uses original w3a names and existing command validation.
 * IDs are the existing map's trigger inputs; effects and grants remain in its JASS. */
export const GEM_COMMAND_IDS = ["A009", "A007", "A00R", "A03M", "A02G", "A008", "A02J"];
export function gemActions(w, unitId) {
  const unit=w.sim.getUnit?.(unitId);
  return GEM_COMMAND_IDS.map(abilityId => {
    const object = w.sim.mapIr.objectMods.find(o => o.kind === "ability" && (o.newId ?? o.baseId) === abilityId);
    const name = object?.mods.findLast(m => m.field === "anam")?.value;
    const label = typeof name === "string" ? name.replace(/\|c[0-9a-fA-F]{8}|\|r/g, "") : abilityId;
    let reason = w.gameOver?'game-over':w.sim.validateAbilityOrder(0, unitId, abilityId);
    // Source ownership/busy checks precede grants in the command validator. Keep
    // unacquired auxiliary commands hidden without changing the actual validator.
    if(['not-owner','busy','paused','stunned'].includes(reason)&&!['A009','A007','A00R'].includes(abilityId)&&typeof unit?.abilities?.get==='function'&&!(unit.abilities.get(rawCodeOf(abilityId))>0))reason='missing-ability';
    if(reason===null&&abilityId==='A02J'&&w.sim.abilityRange?.(abilityId,w.sim.getUnit(unitId)?.abilities?.get(rawCodeOf(abilityId))??1)===undefined)reason='missing-ability-data';
    return {abilityId, label, reason, disabled: reason !== null};
  });
}
export function gemBuildHint(vm, playerId = 0) {
  const state=gemTowerPlayerState(vm,playerId);
  const chosen=state.chosen,round=state.round??1;
  if (chosen === true) return `웨이브 ${round} 진행 · 몹이 끝나면 다음 보석을 만드세요`;
  const count=state.buildCount??0;
  return count < 5 ? `보석 건설 ${count}/5 · 다섯 개를 만든 뒤 선택 또는 조합` : "보석을 선택하거나 같은 보석을 조합하세요";
}
export function isGemSelectable(entity, def) {
  return Boolean(entity?.alive && entity.typeId !== "u000" &&
    (def?.attack || (entity.owner === 0 && entity.abilities.size > 0)));
}

/** Capture only view-observation identity; input replays still store ordinary intent. */
export function captureGemCast(w,unit,abilityId){
 return {unitId:unit.id,abilityId,fromTypeId:unit.typeId,owner:unit.owner,x:unit.x,y:unit.y,existingUnitIds:new Set(w.sim.entities?.keys?.()??[])};
}

export function observeGemCast(w, request, tick) {
  if (request.spellTick === undefined) return {state: "waiting"};
  const still = w.sim.getUnit(request.unitId);
  if(still?.alive&&still.owner===request.owner&&still.typeId!==request.fromTypeId)return {state:"replaced",result:still};
  if (!still?.alive || still.typeId !== request.fromTypeId) {
    const result = [...w.sim.entities.values()].find(e => e.alive && e.owner === request.owner && e.x === request.x && e.y === request.y && e.typeId !== request.fromTypeId && (!request.existingUnitIds||!request.existingUnitIds.has(e.id)));
    if (result) return {state: "replaced", result};
  }
  return tick - request.spellTick < 20 ? {state: "waiting"} : {state: "processed"};
}

export function parseSessionSeed(input, fallback = 424242) {
  if (typeof input !== "string" || !/^\d+$/.test(input)) return fallback;
  const value = Number(input);
  return Number.isSafeInteger(value) && value <= 0xffffffff ? value : fallback;
}

/** Browser session boundary only; a running Sim always retains its one fixed seed. */
export function freshSessionSeed(previousSeed, entropy = globalThis.crypto) {
  const values = new Uint32Array(1);
  entropy.getRandomValues(values);
  const seed = values[0];
  // A second game must not accidentally reuse the previous draw, including uint32 wrap.
  return seed === previousSeed ? (seed + 1) >>> 0 : seed;
}

export function flushModeChoice(w) {
  const dialog = w.modeDialog;
  if (!dialog || dialog.pendingButtonId === undefined || w.sim.tickCount < 2) return;
  w.sim.injectDialogClick(0, dialog.pendingButtonId);
  w.recordInput?.({kind:"dialog",playerId:0,buttonId:dialog.pendingButtonId,dialogId:dialog.dialogId});
  delete dialog.pendingButtonId;
}
export function requestModeChoice(w, mode) {
  const dialog = w.modeDialog;
  if (!dialog || dialog.clicked || !["classic", "race"].includes(mode)) return false;
  dialog.pendingButtonId = mode === "classic" ? dialog.classicButtonId : dialog.raceButtonId;
  dialog.clicked = true;
  // The original default-mode timer fires at tick 2; deliver the actual user click afterwards.
  flushModeChoice(w);
  return true;
}

/** Original name/identity census, separate from optional presentation images. */
export function extractGemPresentation(specials={},towers={}){
 const names={},gemIds=new Set();
 for(const unit of specials.units??[]){if(unit.id&&unit.name)names[unit.id]=unit.name;if(unit.classification==='gem')gemIds.add(unit.id);}
 for(const unit of [...(towers.grid??[]),...(towers.beyondGrid??[])]){if(unit.id&&unit.name){names[unit.id]=unit.name;gemIds.add(unit.id);}}
 return {names,gemIds};
}

/** Saved runs contain ordinary player intent, never serialized VM/unit/outcome state. */
export function validateInputReplay(input){
 const trace=typeof input==='string'?JSON.parse(input):input;
 const int=n=>Number.isSafeInteger(n)&&n>=0,code=s=>typeof s==='string'&&/^[\x00-\xff]{4}$/.test(s);
 if(!trace||trace.format!=='uzmap-ui-input-v1'||!int(trace.seed)||trace.seed>0xffffffff||!int(trace.tick)||trace.tick>1_000_000||!/^[a-f0-9]{8}$/i.test(trace.stateHash)||!Array.isArray(trace.actions)||trace.actions.length>50_000)throw Error('지원하지 않는 저장 기록입니다');
 let previous=0;
 for(const a of trace.actions){
  if(!a||!int(a.tick)||a.tick<previous||a.tick>trace.tick||a.playerId!==0)throw Error('조작 순서나 플레이어가 올바르지 않습니다');previous=a.tick;
  if(a.kind==='dialog'){if(!int(a.buttonId)||a.buttonId===0||!int(a.dialogId))throw Error('대화상자 기록 오류');}
  else if(a.kind==='chat'){if(typeof a.text!=='string')throw Error('채팅 기록 오류');}
  else if(a.kind==='place'){if(a.typeId!=='h006'||!Number.isFinite(a.x)||!Number.isFinite(a.y))throw Error('건설 기록 오류');}
  else if(a.kind==='ability'){
   const targeted=GEM_TARGET_COMMAND_IDS.includes(a.abilityId);
   if(!int(a.unitId)||a.unitId===0||(!targeted&&(!GEM_COMMAND_IDS.includes(a.abilityId)||a.abilityId==='A02J'))||(targeted?(!int(a.targetUnitId)||a.targetUnitId===0):Object.hasOwn(a,'targetUnitId')))throw Error('능력 기록 오류');
  }
  else if(a.kind==='pointAbility'){if(!int(a.unitId)||a.unitId===0||a.abilityId!=='A02J'||!Number.isFinite(a.x)||!Number.isFinite(a.y))throw Error('위치 주문 기록 오류');}
  else if(a.kind==='move'){if(!int(a.unitId)||a.unitId===0||!Number.isFinite(a.x)||!Number.isFinite(a.y)||typeof a.accepted!=='boolean')throw Error('이동 기록 오류');}
  else if(a.kind==='train'){if(!int(a.producerId)||a.producerId===0||!code(a.typeId)||typeof a.accepted!=='boolean')throw Error('구매 기록 오류');}
  else if(a.kind==='research'){if(!['R000','R001','R002'].includes(a.techId)||typeof a.accepted!=='boolean')throw Error('연구 기록 오류');}
  else if(a.kind==='upgrade'){if(!int(a.unitId)||a.unitId===0||!code(a.targetTypeId)||typeof a.accepted!=='boolean')throw Error('강화 기록 오류');}
  else throw Error('저장할 수 없는 조작 종류입니다');
 }
 return trace;
}
export function replayInputBatch(w,trace,cursor,advance,maxTicks=200,shouldYield=()=>false){
 let steps=0;
 while(true){
  while(cursor<trace.actions.length&&trace.actions[cursor].tick===w.sim.tickCount){
   const a=trace.actions[cursor++];let accepted=true;
   if(a.kind==='dialog'){
    if(a.buttonId===w.modeDialog?.classicButtonId)throw Error('클래식 수동 시작 기록은 아직 이어하기를 지원하지 않습니다');
    const button=w.vm.handles.get(a.buttonId),dialog=w.vm.handles.get(a.dialogId);
    if(button?.kind!=='button'||dialog?.kind!=='dialog'||button.data.dialogId!==dialog.id||!dialog.data.buttons.includes(button.id)||dialog.id!==w.modeDialog?.dialogId&&!dialog.data.visibleTo.includes(a.playerId))throw Error('저장 당시의 선택창과 일치하지 않습니다');
    w.sim.injectDialogClick(a.playerId,a.buttonId);if(a.dialogId===w.modeDialog?.dialogId){w.modeDialog.clicked=true;delete w.modeDialog.pendingButtonId;}else if(a.tick===trace.tick)w.nativeDialogPendingId=a.dialogId;
   }else if(a.kind==='chat'){w.sim.injectChat(a.playerId,a.text);}
   else if(a.kind==='place'){accepted=w.sim.placeStructure(a.playerId,a.typeId,a.x,a.y);if(accepted)w.pendingBuilds?.push({x:a.x,y:a.y});}
   else if(a.kind==='ability'){const unit=w.sim.getUnit(a.unitId);accepted=GEM_TARGET_COMMAND_IDS.includes(a.abilityId)?w.sim.issueAbilityOrder(a.playerId,a.unitId,a.abilityId,a.targetUnitId):w.sim.issueAbilityOrder(a.playerId,a.unitId,a.abilityId);if(accepted&&unit&&!GEM_TARGET_COMMAND_IDS.includes(a.abilityId))w.pendingCasts?.push(captureGemCast(w,unit,a.abilityId));}
   else if(a.kind==='pointAbility')accepted=w.sim.issuePointAbilityOrder(a.playerId,a.unitId,a.abilityId,a.x,a.y);
   else if(a.kind==='move')accepted=w.sim.issueMoveOrder(a.playerId,a.unitId,a.x,a.y);
   else if(a.kind==='train')accepted=w.sim.issueTrainUnit(a.playerId,a.producerId,a.typeId);
   else if(a.kind==='research')accepted=w.sim.research(a.playerId,a.techId);
   else if(a.kind==='upgrade')accepted=w.sim.issueUnitUpgrade(a.playerId,a.unitId,a.targetTypeId);
   if(accepted!==(a.accepted??true))throw Error('저장 당시와 조작 결과가 다릅니다');
   if(shouldYield())return cursor;
  }
  if(cursor<trace.actions.length&&trace.actions[cursor].tick<w.sim.tickCount)throw Error('조작을 건너뛴 기록입니다');
  if(w.sim.tickCount>=trace.tick||steps++>=maxTicks)return cursor;
  advance(1);if(shouldYield())return cursor;
 }
}

export function ownedRocks(w){return [...w.sim.entities.values()].filter(e=>e.alive&&e.owner===0&&e.typeId==='h00G');}
export function blockedCreepCount(w){
 const nav=w.sim.navigation;if(!nav)return 0;const size=nav.grid.cellSize;let count=0;
 for(const e of w.sim.entities.values())if(e.alive&&e.owner===11&&e.orderActive===1&&!e.spawnPending&&Math.max(Math.abs(e.x-e.orderX),Math.abs(e.y-e.orderY))>size&&nav.waypoint(e)===null)count++;
 return count;
}

/** Discover source-acquired options; retained ownership changes during a wave. */
export function availableGemCombinations(w,gems){
 return gems.filter(e=>e?.alive&&['A00R','A03M'].some(id=>w.sim.validateAbilityOrder(0,e.id,id)===null)).map(e=>e.id);
}

/** Source-owned A02J uses the same ordinary order queue; only the destination is selected here. */
export function armSlateMove(w,unitId){
 if(w.gameOver||w.sim.validateAbilityOrder(0,unitId,'A02J')!==null)return false;
 w.pendingPointAbility={unitId,abilityId:'A02J'};return true;
}
export function issueSlateMove(w,x,y){
 const request=w.pendingPointAbility;if(!request)return false;
 if(!w.sim.issuePointAbilityOrder(0,request.unitId,request.abilityId,x,y))return false;
 w.recordInput?.({kind:'pointAbility',playerId:0,unitId:request.unitId,abilityId:request.abilityId,x,y});
 (w.pendingMoves??=[]).push({unitId:request.unitId,x,y,issuedTick:w.sim.tickCount});
 w.pendingPointAbility=null;return true;
}

/** Offered training comes only from current, source-authored owned producers. */
export function trainingActions(w){
 const rows=[];for(const producer of w.sim.entities.values()){
  if(!producer.alive||producer.owner!==0)continue;const from=w.sim.defStore?.getDef(producer.typeId);
  for(const typeId of from?.trainingOptions??[]){const target=w.sim.defStore.getDef(typeId);rows.push({producerId:producer.id,producerType:producer.typeId,typeId,cost:target.sourceGoldCost,durationTicks:target.buildTimeTicks,reason:w.sim.validateTrainUnit(0,producer.id,typeId)});}
 }return rows;
}
export function requestTraining(w,producerId,typeId){
 const accepted=w.sim.issueTrainUnit(0,producerId,typeId);w.recordInput?.({kind:'train',playerId:0,producerId,typeId,accepted});return accepted;
}

/** A UI batch remains individual source-costed, timed train requests in the replay. */
export function requestTrainingBatch(w,producerId,typeId,count){
 if(!Number.isInteger(count)||count<1||count>10||w.trainingBatch)return false;
 const row=trainingActions(w).find(r=>r.producerId===producerId&&r.typeId===typeId);
 if(!row||row.reason||!Number.isFinite(row.cost)||w.sim.ledger.gold(0)<row.cost*count)return false;
 if(!requestTraining(w,producerId,typeId))return false;
 if(count>1)w.trainingBatch={producerId,typeId,remaining:count-1};return true;
}
export function advanceTrainingBatch(w,event,limitReached=false){
 const batch=w.trainingBatch;if(!batch||event.producerId!==batch.producerId||event.typeId!==batch.typeId)return false;
 if(event.kind!=='TrainingFinished'){
  if(event.kind==='TrainingRejected')w.trainingBatch=null;return false;
 }
 if(limitReached||w.gameOver||batch.remaining<=0){w.trainingBatch=null;return false;}
 batch.remaining--;if(!requestTraining(w,batch.producerId,batch.typeId)){w.trainingBatch=null;return false;}
 return true;
}
