const {test} = require('node:test');
const assert = require('node:assert/strict');
const {OllamaManager} = require('../out/ollama');

function setup({running=true, autoStart=true, installed=['all-minilm:latest','qwen3:1.7b'], allow=true}={}) {
  const calls={starts:0,pulls:[],prompts:[],indexes:0,status:[]}; let clock=0;
  const runtime={now:()=>clock,start:async()=>{calls.starts++;running=true;},
    api:async(route,body)=>{
      if(!running)throw new Error('refused');
      if(route==='/api/pull'){calls.pulls.push(body.model);installed.push(body.model);return {};}
      return {models:installed.map(name=>({name}))};
    }};
  const manager=new OllamaManager({autoStart:()=>autoStart,models:()=>['all-minilm','qwen3:1.7b'],
    consent:async model=>{calls.prompts.push(model);return allow;},
    index:async()=>{calls.indexes++;},notify:status=>calls.status.push(status)},runtime);
  return {manager,calls,runtime,advance:ms=>clock+=ms,crash:()=>{running=false;}};
}

test('existing server and models are reused, checks are throttled',async()=>{
  const app=setup();await Promise.all([app.manager.tick(),app.manager.tick()]);
  assert.equal(app.calls.starts,0);assert.equal(app.calls.indexes,1);
  assert.equal(app.calls.prompts.length,0);await app.manager.tick();assert.equal(app.calls.indexes,1);
  app.manager.dispose();app.advance(60000);await app.manager.tick();assert.equal(app.calls.starts,0);
});
test('missing service starts once and reconnects after a crash',async()=>{
  const app=setup({running:false});await Promise.all([app.manager.tick(),app.manager.tick()]);
  assert.equal(app.calls.starts,1);app.crash();app.advance(30000);await app.manager.tick();assert.equal(app.calls.starts,2);
});
test('disabled startup never starts a server and retries quietly',async()=>{
  const app=setup({running:false,autoStart:false});await app.manager.tick();await app.manager.tick();
  assert.equal(app.calls.starts,0);assert.equal(app.calls.indexes,0);assert.match(app.calls.status[0],/Recording locally/);
});
test('missing models download only after consent, with no repeated prompts',async()=>{
  const app=setup({installed:[]});await app.manager.tick();
  assert.deepEqual(app.calls.pulls,['all-minilm','qwen3:1.7b']);
  app.advance(30000);await app.manager.tick();assert.equal(app.calls.prompts.length,2);
  const declined=setup({installed:[],allow:false});await declined.manager.tick();
  declined.advance(30000);await declined.manager.tick();assert.equal(declined.calls.pulls.length,0);
  assert.equal(declined.calls.prompts.length,2);assert.equal(declined.calls.indexes,0);
});
test('failed model downloads retry using retained consent',async()=>{
  const app=setup({installed:[]});const original=app.runtime.api;let fail=true;
  app.runtime.api=async(route,body)=>{if(route==='/api/pull'&&fail){fail=false;throw new Error('network');}return original(route,body);};
  await app.manager.tick();app.advance(10000);await app.manager.tick();
  assert.deepEqual(app.calls.pulls,['all-minilm','qwen3:1.7b']);
});
