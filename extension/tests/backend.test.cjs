const {test} = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const {Backend} = require('../out/backend');
const {memoryRows} = require('../out/model');
const {EventEmitter} = require('node:events');
test('literal arguments, busy handling and cancellation keep projects isolated', async () => {
  const saved = cp.execFile; let done; let seen; let killed = false;
  cp.execFile = (_, args, options, callback) => {seen = {args, options}; done = callback; return {kill(){killed = true;}};};
  try {
    const backend = new Backend('python', process.cwd(), '/tmp/arc.sqlite3');
    const request = backend.request(['search', '$(echo secret); "quoted"']);
    assert.deepEqual(seen.args.slice(-2), ['search', '$(echo secret); "quoted"']);
    assert.equal(seen.options.shell, undefined);
    assert.equal(seen.options.cwd, process.cwd());
    await assert.rejects(backend.request(['state']), /busy/);
    backend.dispose(); done(null, '{"project":"old"}', '');
    await assert.rejects(request, /disconnected/);
    assert.equal(killed, true);
    await assert.rejects(backend.request(['state']), /disconnected/);
  } finally {cp.execFile = saved;}
});
test('observer is workspace scoped and disposed with the connection', () => {
  const saved = cp.spawn; let seen; let killed = false;
  const worker = new EventEmitter(); worker.stderr = new EventEmitter(); worker.kill = () => {killed = true;};
  cp.spawn = (_, args, options) => {seen = {args, options}; return worker;};
  try {
    const backend = new Backend('python', '/selected/project', '/shared/arc.sqlite3');
    backend.startObserver();
    assert.deepEqual(seen.args, ['-m','arc.cli','--project','/selected/project','--db','/shared/arc.sqlite3','watch']);
    assert.equal(seen.options.shell, undefined);
    assert.equal(backend.observing, true);
    worker.stderr.emit('data', Buffer.from('worker error'));
    assert.equal(backend.observerError, 'worker error');
    backend.dispose();
    assert.equal(killed, true);
    assert.equal(backend.observing, false);
  } finally {cp.spawn = saved;}
});
test('status shows paused collection and pending records', () => {
  const rows = memoryRows({project:{name:'Example',path:'/example'},git:{changed_paths:[]},tasks:[],recent_events:[],observer:{enabled:true,paused:true,running:true},index:{indexed_records:4,pending_records:3}});
  assert.equal(rows[0].children[2].label, 'Collection: paused');
  assert.equal(rows[0].children[3].label, 'Index: 4 indexed · 3 pending');
});
test('pause controls remain available during an active chat request', async () => {
  const saved = cp.execFile; const callbacks = [];
  cp.execFile = (_, args, options, callback) => {callbacks.push(callback);return {kill(){}};};
  try {
    const backend = new Backend('python', process.cwd(), '/tmp/arc.sqlite3');
    const chat = backend.request(['chat','question']);
    const pause = backend.request(['observer','pause']);
    callbacks[1](null, '{"paused":true}', '');
    assert.equal((await pause).paused, true);
    callbacks[0](null, '{"answer":"evidence"}', '');
    assert.equal((await chat).answer, 'evidence');
    backend.dispose();
  } finally {cp.execFile = saved;}
});
test('display preserves evidence IDs and unverified status', () => {
  const rows = memoryRows({project:{name:'Example',path:'/example'},git:{changed_paths:[]},tasks:[{title:'Login',state:'implementation_observed',agent_claim:'Complete',tests_are_current:false,implementation_event_ids:['git-1'],current_passing_test_event_ids:[]}],recent_events:[],latest_checkpoint:{id:'cp-1',stale:true}});
  assert.equal(rows[1].children[0].description, 'implementation observed');
  assert.match(rows[1].children[0].children[0].label, /Unverified claim/);
  assert.equal(rows[1].children[0].children[2].eventId, 'git-1');
  assert.match(rows[4].children[0].description, /Stale.*unconfirmed/);
});
