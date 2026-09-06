// Rough motion review: eight sampled poses per second, not final-quality media.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
const root=resolve(process.argv[2]);
const output=join(root,'review');await mkdir(output,{recursive:true});
const manifest=JSON.parse(await readFile(join(root,'render.json'),'utf8'));
if(!manifest.operations || manifest.profile!=='motion-proof' || manifest.frame_step!==3 || manifest.frames_per_shot!==288)throw Error('Expected complete operating motion proof');
if(manifest.shots.map(s=>s.shot).join(',')!=='cylinder,pressure,temperature,mounting,pellets,actuator,complete')throw Error('Expected all seven approved shots');
for(const {shot} of manifest.shots){
  for(let i=0;i<96;i++)await readFile(join(root,`${shot}-${String(i).padStart(3,'0')}.png`));
  const result=spawnSync('ffmpeg',['-v','error','-n','-framerate','8','-i',join(root,`${shot}-%03d.png`),'-filter_complex','color=c=0xf3f5f6:s=640x360:r=8[bg];[bg][0:v]overlay=shortest=1:format=auto,format=yuv420p','-c:v','libx264','-crf','18','-movflags','+faststart','-an',join(output,`${shot}.mp4`)],{encoding:'utf8'});
  if(result.status!==0)throw Error(result.stderr);
}
const list=join(output,'sequence.txt');
await writeFile(list,manifest.shots.map(({shot})=>`file '${shot}.mp4'`).join('\n')+'\n');
const combined=spawnSync('ffmpeg',['-v','error','-n','-f','concat','-safe','1','-i',list,'-c','copy','-movflags','+faststart',join(output,'operating-sequence.mp4')],{encoding:'utf8'});
if(combined.status!==0)throw Error(combined.stderr);
console.log(output);
