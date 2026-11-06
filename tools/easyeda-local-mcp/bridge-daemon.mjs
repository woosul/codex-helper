import { WebSocketServer } from 'ws';
import net from 'node:net';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { mkdir, chmod, writeFile, unlink } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { readFile } from 'node:fs/promises';
const root = path.dirname(fileURLToPath(import.meta.url));
const runtime = path.join(root,'.runtime');
const socketPath = path.join(runtime,'bridge.sock');
const tokenPath = path.join(runtime,'pairing-code');
const pidPath = path.join(runtime,'bridge.pid');
await mkdir(runtime,{recursive:true,mode:0o700});
await chmod(runtime,0o700);
const token = randomBytes(32).toString('hex');
let extension;
const pending = new Map();
const operations=new Set(['environment',...['read','add_marker','modify_marker','save','delete_marker','restore_marker','reopen'].map(x=>'project1_'+x)]);
const {projectUuid,pageUuid}=JSON.parse(await readFile(path.join(root,'project1-scope.json'),'utf8'));
const keys = ['editorVersion','isClient','isOnline','isHalfOffline','isOffline'];
function validEnvironment(v) {
  return v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 5 &&
    typeof v.editorVersion === 'string' && /^\d+(\.\d+){2,4}$/.test(v.editorVersion) &&
    keys.slice(1).every(k=>typeof v[k]==='boolean');
}
function parse(data) { try { return JSON.parse(data); } catch { return null; } }
function object(m) { return m && typeof m==='object' && !Array.isArray(m); }
const wss = new WebSocketServer({host:'127.0.0.1',port:18149,path:'/easyeda',maxPayload:4096,
  perMessageDeflate:false,verifyClient:info=>info.req.headers.host==='127.0.0.1:18149'});
wss.on('error',e=>{console.error('Loopback listener failed:',e.code);process.exit(1);});
await new Promise(resolve=>wss.once('listening',resolve));
// A stale socket may be removed only after the exclusive TCP bind succeeds.
await unlink(socketPath).catch(e=>{if(e.code!=='ENOENT')throw e;});
await writeFile(tokenPath,token+'\n',{mode:0o600});
await chmod(tokenPath,0o600);
wss.on('connection',ws=>{
  let authenticated=false;
  const timer=setTimeout(()=>ws.close(1008,'Authentication required'),3000);
  ws.on('error',()=>{});
  ws.on('message',(data,isBinary)=>{
    const m=parse(data.toString());
    if(isBinary || !object(m)) {ws.close(1008,'Invalid message');return;}
    if(!authenticated) {
      const supplied=typeof m.token==='string' && /^[a-f0-9]{64}$/.test(m.token) ? Buffer.from(m.token) : Buffer.alloc(0);
      if(m.type!=='authenticate' || Object.keys(m).length!==2 || supplied.length!==64 ||
         !timingSafeEqual(supplied,Buffer.from(token)) || extension) {ws.close(1008,'Authentication failed');return;}
      clearTimeout(timer);authenticated=true;extension=ws;
      ws.send(JSON.stringify({type:'paired'}));console.error(new Date().toISOString(),'EasyEDA extension paired (environment only).');return;
    }
    if(m.type!=='response' || typeof m.id!=='string' || Object.keys(m).length!==3) return;
    const p=pending.get(m.id);if(!p)return;
    if(typeof m.error==='string' && /^[a-z_]+$/.test(m.error))p.finish({error:m.error});
    else if(p.method==='environment' ? validEnvironment(m.result) : m.result?.scope===projectUuid && m.result.document===pageUuid && m.result.action===p.method.slice(9) && typeof m.result.ok==='boolean' && Array.isArray(m.result.markers))p.finish({result:m.result});
    else p.finish({error:'invalid_extension_response'});
  });
  ws.on('close',()=>{
    clearTimeout(timer);
    if(extension===ws){extension=undefined;for(const p of pending.values())p.finish({error:'extension_disconnected'});}
  });
});
const ipc=net.createServer(socket=>{
  let buffer='';let used=false;
  socket.setTimeout(24000,()=>socket.destroy());socket.on('error',()=>{});
  socket.on('data',data=>{
    buffer+=data.toString();if(Buffer.byteLength(buffer)>4096 || used){socket.destroy();return;}
    if(!buffer.includes('\n'))return;used=true;
    const m=parse(buffer.trim());
    const reply=value=>socket.end(JSON.stringify(value)+'\n');
    if(!object(m) || !operations.has(m.method) || typeof m.id!=='string' ||
       !/^[a-zA-Z0-9_-]{1,64}$/.test(m.id) || Object.keys(m).length!==2) {reply({error:'operation_not_allowed'});return;}
    if(!extension || extension.readyState!==1){reply({error:'extension_not_connected'});return;}
    const id=randomBytes(16).toString('hex');
    const timer=setTimeout(()=>finish({error:'environment_timeout'}),20000);
    function finish(value){clearTimeout(timer);pending.delete(id);reply(value);}
    pending.set(id,{finish,method:m.method});
    socket.once('close',()=>{clearTimeout(timer);pending.delete(id);});
    extension.send(JSON.stringify({type:'request',id,method:m.method}));
  });
});
await new Promise((resolve,reject)=>{ipc.once('error',reject);ipc.listen(socketPath,resolve);});
await chmod(socketPath,0o600);
await writeFile(pidPath,String(process.pid)+'\n',{mode:0o600});
console.error(new Date().toISOString(),'Environment bridge ready: 127.0.0.1:18149; private local IPC.');
let stopping=false;
async function stop(signal){
  if(stopping)return;stopping=true;
  console.error(new Date().toISOString(),'Bridge stopping:',signal);
  for(const ws of wss.clients)ws.terminate();wss.close();ipc.close();
  await Promise.all([unlink(socketPath).catch(()=>{}),unlink(tokenPath).catch(()=>{}),unlink(pidPath).catch(()=>{})]);process.exit(0);
}
process.on('SIGINT',()=>stop('SIGINT'));process.on('SIGTERM',()=>stop('SIGTERM'));
