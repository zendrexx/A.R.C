import * as vscode from 'vscode';
import * as path from 'node:path';
import { existsSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { Backend } from './backend';
import { memoryRows, Row } from './model';

class MemoryView implements vscode.TreeDataProvider<Row>, vscode.Disposable {
  private changed = new vscode.EventEmitter<Row | undefined>();
  readonly onDidChangeTreeData = this.changed.event;
  rows: Row[] = [];
  set(rows: Row[]) { this.rows = rows; this.changed.fire(undefined); }
  getChildren(row?: Row) { return row?.children ?? this.rows; }
  getTreeItem(row: Row) {
    const item = new vscode.TreeItem(row.label, row.children ? vscode.TreeItemCollapsibleState.Expanded : vscode.TreeItemCollapsibleState.None);
    item.description = row.description;
    item.tooltip = [row.label, row.description].filter(Boolean).join('\n');
    if (row.eventId) item.command = {command: 'arc.openEvent', title: 'Inspect Evidence', arguments: [row.eventId]};
    if (row.path) item.command = {command: 'arc.openFile', title: 'Open File', arguments: [row.path]};
    if (row.payload) item.command = {command: 'arc.inspect', title: 'Inspect', arguments: [row.payload]};
    return item;
  }
  dispose() { this.changed.dispose(); }
}

export function activate(context: vscode.ExtensionContext) {
  const memory = new MemoryView();
  let backend: Backend | undefined;
  let selected: vscode.WorkspaceFolder | undefined;
  let generation = 0;
  let chatView: vscode.WebviewView | undefined;
  let timer: ReturnType<typeof setInterval> | undefined;
  let refreshPending = false;
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
  status.text = '$(database) A.R.C.: disconnected'; status.command = 'arc.connect'; status.show();
  const inspect = async (data: unknown) => {
    const doc = await vscode.workspace.openTextDocument({language: 'json', content: JSON.stringify(data, null, 2)});
    await vscode.window.showTextDocument(doc, {preview: true});
  };
  const requireBackend = () => {
    if (!backend) throw new Error('Connect a project first using A.R.C.: Connect Project.');
    return backend;
  };
  const inspectFor = async (current: Backend, data: unknown) => {
    if (current === backend) await inspect(data);
  };
  const refresh = async () => {
    const current = requireBackend(); const token = generation;
    if (current.busy) return;
    const state = await current.request(['state']);
    if (token !== generation) return;
    const observer = await current.request(['observer', 'status']);
    if (token !== generation) return;
    state.observer = {...observer, running: current.observing, error: current.observerError};
    memory.set(memoryRows(state)); status.text = `$(database) A.R.C.: ${state.project.name}`;
    status.tooltip = `Collection: ${observer.enabled ? observer.paused ? 'paused' : current.observing ? 'observing' : 'worker stopped' : 'disabled'} · ${state.index.pending_records} pending records`;
  };
  const disconnect = () => {
    generation++; backend?.dispose(); backend = undefined; selected = undefined;
    if (timer) clearInterval(timer); timer = undefined;
    void chatView?.webview.postMessage({action: 'reset'});
    memory.set([]); status.text = '$(database) A.R.C.: disconnected'; status.tooltip = undefined;
  };
  const register = (name: string, action: (...args: any[]) => any) => {
    context.subscriptions.push(vscode.commands.registerCommand(name, async (...args: any[]) => {
      try { await action(...args); } catch (error) { vscode.window.showErrorMessage(String(error instanceof Error ? error.message : error)); }
    }));
  };
  const pickFolder = async (title: string) => {
    const folders = vscode.workspace.workspaceFolders?.filter(f => f.uri.scheme === 'file') ?? [];
    if (!folders.length) throw new Error('Open a local project folder first.');
    return folders.length === 1 ? folders[0] : (await vscode.window.showQuickPick(folders.map(folder => ({label: folder.name, description: folder.uri.fsPath, folder})), {title}))?.folder;
  };
  const backendFor = (folder: vscode.WorkspaceFolder) => {
    const config = vscode.workspace.getConfiguration('arc');
    const localPython = path.join(folder.uri.fsPath, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    const python = config.get<string>('pythonPath') || (existsSync(localPython) ? localPython : process.platform === 'win32' ? 'python' : 'python3');
    const database = config.get<string>('databasePath') || '';
    if (database && !path.isAbsolute(database)) throw new Error('A.R.C. databasePath must be absolute.');
    return new Backend(python, folder.uri.fsPath, database);
  };
  const approve = async (choice: vscode.WorkspaceFolder, message: string, action: string) => {
    const approved = context.workspaceState.get<string[]>('approvedProjects', []);
    if (approved.includes(choice.uri.fsPath)) return true;
    const answer = await vscode.window.showInformationMessage(message, {modal: true}, action);
    if (answer !== action) return false;
    await context.workspaceState.update('approvedProjects', [...approved, choice.uri.fsPath]);
    return true;
  };
  const connectTo = async (choice: vscode.WorkspaceFolder) => {
    if (!await approve(choice, `Connect A.R.C. to ${choice.name}? It reads local Git metadata and stored memory. Automatic observation is a separate opt-in command.`, 'Connect')) return;
    disconnect(); selected = choice;
    backend = backendFor(choice);
    const connected = backend; const connectToken = generation;
    try { await refresh(); } catch (error) {
      if (connectToken !== generation) return;
      connected.dispose(); backend = undefined; selected = undefined;
      memory.set([{label: 'Could not load project', description: 'Check Python and database; run A.R.C.: Create Project to register'}, {label: String(error)}]);
      status.text = '$(warning) A.R.C.: connection error'; throw error;
    }
    if (connectToken !== generation) return;
    await context.workspaceState.update('selectedProject', choice.uri.fsPath);
    if (connectToken !== generation) return;
    const observer = await connected.request(['observer', 'status']);
    if (connectToken !== generation) return;
    if (observer.enabled) connected.startObserver();
    timer = setInterval(async () => {
      if (refreshPending) return;
      refreshPending = true;
      try {await refresh();} catch { /* Interactive commands show errors; polling retries. */ }
      finally {refreshPending = false;}
    }, 10000);
    await refresh();
  };
  register('arc.connect', async () => {
    if (!vscode.workspace.isTrusted) throw new Error('Trust this workspace before connecting A.R.C.');
    const choice = await pickFolder('Choose the A.R.C. project');
    if (choice) await connectTo(choice);
  });
  register('arc.create', async () => {
    if (!vscode.workspace.isTrusted) throw new Error('Trust this workspace before creating an A.R.C. project.');
    const choice = await pickFolder('Choose the project folder to register');
    if (!choice) return;
    if (!await approve(choice, `Create an A.R.C. project for ${choice.name}? Registration reads local Git metadata. Automatic observation is a separate opt-in command.`, 'Create')) return;
    const testCommand = await vscode.window.showInputBox({title: 'Test command for A.R.C.: Run Configured Test (optional)', prompt: 'Approved executable and arguments, no shell syntax. Leave empty to skip.'});
    if (testCommand === undefined) return;
    const setup = backendFor(choice);
    try {
      await setup.request(['init', ...(testCommand.trim() ? ['--test-command', testCommand.trim()] : [])]);
    } finally { setup.dispose(); }
    await connectTo(choice);
  });
  register('arc.delete', async () => {
    const current = requireBackend();
    if (!selected) throw new Error('Connect a project first.');
    const expected = `DELETE ${selected.name}`;
    const confirmation = await vscode.window.showInputBox({
      title: `Permanently delete A.R.C. memory for ${selected.name}?`,
      prompt: `Events, tasks, sessions, incidents, checkpoints and embeddings are removed; registration and source files remain. Type ${expected} to continue.`,
      validateInput: value => value === expected ? undefined : `Type ${expected} to confirm.`
    });
    if (confirmation !== expected || current !== backend) return;
    const result = await current.request(['delete', confirmation]);
    await inspectFor(current, result);
    if (current === backend) await refresh();
  });
  register('arc.refresh', refresh);
  register('arc.disconnect', async () => {disconnect(); await context.workspaceState.update('selectedProject', undefined);});
  register('arc.observe', async () => {
    const current = requireBackend();
    const answer = await vscode.window.showInformationMessage('Enable automatic observation for this project? A.R.C. records eligible Git path changes and commits while connected, recovers commits after restart, and indexes summaries locally. It never stores file bodies. Pause deliberately excludes activity until resume.', {modal: true}, 'Enable');
    if (answer !== 'Enable' || current !== backend) return;
    await current.request(['observer', 'enable']); current.startObserver(); await refresh();
  });
  for (const action of ['pause', 'resume', 'disable']) {
    register(`arc.${action}`, async () => {
      const current = requireBackend(); await current.request(['observer', action]);
      if (current !== backend) return;
      if (action === 'resume') current.startObserver();
      if (action === 'disable') current.stopObserver();
      await refresh();
    });
  }
  register('arc.timeline', async () => {
    const current = requireBackend(); const token = generation;
    const kind = await vscode.window.showQuickPick(['All', 'git', 'test', 'error', 'decision', 'note', 'claim', 'confirmation'], {title: 'Filter recorded timeline'});
    if (!kind || token !== generation) return;
    const period = await vscode.window.showQuickPick(['All history', 'Today', 'Yesterday', 'Custom date range'], {title: 'Choose timeline dates'});
    if (!period || token !== generation) return;
    let since: string | undefined; let until: string | undefined;
    if (period === 'Today' || period === 'Yesterday') {
      const start = new Date(); start.setHours(0, 0, 0, 0);
      if (period === 'Yesterday') start.setDate(start.getDate() - 1);
      const end = new Date(start); end.setDate(end.getDate() + 1);
      since = start.toISOString(); until = end.toISOString();
    } else if (period === 'Custom date range') {
      const dates = await vscode.window.showInputBox({title: 'UTC timeline range', prompt: 'Start date, exclusive end date (YYYY-MM-DD, YYYY-MM-DD)', validateInput: value => /^\d{4}-\d{2}-\d{2},\s*\d{4}-\d{2}-\d{2}$/.test(value) ? undefined : 'Enter two dates separated by a comma.'});
      if (!dates || token !== generation) return;
      [since, until] = dates.split(',').map(s => s.trim());
    }
    let offset = 0;
    let snapshot: number | undefined;
    while (token === generation) {
      const args = ['timeline', '--offset', String(offset)];
      if (snapshot !== undefined) args.push('--snapshot', String(snapshot));
      if (kind !== 'All') args.push('--kind', kind);
      if (since) args.push('--since', since);
      if (until) args.push('--until', until);
      const page = await current.request(args);
      snapshot = page.snapshot_rowid;
      if (token !== generation) return;
      const items = page.events.map((e: any) => ({label: e.summary, description: `${e.kind} · ${new Date(e.created_at).toLocaleString()}`, id: e.id}));
      if (page.next_offset !== null) items.push({label: 'Load older records…', id: ''});
      const pick = await vscode.window.showQuickPick(items, {title: `Timeline · ${page.total_events} records`}) as {id: string} | undefined;
      if (!pick || token !== generation) return;
      if (pick.id) {await inspectFor(current, await current.request(['event', pick.id])); return;}
      offset = page.next_offset;
    }
  });
  register('arc.inspect', inspect);
  register('arc.openEvent', async (id: string) => {
    const current = requireBackend(); await inspectFor(current, await current.request(['event', id]));
  });
  register('arc.openFile', async (relative: string) => {
    if (!selected) throw new Error('Connect a project first.');
    const root = selected.uri.fsPath; const target = path.resolve(root, relative);
    const rel = path.relative(root, target);
    if (rel.startsWith('..') || path.isAbsolute(rel)) throw new Error('File is outside the selected workspace.');
    await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(vscode.Uri.file(target)));
  });
  register('arc.search', async () => {
    const current = requireBackend();
    const query = await vscode.window.showInputBox({title: 'Search recorded project memory', prompt: 'Semantic search uses local Ollama; keyword fallback is labelled.'});
    if (!query?.trim() || current !== backend) return;
    const result = await current.request(['search', query, '--limit', '20']);
    if (current !== backend) return;
    const pick = await vscode.window.showQuickPick((result.hits ?? []).map((hit: any) => ({label: hit.summary, description: hit.source_ref, detail: `${result.mode} · ${result.score_kind ?? 'rank'}: ${hit.score}`, hit})), {title: `Memory · ${result.mode}`, placeHolder: result.hits?.length ? 'Select evidence to inspect' : 'No matching evidence recorded'});
    if (pick && current === backend) await inspectFor(current, await current.request(['event', (pick as any).hit.event_id]));
  });
  for (const [name, command] of [['capture', 'capture'], ['checkpoint', 'checkpoint'], ['index', 'index'], ['test', 'test']]) {
    register(`arc.${name}`, async () => {
      const current = requireBackend();
      const result = await current.request([command]);
      await inspectFor(current, result); if (current === backend) await refresh();
    });
  }
  const chat: vscode.WebviewViewProvider = {
    resolveWebviewView(view) {
      chatView = view;
      const nonce = randomBytes(16).toString('hex');
      view.webview.options = {enableScripts: true, localResourceRoots: []};
      view.webview.html = `<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}'"><style nonce="${nonce}">
        body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);padding:16px;line-height:1.5} h1{font-size:21px;margin:8px 0} .muted{color:var(--vscode-descriptionForeground)} .card{border:1px solid var(--vscode-widget-border);border-radius:8px;padding:14px;margin:18px 0} button{width:100%;padding:9px;margin:5px 0;background:var(--vscode-button-background);color:var(--vscode-button-foreground);border:0;cursor:pointer} button:hover{background:var(--vscode-button-hoverBackground)} button:focus-visible{outline:2px solid var(--vscode-focusBorder)} textarea{box-sizing:border-box;width:100%;padding:9px;background:var(--vscode-input-background);color:var(--vscode-input-foreground);border:1px solid var(--vscode-input-border)}
      </style></head><body><p class="muted">A.R.C. / LOCAL MEMORY</p><h1>Pick up where you left off.</h1><p>Find the evidence behind your project's progress.</p><div class="card"><label for="question">Ask about your project</label><textarea id="question" rows="3" maxlength="2000" placeholder="What did we work on yesterday?"></textarea><button id="ask">Ask A.R.C.</button><button id="more" hidden>Load older history</button><p id="answer" role="status" aria-live="polite" style="white-space:pre-wrap"></p><div id="sources"></div></div><button id="search">Search memory</button><button id="connect">Connect project</button><p class="muted">Answers quote recorded evidence. Claims remain unverified; local Ollama optionally selects sources.</p><script nonce="${nonce}">
      const vscode=acquireVsCodeApi(); let offset=0; let snapshot; let question=''; let requestId=0;
      for(const action of ['search','connect'])document.getElementById(action).addEventListener('click',()=>vscode.postMessage({action}));
      function ask(next){question=next?question:document.getElementById('question').value.trim();if(!question)return;offset=next?offset:0;snapshot=next?snapshot:undefined;requestId++;document.getElementById('ask').disabled=true;document.getElementById('more').hidden=true;document.getElementById('answer').textContent='Reading local evidence…';document.getElementById('sources').replaceChildren();vscode.postMessage({action:'ask',question,offset,snapshot,requestId,timezoneOffset:-new Date().getTimezoneOffset()});}
      document.getElementById('ask').addEventListener('click',()=>ask(false)); document.getElementById('more').addEventListener('click',()=>ask(true));
      window.addEventListener('message',({data})=>{if(data.action==='reset'){requestId++;document.getElementById('ask').disabled=false;document.getElementById('answer').textContent='Connect a project to ask about its evidence.';document.getElementById('sources').replaceChildren();document.getElementById('more').hidden=true;return;}if(data.requestId!==requestId)return;document.getElementById('ask').disabled=false;document.getElementById('answer').textContent=data.error||data.result.answer;const sources=document.getElementById('sources');sources.replaceChildren();for(const source of data.result?.citations||[]){const b=document.createElement('button');b.textContent='Inspect '+source.id.slice(0,8)+' · '+source.summary;b.addEventListener('click',()=>vscode.postMessage({action:'event',id:source.id}));sources.appendChild(b);}offset=data.result?.next_offset;snapshot=data.result?.snapshot_rowid;document.getElementById('more').hidden=offset==null;});
      </script></body></html>`;
      const listener = view.webview.onDidReceiveMessage(message => {
        if (message?.action === 'search' || message?.action === 'connect') void vscode.commands.executeCommand(`arc.${message.action}`);
        if (message?.action === 'event' && typeof message.id === 'string') void vscode.commands.executeCommand('arc.openEvent', message.id);
        if (message?.action === 'ask' && typeof message.question === 'string' && message.question.length <= 2000 && Number.isInteger(message.offset) && message.offset >= 0 && Number.isInteger(message.timezoneOffset) && (message.snapshot === undefined || Number.isInteger(message.snapshot) && message.snapshot >= 0)) {
          const current = backend; const token = generation;
          void (async () => {
            try {
              if (!current) throw new Error('Connect a project first.');
              const args = ['chat', message.question, '--timezone-offset', String(message.timezoneOffset), '--offset', String(message.offset)];
              if (message.snapshot !== undefined) args.push('--snapshot', String(message.snapshot));
              const result = await current.request(args);
              if (token === generation) await view.webview.postMessage({requestId: message.requestId, result});
            } catch (error) {if (token === generation) await view.webview.postMessage({requestId: message.requestId, error: String(error instanceof Error ? error.message : error)});}
          })();
        }
      });
      view.onDidDispose(() => {listener.dispose(); if (chatView === view) chatView = undefined;});
    }
  };
  context.subscriptions.push(memory, status, vscode.window.registerTreeDataProvider('arc.memory', memory), vscode.window.registerWebviewViewProvider('arc.chat', chat),
    vscode.workspace.onDidChangeWorkspaceFolders(() => { if (selected && !vscode.workspace.workspaceFolders?.some(f => f.uri.toString() === selected!.uri.toString())) disconnect(); }),
    vscode.workspace.onDidChangeConfiguration(e => { if (e.affectsConfiguration('arc')) disconnect(); }),
    {dispose: disconnect});
  const previous = context.workspaceState.get<string>('selectedProject');
  const approved = context.workspaceState.get<string[]>('approvedProjects', []);
  if (vscode.workspace.isTrusted && previous && approved.includes(previous) && vscode.workspace.workspaceFolders?.length === 1 && vscode.workspace.workspaceFolders[0].uri.fsPath === previous) {
    void vscode.commands.executeCommand('arc.connect');
  }
}
