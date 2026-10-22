import {recipeBookRows} from './recipe-book.js';
/** On-demand source recipe guide. It cannot issue orders or decide combination eligibility. */
export function mountRecipeBook(doc){
 const group=doc.createElement('details');group.id='recipeOptions';group.className='menu-group';
 const summary=doc.createElement('summary');summary.textContent='보석 · 슬레이트 조합표';group.append(summary);
 const intro=doc.createElement('p');intro.className='recipe-intro';intro.textContent='보석을 선택하면 사용할 수 있는 조합 버튼이 나옵니다.';
 const filters=doc.createElement('div');filters.className='recipe-filters';filters.setAttribute('role','group');filters.setAttribute('aria-label','조합 종류');
 let category='gem',book=null,query='';const choices=[];
 for(const [value,label] of [['gem','보석'],['slate','슬레이트'],['all','전체']]){
  const button=doc.createElement('button');button.type='button';button.textContent=label;button.dataset.recipeCategory=value;button.setAttribute('aria-pressed',String(value===category));
  button.addEventListener('click',()=>{category=value;render();});filters.append(button);choices.push(button);
 }
 const label=doc.createElement('label');label.htmlFor='recipeSearch';label.className='recipe-search-label';label.textContent='이름 · 재료 검색';
 const search=doc.createElement('input');search.type='search';search.id='recipeSearch';search.placeholder='예: 루비, 독, 슬레이트';search.autocomplete='off';
 const status=doc.createElement('p');status.id='recipeStatus';status.setAttribute('role','status');
 const list=doc.createElement('div');list.id='recipeList';
 const warning=doc.createElement('p');warning.className='recipe-warning';warning.hidden=true;
 group.append(intro,filters,label,search,status,list,warning);doc.getElementById('saveOptions').before(group);
 search.addEventListener('input',()=>{query=search.value;render();});
 function render(){
  const rows=recipeBookRows(book??{rows:[]},{category,query});
  for(const button of choices)button.setAttribute('aria-pressed',String(button.dataset.recipeCategory===category));
  status.textContent=rows.length?`${rows.length}개 항목 · 원작 레시피 책`:'검색 결과가 없습니다';list.replaceChildren();
  for(const row of rows){
   const item=doc.createElement('details');item.className='recipe-item';item.dataset.recipeId=row.id;item.open=Boolean(query.trim());
   const title=doc.createElement('summary');title.textContent=row.title;
   const description=doc.createElement('p');description.textContent=row.description;item.append(title,description);list.append(item);
  }
  warning.hidden=!(book?.warnings?.length);warning.textContent=warning.hidden?'':'일부 조합 설명을 불러오지 못했습니다.';
 }
 render();return {setBook(next){if(book===next)return;book=next;render();}};
}
