/** Read-only GemTower handbook adapter. The original recipe facilities declare
 * their note abilities in uabi; atp1/aub1 remain the authority, not parsed rules.
 * No inventory, executable combinations, stats, costs or availability are inferred.
 * Keep this plain JS independent of generated dist files for intake and tests. */
const SECTIONS=[{unitId:'h00E',category:'gem'},{unitId:'h034',category:'slate'}];
const MESSAGES={
 'invalid-objects':'원작 조합 설명 자료를 읽을 수 없습니다.',
 'missing-unit':'원작 조합 설명 시설을 찾을 수 없습니다.',
 'invalid-ability-list':'원작 조합 설명 목록을 읽을 수 없습니다.',
 'invalid-ability-id':'원작 조합 설명의 연결을 확인할 수 없습니다.',
 'missing-ability':'연결된 원작 조합 설명을 찾을 수 없습니다.',
 'missing-title':'원작 조합 설명의 제목을 읽을 수 없습니다.',
 'missing-description':'원작 조합 설명의 본문을 읽을 수 없습니다.',
 'invalid-strings':'원작 번역 자료를 읽을 수 없습니다.',
 'missing-string':'일부 원작 설명의 번역을 찾을 수 없습니다.',
};
// Original handbook padding separates lines; retain it without parsing ingredients.
const displayText=text=>text.replace(/\|c[0-9a-f]{8}|\|r/gi,'').replace(/\|n/gi,'\n').replace(/\r\n?/g,'\n').replace(/[\t ]{3,}/g,'\n').split('\n').map(line=>line.replace(/[\t ]+/g,' ').trim()).join('\n').trim().normalize('NFC');
const searchable=text=>displayText(text).replace(/\s+/g,' ').trim().toLowerCase();
/** First-level source note only. A level-two tooltip is not a fallback recipe. */
function field(object,name){
 let found,level=-1;
 for(const mod of Array.isArray(object?.mods)?object.mods:[]){
  const at=mod?.level??0;
  if(mod?.field===name&&Number.isInteger(at)&&at>=0&&at<=1&&at>=level){found=mod;level=at;}
 }
 return found;
}
export function extractRecipeBook(ir,options={}){
 const rows=[],warnings=[];
 const warn=(code,source={})=>warnings.push({code,message:MESSAGES[code],...source});
 if(!Array.isArray(ir?.objectMods)){warn('invalid-objects');return {rows,warnings};}
 const objects=ir.objectMods,find=(kind,id)=>objects.findLast(o=>o?.kind===kind&&(o.newId??o.baseId)===id);
 let strings=options?.strings;
 if(strings!==undefined&&typeof strings?.get!=='function'){warn('invalid-strings');strings=undefined;}
 // Same single-pass TRIGSTR token policy as formats/wts.resolveWtsText. This leaf
 // cannot import generated dist or TS at browser intake; supplied WTS stays data.
 const text=(raw,source)=>{
  const missing=new Set();
  const resolved=raw.replace(/TRIGSTR_(\d+)/g,(token,id)=>{
   const value=strings?.get(Number(id));if(typeof value==='string')return value;
   if(!missing.has(token)){warn('missing-string',{...source,token});missing.add(token);}return token;
  });
  return displayText(resolved);
 };
 for(const section of SECTIONS){
  const unit=find('unit',section.unitId);
  if(!unit){warn('missing-unit',{unitId:section.unitId});continue;}
  const list=field(unit,'uabi')?.value;
  if(typeof list!=='string'){warn('invalid-ability-list',{unitId:section.unitId});continue;}
  const seen=new Set();
  for(const id of list.split(',').map(id=>id.trim())){
   if(!id||id==='_ '||id==='_')continue;
   if(seen.has(id))continue;seen.add(id);
   const source={unitId:section.unitId,abilityId:id};
   if(!/^[\x20-\xff]{4}$/.test(id)){warn('invalid-ability-id',source);continue;}
   const ability=find('ability',id);
   // Both original facilities also carry stock invulnerability, not a note.
   if(id==='Avul'&&!ability)continue;
   if(!ability){warn('missing-ability',source);continue;}
   const titleMod=field(ability,'atp1')??field(ability,'anam'),descriptionMod=field(ability,'aub1');
   if(typeof titleMod?.value!=='string'||!titleMod.value.trim()){warn('missing-title',source);continue;}
   if(typeof descriptionMod?.value!=='string'||!descriptionMod.value.trim()){warn('missing-description',source);continue;}
   const title=text(titleMod.value,{...source,field:titleMod.field}),description=text(descriptionMod.value,{...source,field:'aub1'});
   if(!title){warn('missing-title',source);continue;}
   if(!description){warn('missing-description',source);continue;}
   rows.push({id:section.category+':'+id,category:section.category,title,description,rawTitle:titleMod.value,rawDescription:descriptionMod.value,
    source:{...source,titleField:titleMod.field,descriptionField:'aub1',level:1}});
  }
 }
 return {rows,warnings};
}
/** Search original display text only; filtering never consults or changes a world. */
export function recipeBookRows(book,options={}){
 const rows=Array.isArray(book?.rows)?book.rows:[],category=options?.category??'all',query=typeof options?.query==='string'?searchable(options.query):'';
 if(!['all','gem','slate'].includes(category))return [];
 return rows.filter(row=>row&&typeof row.title==='string'&&typeof row.description==='string'&&(category==='all'||row.category===category)&&(!query||searchable(row.title+' '+row.description).includes(query)));
}
