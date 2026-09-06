import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test('English hero typography uses the existing self-hosted Outfit without changing Thai or navigation',async()=>{
  const css=await readFile(new URL('../../assets/maliev-pimm-cinematic.css',import.meta.url),'utf8');
  assert.match(css,/\.pimm-machine__hero:lang\(en\)[\s\S]*?font-family: 'Outfit', sans-serif;/);
  assert.doesNotMatch(css,/\.mc-header/);
  const fonts=await readFile(new URL('../../assets/maliev-pimm-30g-hero.css',import.meta.url),'utf8');
  assert.match(fonts,/font-family: 'Outfit'/);
  assert.ok((await readFile(new URL('../../assets/Outfit-Latin.woff2',import.meta.url))).length>1000);
});

async function harness({reduced=false, saveData=false, denied=false, alpha}={}) {
  let Controller;
  const hero={dataset:{}};
  const motion={matches:reduced,addEventListener(){}};
  const doc={hidden:false,addEventListener(){}};
  if(alpha!==undefined)doc.createElement=()=>({getContext:()=>({drawImage(){},getImageData:()=>({data:[0,0,0,alpha]})})});
  const videos=Array.from({length:6},(_,i)=>({
    dataset:{src:`shot-${i}.webm`},events:{},currentTime:0,plays:0,paused:true,
    classList:{toggle(name,on){this.current=on;},remove(){this.current=false;}},
    addEventListener(name,cb){this.events[name]=cb;},getAttribute(){return this.src;},
    removeAttribute(){delete this.src;},load(){},pause(){this.paused=true;},
    play(){this.paused=false;this.plays++;return denied?Promise.reject(Error('denied')):Promise.resolve();}
  }));
  class Element {constructor(){this.dataset={};}querySelectorAll(){return videos;}closest(){return hero;}}
  vm.runInNewContext(await readFile(new URL('../../assets/maliev-pimm-cinematic.js',import.meta.url),'utf8'),{
    HTMLElement:Element,AbortController,window:{IntersectionObserver:true},document:doc,navigator:{connection:{saveData}},matchMedia:()=>motion,
    IntersectionObserver:class {constructor(cb){this.cb=cb;}observe(){}disconnect(){}},
    customElements:{get(){},define(n,c){Controller=c;}}
  });
  const el=new Controller();el.connectedCallback();el.observer.cb([{isIntersecting:true}]);
  return {el,videos,hero,motion,doc};
}
test('six authored shots play in order and wrap after the full-machine shot',async()=>{
  const {el,videos}=await harness();
  for(let i=0;i<6;i++){
    assert.equal(el.index,i);videos[i].events.playing();assert.equal(videos[i].classList.current,true);
    videos[i].events.ended();
  }
  assert.equal(el.index,0);assert.equal(videos[0].plays,2);
});
test('offscreen and hidden tabs preserve the current shot timeline',async()=>{
  const {el,videos,hero,doc}=await harness();videos[0].events.playing();videos[0].currentTime=1.2;
  doc.hidden=true;el.sync();assert.equal(videos[0].paused,true);
  assert.equal(hero.dataset.cinematicPlaying,'false');
  doc.hidden=false;el.sync();assert.equal(videos[0].currentTime,1.2);
  doc.hidden=false;el.visible=false;el.sync();assert.equal(videos[0].paused,true);
});
test('reduced motion and data saving do not request video',async()=>{
  for(const options of [{reduced:true},{saveData:true}]){
    const {videos}=await harness(options);assert.ok(videos.every(v=>!v.src && v.plays===0));
  }
});
test('failure and changing reduced-motion preference restore static fallback',async()=>{
  const {el,videos}=await harness({denied:true});await Promise.resolve();await Promise.resolve();
  assert.equal(el.failed,true);assert.equal(el.dataset.started,undefined);
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
  const {el,videos}=await harness({alpha:0});
  videos[0].events.playing();el.disconnectedCallback();el.connectedCallback();
  assert.equal(el.alphaChecked,false);assert.equal(el.dataset.started,undefined);
  assert.ok(videos.every(video=>!video.classList.current));
});

test('hero has no pause button and uses restrained background type motion',async()=>{
  const snippet=await readFile(new URL('../../snippets/pimm-cinematic-hero.liquid',import.meta.url),'utf8');
  assert.doesNotMatch(snippet,/<button|cinematic_pause/);
  const css=await readFile(new URL('../../assets/maliev-pimm-cinematic.css',import.meta.url),'utf8');
  assert.match(css,/pimm-type-drift 40s linear/);
  assert.match(css,/prefers-reduced-motion: reduce/);
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

test('component cinema has distinct CAD anchors, restrained eight-second moves, and verified media',async()=>{
  const snippet=await readFile(new URL('../../snippets/pimm-cinematic-hero.liquid',import.meta.url),'utf8');
  assert.match(snippet,/'cylinder,temperature,pressure,mounting,actuator,complete'/);
  assert.match(snippet,/pimm-cinematic-r59-/);
  assert.doesNotMatch(snippet,/pimm-cinematic-r58-/);
  const manifest=JSON.parse(await readFile(new URL('../../assets/pimm-cinematic-r59.json',import.meta.url),'utf8'));
  assert.equal(manifest.fps,24);assert.equal(manifest.frames_per_shot,192);
  assert.equal(manifest.alpha,true);
  assert.deepEqual(manifest.shots.map(s=>s.shot),['cylinder','temperature','pressure','mounting','actuator','complete']);
  assert.equal(new Set(manifest.shots.slice(0,-1).map(s=>s.anchor)).size,5);
  assert.ok(new Set(manifest.shots.map(s=>s.target[0])).size>=3);
  assert.ok(new Set(manifest.shots.map(s=>s.lens_mm)).size>=3);
  assert.ok(manifest.shots.find(s=>s.shot==='mounting').elevation[0]>=45);
  for(const shot of manifest.shots){
    const duration=manifest.frames_per_shot/manifest.fps;
    // The mixed linear/smoothstep timing curve peaks at 1.175 times mean speed.
    assert.ok(Math.abs(shot.azimuth[1]-shot.azimuth[0])/duration*1.175<=2.5);
  }
  assert.equal(manifest.frames.length,1152);
  assert.equal(new Set(manifest.frames.map(f=>f.filename)).size,1152);
  assert.equal(manifest.outputs.length,7);
  for(const output of manifest.outputs){
    const bytes=await readFile(new URL(`../../assets/${output.filename}`,import.meta.url));
    assert.equal(bytes.length,output.bytes);
    assert.equal(createHash('sha256').update(bytes).digest('hex'),output.sha256);
    if(output.filename.endsWith('.webm')){
      assert.equal(output.width,960);assert.equal(output.height,1080);
      assert.equal(output.nb_read_frames,'192');assert.equal(output.tags.alpha_mode,'1');
    }
  }
});
