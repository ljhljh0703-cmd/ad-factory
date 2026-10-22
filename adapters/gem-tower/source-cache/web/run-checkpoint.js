/** Schedule synchronous checkpoints around the existing atomic save writer.
 * Each world owns one controller. Only a successful write marks a revision saved;
 * neither snapshots nor writes run for skipped attempts. No game state lives here. */
export function createRunCheckpoint(write,{intervalMs=30000}={}){
 if(typeof write!=='function')throw TypeError('checkpoint write must be a function');
 if(!Number.isFinite(intervalMs)||intervalMs<=0)throw RangeError('invalid checkpoint interval');
 let lastAttemptAt=null,lastObservedAt=null,lastSavedRevision,hasSavedRevision=false;
 return {
  attempt({now,eligible,revision,force=false,snapshot}={}){
   if(!eligible)return {kind:'skipped',reason:'ineligible'};
   if(!Number.isFinite(now)||now<0)return {kind:'failed',error:RangeError('invalid checkpoint time')};
   if(lastObservedAt!==null&&now<lastObservedAt)return {kind:'skipped',reason:'clock'};
   lastObservedAt=now;
   if(hasSavedRevision&&Object.is(revision,lastSavedRevision))return {kind:'skipped',reason:'unchanged'};
   if(!force&&lastAttemptAt!==null&&now-lastAttemptAt<intervalMs)return {kind:'skipped',reason:'interval',nextAt:lastAttemptAt+intervalMs};
   // Start the throttle before taking a snapshot so either failure path is bounded.
   lastAttemptAt=now;
   try{
    const record=write(snapshot(),now);
    lastSavedRevision=revision;hasSavedRevision=true;
    return {kind:'saved',record,revision,savedAt:now};
   }catch(error){return {kind:'failed',error};}
  }
 };
}
