import {Client} from '../easyeda-local-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import {StdioClientTransport} from '../easyeda-local-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
import {mkdir,writeFile} from 'node:fs/promises';
import {createInterface} from 'node:readline';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
await mkdir(path.join(root,'.runtime'),{recursive:true,mode:0o700});
await mkdir(path.join(root,'artifacts'),{recursive:true});
const env={PATH:process.env.PATH,NODE_ENV:'development',LOG_LEVEL:'warn',TOOL_PROFILE:'dev',TRANSPORT:'stdio',MCP_BRIDGE_BACKEND:'local_bridge',BRIDGE_HOST:'127.0.0.1',BRIDGE_PORT:'49620',BRIDGE_PORT_SCAN:'49620-49620',DATA_DIR:path.join(root,'.runtime'),BRIDGE_RAW_EXEC_ENABLED:'true',MCP_RAW_EXEC_EXPERIMENTAL:'true',BRIDGE_HOT_SWAP_ENABLED:'false',JLCSEARCH_ENABLED:'true',KEYLESS_SOURCING_ENABLED:'true',JLCPCB_MODE:'disabled',JLCPCB_ENABLE_ORDERING:'false',AI_PROVIDER:'none',MOUSER_ENABLED:'false',DIGIKEY_ENABLED:'false',OTEL_ENABLED:'false'};
await writeFile(path.join(root,'artifacts/trial-config.json'),JSON.stringify(env,null,2)+'\n');
const client=new Client({name:'codex-easyeda-isolated-trial',version:'1.0.0'});
await client.connect(new StdioClientTransport({command:process.execPath,args:[path.join(root,'node_modules/easyeda-mcp-pro/dist/index.js')],env,stderr:'inherit'}));
const catalog=await client.listTools();
await writeFile(path.join(root,'artifacts/tool-catalog.json'),JSON.stringify(catalog,null,2)+'\n');
console.log(JSON.stringify({ready:true,count:catalog.tools.length,tools:catalog.tools.map(t=>t.name)}));
for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})){
 try{
  const q=JSON.parse(line);if(q.exit){await client.close();break;}
  if(q.schema){console.log(JSON.stringify(catalog.tools.filter(t=>q.schema.includes(t.name)).map(t=>({name:t.name,inputSchema:t.inputSchema}))));continue;}
  const result=await client.callTool({name:q.name,arguments:q.arguments||{}},undefined,{timeout:120000});
  const report={checkedAt:new Date().toISOString(),request:q,result};
  await writeFile(path.join(root,'artifacts',`${Date.now()}-${q.name}.json`),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({checkedAt:report.checkedAt,name:q.name,result:result.structuredContent ?? result}));
 }catch(e){console.log(JSON.stringify({error:e.message}));}
}
