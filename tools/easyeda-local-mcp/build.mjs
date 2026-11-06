import { build } from 'esbuild';
import JSZip from 'jszip';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = path.dirname(fileURLToPath(import.meta.url));
const extension = path.join(root, 'extension');
const menu = [{id:'environmentBridge', title:'Local Environment', menuItems:[
  {id:'connect',title:'Connect local bridge...',registerFn:'connect'},
  {id:'disconnect',title:'Disconnect local bridge',registerFn:'disconnect'},
]}];
const manifest = {
  name:'codex-environment-bridge', uuid:'b3120149ce4c456ca451177e823ab927',
  displayName:'Local Environment Bridge', description:'Environment read and fixed Project1 sample controls.',
  version:'0.2.2', publisher:'Local Codex', engines:{eda:'^3.2.0'}, license:'Apache-2.0',
  repository:{type:'extension-store',url:''},categories:'Other',keywords:['Tool'],
  images:{},homepage:'',bugs:'',activationEvents:{},entry:'./dist/index',dependentExtensions:{},
  headerMenus:{home:menu,sch:menu,pcb:menu},
};
await mkdir(path.join(extension,'dist'),{recursive:true});
// Build settings copied from the official easyeda/easyeda-api-sdk config.
await build({entryPoints:[path.join(extension,'index.js')],outfile:path.join(extension,'dist/index.js'),
  bundle:true,minify:false,platform:'browser',format:'iife',globalName:'edaEsbuildExportName',
  treeShaking:true,ignoreAnnotations:true});
await writeFile(path.join(extension,'extension.json'),JSON.stringify(manifest,null,2)+'\n');
const zip = new JSZip();
for (const name of ['extension.json','dist/index.js']) zip.file(name,await readFile(path.join(extension,name)));
await mkdir(path.join(root,'artifacts'),{recursive:true});
await writeFile(path.join(root,'artifacts/codex-environment-bridge_v0.2.2.eext'),await zip.generateAsync({type:'nodebuffer',compression:'DEFLATE'}));
console.log('Built environment and fixed Project1 control extension .eext');
