/** View-only choices for units hit by the existing map picker. No world commands. */
export function mountOverlapPicker(doc,onSelect){
 const panel=doc.createElement('section');panel.id='overlapPicker';panel.className='overlap-picker';panel.hidden=true;panel.setAttribute('aria-label','겹친 건물 선택');
 const title=doc.createElement('p');title.className='overlap-title';
 const list=doc.createElement('div');list.className='overlap-choices';list.setAttribute('role','group');list.setAttribute('aria-label','이 위치에서 선택');panel.append(title,list);
 doc.getElementById('gemNone').before(panel);const buttons=new Map();let signature='';
 return {render(items=[],selectedId=null){
  const next=JSON.stringify([items.map(item=>[item.id,item.name]),selectedId]);if(signature===next)return;signature=next;panel.hidden=items.length<2;title.textContent=`이 위치의 건물 ${items.length}개 · 누를 대상을 고르세요`;
  const keep=new Set();for(const item of items){keep.add(item.id);let button=buttons.get(item.id);
   if(!button){button=doc.createElement('button');button.type='button';button.className='sec overlap-choice';button.dataset.unitId=String(item.id);button.addEventListener('click',()=>onSelect(item.id));list.append(button);buttons.set(item.id,button);}
   button.textContent=item.name;button.setAttribute('aria-label',`${item.name} 선택`);button.setAttribute('aria-pressed',String(item.id===selectedId));button.title=item.name;
  }
  for(const [id,button]of buttons)if(!keep.has(id)){button.remove();buttons.delete(id);}
 }};
}
