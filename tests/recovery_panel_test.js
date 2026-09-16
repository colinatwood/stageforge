const assert = require('node:assert/strict');
const {mountRecordingRecovery} = require('../frontend/recovery.js');
class Element {
  constructor() { this.options=[]; this.handlers={}; }
  get value() { return this.options[0]?.value || ''; }
  addEventListener(name, handler) { this.handlers[name]=handler; }
  replaceChildren() { this.options=[]; }
  appendChild(option) { this.options.push(option); }
}
async function main() {
  const nodes=Object.fromEntries(['recoveryScan','recoveryFile','recoveryCreate','recoveryStatus'].map(id=>[id,new Element()]));
  let result={available:true,files:[{fileName:'<take>.partial.wav',bytes:52}]};
  let release; const calls=[];
  mountRecordingRecovery({querySelector:id=>nodes[id.slice(1)],createElement:()=>({})},async(path,options)=>{
    calls.push({path,options});
    if(options)return new Promise(resolve=>{release=resolve;});
    if(result instanceof Error)throw result;
    return result;
  });
  await nodes.recoveryScan.handlers.click();
  assert.equal(nodes.recoveryFile.options[0].textContent,'<take>.partial.wav (52 bytes)');
  const pending=nodes.recoveryCreate.handlers.click();
  assert.equal(nodes.recoveryCreate.disabled,true);
  await nodes.recoveryCreate.handlers.click();
  assert.equal(calls.length,2);
  assert.deepEqual(JSON.parse(calls[1].options.body),{action:'recover',fileName:'<take>.partial.wav'});
  release({frames:1,path:'recovered.wav',discardedTrailingBytes:0}); await pending;
  assert.match(nodes.recoveryStatus.textContent,/Original kept/);
  result={available:false,reason:'Pending capture',files:[]};
  await nodes.recoveryScan.handlers.click();
  assert.equal(nodes.recoveryCreate.disabled,true);
  assert.equal(nodes.recoveryStatus.textContent,'Pending capture');
  result=new Error('Connection failed'); await nodes.recoveryScan.handlers.click();
  assert.equal(nodes.recoveryStatus.textContent,'Connection failed');
  assert.equal(nodes.recoveryScan.disabled,false);
}
main().catch(error=>{console.error(error);process.exitCode=1;});
