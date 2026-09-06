import {readFile, writeFile, stat, access} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {resolve,join} from 'node:path';

const source=resolve(process.argv[2]);
const assets=resolve('assets');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const run=(program,args)=>{
  const result=spawnSync(program,args,{encoding:'utf8',maxBuffer:1024*1024});
  if(result.status!==0)throw Error(result.stderr || `${program} failed`);
  return result.stdout;
};
const provenance=JSON.parse(await readFile(join(source,'render.json'),'utf8'));
if(provenance.provenance.master_sha256!=='98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA')throw Error('Unapproved master');
const component=provenance.shots.length===6;
const shots=component?['cylinder','temperature','pressure','mounting','actuator','complete']:['drive','control','tooling','complete'];
const release=component?'r59':'r58';
const frameCount=component?192:96;
if(provenance.frames_per_shot!==frameCount||provenance.fps!==24||JSON.stringify(provenance.shots.map(s=>s.shot))!==JSON.stringify(shots))throw Error('Incomplete camera sequence');
const renderer=component?'blender_30g_component_cinema.py':'blender_30g_cinematic_hero.py';
const manifest={...provenance,renderer:`scripts/blender/pimm_production/${renderer}`,width:960,height:1080,samples:provenance.samples??48,outputs:[],frames:[]};
for(const shot of shots){
  for(let i=0;i<frameCount;i++){
    const name=`${shot}-${String(i).padStart(3,'0')}.png`;
    const bytes=await readFile(join(source,name));
    manifest.frames.push({shot,index:i,filename:name,sha256:hash(bytes)});
  }
  const filename=`pimm-cinematic-${release}-${shot}.webm`;
  const target=join(assets,filename);
  let existing=false;
  try {await access(target);existing=true;}catch(error){if(error.code!=='ENOENT')throw error;}
  if(existing&&!process.argv.includes('--resume'))throw Error(`Refusing existing release ${target}`);
  if(!existing)run('ffmpeg',['-v','error','-n','-framerate','24','-i',join(source,`${shot}-%03d.png`),'-frames:v',String(frameCount),'-c:v','libvpx-vp9','-pix_fmt','yuva420p','-b:v','0','-crf','25','-deadline','good','-cpu-used','3','-row-mt','1','-an',target]);
  const probe=JSON.parse(run('ffprobe',['-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames:stream_tags=alpha_mode','-of','json',target])).streams[0];
  if(probe.width!==960||probe.height!==1080||probe.nb_read_frames!==String(frameCount)||probe.tags?.alpha_mode!=='1')throw Error('Invalid video contract');
  manifest.outputs.push({filename,bytes:(await stat(target)).size,sha256:hash(await readFile(target)),...probe});
}
const poster=`pimm-cinematic-${release}-complete.webp`;
if(component){
  try{await access(join(assets,poster));}catch(error){
    if(error.code!=='ENOENT')throw error;
    run('ffmpeg',['-v','error','-n','-i',join(source,'complete-095.png'),'-lossless','1',join(assets,poster)]);
  }
}
manifest.outputs.push({filename:poster,bytes:(await stat(join(assets,poster))).size,sha256:hash(await readFile(join(assets,poster)))});
await writeFile(join(assets,`pimm-cinematic-${release}.json`),JSON.stringify(manifest,null,2)+'\n');
console.log(`${shots.length} native alpha videos verified and packaged.`);
