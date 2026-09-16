const assert=require('node:assert/strict');
global.crypto={randomUUID:()=> 'uuid'};const {render}=require('../frontend/automation.js');
class Element{
 constructor(value=''){this.value=value;this.dataset={};this.handlers={};this.children=[];this.style={};this.attributes={};this.clientWidth=100;this.clientHeight=100;this.disabled=false;this.textContent='';}
 addEventListener(name,handler){this.handlers[name]=handler;}setAttribute(name,value){this.attributes[name]=value;}replaceChildren(){this.children=[];this.value='';}appendChild(child){this.children.push(child);if(!this.value)this.value=child.value;}
}
async function main(){
 const ids=['dawAutomationNew','dawAutomationTrack','dawAutomationPoint','dawAutomationSeconds','dawAutomationValue','dawAutomationSave','dawAutomationDelete','dawAutomationLane','dawAutomationStatus'];const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));nodes.dawAutomationSeconds.value='2';nodes.dawAutomationValue.value='.5';
 const doc={querySelector:id=>nodes[id.slice(1)],createElement:()=>new Element()};const edits=[];const session={tracks:[{trackId:'vox',name:'Vox',automation:[{pointId:'v1',parameter:'volume',frame:192000,value:1,interpolation:'linear'}]}]};
 render({doc,session,zoomSeconds:10,onEdit:value=>edits.push(value)});assert.equal(nodes.dawAutomationLane.children.length,1);assert.match(nodes.dawAutomationStatus.textContent,/1 linear/);
 const point=nodes.dawAutomationLane.children[0];point.handlers.click();assert.equal(nodes.dawAutomationPoint.value,'v1');assert.equal(nodes.dawAutomationDelete.disabled,false);
 nodes.dawAutomationSave.handlers.click();await Promise.resolve();assert.equal(edits[0].action,'upsert');assert.equal(edits[0].pointId,'v1');
 point.handlers.pointerdown({clientX:0,clientY:0,pointerId:1});point.handlers.pointerup({clientX:10,clientY:25});assert.equal(edits[1].frame,384000);assert.equal(edits[1].value,.5);
 await Promise.resolve();nodes.dawAutomationDelete.handlers.click();await Promise.resolve();assert.deepEqual(edits[2],{action:'delete',trackId:'vox',pointId:'v1'});
 nodes.dawAutomationPoint.value='';nodes.dawAutomationSave.handlers.click();assert.match(edits[3].pointId,/^automation-.+/);
 await Promise.resolve();
 let rejectEdit,calls=0;
 render({doc,session,zoomSeconds:10,onEdit:()=>{calls++;return new Promise((resolve,reject)=>{rejectEdit=reject;});}});
 nodes.dawAutomationSave.handlers.click();nodes.dawAutomationSave.handlers.click();
 assert.equal(calls,1,'repeat requests are blocked and current callback is used');
 assert.equal(nodes.dawAutomationSave.disabled,true);
 rejectEdit(new Error('Stale session revision'));await Promise.resolve();
 assert.equal(nodes.dawAutomationStatus.textContent,'Stale session revision');
 assert.equal(nodes.dawAutomationSave.disabled,false);
 assert.equal(nodes.dawAutomationStatus.attributes['aria-busy'],'false');
 const precise={pointId:'shared',parameter:'volume',frame:192001,value:0.123456789,interpolation:'linear'};
 const twoTracks={tracks:[{trackId:'vox',name:'Vox',automation:[precise]},{trackId:'keys',name:'Keys',automation:[{...precise,frame:200,value:1}]}]};
 render({doc,session:twoTracks,zoomSeconds:10,onEdit:edit=>edits.push(edit)});
 nodes.dawAutomationLane.children[0].handlers.click();
 nodes.dawAutomationSave.handlers.click();await Promise.resolve();
 assert.equal(edits.at(-1).frame,192001,'unchanged selection preserves exact canonical frame');
 assert.equal(edits.at(-1).value,precise.value,'unchanged selection preserves full gain precision');
 nodes.dawAutomationTrack.value='keys';nodes.dawAutomationTrack.handlers.change();
 assert.equal(nodes.dawAutomationPoint.value,'','same point ID on another track must not retain selection');
 assert.equal(nodes.dawAutomationDelete.disabled,true);
 nodes.dawAutomationLane.children[0].handlers.click();nodes.dawAutomationNew.handlers.click();
 assert.equal(nodes.dawAutomationPoint.value,'');assert.equal(nodes.dawAutomationDelete.disabled,true);
 const count=edits.length;nodes.dawAutomationSeconds.value='';nodes.dawAutomationSave.handlers.click();
 assert.equal(edits.length,count,'blank time must not silently become frame zero');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
