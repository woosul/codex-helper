// Manual launcher only: no login service, auto-start registration, or new API.
import { spawn } from 'node:child_process';
import { mkdir, chmod, open, readFile } from 'node:fs/promises';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const runtime=path.join(root,'.runtime');
async function running(){return new Promise(resolve=>{
  const s=net.createConnection(path.join(runtime,'bridge.sock'));
  s.setTimeout(500,()=>{s.destroy();resolve(false);});
  s.on('connect',()=>{s.destroy();resolve(true);});
  s.on('error',()=>resolve(false));
});}
if(await running()) { console.log('Local bridge already running; pairing code unchanged.');process.exit(0); }
await mkdir(runtime,{recursive:true,mode:0o700});await chmod(runtime,0o700);
const logPath=path.join(runtime,'bridge.log');
const log=await open(logPath,'a',0o600);await chmod(logPath,0o600);
const child=spawn(process.execPath,[path.join(root,'bridge-daemon.mjs')],{
  cwd:root,detached:true,stdio:['ignore',log.fd,log.fd],
});
child.unref();await log.close();
for(let n=0;n<40;n++) {
  if(await running()) {
    try {
      const pid=(await readFile(path.join(runtime,'bridge.pid'),'utf8')).trim();
      console.log('Detached local bridge ready; PID '+pid);process.exit(0);
    } catch (e) { if(e.code!=='ENOENT')throw e; }
  }
  await new Promise(resolve=>setTimeout(resolve,50));
}
console.error('Bridge did not become ready; consult private .runtime/bridge.log.');process.exit(1);
