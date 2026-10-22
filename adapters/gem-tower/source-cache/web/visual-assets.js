/** Reuses ClaudeCraft's manifest -> cached Image -> atlas frame -> drawImage/fallback flow.
 * Adapted for the existing GemTower view; gameplay never imports this module.
 * Existing art is copied byte-for-byte. Colour variants are view-only cached Canvas composites.
 */
export function resolveVisualKey(entries, aliases, input) {
  const key=aliases?.[input]??input;
  const parts=key.split(':');
  for(const candidate of [key,...parts.slice(0,-1).map((_,i)=>parts.slice(0,parts.length-1-i).join(':')+':*')])if(entries[candidate])return candidate;
  return null;
}
export function spriteFrame(spec,tick=0){
 const f=spec.frame,count=spec.frames??1;
 if(!f||![f.x,f.y,f.w,f.h,count].every(Number.isInteger)||f.x<0||f.y<0||f.w<=0||f.h<=0||count<=0)throw Error('invalid sprite frame');
 const frame=Math.floor(Math.max(0,tick)*.05*(spec.fps??0))%count;
 return {x:f.x+frame*f.w,y:f.y,w:f.w,h:f.h};
}
const browserImage=src=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(Error('sprite load failed: '+src));image.src=src;});
export class SpriteBank{
 constructor(options={}){this.fetch=options.fetch??globalThis.fetch?.bind(globalThis);this.loadImage=options.loadImage??browserImage;this.entries={};this.aliases={};this.loaded=new Map();this.images=new Map();this.tints=new Map();this.errors=[];this.drawn=0;this.ready=false;}
 async load(url){
  try{
   const res=await this.fetch(url);if(!res.ok)throw Error('sprite manifest HTTP error');const manifest=await res.json();
   if(manifest.version!==1||!manifest.entries||typeof manifest.entries!=='object')throw Error('invalid sprite manifest');
   this.entries=manifest.entries;this.aliases=manifest.aliases??{};
   await Promise.all(Object.entries(this.entries).map(async([key,spec])=>{try{
    if(typeof spec.src!=='string'||!/^sprites\/[a-zA-Z0-9_/-]+\.png$/.test(spec.src)||spec.src.includes('..'))throw Error('invalid sprite path');
    const frame=spriteFrame(spec,0),imageURL=new URL(spec.src,url);
    const build=new URL(url).searchParams.get('build');if(build)imageURL.searchParams.set('build',build);
    const src=imageURL.href;
    if(!this.images.has(src))this.images.set(src,this.loadImage(src));
    const image=await this.images.get(src),width=image.naturalWidth??image.width,height=image.naturalHeight??image.height;
    if(frame.x+frame.w*(spec.frames??1)>width||frame.y+frame.h>height)throw Error('atlas out of bounds');
    this.loaded.set(key,{spec,image,key,src});
   }catch(error){this.errors.push(key+': '+error.message);}}));
  }catch(error){this.errors.push(error.message);}
  this.ready=true;return this;
 }
 get(key){const resolved=resolveVisualKey(this.entries,this.aliases,key);return resolved?this.loaded.get(resolved)??null:null;}
 draw(ctx,key,x,y,size,options={}){
  const sprite=this.get(key);if(!sprite)return false;
  const frame=spriteFrame(sprite.spec,options.tick??0);let source=sprite.image,rect=frame;
  if(options.tint){
   const cacheKey=sprite.src+JSON.stringify(frame)+options.tint;
   if(!this.tints.has(cacheKey)){
    const off=document.createElement('canvas');off.width=frame.w;off.height=frame.h;const c=off.getContext('2d');
    c.drawImage(source,frame.x,frame.y,frame.w,frame.h,0,0,frame.w,frame.h);
    c.globalCompositeOperation='color';c.fillStyle=options.tint;c.fillRect(0,0,frame.w,frame.h);
    c.globalCompositeOperation='destination-in';c.drawImage(source,frame.x,frame.y,frame.w,frame.h,0,0,frame.w,frame.h);
    this.tints.set(cacheKey,off);
   }
   source=this.tints.get(cacheKey);rect={x:0,y:0,w:frame.w,h:frame.h};
  }
  ctx.save();ctx.imageSmoothingEnabled=false;
  ctx.fillStyle='rgba(14,31,20,.26)';ctx.beginPath();ctx.ellipse(x,y+size*.18,size*.26,size*.09,0,0,Math.PI*2);ctx.fill();
  ctx.translate(Math.round(x),Math.round(y));if(options.flip)ctx.scale(-1,1);
  const anchor=options.anchor??.5;
  ctx.drawImage(source,rect.x,rect.y,rect.w,rect.h,Math.round(-size/2),Math.round(-size*anchor),Math.round(size),Math.round(size));
  ctx.restore();this.drawn++;return true;
 }
}
