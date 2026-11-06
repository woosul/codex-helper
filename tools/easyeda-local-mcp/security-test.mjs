import { spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import net from 'node:net';
import { once } from 'node:events';
import assert from 'node:assert/strict';
import { WebSocket } from 'ws';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const daemon=spawn(process.execPath,[path.join(root,'bridge-daemon.mjs')],{stdio:['ignore','ignore','pipe']});
await new Promise((resolve,reject)=>{let text='';daemon.stderr.on('data',x=>{text+=x;if(text.includes('Environment bridge ready'))resolve();});daemon.once('exit',code=>reject(new Error('daemon exited '+code)));});
function ipc(message){return new Promise((resolve,reject)=>{
 const s=net.createConnection(path.join(root,'.runtime/bridge.sock'));let body='';
 s.on('connect',()=>s.write(JSON.stringify(message)+'\n'));s.on('data',x=>body+=x);
 s.on('end',()=>resolve(JSON.parse(body)));s.on('error',reject);
});}
try {
 const bad=new WebSocket('ws://127.0.0.1:18149/easyeda');await once(bad,'open');
 bad.send(JSON.stringify({type:'authenticate',token:'0'.repeat(64)}));
 const [closeCode]=await once(bad,'close');assert.equal(closeCode,1008);
 assert.equal((await ipc({id:'blocked',method:'eval'})).error,'operation_not_allowed');
 assert.equal((await ipc({id:'blocked',method:'environment',code:'x'})).error,'operation_not_allowed');
 assert.equal((await ipc({id:'offline',method:'environment'})).error,'extension_not_connected');
 const token=(await readFile(path.join(root,'.runtime/pairing-code'),'utf8')).trim();
 const ws=new WebSocket('ws://127.0.0.1:18149/easyeda');await once(ws,'open');
 const paired=once(ws,'message');ws.send(JSON.stringify({type:'authenticate',token}));
 assert.equal(JSON.parse((await paired)[0]).type,'paired');
 ws.on('message',x=>{const m=JSON.parse(x);if(m.type==='request'){
   assert.deepEqual(Object.keys(m).sort(),['id','method','type']);assert.equal(m.method,'environment');
   ws.send(JSON.stringify({type:'response',id:m.id,result:{editorVersion:'3.2.149.88089769',isClient:true,isOnline:false,isHalfOffline:true,isOffline:false}}));
 }});
 const result=await ipc({id:'mock',method:'environment'});assert.equal(result.result.isHalfOffline,true);
 ws.close();
 console.log('PASS: wrong token rejected; unknown command and extra fields rejected; no-extension denied; authenticated environment-only mock path passed.');
} finally {daemon.kill('SIGTERM');await once(daemon,'exit');}
