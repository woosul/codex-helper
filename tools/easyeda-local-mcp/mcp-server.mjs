import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema,ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes } from 'node:crypto';
const root=path.dirname(fileURLToPath(import.meta.url));
const actions=['read','add_marker','modify_marker','save','delete_marker','restore_marker','reopen'];
const server=new Server({name:'easyeda-local-environment',version:'0.2.0'},{capabilities:{tools:{}},instructions:'Only environment read and fixed Project1 sample actions. No arbitrary code, identifiers, text, paths, files, cloud or orders.'});
server.setRequestHandler(ListToolsRequestSchema,async()=>({tools:[
{name:'easyeda_environment',description:'Read editor version and mode from the paired local EasyEDA application.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:false}},
{name:'easyeda_project1_control',description:'Fixed reversible annotation test in Project1-LiIon-LED page 96a9421bbf9318e7 only.',inputSchema:{type:'object',properties:{action:{type:'string',enum:actions}},required:['action'],additionalProperties:false},annotations:{readOnlyHint:false,destructiveHint:false,idempotentHint:false,openWorldHint:false}}
]}));
function query(method){return new Promise((resolve,reject)=>{
 const s=net.createConnection(path.join(root,'.runtime/bridge.sock'));let data='';
 s.setTimeout(22000,()=>{s.destroy();reject(Error('bridge_timeout'));});
 s.on('connect',()=>s.write(JSON.stringify({id:randomBytes(16).toString('hex'),method})+'\n'));
 s.on('data',chunk=>{data+=chunk.toString();if(Buffer.byteLength(data)>4096){s.destroy();reject(Error('invalid_bridge_response'));}});
 s.on('error',()=>reject(Error('local_bridge_not_running')));
 s.on('end',()=>{try{const m=JSON.parse(data);if(m.error)reject(Error(m.error));else resolve(m.result);}catch{reject(Error('invalid_bridge_response'));}});
});}
server.setRequestHandler(CallToolRequestSchema,async request=>{
 const p=request.params,a=p.arguments||{};let method;
 if(p.name==='easyeda_environment' && Object.keys(a).length===0)method='environment';
 else if(p.name==='easyeda_project1_control' && Object.keys(a).length===1 && actions.includes(a.action))method='project1_'+a.action;
 else return {isError:true,content:[{type:'text',text:'operation_not_allowed'}]};
 try{const result=await query(method);return{structuredContent:result,content:[{type:'text',text:JSON.stringify(result)}]};}
 catch(e){return{isError:true,content:[{type:'text',text:e.message}]};}
});
await server.connect(new StdioServerTransport());
