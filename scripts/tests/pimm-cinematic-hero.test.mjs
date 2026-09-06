import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

async function harness({reduced=false, saveData=false, denied=false, alpha}={}) {
  let Controller;
  const hero={dataset:{}};
  const motion={matches:reduced,addEventListener(){}};
  const doc={hidden:false,addEventListener(){}};
  if(alpha!==undefined)doc.createElement=()=>({getContext:()=>({drawImage(){},getImageData:()=>({data:[0,0,0,alpha]})})});
  const videos=Array.from({length:4},(_,i)=>({
    dataset:{src:`shot-${i}.webm`},events:{},currentTime:0,plays:0,paused:true,
    classList:{toggle(name,on){this.current=on;},remove(){this.current=false;}},
    addEventListener(name,cb){this.events[name]=cb;},getAttribute(){return this.src;},
    removeAttribute(){delete this.src;},load(){},pause(){this.paused=true;},
    play(){this.paused=false;this.plays++;return denied?Promise.reject(Error('denied')):Promise.resolve();}
  }));
  const button={hidden:true,addEventListener(n,cb){this.click=cb;},setAttribute(n,v){this[n]=v;}};
  class Element {constructor(){this.dataset={};}querySelectorAll(){return videos;}querySelector(){return button;}closest(){return hero;}}
  vm.runInNewContext(await readFile(new URL('../../assets/maliev-pimm-cinematic.js',import.meta.url),'utf8'),{
    HTMLElement:Element,AbortController,window:{IntersectionObserver:true},document:doc,navigator:{connection:{saveData}},matchMedia:()=>motion,
    IntersectionObserver:class {constructor(cb){this.cb=cb;}observe(){}disconnect(){}},
    customElements:{get(){},define(n,c){Controller=c;}}
  });
  const el=new Controller();el.connectedCallback();el.observer.cb([{isIntersecting:true}]);
  return {el,videos,button,hero,motion,doc};
}
test('four authored shots play in order and wrap after the full-machine shot',async()=>{
  const {el,videos}=await harness();
  for(let i=0;i<4;i++){
    assert.equal(el.index,i);videos[i].events.playing();assert.equal(videos[i].classList.current,true);
    videos[i].events.ended();
  }
  assert.equal(el.index,0);assert.equal(videos[0].plays,2);
});
test('pause, offscreen and hidden tabs preserve the current shot timeline',async()=>{
  const {el,videos,button,hero,doc}=await harness();videos[0].events.playing();videos[0].currentTime=1.2;
  button.click();assert.equal(videos[0].paused,true);assert.equal(hero.dataset.cinematicPlaying,'false');
  button.click();assert.equal(videos[0].currentTime,1.2);
  doc.hidden=true;el.sync();assert.equal(videos[0].paused,true);
  doc.hidden=false;el.visible=false;el.sync();assert.equal(videos[0].paused,true);
});
test('reduced motion and data saving do not request video',async()=>{
  for(const options of [{reduced:true},{saveData:true}]){
    const {videos}=await harness(options);assert.ok(videos.every(v=>!v.src && v.plays===0));
  }
});
test('failure and changing reduced-motion preference restore static fallback',async()=>{
  const {el,videos,button}=await harness({denied:true});await Promise.resolve();await Promise.resolve();
  assert.equal(el.failed,true);assert.equal(el.dataset.started,undefined);assert.equal(button.hidden,true);
  const h=await harness();h.videos[0].events.playing();h.motion.matches=true;h.el.sync();
  assert.equal(h.el.dataset.started,undefined);h.videos[0].events.playing();assert.equal(h.videos[0].paused,true);
});
test('disconnect releases videos and ignores a pending autoplay rejection',async()=>{
  const {el,videos}=await harness({denied:true});el.disconnectedCallback();
  await Promise.resolve();await Promise.resolve();
  assert.ok(videos.every(video=>video.paused&&!video.src));assert.equal(el.abort,null);
});
test('opaque video decoders keep the transparent poster instead of a black rectangle',async()=>{
  const bad=await harness({alpha:255});bad.videos[0].events.playing();
  assert.equal(bad.el.failed,true);assert.equal(bad.el.dataset.started,undefined);
  const good=await harness({alpha:0});good.videos[0].events.playing();
  assert.equal(good.el.dataset.started,'true');assert.ok(good.videos[1].src);
});

test('a theme-editor reconnect starts from the poster and rechecks video alpha',async()=>{
  const {el,videos,button}=await harness({alpha:0});
  videos[0].events.playing();button.click();el.disconnectedCallback();el.connectedCallback();
  assert.equal(el.alphaChecked,false);assert.equal(el.dataset.started,undefined);
  assert.equal(button.hidden,true);assert.equal(button['aria-pressed'],'false');
  assert.ok(videos.every(video=>!video.classList.current));
});

test('the four released alpha clips match the verified native-render manifest',async()=>{
  const manifest=JSON.parse(await readFile(new URL('../../assets/pimm-cinematic-r58.json',import.meta.url),'utf8'));
  assert.equal(manifest.alpha,true);
  assert.equal(manifest.fps,24);
  assert.equal(manifest.frames_per_shot,96);
  assert.deepEqual(manifest.shots.map(shot=>shot.shot),['drive','control','tooling','complete']);
  assert.equal(manifest.frames.length,384);
  assert.equal(new Set(manifest.frames.map(frame=>frame.filename)).size,384);
  assert.equal(manifest.outputs.length,5);
  for(const output of manifest.outputs){
    const bytes=await readFile(new URL(`../../assets/${output.filename}`,import.meta.url));
    assert.equal(bytes.length,output.bytes);
    assert.equal(createHash('sha256').update(bytes).digest('hex'),output.sha256);
    if(output.filename.endsWith('.webm')){
      assert.equal(output.width,960);assert.equal(output.height,1080);
      assert.equal(output.nb_read_frames,'96');assert.equal(output.tags.alpha_mode,'1');
    }
  }
});
