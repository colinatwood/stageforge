const assert = require('node:assert/strict');
const {mountDawProduction} = require('../frontend/production.js');

class Element {
  constructor(value='') { this.value=value; this.handlers={}; this.attributes={}; this.textContent=''; this.disabled=false; }
  addEventListener(name, handler) { this.handlers[name]=handler; }
  setAttribute(name, value) { this.attributes[name]=value; }
}

async function main() {
  const ids=['dawPlaybackStart','dawPlaybackLoop','dawPlaybackStop','dawCaptureStart','dawCaptureFinish','dawCaptureAbort','dawProductionRefresh','dawTempCleanup','dawProductionStatus','captureFinishName'];
  const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));
  nodes.dawPlaybackBegin=new Element('1'); nodes.dawPlaybackEnd=new Element('2');
  const calls=[];
  const projection={canonicalSampleRate:192000,playback:{producer:{running:false}},capture:{state:'idle'},recovery:{files:[]},temporaryResources:{resourceCount:2,reclaimableCount:1},physicalOutputsArmed:false};
  const request=async(path, options)=>{ calls.push({path,options}); if(path.endsWith('/production'))return projection; return {state:'idle'}; };
  const mounted=mountDawProduction({querySelector:id=>nodes[id.slice(1)]},request,()=>true);
  await mounted.ready;
  assert.match(nodes.dawProductionStatus.textContent,/192 kHz.*outputs disarmed/);
  await nodes.dawPlaybackStart.handlers.click();
  assert.deepEqual(JSON.parse(calls[1].options.body),{action:'start',startFrame:192000,endFrame:384000});
  nodes.dawPlaybackBegin.value='0'; nodes.dawPlaybackEnd.value=String(256/192000);
  await nodes.dawPlaybackLoop.handlers.click();
  assert.equal(JSON.parse(calls[3].options.body).action,'loop');
  const beforeAbort=calls.length; await nodes.dawCaptureAbort.handlers.click();
  assert.equal(JSON.parse(calls[beforeAbort].options.body).action,'abort');
  assert.equal(nodes.dawProductionStatus.attributes['aria-busy'],'false');
  await nodes.dawTempCleanup.handlers.click();assert.equal(JSON.parse(calls.at(-1).options.body).acknowledgeCleanup,true);
  const denied=mountDawProduction({querySelector:id=>nodes[id.slice(1)]},request,()=>false); await denied.ready;
  const beforeDenied=calls.length; await nodes.dawCaptureAbort.handlers.click(); assert.equal(calls.length,beforeDenied);
}
main().catch(error=>{console.error(error);process.exitCode=1;});
