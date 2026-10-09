import * as vscode from 'vscode';
import { Backend } from './backend';
import { localApi, startLocalServer, validModelName } from './ollama';
import { ensureDashboard } from './dashboard';
import { Row } from './model';

export const quickActions = [
  ['Dashboard','Open Dashboard','arc.dashboard'],['Dashboard','Open Sidebar','arc.sidebar'],
  ['AI Models','Start Ollama','arc.startOllama'],['AI Models','Show Model Status','arc.modelStatus'],
  ['AI Models','View Installed Models','arc.installedModels'],['AI Models','Select AI Model','arc.selectChatModel'],
  ['AI Models','Select Embedding Model','arc.selectEmbeddingModel'],['AI Models','Load Selected Model','arc.loadModel'],
  ['AI Models','Unload Selected Model','arc.unloadModel'],['AI Models','Retry Model Operation','arc.retryModel'],
  ['AI Models','Download a Model','arc.downloadModel'],['AI Models','Open AI Chat','arc.chat.focus'],
  ['Memory and Search','Search Memory','arc.search'],['Memory and Search','Show Timeline','arc.timeline'],
  ['Memory and Search','Show Project State','arc.state'],['Memory and Search','Index Memories','arc.index'],
  ['Memory and Search','Capture Changes','arc.capture'],['Memory and Search','Create Checkpoint','arc.checkpoint'],
  ['Memory and Search','Run Configured Test','arc.test'],
  ['Sessions and Handoffs','Show Handoff','arc.handoff'],['Sessions and Handoffs','Start Session','arc.sessionStart'],
  ['Sessions and Handoffs','End Session','arc.sessionEnd'],['Sessions and Handoffs','Review Unfinished Tasks','arc.unfinished'],
  ['Settings','Open Settings','arc.settings'],['Settings','Enable Automatic Tracking','arc.observe'],
  ['Settings','Pause Automatic Tracking','arc.pause'],['Settings','Resume Automatic Tracking','arc.resume'],
  ['Settings','Disable Automatic Tracking','arc.disable'],['Settings','Connect Project','arc.connect'],
  ['Settings','Register Project','arc.createProject'],['Settings','Disconnect Project','arc.disconnect'],
] as const;
interface Host {
  register:(name:string,action:(...args:any[])=>any)=>void;
  backend:()=>Backend;
  inspect:(value:any)=>Promise<void>;
  refresh:()=>Promise<void>;
  retry:()=>Promise<void>;
  rows:(rows:Row[])=>void;
}
export function installControls(host:Host){
  let running=false;
  let lastOperation:{operation:string;role:string}|undefined;
  const config=()=>vscode.workspace.getConfiguration('arc');
  const selected=(role:string)=>config().get<string>(role==='embedding'?'models.embedding':'models.chat',role==='embedding'?'all-minilm':'');
  const updateRows=()=>host.rows([
    {label:'Open Dashboard',command:'arc.dashboard',icon:'browser'},
    {label:'Ask A.R.C.',command:'arc.openChat',icon:'comment-discussion'},
    {label:'Quick Actions',command:'arc.quickActions',icon:'list-selection'},
    {label:'AI Models',children:[
      {label:`Ollama: ${running?'Running':'Offline'}`,command:'arc.modelStatus'},
      {label:`Embedding: ${selected('embedding')}`,command:'arc.selectEmbeddingModel'},
      {label:`Chat: ${selected('chat')||'Choose a model'}`,command:'arc.selectChatModel'},
      {label:'AI Model Controls…',command:'arc.modelActions'},
      {label:'Model Settings',command:'arc.modelSettings'}
    ]},
    {label:'Controls',children:[{label:'Pause Tracking',command:'arc.pause'},{label:'Resume Tracking',command:'arc.resume'},{label:'Settings',command:'arc.settings'}]}
  ]);
  const tags=async()=>{
    let payload;
    try{payload=await localApi('/api/tags');}
    catch{running=false;updateRows();throw new Error('Ollama is offline. Use ARC: Start Ollama, or install Ollama if it is missing.');}
    running=true;updateRows();
    return (payload.models||[]).filter((model:any)=>!model.remote_host&&!model.remote_model&&validModelName(model.name));
  };
  const status=async()=>{
    let loaded:string[]=[];
    try{await tags();}catch{running=false;updateRows();}
    if(running){try{const result=await localApi('/api/ps');loaded=(result.models||[]).map((model:any)=>model.name);}catch{}}
    return {ollama:running?'Running':'Offline',embedding:selected('embedding'),chat:selected('chat')||'Not selected',loaded};
  };
  const select=async(role:string)=>{
    const installed=await tags();
    const items:{label:string;description:string;model:string}[]=installed.map((model:any)=>({label:model.name,description:model.name===selected(role)?'Selected':'',model:model.name}));
    items.push({label:'Download another local model…',description:'Requires confirmation',model:''});
    const pick=await vscode.window.showQuickPick(items,{title:`Select ${role==='embedding'?'embedding':'conversational'} model`});
    if(!pick)return;
    if(!pick.model){await vscode.commands.executeCommand('arc.downloadModel');return;}
    const details=await localApi('/api/show',{model:pick.model});
    const capability=role==='embedding'?'embedding':'completion';
    if(Array.isArray(details.capabilities)&&!details.capabilities.includes(capability))throw new Error(`This model does not support ${role} operations. Choose another installed model.`);
    await config().update(role==='embedding'?'models.embedding':'models.chat',pick.model,vscode.ConfigurationTarget.Global);
    updateRows();await vscode.commands.executeCommand('arc.connect');
  };
  const operate=async(operation:string)=>{
    const role=await vscode.window.showQuickPick(['embedding','chat'],{title:`${operation==='load'?'Load':'Unload'} which selected model?`});
    if(!role)return;
    if(!selected(role))throw new Error('Select a model first.');
    lastOperation={operation,role};
    await host.backend().request(['model',operation,'--role',role]);await status();
  };
  host.register('arc.quickActions',async()=>{
    const items:vscode.QuickPickItem[]=[];
    let group='';
    for(const [section,label,command] of quickActions){
      if(section!==group){items.push({label:section,kind:vscode.QuickPickItemKind.Separator});group=section;}
      items.push({label,description:section,...{command}});
    }
    const pick=await vscode.window.showQuickPick(items,{title:'A.R.C. Quick Actions'}) as (vscode.QuickPickItem&{command?:string})|undefined;
    if(pick?.command)await vscode.commands.executeCommand(pick.command);
  });
  host.register('arc.modelActions',async()=>{
    const items=quickActions.filter(([group])=>group==='AI Models').map(([,label,command])=>({label,command}));
    const pick=await vscode.window.showQuickPick(items,{title:'A.R.C. AI Models'});
    if(pick)await vscode.commands.executeCommand(pick.command);
  });
  host.register('arc.dashboard',async()=>{
    const backend=host.backend();
    const url=await ensureDashboard(backend,config().get<string>('dashboard.url','http://127.0.0.1:8765'));
    if(backend!==host.backend())throw new Error('The connected project changed. Open Dashboard again.');
    if(!await vscode.env.openExternal(vscode.Uri.parse(url)))throw new Error('The dashboard is ready, but your default browser could not open it.');
  });
  host.register('arc.sidebar',()=>vscode.commands.executeCommand('workbench.view.extension.arc'));
  host.register('arc.openChat',async()=>{await vscode.commands.executeCommand('workbench.view.extension.arc');await vscode.commands.executeCommand('arc.chat.focus');});
  host.register('arc.settings',()=>vscode.commands.executeCommand('workbench.action.openSettings','@ext:arc-local.arc-memory'));
  host.register('arc.modelSettings',()=>vscode.commands.executeCommand('workbench.action.openSettings','arc.models'));
  host.register('arc.startOllama',async()=>{await startLocalServer();await status();await host.retry();});
  host.register('arc.modelStatus',async()=>host.inspect(await status()));
  host.register('arc.installedModels',async()=>{
    const installed=await tags();await vscode.window.showQuickPick(installed.map((model:any)=>({label:model.name,description:`${Math.round((model.size||0)/1024/1024)} MB`})),{title:'Installed local Ollama models'});
  });
  host.register('arc.selectChatModel',()=>select('chat'));
  host.register('arc.selectEmbeddingModel',()=>select('embedding'));
  host.register('arc.loadModel',()=>operate('load'));
  host.register('arc.unloadModel',()=>operate('unload'));
  host.register('arc.retryModel',async()=>{
    if(lastOperation)await host.backend().request(['model',lastOperation.operation,'--role',lastOperation.role]);
    await host.retry();await status();
  });
  host.register('arc.downloadModel',async()=>{
    const model=await vscode.window.showInputBox({title:'Download a local Ollama model',prompt:'Enter a model name and tag. Downloads may use several GB.',validateInput:value=>validModelName(value)?undefined:'Enter a valid local model name; cloud models are not supported.'});
    if(!model)return;
    if(await vscode.window.showInformationMessage(`Download ${model}? This uses internet access and may require several GB of disk space.`,{modal:true},'Download')!=='Download')return;
    await localApi('/api/pull',{model,stream:false},15*60*1000);await status();
  });
  for(const [command,args] of [['arc.state',['state']],['arc.handoff',['handoff']],['arc.sessionEnd',['session','end']]] as const)
    host.register(command,async()=>{await host.inspect(await host.backend().request([...args]));await host.refresh();});
  host.register('arc.sessionStart',async()=>{
    const label=await vscode.window.showInputBox({title:'Start A.R.C. session',value:'Development session'});
    if(label?.trim()){await host.backend().request(['session','start',label.trim()]);await host.refresh();}
  });
  host.register('arc.unfinished',async()=>{
    const state=await host.backend().request(['state']);
    const tasks=(state.tasks||[]).filter((task:any)=>!['confirmed','completed_confirmed'].includes(task.state));
    const items:{label:string;description:string;id:string}[]=tasks.map((task:any)=>({label:task.title,description:task.state,id:task.id}));
    const pick=await vscode.window.showQuickPick(items,{title:'Unfinished tasks',placeHolder:tasks.length?'Choose a task to review':'No unfinished tasks recorded'});
    if(pick)await host.inspect(await host.backend().request(['task','review',pick.id]));
  });
  updateRows();return {status,updateRows};
}
