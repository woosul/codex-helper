import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { writeFile } from 'node:fs/promises';
const root=path.dirname(fileURLToPath(import.meta.url));
const client=new Client({name:'local-stage-one-check',version:'0.1.0'});
await client.connect(new StdioClientTransport({command:process.execPath,args:[path.join(root,'mcp-server.mjs')]}));
try {
  const tools=await client.listTools();
  if(tools.tools.length!==1 || tools.tools[0].name!=='easyeda_environment')throw new Error('Unexpected tool catalog');
  const denied=await client.callTool({name:'easyeda_environment',arguments:{code:'blocked'}});
  if(!denied.isError)throw new Error('Extra argument accepted');
  const result=await client.callTool({name:'easyeda_environment',arguments:{}});
  console.log(JSON.stringify({toolCount:tools.tools.length,extraArgumentsRejected:denied.isError,result},null,2));
  await writeFile(path.join(root,'artifacts/stdio-probe-result.json'),JSON.stringify({checkedAt:new Date().toISOString(),toolCount:tools.tools.length,extraArgumentsRejected:denied.isError,result},null,2)+'\n');
  if(result.isError)process.exitCode=1;
} finally {await client.close();}
