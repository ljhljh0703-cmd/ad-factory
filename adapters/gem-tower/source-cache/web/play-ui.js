/** View-only helpers. Existing world commands still own all gameplay. */
export function playerCamera(anchor, width, height) {
  return {cx:anchor.x,cy:anchor.y,zoom:Math.max(.03,Math.min(0.6,(width-64)/1024,(height-64)/1024))};
}
/** Fit the source battle-loop rectangles, with room for a tower footprint at its edges.
 * Presentation only: world coordinates, pathing, source orders and RNG stay untouched. */
export function battlefieldBounds(rects){
 return {minX:Math.min(...rects.map(r=>r.minX))-128,maxX:Math.max(...rects.map(r=>r.maxX))+128,minY:Math.min(...rects.map(r=>r.minY))-128,maxY:Math.max(...rects.map(r=>r.maxY))+128};
}
export function battlefieldCamera(rects,width,height,padding=20){
 const {minX,maxX,minY,maxY}=battlefieldBounds(rects);
 return {cx:(minX+maxX)/2,cy:(minY+maxY)/2,zoom:Math.max(.001,Math.min((Math.max(1,width-padding*2))/(maxX-minX),(Math.max(1,height-padding*2))/(maxY-minY)))};
}
export function keyboardBuildPoint(pm, builder, current, key, cells=2) {
  const centre = (v, origin) => origin + (Math.floor((v-origin)/pm.cellSize/cells)*cells+(cells-1)/2)*pm.cellSize;
  const point = current ? {...current} : {x:centre(builder.x+pm.cellSize*cells,pm.originX),y:centre(builder.y,pm.originY)};
  if(current){if(key==='ArrowRight')point.x+=pm.cellSize*cells;if(key==='ArrowLeft')point.x-=pm.cellSize*cells;if(key==='ArrowUp')point.y+=pm.cellSize*cells;if(key==='ArrowDown')point.y-=pm.cellSize*cells;}
  return point;
}

export function attackDisplay(attack, stepSeconds) {
  if(!attack)return {damage:"—",interval:"—"};
  return {damage:attack.dmgSpread ? `${attack.dmgBase} ~ ${attack.dmgBase+attack.dmgSpread}` : String(attack.dmgBase), interval:(attack.cooldownTicks*stepSeconds).toFixed(2)+"초"};
}


/** Current Def weapon masks only. This does not predict damage or resolve auras. */
export function attackTargetLabel(def) {
 const weapons=[def?.attack,def?.secondaryAttack].filter(Boolean);
 if(!weapons.length)return "일반 공격 없음";
 const mask=weapons.reduce((value,attack)=>value|attack.targetsMask,0)&3;
 return mask===1?"지상 공격":mask===2?"공중 공격":mask===3?"지상·공중 공격":"공격 대상 확인 필요";
}
/** Next form's base stats, reusing attackDisplay. Effects and final damage stay separate. */
export function upgradeAttackSummary(def,stepSeconds) {
 return [def?.attack,def?.secondaryAttack].filter(Boolean).map(attack=>{
  const text=attackDisplay(attack,stepSeconds);
  return `${attackTargetLabel({attack})} · 기본 ${text.damage} · ${text.interval}`;
 }).join(" / ")||"일반 공격 없음";
}

export function combatEffectLabels(effects,stepSeconds){
 const seconds=ticks=>Number((ticks*stepSeconds).toFixed(3));
 return effects.map(e=>e.kind==='venom'?`독 초당 ${e.damagePerSecondPm/1000} · ${seconds(e.durationTicks)}초 · 공격자별 중첩 · 체력 1에서 멈춤`:e.kind==='liquidFire'?`불 초당 ${e.damagePerSecondPm/1000} · ${seconds(e.durationTicks)}초 · 중첩 없이 갱신`:e.kind==='bash'?`강타 ${e.chancePm/10}% · 공격 피해 ${Math.max(1000,e.multiplierPm)/1000}배 · 기절 ${e.durationTicks*stepSeconds}초${e.heroDurationTicks!==e.durationTicks?` · 영웅 ${e.heroDurationTicks*stepSeconds}초`:''}`:e.kind==='armorReduction'?`명중 시 방어 ${e.amount} 감소 · ${e.durationTicks*stepSeconds}초`:e.kind==='armorAura'?`방어 감소 오라 ${-e.flatBonus} · ${attackTargetLabel({attack:{targetsMask:e.targetsMask}}).replace(' 공격','')} · 범위 ${e.radiusU}`:e.kind==='enemySlowAura'?`감속 오라 ${e.slowPm/10}% · 범위 ${e.radiusU}`:e.kind==='selfArmor'?`자기 방어 ${e.flatBonus>=0?'+':''}${e.flatBonus}`:e.kind==='critical'?`치명타 ${e.chancePm/10}% · 피해 ${e.multiplierPm/1000}배`:e.kind==='damageAura'?`공격 보너스 ${[e.bonusPm?`${e.bonusPm/10}%`:'',e.flatBonus?`${e.flatBonus>0?'+':''}${e.flatBonus}`:''].filter(Boolean).join(' ')||'0'}${e.selfOnly?' · 자신':' · 범위 '+e.radiusU}`:e.kind==='speedAura'?`공격 속도 +${e.bonusPm/10}%${e.selfOnly?' · 자신':' · 범위 '+e.radiusU}`:e.kind==='barrage'?`다중 공격 · 최대 ${e.extraTargets+1}마리`:e.kind==='frost'?`냉기 · 이동 ${e.slowPm/10}% 감소 · ${e.durationTicks*stepSeconds}초`:e.kind==='immolation'?`범위 ${e.radiusU} · ${e.intervalTicks*stepSeconds}초마다 ${e.pulseDamagePm/1000} 화염`:e.kind==='poison'?`독 초당 ${e.damagePerSecondPm/1000} · ${e.durationTicks*stepSeconds}초${e.slowPm?` · 이동 ${e.slowPm/10}% 감소`:''}`:'효과 정보 확인 중');
}

/** Display candidates only; the existing placement validator decides which are usable. */
export function visibleBuildBlocks(pm,cam,width,height,cells){
 const span=pm.cellSize*cells,half=(cells-1)/2;
 const minX=cam.cx-width/2/cam.zoom,maxX=cam.cx+width/2/cam.zoom,minY=cam.cy-height/2/cam.zoom,maxY=cam.cy+height/2/cam.zoom;
 const fromC=Math.max(0,Math.floor((minX-pm.originX)/span)*cells),toC=Math.min(pm.width-cells,Math.ceil((maxX-pm.originX)/span)*cells);
 const fromR=Math.max(0,Math.floor((minY-pm.originY)/span)*cells),toR=Math.min(pm.height-cells,Math.ceil((maxY-pm.originY)/span)*cells),out=[];
 for(let row=toR;row>=fromR;row-=cells)for(let col=fromC;col<=toC;col+=cells){const x=pm.originX+(col+half)*pm.cellSize,y=pm.originY+(row+half)*pm.cellSize;if(x>=minX&&x<=maxX&&y>=minY&&y<=maxY)out.push({col,row});}
 return out;
}

/** Labels only: callers supply the existing command validator result. */
export function upgradeConditionText(reason,owner){
 if(reason===null)return '강화 가능';
 if(reason==='not-owner'&&owner===9)return '보석을 남긴 뒤 전투 중에 강화할 수 있어요';
 return ({busy:'강화 진행 중','insufficient-gold':'골드가 부족합니다','missing-data':'원작 강화 정보를 확인할 수 없습니다','prereq-unmet':'필요한 보석이나 연구가 없습니다','not-owner':'조종할 수 없는 보석입니다','game-over':'게임이 끝났습니다'})[reason]??'지금은 강화할 수 없습니다';
}
export function gemActionConditions(actions){
 return actions.filter(action=>['A007','A00R','A03M'].includes(action.abilityId)).map(action=>`${action.label} · ${!action.disabled?'사용 가능':action.reason==='missing-ability'?'현재 보석에 조합 능력이 없습니다':action.reason==='not-owner'?'조종할 수 없는 보석입니다':action.reason==='game-over'?'게임이 끝났습니다':'지금은 사용할 수 없습니다'}`);
}


/** A source-unacquired command is noise; an acquired but blocked one still explains its condition. */
export function showGemAction(action){return action.reason!=='missing-ability';}

/** Reparent existing controls once. Their IDs, event bindings and game commands are preserved. */
export function simplifyPlayShell(doc){
 const app=doc.getElementById('gameApp');if(app.dataset.simpleUi==='true')return;
 const byId=id=>doc.getElementById(id),drawer=byId('gameDrawer');
 const fold=(first,last,label,id)=>{
  const group=doc.createElement('details');group.id=id;group.className='menu-group';
  const summary=doc.createElement('summary');summary.textContent=label;group.append(summary);first.before(group);
  let node=first;while(node){const next=node.nextElementSibling;group.append(node);if(node===last)break;node=next;}
  return group;
 };
 const controls=doc.createElement('section');controls.className='menu-controls';controls.setAttribute('aria-label','게임 조작');
 const title=doc.createElement('h3');title.textContent='게임 조작';controls.append(title,byId('reset'),doc.querySelector('.speed-control'));
 drawer.querySelector('.drawer-head').after(controls);
 doc.querySelector('.header-actions').prepend(byId('play'));
 controls.after(byId('ownedExplorer'));
 const difficulty=doc.createElement('p');difficulty.className='menu-difficulty';difficulty.append('난이도 · ',byId('difficultyTag'));controls.append(difficulty);
 const save=drawer.querySelector('.save-section');fold(save,save,'저장·이어하기','saveOptions');
 const training=byId('trainingOptions');fold(training.previousElementSibling.previousElementSibling,byId('trainingStatus'),'광산 관리','mineOptions');
 const research=byId('rsR000Btn').closest('.research');fold(research.previousElementSibling.previousElementSibling,byId('rsR002Btn').closest('.research'),'보석 연구','researchOptions');
 const casino=byId('casinoPanel');fold(casino,casino,'도박장','casinoOptions');
 fold(byId('devInfo'),byId('replayDetails'),'실행 정보·조작 기록','advancedOptions');
 const meta=doc.querySelector('.gem-meta'),summary=meta.querySelector('summary');summary.textContent='정보·강화';
 const body=doc.createElement('div');body.className='gem-detail-body';
 body.append(byId('gemCombatTarget'),doc.querySelector('.gem-stats'),byId('gemUpgrades'),byId('upgradeStatus'),byId('gemTargetAbilities'));
 for(const child of [...meta.children])if(child!==summary)body.append(child);
 meta.append(body);app.dataset.simpleUi='true';
}


/** Board art and its hit footprint share the same dimensions, including at phone zoom. */
export function gemSpriteSize(footprintPixels,stone=false){return Math.max(1,Math.floor(Math.min(footprintPixels,stone?footprintPixels*.8:footprintPixels*.95,stone?48:62)));}
export function remainingBuildSlots(state,pending=[]){return Math.max(0,5-(state.buildCount??0)-pending.length);}
export function screenFootprintBox(point,size,cam,width,height){
 const left=Math.round((point.x-size/2-cam.cx)*cam.zoom+width/2),right=Math.round((point.x+size/2-cam.cx)*cam.zoom+width/2);
 const top=Math.round(-(point.y+size/2-cam.cy)*cam.zoom+height/2),bottom=Math.round(-(point.y-size/2-cam.cy)*cam.zoom+height/2);
 return {left,top,width:Math.max(1,right-left),height:Math.max(1,bottom-top)};
}
/** Screen-space source spawn -> entry direction; no new path or movement rule. */
export function ingressMarker(from,to,box,outgoing=false){
 const angle=Math.atan2(to.y-from.y,to.x-from.x),c=Math.cos(angle),s=Math.sin(angle),half=8*(Math.abs(c)+Math.abs(s)),gap=2;
 const horizontal=Math.abs(to.x-from.x)>=Math.abs(to.y-from.y),forward=horizontal?c>=0:s>=0;
 const side=horizontal?(forward!==outgoing?'left':'right'):(forward!==outgoing?'top':'bottom');
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 return {x:side==='left'?box.left-half-gap:side==='right'?box.left+box.width+half+gap:clamp(to.x,box.left+half,box.left+box.width-half),y:side==='top'?box.top-half-gap:side==='bottom'?box.top+box.height+half+gap:clamp(to.y,box.top+half,box.top+box.height-half),angle:angle*180/Math.PI,side};
}
/** Source life observation only. Initial state, purchases and unchanged life are silent. */
export function lifeLossFeedback(previous,current){
 return Number.isFinite(previous)&&Number.isFinite(current)&&current<previous?`광산 도달 · 생명 ${previous-current} 감소`:null;
}

/** World-space centre visibility. A large off-field picture must not peek into a local field. */
export function pointInBattlefield(point,bounds){
 if(!point||!bounds||![point.x,point.y,bounds.minX,bounds.minY,bounds.maxX,bounds.maxY].every(Number.isFinite))return false;
 return point.x>=bounds.minX&&point.x<=bounds.maxX&&point.y>=bounds.minY&&point.y<=bounds.maxY;
}
