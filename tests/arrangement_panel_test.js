const assert=require('node:assert/strict');
const {snapFrames,bindClips}=require('../frontend/arrangement.js');
class Button {
  constructor(id='clip-1'){this.dataset={dawClip:id,dawTrack:'vox'};this.handlers={};this.parentElement={clientWidth:100};this.attributes={};this.style={};}
  addEventListener(name,handler){this.handlers[name]=handler;}
  setAttribute(name,value){this.attributes[name]=value;}
}
async function main(){
  const button=new Button();const edits=[];const selections=[];
  const session={tempoMap:[{bpm:120,numerator:4}],tracks:[{trackId:'vox',clips:[{clipId:'clip-1',startFrame:100,lengthFrames:192000}]},{trackId:'band',clips:[]}]};
  assert.equal(snapFrames(session,'sixteenth'),24000);assert.equal(snapFrames(session,'beat'),96000);assert.equal(snapFrames(session,'bar'),384000);
  const lane={closest:()=>({dataset:{dawLane:'band'}})};
  const doc={querySelectorAll:()=>[button],elementFromPoint:()=>lane};
  bindClips({doc,session,zoomSeconds:10,snap:'beat',onSelect:id=>selections.push(id),onEdit:edit=>edits.push(edit)});
  button.handlers.click({});assert.deepEqual(selections,[['clip-1']]);assert.match(button.attributes['aria-label'],/Drag or use arrow keys/);
  button.handlers.pointerdown({clientX:0,pointerId:1,target:button});button.handlers.pointermove({clientX:25});assert.equal(button.style.transform,'translateX(25px)');button.handlers.pointerup({clientX:50,clientY:10});assert.equal(button.style.transform,'');
  assert.deepEqual(edits[0],{op:'move',clipId:'clip-1',startFrame:960100,targetTrackId:'band',snapFrames:96000});
  let prevented=false;button.handlers.keydown({key:'ArrowLeft',altKey:true,preventDefault:()=>{prevented=true;}});
  assert.equal(prevented,true);assert.deepEqual(edits[1],{op:'move',clipId:'clip-1',startFrame:0,targetTrackId:'vox',snapFrames:1});
  const startHandle={dataset:{dawResize:'start'}};button.handlers.pointerdown({clientX:0,pointerId:2,target:startHandle});button.handlers.pointermove({clientX:10});assert.match(button.style.width,/calc/);button.handlers.pointerup({clientX:10,clientY:0});assert.equal(edits[2].op,'resize');assert.equal(edits[2].endFrame,192100);
  button.handlers.keydown({key:']',preventDefault:()=>{}});assert.deepEqual(edits[3],{op:'resize',clipId:'clip-1',startFrame:100,endFrame:96100,snapFrames:96000});
  const second=new Button('clip-2');session.tracks[0].clips.push({clipId:'clip-2',startFrame:300000,lengthFrames:192000});doc.querySelectorAll=()=>[button,second];
  bindClips({doc,session,zoomSeconds:10,snap:'beat',onSelect:ids=>selections.push(ids),onEdit:edit=>edits.push(edit)});
  const countBefore=selections.length;
  second.handlers.pointerdown({clientX:0,pointerId:3,target:second,shiftKey:true});
  second.handlers.pointerup({clientX:0,clientY:0});
  assert.equal(selections.length,countBefore,'pointerdown must not rerender before capture');
  second.handlers.click({shiftKey:true});assert.deepEqual(selections.at(-1),['clip-1','clip-2']);
  button.handlers.keydown({key:'ArrowRight',altKey:false,preventDefault:()=>{}});assert.deepEqual(edits.at(-1),{op:'moveMany',clipIds:['clip-1','clip-2'],deltaFrames:96000,snapFrames:96000});
  second.handlers.pointerdown({clientX:0,pointerId:4,target:second,ctrlKey:true});
  second.handlers.pointerup({clientX:0,clientY:0});second.handlers.click({ctrlKey:true});
  assert.deepEqual(selections.at(-1),['clip-1']);
  const beforeDrag=selections.length;
  second.handlers.pointerdown({clientX:0,pointerId:5,target:second});
  assert.equal(selections.length,beforeDrag,'unselected drag must not detach its button');
  assert.equal(second.attributes['aria-pressed'],'true');
  second.handlers.pointerup({clientX:5,clientY:0});second.handlers.click({});
  assert.equal(edits.at(-1).op,'move');assert.equal(edits.at(-1).clipId,'clip-2');
  assert.equal(selections.length,beforeDrag,'post-drag click must be suppressed');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
