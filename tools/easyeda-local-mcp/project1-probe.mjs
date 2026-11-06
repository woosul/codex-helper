import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.dirname(fileURLToPath(import.meta.url)),action=process.argv[2]||'read';
const client=new Client({name:'project1-fixed-control-check',version:'0.2.0'});
await client.connect(new StdioClientTransport({command:process.execPath,args:[path.join(root,'mcp-server.mjs')]}));
try{
const catalog=await client.listTools();
const denied=await client.callTool({name:'easyeda_project1_control',arguments:{action:'read',code:'blocked'}});
if(!denied.isError)throw Error('Extra argument accepted');
const result=await client.callTool({name:'easyeda_project1_control',arguments:{action}});
const report={checkedAt:new Date().toISOString(),toolCount:catalog.tools.length,extraArgumentsRejected:true,result};
console.log(JSON.stringify(report,null,2));
await writeFile(path.join(root,'artifacts/project1-'+action+'-'+Date.now()+'.json'),JSON.stringify(report,null,2)+'\n');
if(result.isError || result.structuredContent?.ok===false)process.exitCode=1;
}finally{await client.close();}
