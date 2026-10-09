import { request } from 'node:http';
import { spawn } from 'node:child_process';
import { existsSync, promises as fs } from 'node:fs';
import * as path from 'node:path';
import { tmpdir } from 'node:os';

export function validModelName(name: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9._-]+)?$/.test(name) && !name.endsWith(':cloud');
}
const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/** Loopback only. Never loads a model for a health check. */
export function localApi(route: string, body?: unknown, timeout = 3000): Promise<any> {
  return new Promise((resolve, reject) => {
    const req = request({hostname: '127.0.0.1', port: 11434, path: route,
      method: body ? 'POST' : 'GET', headers: {'Content-Type': 'application/json'}}, res => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', chunk => {data += chunk; if (data.length > 2_000_000) req.destroy(new Error('Response too large'));});
      res.on('error', reject);
      res.on('end', () => {
        try {
          if (res.statusCode !== 200) throw new Error('Local API unavailable');
          const value = JSON.parse(data);
          if (value.error) throw new Error('Local API request failed');
          resolve(value);
        } catch (error) {reject(error);}
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('Local API timed out')), timeout);
    req.on('close', () => clearTimeout(timer));
    req.on('error', reject);
    req.end(body ? JSON.stringify(body) : undefined);
  });
}

function executable(): string {
  const candidates = process.platform === 'win32' ? [
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Ollama', 'ollama.exe'),
    ...String(process.env.PATH || '').split(path.delimiter).map(dir => path.join(dir, 'ollama.exe'))
  ] : ['/usr/local/bin/ollama', '/usr/bin/ollama', '/Applications/Ollama.app/Contents/Resources/ollama',
    ...String(process.env.PATH || '').split(path.delimiter).map(dir => path.join(dir, 'ollama'))];
  return candidates.find(file => path.isAbsolute(file) && existsSync(file)) || '';
}

/** The lock is shared by VS Code windows. The server survives extension reloads. */
export async function startLocalServer(): Promise<void> {
  const lockPath = path.join(tmpdir(), 'arc-ollama-start.lock');
  let lock;
  let serverPid: number | undefined;
  try {lock = await fs.open(lockPath, 'wx');}
  catch (error: any) {
    if (error.code !== 'EEXIST') throw error;
    try {
      const pid = Number(await fs.readFile(lockPath, 'utf8'));
      if (Number.isInteger(pid) && pid > 0) {
        try {process.kill(pid, 0); return;} catch (error: any) {if (error.code !== 'ESRCH') return;}
      } else if (Date.now() - (await fs.stat(lockPath)).mtimeMs < 30000) return;
      await fs.unlink(lockPath);
    } catch {return;}
    return; // Retry on next tick rather than racing another window.
  }
  try {
    await lock.writeFile(String(process.pid));
    try {await localApi('/api/tags'); return;} catch { /* Start only after a second check. */ }
    const binary = executable();
    if (!binary) throw new Error('Ollama is not installed');
    const child = spawn(binary, ['serve'], {detached: true, windowsHide: true, stdio: 'ignore',
      env: {...process.env, OLLAMA_HOST: '127.0.0.1:11434', OLLAMA_NO_CLOUD: '1',
        OLLAMA_MAX_LOADED_MODELS: '1', OLLAMA_NUM_PARALLEL: '1', OLLAMA_KEEP_ALIVE: '30s'}});
    let failed = false;
    child.on('error', () => {failed = true;});
    child.on('exit', () => {failed = true;});
    serverPid = child.pid;
    if (serverPid) {await lock.truncate(0); await lock.write(String(serverPid), 0, 'utf8');}
    child.unref();
    for (let count = 0; count < 20; count++) {
      if (failed) throw new Error('Local server did not start');
      await pause(500);
      try {await localApi('/api/tags'); return;} catch { /* Wait for readiness. */ }
    }
    throw new Error('Local server is still starting');
  } finally {await lock.close(); if (!serverPid) await fs.unlink(lockPath).catch(() => {});}
}

interface Options {
  models?: () => string[];
  autoStart: () => boolean;
  consent: (model: string) => Promise<boolean>;
  index: () => Promise<void>;
  notify: (status: string, chatReady?: boolean) => void;
}
interface Runtime {
  api: typeof localApi;
  start: typeof startLocalServer;
  now: () => number;
}

export class OllamaManager {
  private pending?: Promise<void>;
  private stopped = false;
  private retryAt = 0;
  private delay = 10000;
  private prompted = new Set<string>();
  constructor(private options: Options, private runtime: Runtime = {api: localApi, start: startLocalServer, now: Date.now}) {}
  tick(): Promise<void> {
    if (this.stopped || this.runtime.now() < this.retryAt) return Promise.resolve();
    if (!this.pending) this.pending = this.run().finally(() => {this.pending = undefined;});
    return this.pending;
  }
  private async run() {
    try {
      let tags: any;
      const models = (this.options.models?.() || ['all-minilm']).filter(Boolean);
      if (models.some(model => !validModelName(model))) throw new Error('Choose local model names');
      try {tags = await this.runtime.api('/api/tags');}
      catch {
        if (!this.options.autoStart()) throw new Error('Automatic startup disabled');
        await this.runtime.start();
        tags = await this.runtime.api('/api/tags');
      }
      for (const model of models) {
        if (this.stopped) return;
        const installed = () => (tags.models || []).some((item: any) =>
          !item.remote_host && !item.remote_model && (item.name === model || item.name === model + ':latest'));
        if (!installed() && !this.prompted.has(model)) {
          this.prompted.add(model);
          if (await this.options.consent(model) && !this.stopped) {
            // Only validated, explicitly selected local model names may be downloaded with consent.
            try {await this.runtime.api('/api/pull', {model, stream: false}, 15 * 60 * 1000);}
            catch (error) {this.prompted.delete(model); throw error;}
            tags = await this.runtime.api('/api/tags');
          }
        }
      }
      const ready = (tags.models || []).some((item: any) => !item.remote_host && !item.remote_model &&
        [models[0], models[0] + ':latest'].includes(item.name));
      this.delay = 10000;
      this.retryAt = this.runtime.now() + 30000;
      const chatReady = Boolean(models[1]) && (tags.models || []).some((item: any) => !item.remote_host && !item.remote_model && [models[1],models[1]+':latest'].includes(item.name));
      this.options.notify(ready ? 'Local memory ready' : 'Recording locally; semantic memory not set up', chatReady);
      if (ready && !this.stopped) await this.options.index();
    } catch {
      this.options.notify('Recording locally; AI assistance unavailable');
      this.retryAt = this.runtime.now() + this.delay;
      this.delay = Math.min(this.delay * 2, 5 * 60 * 1000);
    }
  }
  dispose() {this.stopped = true; /* Never terminate an existing or shared Ollama server. */}
  resetSetup() {this.prompted.clear(); this.retryAt = 0;}
}
