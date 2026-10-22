import {FLAG_NO_WALK,FLAG_NO_BUILD} from './dist/ir/pathing.js';
// Terrain remains a view of the existing WPM; no decorative cell becomes walkable.
export function terrainKind(flags){return flags&FLAG_NO_WALK?'wall':flags&FLAG_NO_BUILD?'path':'build';}
const FLOOR={build:[[74,103,62],[78,107,65],[71,100,59]],path:[[181,157,107],[188,164,113],[194,170,119]],wall:[[43,57,41],[47,61,44],[50,65,47]]};
export function terrainPixel(flags,col,row){const seed=(Math.imul(col,374761393)+Math.imul(row,668265263))|0,n=Math.imul(seed^(seed>>>13),1274126177)>>>0,tone=n%23<3?1:n%23<5?2:0;return FLOOR[terrainKind(flags)][tone];}
export function fieldRimRects(box,thickness=4){
 if(!box||![box.left,box.top,box.width,box.height,thickness].every(Number.isFinite)||box.width<=0||box.height<=0||thickness<=0)return [];
 const l=Math.floor(box.left),t=Math.floor(box.top),r=Math.ceil(box.left+box.width),b=Math.ceil(box.top+box.height),n=Math.ceil(thickness);
 return [{x:l-n,y:t-n,width:r-l+n*2,height:n},{x:l-n,y:b,width:r-l+n*2,height:n},{x:l-n,y:t,width:n,height:b-t},{x:r,y:t,width:n,height:b-t}];
}
/** Existing stone atlas is clipped to gutters; gameplay pixels stay uncovered. */
function paintFieldRim(ctx,box,sprites){
 for(const r of fieldRimRects(box)){
  ctx.save();ctx.beginPath();ctx.rect(r.x,r.y,r.width,r.height);ctx.clip();ctx.fillStyle='#3e4436';ctx.fillRect(r.x,r.y,r.width,r.height);
  for(let y=r.y;y<r.y+r.height;y+=16)for(let x=r.x;x<r.x+r.width;x+=16)sprites.draw(ctx,'terrain:stone',x+8,y+8,16,{anchor:.5,tick:0});
  ctx.restore();
 }
}
// One cached gutter image per sprite bank; static stone is not repainted every frame.
const rimCache=new WeakMap();
export function drawFieldRim(ctx,box,sprites){
 if(!ctx.canvas||typeof document==='undefined'||typeof sprites.get!=='function')return paintFieldRim(ctx,box,sprites);
 const texture=sprites.get('terrain:stone'),key=JSON.stringify([ctx.canvas.width,ctx.canvas.height,box,texture?.src??null]);let cached=rimCache.get(sprites);
 if(cached?.key!==key){const image=document.createElement('canvas');image.width=ctx.canvas.width;image.height=ctx.canvas.height;paintFieldRim(image.getContext('2d'),box,sprites);cached={key,image};rimCache.set(sprites,cached);}
 ctx.drawImage(cached.image,0,0);
}
/** Thin ground forecast only, below units. Partial blocked routes are never extended. */
export function drawBuildRoute(ctx,preview,project){
 if(!preview||preview.status==='invalid'||preview.points.length<2)return;
 ctx.save();ctx.beginPath();preview.points.forEach((p,index)=>{const q=project(p);if(index)ctx.lineTo(q.x,q.y);else ctx.moveTo(q.x,q.y);});
 ctx.lineWidth=2;ctx.lineJoin='round';ctx.lineCap='round';ctx.setLineDash([4,4]);ctx.strokeStyle=preview.status==='blocked'?'#efaa8c':'#eadcb1';ctx.stroke();ctx.restore();
}
