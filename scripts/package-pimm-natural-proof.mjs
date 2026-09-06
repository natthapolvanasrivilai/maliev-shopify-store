// Editorial 30-second cut: trim source intervals without accelerating motion.
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawnSync} from 'node:child_process';
const [source,mounting,output]=process.argv.slice(2).map(p=>resolve(p));
const cuts=[
  ['cylinder',[[3,5]]],
  ['pressure',[[1,2.5],[4,6],[9,10.5]]],
  ['temperature',[[0,1],[3,4],[8,11]]],
  ['mounting',[[2,7]]],
  ['pellets',[[0,1],[2,6],[8.5,10.5]]],
  ['actuator',[[3.8,5.8],[9.2,11.2]]],
  ['complete',[[4,6]]],
];
const run=args=>{const r=spawnSync('ffmpeg',args,{encoding:'utf8'});if(r.status!==0)throw Error(r.stderr);};
await mkdir(output,{recursive:true});
const files=[];
for(const [shot,intervals] of cuts){
  for(const [start,end] of intervals){
    const file=`cut-${String(files.length).padStart(2,'0')}.mp4`;
    run(['-v','error','-n','-ss',String(start),'-i',shot==='mounting'?mounting:join(source,'review',`${shot}.mp4`),'-t',String(end-start),'-vf','fps=24','-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',join(output,file)]);
    files.push(file);
  }
}
await writeFile(join(output,'sequence.txt'),files.map(f=>`file '${f}'`).join('\n'));
run(['-v','error','-n','-f','concat','-safe','1','-i',join(output,'sequence.txt'),'-c','copy','-movflags','+faststart',join(output,'hero-natural-30s.mp4')]);
await writeFile(join(output,'edit.json'),JSON.stringify({speed:1,sourceFps:8,preview:true,cuts},null,2));
