import { execFile, spawn, ChildProcess } from 'node:child_process';
import * as path from 'node:path';

function readableError(message: string): string {
  if (/Ollama|urlopen error|WinError 10061|ECONNREFUSED/i.test(message)) {
    return 'AI assistance is currently unavailable. Please try again later.';
  }
  if (/Traceback \(most recent call last\)|SyntaxError:|<frozen runpy>/i.test(message)) {
    return 'A.R.C. could not process your message because its backend encountered an error. Please try again after the backend is fixed.';
  }
  return message;
}

/** Windows venv launchers can have a second Python process holding the database. */
function terminate(child?: ChildProcess): void {
  if (!child) return;
  if (process.platform === 'win32' && child.pid) {
    const taskkill = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe');
    execFile(taskkill, ['/PID', String(child.pid), '/T', '/F'], {windowsHide: true}, error => {
      if (error) child.kill();
    });
  } else child.kill();
}

/** Bounded CLI requests plus a project-scoped, opt-in observer. No shell. */
export class Backend {
  private child?: ChildProcess;
  private control?: ChildProcess;
  private disposed = false;
  private worker?: ChildProcess;
  observerError?: string;
  constructor(readonly python: string, readonly project: string, readonly database: string,
    readonly modelEnv: Record<string,string> = {}) {}
  request(args: string[]): Promise<any> {
    if (this.disposed) return Promise.reject(new Error('Project disconnected.'));
    const slot = args[0] === 'observer' ? 'control' : 'child';
    if (this[slot]) return Promise.reject(new Error('A.R.C. is busy. Wait for the current request.'));
    const argv = ['-m', 'arc.cli', '--project', this.project];
    if (this.database) argv.push('--db', this.database);
    argv.push(...args);
    return new Promise((resolve, reject) => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      let timedOut = false;
      const child = execFile(this.python, argv, {
        cwd: this.project, windowsHide: true, maxBuffer: 4 * 1024 * 1024,
        env: { ...process.env, ...this.modelEnv, PYTHONIOENCODING: 'utf-8' }
      }, (error, stdout, stderr) => {
        if (timer) clearTimeout(timer);
        this[slot] = undefined;
        if (this.disposed) { reject(new Error('Project disconnected.')); return; }
        if (timedOut) {reject(new Error('A.R.C. request timed out. Recorded evidence remains in SQLite.'));return;}
        if (error) { reject(new Error(readableError(stderr.trim() || error.message))); return; }
        try { resolve(JSON.parse(stdout)); } catch { reject(new Error('Backend returned invalid JSON.')); }
      });
      this[slot] = child;
      const timeout = args[0] === 'test' ? 150000 : ['chat','model'].includes(args[0]) ? 90000 : 60000;
      timer = setTimeout(() => {timedOut = true; terminate(child);}, timeout);
    });
  }
  startObserver(): void {
    if (this.disposed || this.worker) return;
    const args = ['-m', 'arc.cli', '--project', this.project];
    if (this.database) args.push('--db', this.database);
    args.push('observer-watch');
    this.observerError = undefined;
    const worker = spawn(this.python, args, {cwd: this.project, windowsHide: true,
      stdio: ['ignore', 'ignore', 'pipe'], env: {...process.env, ...this.modelEnv, PYTHONIOENCODING: 'utf-8'}});
    this.worker = worker;
    worker.stderr?.on('data', chunk => {this.observerError = readableError(String(chunk).slice(-2000));});
    worker.on('error', error => {this.observerError = error.message; if (this.worker === worker) this.worker = undefined;});
    worker.on('exit', code => {
      if (this.worker === worker) this.worker = undefined;
      if (!this.disposed && code) this.observerError ||= `Observer exited with code ${code}`;
    });
  }
  get observing(): boolean {return Boolean(this.worker);}
  startDashboard(port: number): number | undefined {
    const args = ['-m','arc.cli','--project',this.project];
    if (this.database) args.push('--db',this.database);
    args.push('dashboard','--no-browser','--port',String(port));
    const child = spawn(this.python,args,{cwd:this.project,detached:true,windowsHide:true,stdio:'ignore',
      env:{...process.env,...this.modelEnv,PYTHONIOENCODING:'utf-8'}});
    child.on('error',()=>{}); child.unref();
    return child.pid;
  }
  get busy(): boolean {return Boolean(this.child || this.control);}
  stopObserver(): void {terminate(this.worker); this.worker = undefined;}
  dispose(): void { this.disposed = true; terminate(this.child); terminate(this.control); this.stopObserver(); }
}
