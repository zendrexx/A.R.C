const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');

function setup(){
  const commands=new Map(),executed=[],requests=[],apiCalls=[],updates=[],inspected=[];
  const settings=new Map([['models.embedding','embedder'],['models.chat','chatty']]);
  let choice,allow=true,rows;
  const vscode={QuickPickItemKind:{Separator:-1},ConfigurationTarget:{Global:1},
    Uri:{parse:value=>value},env:{openExternal:async value=>{executed.push(['browser',value]);return true;}},
    workspace:{getConfiguration:()=>({get:(key,fallback)=>settings.get(key)??fallback,update:async(key,value)=>{updates.push([key,value]);settings.set(key,value);}})},
    commands:{executeCommand:async(...args)=>{executed.push(args);}},
    window:{showQuickPick:async(items)=>choice?items.find(choice):items.find(item=>item.kind!==-1),
      showInputBox:async()=> 'newmodel:small',showInformationMessage:async()=>allow?'Download':undefined}};
  const api=async(route,body)=>{
    apiCalls.push([route,body]);
    if(route==='/api/tags')return {models:[{name:'embedder',size:100},{name:'chatty',size:200},{name:'remote:cloud',remote_host:'cloud'}]};
    if(route==='/api/show')return {capabilities:[body.model==='embedder'?'embedding':'completion']};
    return {};
  };
  const exports={};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../out/controls.js'),'utf8'),{exports,
    require:name=>name==='vscode'?vscode:name==='./ollama'?{localApi:api,startLocalServer:async()=>executed.push(['start']),validModelName:name=>!name.includes(':cloud')}:name==='./dashboard'?{ensureDashboard:async()=> 'http://127.0.0.1:9876/?project=test'}:require(name)});
  const backend={request:async args=>{requests.push(Array.from(args));return args[0]==='state'?{tasks:[{id:'task1',title:'unfinished',state:'planned'},{id:'task2',title:'complete',state:'confirmed'}]}:{};}};
  const control=exports.installControls({register:(name,fn)=>commands.set(name,fn),backend:()=>backend,
    inspect:async value=>inspected.push(value),refresh:async()=>{},retry:async()=>executed.push(['retry']),rows:value=>{rows=value;}});
  return {commands,executed,requests,apiCalls,updates,inspected,control,
    actions:exports.quickActions,rows:()=>rows,choose:fn=>{choice=fn;},decline:()=>{allow=false;}};
}

test('every Quick Actions choice dispatches its corresponding command',async()=>{
  const app=setup();
  for(const [group,label,command] of app.actions){
    app.choose(item=>item.command===command);
    await app.commands.get('arc.quickActions')();
    assert.equal(app.executed.at(-1)[0],command);
  }
  const packageJson=require('../package.json');
  const declared=new Set(packageJson.contributes.commands.map(item=>item.command));
  for(const command of app.commands.keys())assert.ok(declared.has(command),`${command} must be contributed`);
  for(const [,,command] of app.actions)assert.ok(declared.has(command)||command==='arc.chat.focus');
});
test('native sidebar rows reference actual commands',()=>{
  const app=setup();const allowed=new Set([...app.commands.keys(),...app.actions.map(item=>item[2])]);
  function check(rows){for(const row of rows){if(row.command)assert.ok(allowed.has(row.command));if(row.children)check(row.children);}}
  check(app.rows());assert.equal(app.rows()[0].command,'arc.dashboard');
});
test('model dropdowns persist capable installed local models and reconnect',async()=>{
  const app=setup();app.choose(item=>item.model==='chatty');await app.commands.get('arc.selectChatModel')();
  app.choose(item=>item.model==='embedder');await app.commands.get('arc.selectEmbeddingModel')();
  assert.deepEqual(app.updates,[['models.chat','chatty'],['models.embedding','embedder']]);
  assert.equal(app.executed.filter(item=>item[0]==='arc.connect').length,2);
  app.choose(item=>item.model==='embedder');await assert.rejects(app.commands.get('arc.selectChatModel')(),/does not support chat/);
});
test('model load, unload, retry and refused downloads use the intended handlers',async()=>{
  const app=setup();app.choose(item=>item==='chat');
  await app.commands.get('arc.loadModel')();await app.commands.get('arc.unloadModel')();await app.commands.get('arc.retryModel')();
  assert.deepEqual(app.requests,[['model','load','--role','chat'],['model','unload','--role','chat'],['model','unload','--role','chat']]);
  app.decline();await app.commands.get('arc.downloadModel')();assert.equal(app.apiCalls.filter(item=>item[0]==='/api/pull').length,0);
});
test('dashboard, chat, settings, state, handoff and sessions are functional',async()=>{
  const app=setup();
  for(const command of ['arc.dashboard','arc.sidebar','arc.openChat','arc.settings','arc.modelSettings','arc.startOllama','arc.modelStatus','arc.installedModels','arc.state','arc.handoff','arc.sessionStart','arc.sessionEnd','arc.unfinished'])await app.commands.get(command)();
  assert.ok(app.executed.some(item=>item[0]==='browser'&&item[1].includes(':9876')));
  for(const args of [['state'],['handoff'],['session','start','newmodel:small'],['session','end'],['task','review','task1']])
    assert.ok(app.requests.some(item=>JSON.stringify(item)===JSON.stringify(args)));
});
