/** View-only browser coordination; never reads or changes Sim/VM state. */
export function createFrameTask(task,{requestFrame=callback=>requestAnimationFrame(callback),cancelFrame=id=>cancelAnimationFrame(id)}={}){
 let frame=null,args=null,destroyed=false;
 function queue(...input){if(destroyed)return;args=input;if(frame!==null)return;frame=requestFrame(()=>{frame=null;const input=args;args=null;if(!destroyed)task(...(input??[]));});}
 queue.cancel=()=>{if(frame!==null)cancelFrame(frame);frame=null;args=null;};
 queue.destroy=()=>{destroyed=true;queue.cancel();};
 return queue;
}
export function resizeCanvasToHost(canvas,rect){
 if(!rect||!Number.isFinite(rect.width)||!Number.isFinite(rect.height)||rect.width<=0||rect.height<=0)return false;
 const width=Math.max(1,Math.floor(rect.width)),height=Math.max(1,Math.floor(rect.height));let changed=false;
 if(canvas.width!==width){canvas.width=width;changed=true;}if(canvas.height!==height){canvas.height=height;changed=true;}
 return changed;
}
