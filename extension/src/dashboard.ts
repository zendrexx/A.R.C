import { get } from 'node:http';
import { Backend } from './backend';
import { promises as fs } from 'node:fs';
import { tmpdir } from 'node:os';
import * as path from 'node:path';

export function dashboardUrl(configured: string): URL {
  const url = new URL(configured);
  if (url.protocol !== 'http:' || !['localhost','127.0.0.1'].includes(url.hostname) ||
      url.username || url.password || url.pathname !== '/' || url.search || url.hash || Number(url.port || 80) < 1) {
    throw new Error('Dashboard URL must be a local HTTP address with a valid port, such as http://127.0.0.1:8765.');
  }
  return url;
}
async function health(url: URL): Promise<any> {
  return new Promise((resolve,reject) => {
    const target = new URL('/api/health',url); target.hostname='127.0.0.1';
    const req=get(target,res=>{
      let body='';res.setEncoding('utf8');res.on('data',chunk=>{body+=chunk;if(body.length>10000)req.destroy(new Error('Invalid dashboard response'));});
      res.on('error',reject);res.on('end',()=>{try {if(res.statusCode!==200)throw new Error('Invalid dashboard service');resolve(JSON.parse(body));}catch(error){reject(error);}});
    });
    req.on('error',reject);req.setTimeout(1500,()=>req.destroy(new Error('Dashboard unavailable')));
  });
}
const pending=new Map<string,Promise<string>>();
export function ensureDashboard(backend: Backend, configured: string): Promise<string> {
  const url=dashboardUrl(configured);const key=url.origin+'|'+backend.database+'|'+backend.project;
  let work=pending.get(key);
  if(!work){work=run(backend,url).finally(()=>pending.delete(key));pending.set(key,work);}
  return work;
}
async function run(backend:Backend,url:URL):Promise<string>{
  const info=await backend.request(['database-info']);
  const check=async()=>{
    const status=await health(url);
    if(status.service!=='arc-dashboard'||status.database_id!==info.database_id)
      throw new Error('This port serves another dashboard or database. Choose a different Dashboard URL in A.R.C. settings.');
  };
  try{await check();}
  catch(error:any){
    if(!['ECONNREFUSED','ECONNRESET'].includes(error.code)&&error.message!=='Dashboard unavailable')throw error;
    const lockPath=path.join(tmpdir(),`arc-dashboard-${url.port||80}.lock`);
    let lock;
    try{lock=await fs.open(lockPath,'wx');}
    catch(error:any){
      if(error.code!=='EEXIST')throw error;
      try{
        const pid=Number(await fs.readFile(lockPath,'utf8'));
        if(pid>0){try{process.kill(pid,0);}catch(error:any){if(error.code==='ESRCH')await fs.unlink(lockPath);}}
        else if(Date.now()-(await fs.stat(lockPath)).mtimeMs>30000)await fs.unlink(lockPath);
      }catch{}
      try{lock=await fs.open(lockPath,'wx');}catch(error:any){if(error.code!=='EEXIST')throw error;}
    }
    let pid:number|undefined;
    if(lock){
      await lock.writeFile(String(process.pid));
      try{await check();}catch(error:any){
        if(!['ECONNREFUSED','ECONNRESET'].includes(error.code)&&error.message!=='Dashboard unavailable'){
          await lock.close();await fs.unlink(lockPath).catch(()=>{});throw error;
        }
        pid=backend.startDashboard(Number(url.port||80));
      }
      if(pid){await lock.truncate(0);await lock.write(String(pid),0,'utf8');}
      await lock.close();
    }
    let ready=false;
    try{for(let i=0;i<30;i++){
      await new Promise(resolve=>setTimeout(resolve,300));
      try{await check();ready=true;break;}catch(error:any){
        if(!['ECONNREFUSED','ECONNRESET'].includes(error.code)&&error.message!=='Dashboard unavailable')throw error;
      }
    }}finally{if(lock&&!pid)await fs.unlink(lockPath).catch(()=>{});}
    if(!ready)throw new Error('Dashboard could not start. Check your Python installation and configured dashboard port.');
  }
  url.searchParams.set('project',backend.project);return url.toString();
}
