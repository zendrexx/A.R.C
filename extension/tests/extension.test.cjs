const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

// Exercise activation and command lifecycles without pretending to certify VS Code visuals.
function setup({trusted = true, names = ['one'], hook, saved = {}, input = 'question', observationApproval = true} = {}) {
  const commands = new Map(); const errors = []; const instances = []; const messages = [];
  const folders = names.map(name => ({name, uri: {scheme: 'file', fsPath: path.resolve(name), toString: () => name}}));
  let choose = folders.length - 1; let provider; let memory; let onConfig; let receive;
  const db = new Map(Object.entries(saved));
  class Backend {
    constructor(python, project, database) {Object.assign(this, {python, project, database, observing: false, busy: false}); instances.push(this);}
    async request(args) {
      if (hook) {const value = hook(this, args); if (value !== undefined) return await value;}
      if (this.disposed) throw new Error('Project disconnected.');
      if (args[0] === 'state') return {project:{name:path.basename(this.project),path:this.project}, git:{changed_paths:[]}, tasks:[], recent_events:[],index:{indexed_records:0,pending_records:0}};
      if (args[0] === 'observer') {
        if (args[1] === 'enable') this.enabled = true;
        if (args[1] === 'disable') this.enabled = false;
        return {enabled: this.enabled, paused: args[1] === 'pause'};
      }
      return {answer: this.project, citations: [], next_offset: null};
    }
    startObserver() {this.observing = true;}
    stopObserver() {this.observing = false;}
    dispose() {this.disposed = true; this.stopObserver();}
  }
  const disposable = () => ({dispose(){}});
  const vscode = {
    EventEmitter: class {event = () => disposable(); fire() {} dispose() {}},
    StatusBarAlignment: {Left:1},
    window: {
      createStatusBarItem: () => ({show(){},dispose(){}}),
      showErrorMessage: message => {errors.push(message);},
      showInformationMessage: async (_, __, action) => action === 'Enable' && !observationApproval ? undefined : action,
      showQuickPick: async items => items[choose],
      showInputBox: async () => input,
      showTextDocument: async () => {},
      registerTreeDataProvider: (_, view) => {memory = view; return disposable();},
      registerWebviewViewProvider: (_, view) => {provider = view; return disposable();}
    },
    commands: {
      registerCommand: (name, callback) => {commands.set(name, callback);return disposable();},
      executeCommand: async (name, ...args) => commands.get(name)(...args)
    },
    workspace: {
      isTrusted: trusted, workspaceFolders: folders,
      getConfiguration: () => ({get: () => ''}),
      openTextDocument: async data => data,
      onDidChangeWorkspaceFolders: () => disposable(),
      onDidChangeConfiguration: callback => {onConfig = callback;return disposable();}
    }
  };
  const context = {subscriptions: [], workspaceState: {
    get: (key, fallback) => db.has(key) ? db.get(key) : fallback,
    update: async (key, value) => {db.set(key, value);}
  }};
  const exports = {};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../out/extension.js'), 'utf8'), {
    exports, process, setInterval: () => 1, clearInterval: () => {},
    require: name => name === 'vscode' ? vscode : name === './backend' ? {Backend} : name === './model' ? require('../out/model') : require(name)
  });
  exports.activate(context);
  return {commands, errors, instances, messages, context, db,
    rows: () => memory.rows,
    pick: value => {choose = value;},
    configure: () => onConfig({affectsConfiguration: () => true}),
    chat: () => {
      const view = {webview:{postMessage: async data => {messages.push(data);},onDidReceiveMessage: callback => {receive = callback;return disposable();}},onDidDispose: () => disposable()};
      provider.resolveWebviewView(view);
      return {html: view.webview.html, send: data => receive(data)};
    },
    dispose: () => context.subscriptions.forEach(item => item.dispose())};
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('chat offers actions before connecting and executes only allowlisted commands', async () => {
  const calls = [];
  const app = setup({hook: (_, args) => {calls.push(args);}});
  const chat = app.chat();
  chat.send({action:'ask',question:'Can you create a project?',offset:0,timezoneOffset:480,requestId:1});
  await tick();
  assert.equal(app.instances.length, 0);
  assert.equal(app.messages.find(message => message.requestId === 1).result.actions[0].command,
    'arc.createProject');
  chat.send({action:'command',command:'arc.createProject'});
  await tick();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].join(','), 'init');
  assert.equal(app.instances[0].disposed, true);
  chat.send({action:'command',command:'arbitrary.command'});
  await tick();
  assert.equal(app.errors.length, 0);
  await app.commands.get('arc.connect')();
  chat.send({action:'ask',question:'Please enable observation',offset:0,timezoneOffset:480,requestId:2});
  await tick();
  assert.equal(app.instances[1].observing, true);
  assert.equal(app.messages.at(-1).result.answer_intro, 'Automatic observation is enabled.');
  assert.equal(app.messages.at(-1).result.actions, undefined);
  app.dispose();
});

test('declining the observation popup does not enable recording', async () => {
  const app = setup({observationApproval: false});
  await app.commands.get('arc.connect')();
  app.chat().send({action:'ask',question:'enable automatic observation',offset:0,timezoneOffset:480,requestId:1});
  await tick();
  assert.equal(app.instances[0].observing, false);
  assert.equal(app.instances[0].enabled, undefined);
  assert.equal(app.messages.at(-1).result.answer_intro, 'Automatic observation was not enabled.');
  assert.equal(app.messages.at(-1).result.actions, undefined);
  app.dispose();
});

test('connection rejects missing or untrusted workspaces', async () => {
  for (const [options, expected] of [[{names:[]}, /Open a local/], [{trusted:false}, /Trust this workspace/]]) {
    const app = setup(options);
    await app.commands.get('arc.connect')();
    assert.match(app.errors[0], expected);
    assert.equal(app.instances.length, 0);
    app.dispose();
  }
});
test('multi-root selection stays scoped and configuration changes stop observation', async () => {
  const app = setup({names:['one','two']});
  await app.commands.get('arc.connect')();
  assert.equal(app.instances[0].project, path.resolve('two'));
  assert.equal(app.rows()[0].label, 'two');
  await app.commands.get('arc.observe')();
  assert.equal(app.instances[0].observing, true);
  app.configure();
  assert.equal(app.instances[0].observing, false);
  assert.equal(app.instances[0].disposed, true);
  app.dispose();
});
test('failed project registration produces a useful connection error', async () => {
  const app = setup({hook: (_, args) => args[0] === 'state' ? Promise.reject(new Error('Project is not registered. Run arc init first.')) : undefined});
  await app.commands.get('arc.connect')();
  assert.match(app.errors[0], /not registered/);
  assert.equal(app.instances[0].observing, false);
  app.dispose();
});
test('disconnect discards an outstanding chat answer and clears its sources', async () => {
  let finish;
  const app = setup({hook: (_, args) => args[0] === 'chat' ? new Promise(resolve => {finish = resolve;}) : undefined});
  await app.commands.get('arc.connect')();
  const chat = app.chat();
  assert.match(chat.html, /default-src 'none'/);
  assert.match(chat.html, /textContent/);
  chat.send({action:'ask',question:'Where did we leave off?',offset:0,timezoneOffset:480,requestId:1});
  await tick();
  await app.commands.get('arc.disconnect')();
  finish({answer:'Old project answer',citations:[]});
  await tick();
  assert.deepEqual(app.messages.filter(m => m.action !== 'ai').map(m => m.action), ['reset']);
  app.dispose();
});
test('create registers the workspace folder then connects it', async () => {
  const seen = [];
  const app = setup({names: ['new'], hook: (backend, args) => {seen.push(`${backend.project} ${args.join(' ')}`);}});
  await app.commands.get('arc.create')();
  const root = path.resolve('new');
  assert.deepEqual(seen[0], `${root} init --test-command question`);
  assert.equal(app.instances[0].disposed, true);
  assert.equal(app.instances[1].project, root);
  assert.equal(app.rows()[0].label, 'new');
  app.dispose();
});
test('delete clears memory only after the typed project name', async () => {
  const requests = [];
  const app = setup({input: 'DELETE one', hook: (_, args) => {requests.push(args.join(' '));}});
  await app.commands.get('arc.connect')();
  await app.commands.get('arc.delete')();
  assert.ok(requests.includes('delete DELETE one'));
  app.dispose();
  const blocked = [];
  const wrong = setup({input: 'DELETE wrong', hook: (_, args) => {blocked.push(args.join(' '));}});
  await wrong.commands.get('arc.connect')();
  await wrong.commands.get('arc.delete')();
  assert.ok(!blocked.some(args => args.startsWith('delete')));
  wrong.dispose();
});
test('an approved saved project reconnects when the extension reopens', async () => {
  const project = path.resolve('one');
  const app = setup({saved:{selectedProject:project,approvedProjects:[project]}});
  await tick();
  assert.equal(app.instances.length, 1);
  assert.equal(app.rows()[0].label, 'one');
  assert.equal(app.errors.length, 0);
  app.dispose();
});

test('chat cards show newest evidence first with separate date, 12-hour time and file rows', () => {
  const app = setup();
  const html = app.chat().html;
  class Element {
    children = []; listeners = {}; attributes = {}; value = '';
    appendChild(child) {this.children.push(child);}
    replaceChildren() {this.children = []; this.value = '';}
    addEventListener(event, callback) {this.listeners[event] = callback;}
    setAttribute(name, value) {this.attributes[name] = value;}
    set textContent(value) {this.value = String(value);}
    get textContent() {return this.value + this.children.map(child => child.textContent).join('');}
  }
  const elements = new Map(); let receive; const posted = [];
  const document = {head:new Element(),createElement:() => new Element(),
    getElementById:id => {if (!elements.has(id)) elements.set(id,new Element());return elements.get(id);}};
  const script = html.match(/<script nonce="[^"]+">([\s\S]*?)<\/script>/)[1];
  vm.runInNewContext(script, {document,window:{addEventListener:(_,callback) => {receive = callback;}},
    acquireVsCodeApi:() => ({postMessage:message => posted.push(message)})});
  const newer = {id:'new-id',created_at:'2026-10-09T16:16:52+00:00',summary:'Git changes',
    changed_paths:['docs/notes, draft.md','<literal-file>.md']};
  receive({data:{requestId:0,result:{answer_intro:'Recorded evidence',answer:'Raw evidence with IDs',
    citations:[{id:'old-id',created_at:'2026-10-08T16:16:52+00:00',summary:'Older record'},newer]}}});
  const cards = elements.get('sources').children;
  assert.equal(cards.length,2);
  const date = new Date(newer.created_at);
  assert.equal(cards[0].children[0].textContent,date.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'}));
  assert.equal(cards[0].children[1].textContent,date.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',hour12:true}));
  assert.match(cards[0].children[1].textContent,/AM|PM/);
  assert.deepEqual(cards[0].children[2].children.map(row => row.textContent),['Git changes',...newer.changed_paths]);
  assert.equal(cards[0].textContent.includes('new-id'),false);
  assert.equal(elements.get('answer').textContent,'Recorded evidence');
  cards[0].listeners.click();
  assert.equal(posted[0].id,'new-id');
  receive({data:{requestId:0,result:{answer_intro:'Could you clarify what you want to find?',citations:[],
    notice:"Local Ollama embedding failed: <urlopen error [WinError 10061] connection refused>. Start Ollama and run ollama pull all-minilm."}}});
  assert.equal(elements.get('answer').textContent,'Could you clarify what you want to find?');
  receive({data:{requestId:0,result:{answer_intro:'Recorded evidence',citations:[newer],notice:'urlopen error [WinError 10061]'}}});
  assert.match(elements.get('answer').textContent,/AI assistance is currently unavailable/);
  assert.doesNotMatch(elements.get('answer').textContent,/urlopen|WinError|10061/);
  app.dispose();
});
