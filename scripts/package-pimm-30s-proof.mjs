// Timing review only: final renders must sample each shortened shot at native 24 fps.
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {spawnSync} from 'node:child_process';

const root=resolve(process.argv[2]);
const output=join(root,'review-30s');
const shots=[['cylinder',4],['pressure',4],['temperature',5],['mounting',4],['pellets',5],['actuator',4],['complete',4]];
const run=args=>{const r=spawnSync('ffmpeg',args,{encoding:'utf8'});if(r.status!==0)throw Error(r.stderr);};
await mkdir(output,{recursive:true});
for(const [shot,duration] of shots){
  run(['-v','error','-n','-i',join(root,'review',`${shot}.mp4`),'-vf',`setpts=${duration}/12*(PTS-STARTPTS),fps=24`,'-t',String(duration),'-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',join(output,`${shot}.mp4`)]);
}
await writeFile(join(output,'sequence.txt'),shots.map(([shot])=>`file '${shot}.mp4'`).join('\n')+'\n');
run(['-v','error','-n','-f','concat','-safe','1','-i',join(output,'sequence.txt'),'-c','copy','-movflags','+faststart',join(output,'hero-30s-preview.mp4')]);
await writeFile(join(output,'timing.json'),JSON.stringify({preview:true,sourceFps:8,outputFps:24,duration:30,shots},null,2));
console.log(join(output,'hero-30s-preview.mp4'));
