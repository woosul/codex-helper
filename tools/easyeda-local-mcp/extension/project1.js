import scope from '../project1-scope.json';
const contents=['CODEX CONTROL TEST','CODEX CONTROL TEST - saved'];
const actions=['read','add_marker','modify_marker','save','delete_marker','restore_marker','reopen'];
export const project1Methods=actions.map(x=>'project1_'+x);
async function guard(){
  if(!eda.sys_Environment.isHalfOfflineMode() || !eda.sys_Environment.isClient())throw Error('mode_scope_mismatch');
  const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();
  if(!d || d.uuid!==scope.pageUuid || d.documentType!==1 || (d.parentProjectUuid && d.parentProjectUuid!==scope.projectUuid))throw Error('document_scope_mismatch');
  return d;
}
async function markers(){return (await eda.sch_PrimitiveText.getAll()).filter(t=>contents.includes(t.getState_Content()));}
function summarize(t){return {id:t.getState_PrimitiveId(),content:t.getState_Content(),x:t.getState_X(),y:t.getState_Y()};}
export async function project1(method){
  if(!project1Methods.includes(method))throw Error('operation_not_allowed');
  const d=await guard(),action=method.slice(9);
  let ok=true;
  const found=await markers();
  if(found.length>2 || (found.length>1 && action!=='delete_marker' && action!=='read'))throw Error('marker_count_mismatch');
  if(action==='add_marker' || action==='restore_marker'){
    if(found.length)throw Error('marker_already_exists');
    ok=!!(await eda.sch_PrimitiveText.create(300,300,action==='restore_marker'?contents[1]:contents[0],0,'#2060a0',null,20,true));
  }else if(action==='modify_marker'){
    if(found.length!==1)throw Error('marker_not_found');
    // Public create + generic delete: dedicated Text.modify does not persist in 3.2.149.
    const replacement=await eda.sch_PrimitiveText.create(350,300,contents[1],0,'#2060a0',null,20,true);
    if(!replacement)throw Error('replacement_create_failed');
    ok=await eda.sch_PrimitiveObject.delete([found[0].getState_PrimitiveId()]);
  }else if(action==='delete_marker'){
    if(!found.length)throw Error('marker_not_found');
    ok=await eda.sch_PrimitiveObject.delete(found.map(t=>t.getState_PrimitiveId()));
  }else if(action==='save')ok=await eda.sch_Document.save();
  else if(action==='reopen'){
    if(!(await eda.sch_Document.save()))throw Error('save_failed');
    if(!(await eda.dmt_EditorControl.closeDocument(d.tabId)))throw Error('close_failed');
    const tab=await eda.dmt_EditorControl.openDocument(scope.pageUuid);
    if(!tab)throw Error('open_failed');
    await eda.dmt_EditorControl.activateDocument(tab);
    await guard();
  }
  const after=await markers();
  if(action==='modify_marker')ok=ok && after.length===1 && after[0].getState_Content()===contents[1] && after[0].getState_X()===350;
  if(action==='delete_marker')ok=ok && after.length===0;
  if(action==='reopen')ok=ok && JSON.stringify(found.map(summarize))===JSON.stringify(after.map(summarize));
  return {scope:scope.projectUuid,document:scope.pageUuid,action,ok,markers:after.map(summarize)};
}
